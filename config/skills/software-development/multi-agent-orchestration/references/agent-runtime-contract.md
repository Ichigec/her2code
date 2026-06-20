# Agent Runtime Contract — `/agent` vs `delegate_task`

Session lesson from reviewing Hermes runtime changes around agent registry, permission policies, and orchestration.

## Core distinction

Hermes currently has two related but separate runtime mechanisms:

1. **Top-level agent switching** — `/agent <id>`
   - Loads agent definitions from built-ins, `~/.hermes/agents/*.md`, and config.
   - `apply_agent()` mutates the live parent `AIAgent`:
     - `current_agent_id`
     - `agent_config`
     - `model`
     - `ephemeral_system_prompt`
     - `permission_policy`
     - `enabled_toolsets`
     - temperature/reasoning.
   - `/agent plan` therefore makes the current session a prompt-driven orchestrator until the next `/agent ...` switch.

2. **Delegated child agents** — `delegate_task(...)`
   - Creates a fresh child `AIAgent` in an isolated context.
   - Child receives only the `goal`, `context`, selected/inherited toolsets, role, and optional model/provider routing.
   - Child returns a summary to the parent; intermediate state/history is not durable in the parent context.
   - Leaf children cannot delegate further; orchestrator children depend on `delegation.orchestrator_enabled` and `delegation.max_spawn_depth`.

## Current limitation

`delegate_task` does **not** currently expose an `agent_id` parameter.

Do **not** assume this works:

```python
# Not current runtime behavior
delegate_task(agent_id="requirements-agent", goal="...")
```

Instead, inject the role/persona explicitly:

```python
delegate_task(
    goal="You are requirements-agent. Collect requirements only; do not design or code.",
    context="Task: ...\nRequired artifact: docs/requirements/<slug>.md\nUser preference: test autonomously; never ask User to verify.",
    toolsets=["clarify"],
    model="gpt-5.5",
    provider="custom:openai",
    role="leaf",
)
```

## Consequences for orchestration

- `~/.hermes/agents/*.md` files are reliable top-level `/agent` presets and good source material for prompts.
- They are **not** automatically addressable child-agent identities until runtime adds explicit support.
- Observer agents are stateless: spawn them at checkpoints, pass previous checkpoint artifacts, and write new checkpoint files.
- A successful default child smoke proves only that delegation works somehow; it does not prove a specific role/model/provider route.

## Desired future runtime feature

A robust implementation would add explicit child role loading, for example:

```python
delegate_task(
    agent_id="developer-agent",
    goal="Implement task DEV-003",
    context="...",
    model="kimi-k2.7-code",
    provider="custom:kimi",
)
```

Acceptance criteria for that feature:

- Loads the disk/built-in agent prompt by id.
- Merges or overrides toolsets deterministically.
- Applies child permission policy, model, provider, reasoning, and mode.
- Keeps parent history isolated from child history.
- Has tests for missing agent ids, per-call overrides, provider routing, permission denial, and nested-orchestrator depth limits.
