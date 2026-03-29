"""Tests for the cost tracker."""

from argos_budget_guardian.core.tracker import CostEvent, CostTracker


class TestCostEvent:
    def test_create_with_defaults(self):
        event = CostEvent.create(model="sonnet", tool_name="Read", session_id="s1")
        assert event.model == "sonnet"
        assert event.tool_name == "Read"
        assert event.cost_usd == 0.0
        assert event.timestamp is not None

    def test_create_with_values(self):
        event = CostEvent.create(
            model="sonnet",
            tool_name="Write",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            session_id="s1",
            agent_id="agent-1",
        )
        assert event.input_tokens == 100
        assert event.output_tokens == 50
        assert event.agent_id == "agent-1"


class TestCostTracker:
    def test_record_and_total(self, tracker, sample_event):
        tracker.record(sample_event)
        assert tracker.get_session_total("test-session-1") == sample_event.cost_usd
        assert tracker.get_global_total() == sample_event.cost_usd

    def test_multiple_events(self, tracker, sample_events):
        for event in sample_events:
            tracker.record(event)
        expected = sum(e.cost_usd for e in sample_events)
        assert abs(tracker.get_session_total("test-session-1") - expected) < 1e-10
        assert abs(tracker.get_global_total() - expected) < 1e-10

    def test_multiple_sessions(self, tracker):
        e1 = CostEvent.create(model="s", tool_name="t", cost_usd=1.0, session_id="s1")
        e2 = CostEvent.create(model="s", tool_name="t", cost_usd=2.0, session_id="s2")
        tracker.record(e1)
        tracker.record(e2)
        assert tracker.get_session_total("s1") == 1.0
        assert tracker.get_session_total("s2") == 2.0
        assert tracker.get_global_total() == 3.0

    def test_unknown_session_returns_zero(self, tracker):
        assert tracker.get_session_total("nonexistent") == 0.0

    def test_breakdown(self, tracker, sample_events):
        for event in sample_events:
            tracker.record(event)
        breakdown = tracker.get_breakdown("test-session-1")
        assert "by_model" in breakdown
        assert "by_tool" in breakdown
        assert len(breakdown["by_model"]) == 2  # sonnet and haiku
        assert len(breakdown["by_tool"]) == 3  # Read, Write, Bash

    def test_reconcile(self, tracker):
        e = CostEvent.create(model="s", tool_name="t", cost_usd=0.5, session_id="s1")
        tracker.record(e)
        assert tracker.get_session_total("s1") == 0.5

        tracker.reconcile("s1", 0.75)
        assert tracker.get_session_total("s1") == 0.75
        assert tracker.get_global_total() == 0.75

    def test_callback(self, tracker):
        received = []
        tracker.on_update(lambda e: received.append(e))
        event = CostEvent.create(model="s", tool_name="t", cost_usd=0.1, session_id="s1")
        tracker.record(event)
        assert len(received) == 1
        assert received[0] is event

    def test_remove_callback(self, tracker):
        received = []
        cb = lambda e: received.append(e)
        tracker.on_update(cb)
        tracker.remove_callback(cb)
        event = CostEvent.create(model="s", tool_name="t", cost_usd=0.1, session_id="s1")
        tracker.record(event)
        assert len(received) == 0

    def test_reset(self, tracker, sample_events):
        for event in sample_events:
            tracker.record(event)
        tracker.reset()
        assert tracker.get_global_total() == 0.0
        assert len(tracker.events) == 0

    def test_session_ids(self, tracker):
        tracker.record(CostEvent.create(model="s", tool_name="t", cost_usd=0.1, session_id="a"))
        tracker.record(CostEvent.create(model="s", tool_name="t", cost_usd=0.1, session_id="b"))
        assert set(tracker.session_ids) == {"a", "b"}

    def test_get_session_events(self, tracker):
        e1 = CostEvent.create(model="s", tool_name="t", cost_usd=0.1, session_id="s1")
        e2 = CostEvent.create(model="s", tool_name="t", cost_usd=0.2, session_id="s2")
        e3 = CostEvent.create(model="s", tool_name="t", cost_usd=0.3, session_id="s1")
        tracker.record(e1)
        tracker.record(e2)
        tracker.record(e3)
        s1_events = tracker.get_session_events("s1")
        assert len(s1_events) == 2
