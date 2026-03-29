"""Smoke tests for CLI commands."""

from typer.testing import CliRunner

from argos_budget_guardian.cli.main import app

runner = CliRunner()


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
        result = runner.invoke(app, ["status"])
        # Should not crash even with no history
        assert result.exit_code == 0

    def test_history_no_sessions(self):
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
