# Plan3 Model Routing Validation — Methodology & Audit (2026-07-15)

Full audit of plan3 "Fully Local" design intent vs. actual deployment state. Discovered 5 agents on cloud, 13 with inconsistent naming, and registry.json with 43 cloud entries.

## Root Cause

When plan3 was forked from plan2, frontmatter and registry.json were copied but never updated. No automated check enforces "local-only" policy. The agent file frontmatter `model/provider` field does NOT control the session's own model — it only applies to sub-agents spawned via `delegate_task`. The session model comes from `model.default` in `config.yaml`.

## 5-Check Validation Methodology

Run before any plan3 cycle:

### Check 1: Sub-agent frontmatter (18 files)

```bash
for f in ~/.hermes/agents/plan3/*.md; do
    name=$(basename "$f")
    model=$(grep -m1 "^model:" "$f" | sed 's/model: *//')
    provider=$(grep -m1 "^provider:" "$f" | sed 's/provider: *//')
    case "$model" in
        agents-a1-abliterated) role="Reasoning :8102" ;;
        nex-n2-mini) role="Coding :8101" ;;
        agentworld) role="Simulation :8103" ;;
        *) echo "❌ $name: UNKNOWN model $model" ;;
    esac
    [[ "$provider" != "custom:local" ]] && echo "❌ $name: provider=$provider (should be custom:local)"
done
```

### Check 2: registry.json

```bash
python3 -c "
import json
with open('$HERMES_HOME/agents/registry.json') as f:
    reg = json.load(f)
cloud = [(n, a['provider']) for n,a in reg['agents'].items() 
         if any(c in a.get('provider','') for c in ['deepseek','kimi','openai','zai'])]
print(f'Cloud agents: {len(cloud)}')
for n,p in cloud: print(f'  ❌ {n} → {p}')
"
# Expected: 0 cloud agents
```

### Check 3: Physical llama-server health

```bash
for port in 8101 8102 8103; do
    models=$(curl -sf http://127.0.0.1:$port/v1/models | \
        python3 -c "import json,sys; d=json.load(sys.stdin); print([m['id'] for m in d.get('data',[])])")
    echo ":$port → $models"
done
# Expected: :8101→nex-n2-mini, :8102→agents-a1, :8103→agentworld
```

### Check 4: LiteLLM model→server mapping

```bash
grep -A3 "model_name:" /home/user/dev/llama/litellm-config.yaml | \
    grep -E "model_name|api_base"
# Confirm: nex-n2-mini→:8101, agents-a1→:8102, agentworld→:8103
```

### Check 5: start-llama.sh $HOME bug detection

```bash
# The script uses ${HOME} for paths — breaks under Hermes terminal ($HOME=/home/user/.hermes/home)
grep "REAL_HOME" /home/user/dev/llama/start-llama.sh || echo "❌ start-llama.sh missing REAL_HOME fix"
grep "getent passwd" /home/user/dev/llama/start-llama.sh || echo "❌ start-llama.sh missing getent fix"  
```

### Check 6: Session model (the orchestrator itself)

```bash
# The #1 failure mode: agent file frontmatter says local, but session uses cloud
grep "^model:" $HERMES_HOME/config.yaml | head -3
# Expected: default: agents-a1-abliterated, provider: local
# If it says glm-5.2 / zai → plan3 will use GLM cloud for the orchestrator
```

## What Was Found (2026-07-15)

| Problem | Count | Fixed |
|---------|:-----:|:-----:|
| Cloud-pointing frontmatter (deepseek/kimi) | 5 | ✅ → local |
| Inconsistent providers (`local` vs `custom:local`) | 13 | ✅ → `custom:local` |
| Stale registry.json (cloud entries) | 43 | ✅ → local |
| start-llama.sh `${HOME}` bug | 5 places | ✅ → `${REAL_HOME}` |
| kimi-k2.7-code broken (HTTP 400) | 2 agents | ✅ → nex-n2-mini |
| Session model = glm-5.2/zai not local | 1 | ✅ → agents-a1/local |

## Correct Model Routing

| Role Type | Model | Provider | Port | Benchmarks |
|-----------|-------|----------|------|------------|
| Reasoning (14 phases) | agents-a1-abliterated | custom:local | :8102 | GAIA 96, IFEval 94.8 |
| Coding (7 phases) | nex-n2-mini | custom:local | :8101 | SWE-Bench 74.4 |
| Simulation (on-demand) | agentworld | custom:local | :8103 | AgentWorldBench 56.39 |

## Session Model Pitfall (CRITICAL)

`/agent plan3` loads the system prompt from `plan3.md` but the **model comes from `config.yaml`**, not the agent file frontmatter. Agent file frontmatter `model:` ONLY applies to sub-agents spawned via `delegate_task`.

```yaml
# ~/.hermes/agents/plan3.md frontmatter:
model: agents-a1-abliterated    # ← ONLY for sub-agents!
provider: custom:local          # ← ONLY for sub-agents!

# ~/.hermes/config.yaml:
model:
  default: agents-a1-abliterated  # ← THIS controls the session model
  provider: local                 # ← THIS controls the session provider
```

**Fix:** `hermes config set model.default agents-a1-abliterated && hermes config set model.provider local`

## Auto-Fix Script

`scripts/validate-plan3-models.py` — runs all 6 checks + auto-fixes frontmatter/registry.
Run before any plan3 cycle: `python3 ~/.hermes/skills/software-development/multi-agent-orchestration/scripts/validate-plan3-models.py`

## Runtime Enforcement (2026-07-15 addition)

Static validation catches configuration drift, but does NOT prevent the orchestrator
from calling `delegate_task(model="deepseek-v4-pro", ...)` at runtime. The
**pre-delegation hook** (`plan3-routing-enforcer` plugin) adds a runtime guard:
- Uses `pre_tool_call` hook to intercept every `delegate_task`
- Auto-classifies role from goal text (203 keywords, EN+RU)
- Blocks invalid model/provider with `{"action": "block", "message": "..."}`
- Supports single-task and batch modes
- Emergency disable: `export PLAN3_ROUTING_DISABLE=1`

Additionally, the **plan3 Hermes profile** (`hermes --profile plan3`) solves the
session model pitfall (Check 6) by setting `model.default=agents-a1-abliterated`.

Full hook architecture + deployment: `references/plan3-pre-delegation-hook.md`
