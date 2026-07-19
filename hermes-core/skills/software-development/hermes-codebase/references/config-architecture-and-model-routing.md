# Hermes Config Architecture & Model Routing Enforcement

How agent presets, profiles, and delegate_task resolve models — and how to
enforce routing rules. Based on deep code analysis (July 2026).

## Agent Preset Loading (`/agent plan3`)

**Chain:** `cli.py:10444` → `agents.load_agents()` → `apply_agent()` → `switch_model()`

### Three-layer merge (lowest → highest priority)

| Layer | Source | What it provides |
|-------|--------|------------------|
| 1. Built-in | `_BUILTIN_AGENTS` in `agent/agents.py` | Default presets |
| 2. Disk | `~/.hermes/agents/*.md` (YAML frontmatter) | User-defined presets |
| 3. Config | `config.yaml → agents:` block | Overrides everything |

`load_agents()` (`agents.py:478`) merges all three. `_load_disk_agents()` (`agents.py:391`)
uses `rglob("*.md")` — discovers agents in subdirectories (e.g. `plan3/developer-agent.md`).

### How frontmatter model/provider reach the LLM

`apply_agent(agent_obj, agent_def)` (`agents.py:661`) → lines 706-719:

```python
if agent_def.model:
    agent_obj.switch_model(
        new_model=agent_def.model,
        new_provider=agent_def.provider or agent_obj.provider,
    )
```

`switch_model` (`agent_runtime_helpers.py:1354`) atomically swaps `agent.model`,
`agent.provider`, rebuilds the OpenAI client, and updates `_primary_runtime`.

**Important:** if `switch_model` fails (e.g. provider not found), the exception
is silently swallowed (`agents.py:718-719`: `logger.debug("apply_agent: model
switch failed")`). The session stays on whatever model it was on — no error
visible to the user.

## Profiles — Fully Independent HERMES_HOME

Each profile (`~/.hermes/profiles/<name>/`) is a completely standalone
HERMES_HOME with its own `config.yaml`, `.env`, `state.db`, agents/, skills/,
memory, sessions.

- `get_hermes_home()` (`hermes_constants.py:53`) resolves via env var override
- **No inheritance** — profiles do NOT inherit providers/models from the default profile
- Activated via `hermes -p <name>` or `hermes profile use <name>`

### Per-agent config overrides: NOT POSSIBLE

There is no mechanism to swap global `custom_providers:` when a specific agent
preset activates. The `model:` and `provider:` in agent frontmatter are just
pointers to entries that must exist in the global `config.yaml`.

## delegate_task Model Resolution

**Chain:** `delegate_tool.py:1990` → `_build_task_route_config:2437` →
`_resolve_delegation_credentials:2464` → `resolve_runtime_provider` (`runtime_provider.py:1241`)

For `provider="custom:local"`:
1. `_get_named_custom_provider("custom:local")` searches `config.yaml → custom_providers`
2. Finds `name: local` entry → extracts `api_base`, `api_key`
3. Passes to `AIAgent(model=..., base_url=..., api_key=...)`

### Model name validation: ABSENT

The `models:` list in `custom_providers` is **informational only** (used for
catalog display and context window resolution). There is NO `model_exists` /
`validate_model` check. If the model name doesn't match anything on the backend,
the error comes from the LLM server itself (HTTP 404 "model not found").

This means: if `config.yaml → custom_providers → local → models` contains
`deepseek-v4-pro`, Hermes will happily route to it through the `custom:local`
provider — even though the user intended `local` to mean "local models only".

## pre_tool_call Hook — Enforcement Pattern

### Capabilities

| Can do | Cannot do |
|--------|-----------|
| BLOCK a tool call (`{"action": "block", "message": "..."}`) | Modify tool args |
| Inspect all args (model, provider, goal, tasks) | Rewrite model/provider before execution |
| Allow passthrough (return `None`) | Selectively allow based on tool args |

The hook fires in `tool_executor.py:346-358` BEFORE any tool executes.

### Building an enforcement plugin

Pattern for a `pre_tool_call` plugin that enforces model routing:

```python
# plugins/my-enforcer/__init__.py
ROUTING = {
    "reasoning": {"model": "agents-a1", "provider": "custom:local"},
    "coding": {"model": "nex-n2-mini", "provider": "custom:local"},
}

CLOUD_INDICATORS = {"deepseek", "openai", "kimi", "zai", "anthropic"}

def _on_pre_tool_call(tool_name, args=None, **kwargs):
    if tool_name != "delegate_task":
        return None

    model = (args or {}).get("model", "")
    provider = (args or {}).get("provider", "")

    if _is_cloud(provider):
        return {"action": "block", "message": "Cloud provider blocked"}

    # Check batch tasks too
    for task in (args or {}).get("tasks", []):
        if _is_cloud(task.get("provider", "")):
            return {"action": "block", "message": "Batch task has cloud provider"}

    return None

def register(ctx):
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
```

```yaml
# plugins/my-enforcer/plugin.yaml
name: my-enforcer
version: "1.0.0"
hooks:
  - pre_tool_call
```

### Role classification for routing enforcement

When the enforcement plugin needs to determine the expected model from the
goal text (not an explicit `role` arg), use keyword-based classification:

```python
ROLE_KEYWORDS = {
    "reasoning": ["анализ", "research", "plan", "architect", "audit", ...],
    "coding": ["code", "implement", "develop", "deploy", "test", "fix", ...],
    "simulation": ["simulat", "agentworld", "rl", "environment", ...],
}
```

Match goal text against keyword sets, pick highest-scoring role.

### Emergency controls

- `PLAN3_ROUTING_DISABLE=1` — completely disable the plugin
- `PLAN3_ROUTING_WARN_ONLY=1` — log warnings but don't block (gradual rollout)

## Enforcement Layers (defense in depth)

| Layer | What it protects | Strength |
|-------|-----------------|----------|
| Agent prompt (plan3.md) | Tells LLM which model to use | Weak — LLM may ignore |
| `pre_tool_call` plugin | Blocks wrong model before spawn | Strong — code-level |
| LiteLLM config | Remove cloud models from proxy | Strongest — infra-level |
| Profile config.yaml | Only local models in custom_providers | Strong — full isolation |
| `delegation.model/provider` in config | Default model for all delegate_task | Medium — global default |

**Recommended combo:** Remove CLOUD routing table from agent prompt + enable
pre_tool_call plugin + strip cloud models from LiteLLM config.

## Key Pitfall: Cloud Models Under "local" Provider Name

When LiteLLM proxy config (`litellm-config.yaml`) contains both local AND cloud
models, and Hermes `config.yaml → custom_providers → local` lists cloud models,
the orchestrator can route to cloud models through `provider: custom:local` —
the name "local" is misleading. The provider name is just a label; it routes
to whatever LiteLLM has registered.

**Fix:** Either remove cloud models from LiteLLM config, or create a separate
custom provider entry (e.g. `name: local-only`) that only lists local models.
