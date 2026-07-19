# Agent Model Routing Enforcement — Full Framework

Session 20260715: deep analysis of how to force Hermes orchestrators
(especially plan3) to use ONLY local models. Covers Hermes architecture
internals, 6 enforcement strategies ranked by complexity/reliability,
and diagnostic methodology.

## Problem Space

An agent preset like plan3 is supposed to route delegations to 3 local
models via LiteLLM :4000 → llama-servers :8101-8103. In practice,
orchestrators leak to cloud models because:

1. **Agent body contains routing tables** — `### Routing Rules (CLOUD)`
   with `deepseek-v4-pro` for almost every role. The orchestrator LLM
   reads these as instructions.
2. **LiteLLM config mixes local + cloud** — `deepseek-v4-pro` is
   registered alongside `agents-a1-abliterated`. Both accessible via
   `custom:local`.
3. **config.yaml `custom_providers` lists cloud models under `local`**
   — reinforces availability.
4. **No enforcement mechanism** — Hermes has no per-agent model
   whitelist, no model name validation in `delegate_task`.

## Hermes Architecture Internals (codebase-verified)

### How `/agent plan3` loads and applies model

```
cli.py:10444 (_handle_agent_command)
  → agents.load_agents()           # agents.py:478 — merge builtin < disk < config
    → _load_disk_agents()          # agents.py:391 — rglob("*.md") in ~/.hermes/agents/
      → _parse_frontmatter()       # agents.py:367 — split on ---, yaml.safe_load
      → _coerce_agent_def()        # agents.py:336 — build AgentDef dataclass
  → apply_agent(self.agent, agent_def)  # agents.py:661
    → agent.switch_model(new_model, new_provider)  # agents.py:706
      → agent_runtime_helpers.switch_model()  # :1354 — atomic model+provider swap
    → self.enabled_toolsets = agent_def.toolsets   # agents.py:686
    → self.reasoning_effort = agent_def.reasoning  # agents.py:698
```

### How `delegate_task` model override reaches the LLM

```
delegate_tool.py:1990 — delegate_task(model="nex-n2-mini", provider="custom:local")
  → _build_task_route_config()          # :2437 — put model/provider in cfg dict
  → _resolve_delegation_credentials()    # :2464
    → resolve_runtime_provider()         # runtime_provider.py:1241
      → _resolve_named_custom_runtime()  # :644
        → _get_named_custom_provider()   # :492 — search config.yaml custom_providers
    → returns {model, provider, base_url, api_key, api_mode}
  → _build_child_agent()                 # delegate_tool.py:1064
    → AIAgent(model=..., provider=..., base_url=..., api_key=...)  # :1149
```

### Key findings

- **NO model name validation** in delegate_task. Only provider existence
  and API key presence are checked. Model string passes through to the
  HTTP call transparently. Non-existent model → HTTP 404 from endpoint,
  not a Hermes-side error.
- **`config.yaml → agents:` section** CAN override frontmatter fields
  (model, provider, toolsets) per agent. But this is field-level, NOT
  a full config override — no per-agent providers/models.
- **Profiles = standalone HERMES_HOME.** Each profile has its own
  config.yaml, .env, state.db, agents/, skills/, sessions. No
  inheritance/merging between profiles. `get_hermes_home()` in
  `hermes_constants.py:53` resolves via env override or HERMES_HOME.
- **`pre_tool_call` hook** (`plugins.py:1789`, invoked at
  `tool_executor.py:346`) — can BLOCK a tool call (returns
  `{"action": "block"}`) but CANNOT modify args (model, provider).
  Unlike `pre_gateway_dispatch` which supports rewrite semantics,
  `pre_tool_call` is block-or-allow only.

## 6 Enforcement Strategies

### A) Remove CLOUD routing table from agent .md body (soft, immediate)

The orchestrator reads the agent .md body as its system prompt. If
it contains `### Routing Rules (CLOUD)` with cloud model assignments,
the LLM follows those instructions.

**Action:** Delete the CLOUD table entirely. Keep only the LOCAL table.

```diff
 ## Model Routing (v3)
-### Routing Rules (CLOUD)
-| Role | Model | Provider |
-| Orchestrator | deepseek-v4-pro | deepseek |
-...
 ### Routing Rules (LOCAL)
 | Role | Model | Provider |
 | Orchestrator | agents-a1-abliterated | custom:local |
```

