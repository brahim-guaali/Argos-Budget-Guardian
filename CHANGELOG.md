# Changelog

## 0.1.0 (2026-03-29)

Initial release.

### Features

- **GuardedAgent**: Drop-in wrapper for Claude Agent SDK with budget enforcement
- **guarded_query()**: Functional wrapper as drop-in replacement for `query()`
- **BudgetPolicy**: Declarative budget configuration (session, daily, global scopes)
- **Real-time cost tracking**: Per-query, per-session, and global cost accumulation
- **Budget enforcement hooks**: PreToolUse hook that denies/pauses/warns at budget limits
- **Natural language budgets**: Parse strings like "$5 per day" into policies
- **Terminal dashboard**: Rich-based live display with budget bar, cost breakdown, and tool log
- **CLI**: `argos setup`, `status`, `history`, `dashboard`, `config`, `export` commands
- **SQLite persistence**: Cost history stored locally for review and export
- **CSV/JSON export**: Export cost history for external analysis
- **Callback support**: `on_warning` and `on_limit` hooks for alerts and integrations
