# Argos Budget Guardian — Implementation Plan

## Context

AI agents built with the Claude Agent SDK can spiral in cost — retrying, looping, spawning subagents — with no way to set limits or see spending in real time. Cost unpredictability is the #1 developer complaint in the AI agent ecosystem.

**Argos Budget Guardian** is a Python library + CLI that tracks costs live, enforces budgets, and provides an accessible dashboard for both developers and non-technical team leads.

Named after **Argos Panoptes** — the all-seeing giant of Greek mythology with 100 eyes who never slept.

### Project Info

| | |
|---|---|
| **GitHub** | `brahim-guaali/argos-budget-guardian` |
| **PyPI** | `argos-budget-guardian` |
| **Import** | `argos_budget_guardian` |
| **License** | MIT |

---

## Project Structure

```
argos-budget-guardian/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── src/
│   └── argos_budget_guardian/
│       ├── __init__.py
│       ├── py.typed
│       ├── core/
│       │   ├── __init__.py
│       │   ├── tracker.py        # CostTracker: real-time accumulator
│       │   ├── budget.py         # BudgetPolicy: limits & enforcement
│       │   ├── pricing.py        # Model pricing registry
│       │   └── store.py          # Persistent storage (SQLite)
│       ├── hooks/
│       │   ├── __init__.py
│       │   ├── budget_hook.py    # PreToolUse: checks budget before execution
│       │   └── stop_hook.py      # Stop/SubagentStop: final session tally
│       ├── wrapper/
│       │   ├── __init__.py
│       │   ├── guardian.py       # GuardedAgent: drop-in wrapper
│       │   └── query.py          # guarded_query(): functional wrapper
│       ├── dashboard/
│       │   ├── __init__.py
│       │   ├── terminal.py       # Rich-based live terminal dashboard
│       │   └── components.py     # Reusable Rich renderables
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py           # Typer CLI entrypoint
│       │   └── setup_wizard.py   # Interactive first-run wizard
│       └── nlp/
│           ├── __init__.py
│           └── budget_parser.py  # Parse "$5 today" -> BudgetPolicy
├── tests/
│   ├── conftest.py
│   ├── test_tracker.py
│   ├── test_budget.py
│   ├── test_pricing.py
│   ├── test_hooks.py
│   ├── test_guardian.py
│   ├── test_store.py
│   ├── test_budget_parser.py
│   └── test_cli.py
├── examples/
│   ├── quickstart.py
│   ├── budget_policies.py
│   ├── with_dashboard.py
│   └── multi_agent.py
├── pyproject.toml
├── README.md
├── PLAN.md
├── CHANGELOG.md
└── LICENSE
```

---

## Phase 1: Core Library

### Step 1.1 — Project Scaffolding

Create `pyproject.toml`, `LICENSE` (MIT), and package directories.

**Dependencies:**
- `claude-agent-sdk` — the SDK we're wrapping
- `rich>=13.0` — terminal dashboard
- `typer>=0.9` — CLI framework

### Step 1.2 — Pricing Registry

**File:** `src/argos_budget_guardian/core/pricing.py`

Map Claude models to per-token costs for real-time estimation.

- `PricingRegistry` class with hardcoded prices:

| Model | Input/1M | Output/1M |
|-------|----------|-----------|
| Haiku 4.5 | $1.00 | $5.00 |
| Sonnet 4.6 | $3.00 | $15.00 |
| Opus 4.6 | $5.00 | $25.00 |

- `estimate_cost(model, input_tokens, output_tokens, cache_read, cache_create) -> float`
- `register(model_name, input_per_m, output_per_m)` — custom model support
- Cache read discount: ~90% off input price
- Cache creation: 25% more than input price

### Step 1.3 — Cost Tracker

**File:** `src/argos_budget_guardian/core/tracker.py`

Central in-memory accumulator. Thread-safe, observable.

- `CostEvent` dataclass: timestamp, model, tool_name, input/output/cache tokens, cost_usd, session_id, agent_id
- `CostTracker` class:
  - `record(event)` — append event, update running totals
  - `get_session_total(session_id) -> float`
  - `get_global_total() -> float`
  - `get_breakdown() -> dict` — by model and by tool
  - `reconcile(session_id, actual_cost)` — adjust estimate to match SDK's authoritative `ResultMessage.total_cost_usd`
  - `on_update(callback)` — subscribe to real-time updates (for dashboard)

### Step 1.4 — Budget Policy

**File:** `src/argos_budget_guardian/core/budget.py`

```python
@dataclass
class BudgetPolicy:
    max_cost_usd: float                          # Hard ceiling
    warn_at_percent: float = 80.0                # Emit warning at this %
    action_on_limit: Literal["warn", "pause", "stop"] = "stop"
    scope: Literal["session", "daily", "global"] = "session"
    cooldown_seconds: float = 0                  # For "pause" action
```

### Step 1.5 — Hooks

**File:** `src/argos_budget_guardian/hooks/budget_hook.py`

- `make_budget_hook(tracker, policy) -> HookCallback` — closure factory
- Registered as `PreToolUse` (no matcher = all tools)
- At limit: returns `permissionDecision: "deny"` with reason message
- At warning threshold: returns `systemMessage` with budget warning

**File:** `src/argos_budget_guardian/hooks/stop_hook.py`

- Registered as `Stop` and `SubagentStop`
- Finalizes session cost, triggers persistence to store

### Step 1.6 — GuardedAgent Wrapper (THE CORE)

**File:** `src/argos_budget_guardian/wrapper/guardian.py`

The heart of the library. It:
1. Wraps `ClaudeSDKClient`
2. Intercepts the message stream to read `AssistantMessage.usage` for real-time cost estimates
3. Reads `ResultMessage.total_cost_usd` for authoritative final cost and reconciles
4. Injects budget enforcement hooks via closure factories
5. Merges its hooks with user-provided hooks (guardian hooks run first)