| Metric | Rating |
|--------|--------|
| Complexity | ⭐ (5 min) |
| Reliability | ⭐⭐⭐ (LLM may still "remember" cloud options) |
| Scope | Per-agent |

### B) Remove cloud models from LiteLLM config (hard, infra-level)

If the model isn't registered in LiteLLM, any delegation to it returns
HTTP 404 — impossible to reach cloud.

**Action:** Edit `litellm-config.yaml`, remove cloud model entries.

| Metric | Rating |
|--------|--------|
| Complexity | ⭐⭐ (edit + restart LiteLLM) |
| Reliability | ⭐⭐⭐⭐⭐ (physically impossible to bypass) |
| Scope | Global (all agents, all consumers) |

### C) Separate Hermes profile (full isolation)

Create `~/.hermes/profiles/plan3/` with only local models in
config.yaml. Cloud models literally don't exist in this profile's
universe.

| Metric | Rating |
|--------|--------|
| Complexity | ⭐⭐⭐ (profile setup, skill/memory duplication) |
| Reliability | ⭐⭐⭐⭐⭐ |
| Scope | Full session isolation |

### D) LiteLLM Router Rules (infra-level guard)

LiteLLM supports routing rules that can block specific models:

```yaml
router_settings:
  routing_rules:
    - model_name: "deepseek-v4-pro"
      action: "block"
```

| Metric | Rating |
|--------|--------|
| Complexity | ⭐⭐⭐ |
| Reliability | ⭐⭐⭐⭐ |
| Scope | LiteLLM proxy level |

### E) `pre_tool_call` plugin — block non-whitelisted delegations

```python
PLAN3_WHITELIST = {"agents-a1-abliterated", "nex-n2-mini", "agentworld"}

def pre_tool_call(tool_name, args, **kwargs):
    if tool_name != "delegate_task":
        return None
    model = args.get("model", "")
    if model and model not in PLAN3_WHITELIST:
        return {"action": "block",
                "message": f"Model '{model}' not allowed. Use local models."}
    return None
```

**Limitation:** Can only BLOCK, not rewrite the model arg. The
orchestrator gets an error and must retry with a local model.

| Metric | Rating |
|--------|--------|
| Complexity | ⭐⭐⭐⭐ (write plugin) |
| Reliability | ⭐⭐⭐⭐ |
| Scope | Per-tool (delegate_task only) |

### F) Code patch — model whitelist in AgentDef

Add `model_whitelist` field to `AgentDef` dataclass, validate in
`delegate_tool.py` before building child agent.

| Metric | Rating |
|--------|--------|
| Complexity | ⭐⭐⭐⭐⭐ (fork Hermes) |
| Reliability | ⭐⭐⭐⭐⭐ |
| Scope | Per-agent, in-code |

## Implementation Validation (session 20260715_214943)

Strategy E (pre_tool_call plugin) was fully implemented and tested:

**What was built and verified working:**
- Plugin `plan3-routing-enforcer` (~/.hermes/plugins/) with role
  classification (bilingual RU/EN keywords), cloud detection, forbidden
  model detection, batch-mode validation
- Validation script `validate-plan3-delegation.py` (~/.hermes/scripts/)
  for manual CLI checks
- Profile `~/.hermes/profiles/plan3/` with `model.default:
  agents-a1-abliterated`, `delegation.model: agents-a1-abliterated`
- All 6 unit tests passed: valid reasoning ✅, cloud blocked ✅,
  wrong model blocked ✅, non-delegate passthrough ✅, batch cloud
  blocked ✅, role classification ✅

**Critical gaps found during validation — ALL RESOLVED (session 20260715_2230):**

| Gap | Impact | Status | Fix Applied |
|-----|--------|--------|-------------|
| Plugin NOT enabled (`hermes plugins list` → "not enabled") | Zero enforcement — plugin exists on disk but Hermes never loads it | ✅ RESOLVED | `hermes plugins enable plan3-routing-enforcer` → status changed to `enabled` |
| CLOUD routing table still in plan3.md body (lines 299-313) | Orchestrator reads cloud model assignments and attempts cloud delegations → plugin blocks every call → orchestrator confused | ✅ RESOLVED | CLOUD table deleted via `patch` (18 lines removed, LOCAL table kept) |
| Profile plan3 `custom_providers → local → models` still lists `deepseek-v4-pro`, `gpt-4.1`, etc. | Cloud models accessible through profile's `custom:local` provider | ✅ RESOLVED | 6 cloud models removed from profile config (deepseek-*, gpt-*) |
| GUI integration (profile launch buttons) | Initially reported as "not completed" | ✅ WAS DONE | **Validation false negative** — GUI was actually completed in the same session (build succeeded, +191 lines in 2 files). First validation pass didn't read far enough into session messages. |

