"""Tests for SQLite store."""

import tempfile
from pathlib import Path

import pytest

from argos_budget_guardian.core.store import Store
from argos_budget_guardian.core.tracker import CostEvent


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        s = Store(db_path=db_path)
        yield s
        s.close()


@pytest.fixture
def sample_event():
    return CostEvent.create(
        model="claude-sonnet-4-6-20250514",
        tool_name="Write",
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.0105,
        session_id="test-session",
    )


class TestStore:
    def test_save_and_retrieve_event(self, store, sample_event):
        store.save_event(sample_event)
        events = store.get_session_events("test-session")
        assert len(events) == 1
        assert events[0]["cost_usd"] == 0.0105

    def test_session_created(self, store, sample_event):
        store.save_event(sample_event)
        sessions = store.get_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "test-session"
        assert sessions[0]["num_events"] == 1

    def test_session_totals_accumulate(self, store):
        for i in range(3):
            store.save_event(
                CostEvent.create(
                    model="s", tool_name="t", cost_usd=0.10, session_id="s1"
                )
            )
        sessions = store.get_sessions()
        assert abs(sessions[0]["total_cost_usd"] - 0.30) < 1e-10
        assert sessions[0]["num_events"] == 3

    def test_finalize_session(self, store, sample_event):
        store.save_event(sample_event)
        store.finalize_session("test-session", total_cost=0.05)
        sessions = store.get_sessions()
        assert sessions[0]["total_cost_usd"] == 0.05
        assert sessions[0]["ended_at"] is not None

    def test_daily_totals(self, store, sample_event):
        store.save_event(sample_event)
        totals = store.get_daily_totals()
        assert len(totals) == 1
        assert totals[0]["total_cost_usd"] == 0.0105

    def test_today_total(self, store, sample_event):
        store.save_event(sample_event)
        assert store.get_today_total() == 0.0105

    def test_export_csv(self, store, sample_event):
        store.save_event(sample_event)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "export.csv"
            count = store.export_csv(out)
            assert count == 1
            assert out.exists()
            content = out.read_text()
            assert "test-session" in content

    def test_export_json(self, store, sample_event):
        import json

        store.save_event(sample_event)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "export.json"
            count = store.export_json(out)
            assert count == 1
            data = json.loads(out.read_text())
            assert len(data) == 1

    def test_empty_export(self, store):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "empty.csv"
            count = store.export_csv(out)
            assert count == 0

    def test_multiple_sessions(self, store):
        store.save_event(
            CostEvent.create(model="s", tool_name="t", cost_usd=1.0, session_id="s1")
        )
        store.save_event(
            CostEvent.create(model="s", tool_name="t", cost_usd=2.0, session_id="s2")
        )
        sessions = store.get_sessions()
        assert len(sessions) == 2