**File:** `src/argos_budget_guardian/wrapper/query.py`

- `guarded_query()` — functional drop-in replacement for `claude_agent_sdk.query()`

### Step 1.7 — SQLite Store

**File:** `src/argos_budget_guardian/core/store.py`

- Storage at `~/.argos-budget-guardian/history.db`
- Tables: `sessions`, `cost_events`, `daily_totals`
- Optional — library works fully in-memory if persistence disabled

---

## Phase 2: CLI + Dashboard

### Step 2.1 — Natural Language Budget Parser

**File:** `src/argos_budget_guardian/nlp/budget_parser.py`

Simple regex-based parser (no ML):
- `"$5"` -> `BudgetPolicy(max=5.0, scope="session")`
- `"$10 per day"` -> `BudgetPolicy(max=10.0, scope="daily")`
- `"spend no more than $5 today"` -> `BudgetPolicy(max=5.0, scope="daily")`

### Step 2.2 — Dashboard Components

**File:** `src/argos_budget_guardian/dashboard/components.py`

Rich renderables:
- `BudgetBar` — green/yellow/red progress bar based on utilization
- `CostTicker` — large live cost display
- `ModelBreakdownTable` — cost per model with percentages
- `ToolCallLog` — scrolling recent tool calls with timestamps and costs
- `TokenSummary` — input/output/cache token counts

### Step 2.3 — Terminal Dashboard

**File:** `src/argos_budget_guardian/dashboard/terminal.py`

Full-screen Rich Live display using `rich.layout.Layout`. Refreshes every 500ms. Reads from `CostTracker` (in-process) or polls SQLite (separate process).

### Step 2.4 — CLI

**File:** `src/argos_budget_guardian/cli/main.py`

Typer-based commands:
- `argos setup` — interactive wizard -> writes `~/.argos-budget-guardian/config.toml`
- `argos status` — current running session costs
- `argos history` — past session costs table
- `argos dashboard` — launch live terminal dashboard
- `argos config` — view/edit configuration
- `argos export` — export to CSV/JSON

**File:** `src/argos_budget_guardian/cli/setup_wizard.py`

Interactive first-run: asks budget, action on limit, dashboard preference.

---

## Phase 3: Polish + GitHub-Ready

### Step 3.1 — Tests

**Directory:** `tests/`

| File | What it tests |
|------|---------------|
| `conftest.py` | Mock SDK messages fixture |
| `test_pricing.py` | Model prices, cache discounts, custom models |
| `test_budget.py` | Policy validation, threshold math |
| `test_tracker.py` | Record, totals, breakdown, reconciliation |
| `test_hooks.py` | Deny at limit, warn at threshold, pass below |
| `test_guardian.py` | Hook merging, message passthrough, budget stop |
| `test_store.py` | SQLite CRUD, daily aggregation |
| `test_budget_parser.py` | NLP parsing edge cases |
| `test_cli.py` | Typer CliRunner smoke tests |

**Mock strategy:** Hooks are plain async functions (dict in, dict out). `GuardedAgent` tests use a mock `ClaudeSDKClient` that yields pre-built messages. No real API calls.

### Step 3.2 — Examples

| File | Description |
|------|-------------|
| `quickstart.py` | Minimal 5-line example |
| `budget_policies.py` | Different policy configurations |
| `with_dashboard.py` | Live dashboard while agent runs |
| `multi_agent.py` | Budget tracking across subagents |

### Step 3.3 — CI/CD

- `.github/workflows/ci.yml` — ruff lint, mypy type-check, pytest on PR
- `.github/workflows/release.yml` — publish to PyPI on git tag

---

## Implementation Order

| # | What | Files |
|---|------|-------|
| 1 | Project scaffold | `pyproject.toml`, `LICENSE`, `__init__.py` |
| 2 | Pricing registry | `core/pricing.py` |
| 3 | Budget policy | `core/budget.py` |
| 4 | Cost tracker | `core/tracker.py` |
| 5 | Hooks | `hooks/budget_hook.py`, `hooks/stop_hook.py` |
| 6 | GuardedAgent + guarded_query | `wrapper/guardian.py`, `wrapper/query.py` |
| 7 | SQLite store | `core/store.py` |
| 8 | Budget parser | `nlp/budget_parser.py` |
| 9 | Dashboard components | `dashboard/components.py` |
| 10 | Terminal dashboard | `dashboard/terminal.py` |
| 11 | CLI | `cli/main.py`, `cli/setup_wizard.py` |
| 12 | Tests | `tests/*` |
| 13 | Examples | `examples/*` |
| 14 | CI/CD | `.github/workflows/*` |

---

## Key Technical Decisions

1. **Dual tracking** — Message stream interception for real-time estimates + `ResultMessage.total_cost_usd` for authoritative reconciliation
2. **Closure-based hooks** — Each `GuardedAgent` creates its own hook closures. No global state, supports multiple agents in one process
3. **Hook merging** — Guardian hooks run first (budget check before user hooks), user hooks preserved
4. **SQLite for history** — Append-heavy, query-heavy data. Right tool for the job
5. **Minimal dependencies** — Only `claude-agent-sdk`, `rich`, `typer` in core

---

## Verification Checklist

- [ ] `pytest tests/` — all pass, ~80% coverage
- [ ] Run `quickstart.py` with real API key — cost tracked and printed
- [ ] Set budget to $0.01 — agent stops with budget exceeded message
- [ ] `argos dashboard` shows live updates while agent runs
- [ ] `argos setup`, `argos history`, `argos status` display correctly
- [ ] `pip install -e .` then import from fresh script works
