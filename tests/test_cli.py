"""Smoke tests for CLI commands."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from argos_budget_guardian.cli.main import app
from argos_budget_guardian.core.store import Store

runner = CliRunner()


def _temp_store():
    """Create a store using a temporary database."""
    tmpdir = tempfile.mkdtemp()
    return Store(db_path=Path(tmpdir) / "test.db")


class TestCLI:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Argos Budget Guardian" in result.output

    def test_status_no_history(self):
        # Patch DEFAULT_DB_PATH to a non-existent path
        fake_path = Path("/tmp/argos-test-nonexistent/history.db")
        with patch("argos_budget_guardian.cli.main.DEFAULT_DB_PATH", fake_path):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "No cost history" in result.output

    def test_history_no_sessions(self):
        store = _temp_store()
        fake_path = store._db_path
        with (
            patch("argos_budget_guardian.cli.main.DEFAULT_DB_PATH", fake_path),
            patch("argos_budget_guardian.cli.main.Store", return_value=store),
        ):
            result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        store.close()

    def test_export_no_history(self):
        fake_path = Path("/tmp/argos-test-nonexistent/history.db")
        with patch("argos_budget_guardian.cli.main.DEFAULT_DB_PATH", fake_path):
            result = runner.invoke(app, ["export"])
        assert result.exit_code == 0
        assert "No cost history" in result.output

    def test_export_invalid_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            Store(db_path=db_path).close()  # Create DB
            with patch("argos_budget_guardian.cli.main.DEFAULT_DB_PATH", db_path):
                result = runner.invoke(app, ["export", "--format", "xml"])
        assert result.exit_code == 1

    def test_config_section_aware(self):
        """Test that _load_config correctly parses TOML sections."""
        from argos_budget_guardian.cli.main import _parse_simple_toml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[budget]\ndefault_budget_usd = 25.0\n\n[dashboard]\nshow_by_default = true\n')
            f.flush()
            config = _parse_simple_toml(Path(f.name))

        assert config["budget"]["default_budget_usd"] == 25.0
        assert config["dashboard"]["show_by_default"] is True
