# Argos Budget Guardian

> Real-time cost tracking and budget enforcement for the Claude Agent SDK

Named after **Argos Panoptes** — the all-seeing giant of Greek mythology with 100 eyes who never slept — because this tool watches every token, every tool call, every dollar.

## The Problem

AI agents built with the Claude Agent SDK can spiral in cost — retrying, looping, spawning subagents — with no way to set limits or see spending in real time. Cost unpredictability is the #1 developer complaint in the AI agent ecosystem. There's no open-source tool that prevents overspend in real time for Claude Agent SDK.

**Argos Budget Guardian** fills this gap.

## Features

- **Real-time cost tracking** per query, session, and daily
- **Budget enforcement** that actually stops agents before you overspend
- **Live terminal dashboard** showing costs as they happen
- **Natural language budgets** ("spend no more than $5 today")
- **Drop-in wrapper** — 2 lines to add to existing code
- **Works with your hooks** — merges with existing SDK hooks
- **CLI tools** for monitoring, history, and configuration
- **Accessible** for both developers and non-technical team leads

## Quick Start

```bash
pip install argos-budget-guardian
```

```python
from argos_budget_guardian import guarded_query

async for msg in guarded_query("Refactor the auth module", budget=5.0):
    print(msg)
# Prints cost summary automatically at the end
```

## Usage

### With GuardedAgent (recommended)

```python
from argos_budget_guardian import GuardedAgent

async with GuardedAgent(budget=10.0, dashboard=True) as agent:
    async for msg in agent.query("Analyze and fix all bugs in src/"):
        pass  # Dashboard shows live costs

    print(f"Total: ${agent.total_cost:.4f}")
    print(f"Remaining: ${agent.budget_remaining:.4f}")
    print(agent.cost_report())
```

### Natural language budget

```python
from argos_budget_guardian import GuardedAgent

async with GuardedAgent(budget="spend no more than $5 today") as agent:
    async for msg in agent.query("..."):
        pass
```

### Custom policy

```python
from argos_budget_guardian import GuardedAgent, BudgetPolicy

policy = BudgetPolicy(
    max_cost_usd=20.0,
    warn_at_percent=70,
    action_on_limit="pause",
    cooldown_seconds=5,
    scope="daily",
)

async with GuardedAgent(budget=policy) as agent:
    async for msg in agent.query("..."):
        pass
```

### With existing SDK options

```python
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher
from argos_budget_guardian import GuardedAgent

options = ClaudeAgentOptions(
    model="sonnet",
    permission_mode="acceptEdits",
    allowed_tools=["Read", "Write", "Bash"],
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[my_custom_hook])]
    }
)

# Guardian merges its hooks with yours — yours still run
async with GuardedAgent(budget=5.0, options=options) as agent:
    async for msg in agent.query("..."):
        pass
```

### Callbacks for alerts

```python
from argos_budget_guardian import GuardedAgent

def on_warn(current: float, limit: float):
    slack.post(f"Agent at {current/limit*100:.0f}% of budget")

def on_limit(current: float, limit: float):
    slack.post(f"Agent budget exhausted: ${current:.2f}")

async with GuardedAgent(
    budget=50.0,
    on_warning=on_warn,
    on_limit=on_limit,
) as agent:
    async for msg in agent.query("..."):
        pass
```

## CLI

```bash
argos setup       # Interactive configuration wizard
argos status      # Current running session costs
argos history     # Past session cost history
argos dashboard   # Launch live terminal dashboard
argos config      # View or edit configuration
argos export      # Export cost history to CSV/JSON
```

## Dashboard

```
+-----------------------------------------------------------+
|  Argos Budget Guardian                    SESSION ACTIVE   |
+-----------------------------------------------------------+
|  Current Cost:  $0.4230                                    |
|  Budget: ################..........  42% of $1.00          |
|                                                            |
|  Cost by Model          |  Recent Tool Calls               |
|  sonnet-4.6  $0.38 90%  |  14:32 Write   $0.045           |
|  haiku-4.5   $0.04 10%  |  14:31 Bash    $0.012           |
|                          |  14:31 Read    $0.003           |
|                                                            |
|  Tokens: 12,450 in / 3,200 out / 8,100 cached             |
+-----------------------------------------------------------+
```

## API Reference

### `GuardedAgent`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `budget` | `float \| str \| BudgetPolicy` | `10.0` | Budget limit — dollar amount, natural language, or policy object |
| `options` | `ClaudeAgentOptions \| None` | `None` | Existing SDK options (hooks will be merged) |
| `on_warning` | `Callable \| None` | `None` | Called when approaching budget threshold |
| `on_limit` | `Callable \| None` | `None` | Called when budget is exceeded |
| `dashboard` | `bool` | `False` | Show live terminal dashboard |

### `BudgetPolicy`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_cost_usd` | `float` | *required* | Hard spending ceiling |
| `warn_at_percent` | `float` | `80.0` | Warning threshold as % of max |
| `action_on_limit` | `"warn" \| "pause" \| "stop"` | `"stop"` | What happens at the limit |
| `scope` | `"session" \| "daily" \| "global"` | `"session"` | Budget time scope |
| `cooldown_seconds` | `float` | `0` | Pause duration (for "pause" action) |

### `guarded_query()`

Drop-in replacement for `claude_agent_sdk.query()` with budget enforcement.

```python
async for msg in guarded_query(prompt, budget=5.0, options=None):
    ...
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT
