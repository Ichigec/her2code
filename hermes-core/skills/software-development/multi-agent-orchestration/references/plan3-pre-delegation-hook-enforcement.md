# Plan3 Pre-Delegation Hook Enforcement

Architecture for mandatory model routing in plan3 orchestrator (2026-07-15).

## Problem

Plan3 model routing is defined in the system prompt (`plan3.md` Model Routing Table) but was **self-enforced by the orchestrator LLM** — if the LLM forgot or hallucinated the routing rules, `delegate_task` could use wrong models (e.g., `deepseek-v4-pro` for reasoning, `nex-n2-mini` for analysis).

Additionally, agent file frontmatter `model:` only controls sub-agent defaults — the **session model** comes from `config.yaml:model.default`, causing a split-brain where the orchestrator runs on cloud but sub-agents run local.

## Solution: 3-Level Enforcement

### Level 1: Hermes Plugin (`pre_tool_call` hook)

**Location:** `~/.hermes/plugins/plan3-routing-enforcer/`

Intercepts EVERY `delegate_task` call via the `pre_tool_call` hook. Returns `{"action": "block", "message": "..."}` to block invalid delegations before the subagent spawns.

```python
# plugin.yaml
name: plan3-routing-enforcer
hooks:
  - pre_tool_call

# __init__.py — register(ctx) function
def register(ctx):
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)

def _on_pre_tool_call(tool_name, args=None, **kwargs):
    if tool_name != "delegate_task":
        return None  # pass through
    
    model = args.get("model", "")
    provider = args.get("provider", "")
    goal = args.get("goal", "")
    
    role, _ = classify_role(goal)
    is_valid, block_msg = validate_delegation(model, provider, role)
    
    if not is_valid:
        return {"action": "block", "message": block_msg}
    return None
```

**Emergency disable:** `export PLAN3_ROUTING_DISABLE=1`
**Warn-only mode:** `export PLAN3_ROUTING_WARN_ONLY=1`

### Level 2: CLI Validation Script

**Location:** `~/.hermes/scripts/validate-plan3-delegation.py`

Auto-classifies delegation goal into reasoning/coding/simulation role using keyword matching, then validates model/provider against the routing table.

```bash
python3 validate-plan3-delegation.py \
  --model agents-a1-abliterated --provider custom:local \
  --goal "Research GRPO papers"
# → {"valid": true, "role": "reasoning", "expected": {...}}

python3 validate-plan3-delegation.py \
  --model deepseek-v4-pro --provider deepseek --role coding
# → {"valid": false, "errors": ["CLOUD PROVIDER...", "WRONG MODEL..."]}
```

### Level 3: Hermes Profile

**Location:** `~/.hermes/profiles/plan3/config.yaml`

```yaml
model:
  default: agents-a1-abliterated
  provider: custom:local
delegation:
  model: agents-a1-abliterated
  provider: custom:local
```

Fixes the session model split-brain. Without this profile, the orchestrator session runs on `config.yaml`'s default model (e.g., `deepseek-v4-pro`) even though sub-agents use local models.

## Routing Table

| Role | Model | Provider | Port | Benchmarks |
|------|-------|----------|------|------------|
| Reasoning | agents-a1-abliterated | custom:local | :8102 | GAIA 96, IFEval 94.8 |
| Coding | nex-n2-mini | custom:local | :8101 | SWE-Bench 74.4 |
| Simulation | agentworld | custom:local | :8103 | AgentWorldBench 56.39 |

## Role Classification

Keyword-based classification from the delegation goal text:
- **Reasoning keywords:** анализ, research, план, architect, audit, critic, observ, review, synthes, verify, strategy...
- **Coding keywords:** code, implement, develop, build, deploy, test, debug, fix, terminal, shell, script, commit...
- **Simulation keywords:** simulat, agentworld, rl, reinforcement, environment, adversar, scenario...

## GUI Integration

Desktop statusbar plan3 button (`🧬 P3`) includes profile controls in dropdown footer:
- "🧠 Plan3 Profile" → `selectProfile('plan3')` + `switchAgentPreset('plan3')`
- "📋 Profile" → `selectProfile('plan3')` only
- "🏠 Default" → `selectProfile('default')`

See: `hermes-desktop-extension` skill → `references/profile-button-integration.md`