**Implemented combo: A + C + E** (prompt cleanup + profile isolation +
plugin enforcement). The docs recommended "A + B" but the actually-implemented
and verified solution was A + C + E — all three layers applied together.

**Final verification results (all passed):**
- Plugin status: `enabled` ✅
- CLOUD routing table: 0 occurrences ✅ (3 remaining = enforcement docs examples only)
- Profile plan3 cloud leaked: `[]` ✅
- Default profile intact: `deepseek-v4-pro` still available for plan2 ✅
- Validation script: valid reasoning ✅, cloud blocked ✅, wrong model ✅
- Profile isolation: different inodes (4461105 vs 35947914), no cross-contamination ✅

**⚠️ Validation methodology lesson:** When validating work from a previous
session, read ALL messages to the end of the session — not just the first
gap you find. The first validation pass reported GUI integration as
"incomplete" when it was actually successfully built. The agent had stopped
reading at message ~100127, but the session continued to message ~100163
with a successful build and summary. **Always check `message_count` and
read the last 10-15 messages before declaring work incomplete.**

**Key lesson: Strategy A + E must be applied TOGETHER.** A plugin that
blocks cloud delegations without removing the cloud routing table from
the agent prompt creates an adversarial loop: orchestrator reads
"Orchestrator → deepseek-v4-pro" in its system prompt, tries to delegate
to deepseek, plugin blocks it, orchestrator retries (same instructions),
gets blocked again. The prompt (Strategy A) and the hook (Strategy E)
are complementary layers — prompt tells the LLM what to do, hook enforces
it when the LLM doesn't listen.

## Plugin Template

See `templates/routing-enforcer-plugin.py` for the complete validated
plugin code (copy → adapt routing table → deploy). See
`templates/routing-enforcer-plugin.yaml` for the plugin.yaml manifest.

**Deployment steps:**
```bash
# 1. Copy plugin files
mkdir -p ~/.hermes/plugins/<name>
cp templates/routing-enforcer-plugin.py ~/.hermes/plugins/<name>/__init__.py
cp templates/routing-enforcer-plugin.yaml ~/.hermes/plugins/<name>/plugin.yaml

# 2. Edit routing table in __init__.py for your models

# 3. ENABLE the plugin (critical — plugin on disk but not enabled = zero enforcement)
hermes plugins enable <name>

# 4. Verify it's loaded
hermes plugins list | grep <name>
# → should show "enabled" not "not enabled"

# 5. Test: delegate with wrong model, verify it's blocked
```

## Recommended Combo: A + C + E (IMPLEMENTED & VERIFIED)

The actually-implemented and fully verified solution combines three layers:

1. **Strategy A** — remove CLOUD routing table from agent .md body.
   Verified: `grep -c "CLOUD.*контекст" plan3.md` → 0.
2. **Strategy C** — create profile with only local models in config.yaml.
   Remove cloud models from `custom_providers → local → models`.
   Verified: `Cloud leaked: []`. Default profile untouched (plan2 keeps deepseek).
3. **Strategy E** — pre_tool_call plugin to block invalid delegations.
   Verified: `hermes plugins list` → `enabled`. All 6 unit tests pass.

**Why all three are needed:**
- A alone: LLM might still "remember" cloud models from training/habit.
- C alone: LLM can still TRY to use cloud models (gets config error, wastes turns).
- E alone: creates adversarial loop (LLM reads CLOUD table, tries cloud, gets blocked, retries).
- A+C+E: prompt says "use local", config makes cloud unavailable, plugin catches leaks.

**Alternative: A + B** (prompt cleanup + LiteLLM model removal) also works
but is more disruptive — removing cloud models from LiteLLM affects ALL
consumers (plan2, other tools), not just plan3. Use A+B only when you want
to block cloud globally, not per-profile.
