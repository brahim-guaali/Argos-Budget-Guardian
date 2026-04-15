# Contributing to Argos Budget Guardian

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/brahim-guaali/argos-budget-guardian.git
cd argos-budget-guardian

# Create a virtual environment and install dev dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

Tests use `pytest-asyncio` (auto mode) for async tests. No external services are required — the test suite is fully self-contained.

## Linting and Type Checking

```bash
ruff check src/ tests/
mypy src/
```

The project targets Python 3.10+ and uses a line length of 100 characters.

## Project Structure

```
src/argos_budget_guardian/
  core/         # Budget policy, pricing registry, cost tracker, SQLite store
  hooks/        # Claude Agent SDK hook implementations (budget enforcement, stop)
  wrapper/      # GuardedAgent and guarded_query() — the main public API
  cli/          # Typer CLI (argos command)
  dashboard/    # Rich-based terminal dashboard components
  nlp/          # Natural language budget parser
```

## Making Changes

1. Create a branch from `main`.
2. Make your changes. Keep them focused — one concern per PR.
3. Add or update tests for any new or changed behavior.
4. Run `pytest`, `ruff check`, and `mypy` before submitting.
5. Open a pull request with a clear description of what and why.

## Conventions

- Use type annotations on all public functions and methods.
- Follow existing code style — ruff enforces the basics.
- Avoid adding dependencies unless necessary. The core library intentionally has a small dependency footprint.
- Tests go in `tests/` with filenames matching `test_<module>.py`.

## Reporting Issues

File issues at [GitHub Issues](https://github.com/brahim-guaali/argos-budget-guardian/issues). Include:

- What you expected vs. what happened
- Python version and OS
- Minimal reproduction steps if applicable

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
