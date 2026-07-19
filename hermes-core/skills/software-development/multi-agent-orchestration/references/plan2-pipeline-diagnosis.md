# plan2 Pipeline Diagnosis — Systematic Diagnostic Methodology

> Session 20260714. plan2 orchestrator was completely non-functional. This document
> captures the diagnostic methodology that identified 5 root causes and the fixes applied.

## Diagnostic Checklist (run in order)

When plan2 "doesn't work" or phases fail silently, check these 5 layers:

### Layer 1: Path Resolution ($HOME mismatch)

**Symptom:** Gate scripts, capability checks, and agent file commands silently fail with "file not found" or return 0 results.

**Root cause:** Hermes terminal sets `$HOME=/home/user/.hermes/home` (NOT `/home/user`). All `~/.hermes/` paths in agent `.md` files, YAML gate configs, and Python scripts resolve incorrectly.

**Diagnostic:**
```bash
echo "$HOME"                          # Should be /home/user, is /home/user/.hermes/home
ls ~/.hermes/scripts/ 2>&1           # "No such file or directory"
ls "$HERMES_HOME/scripts/" 2>&1     # Works!
grep -rn '~/.hermes/' "$HERMES_HOME/agents/"*.md "$HERMES_HOME/gates/"*.yaml
```

**Fix:**
```bash
# Agent files: replace ~/.hermes/ → $HERMES_HOME/
sed -i 's|~/.hermes/|$HERMES_HOME/|g' "$HERMES_HOME/agents/plan2.md"
sed -i 's|\$HOME/\.hermes/|$HERMES_HOME/|g' "$HERMES_HOME/agents/plan2.md"

# YAML gate configs: same replacement
sed -i 's|~/.hermes/|$HERMES_HOME/|g' "$HERMES_HOME/gates/all_gates.yaml"

# Python scripts: replace os.path.expanduser("~") with HERMES_HOME env
# See hermes-scripting-patterns skill → "Agent Prompt Files and YAML Gate Configs"
```

**Scope (this session):** 38 replacements in plan2.md, 7 in all_gates.yaml, 1 in orchestrator_gate.py.

### Layer 2: Provider Configuration

**Symptom:** Agent file specifies `provider: deepseek` but that provider doesn't exist in config.yaml. Models exist under a different provider (e.g., `custom:local` via LiteLLM).

**Diagnostic:**
```bash
# What providers are configured?
grep -A5 'custom_providers:\|^providers:' "$HERMES_HOME/config.yaml"

# What does the agent file specify?
grep 'provider' "$HERMES_HOME/agents/plan2.md" | head -20

# Does the provider name match?
# plan2.md says: provider: deepseek
# config.yaml has: custom_providers: [{name: local, ...}] (no "deepseek" entry)
```

**Fix:**
```bash
# Replace all provider references in agent file
sed -i 's|provider: deepseek|provider: custom:local|g' "$HERMES_HOME/agents/plan2.md"
sed -i 's|provider="deepseek"|provider="custom:local"|g' "$HERMES_HOME/agents/plan2.md"
```

**Key insight:** The model name (`deepseek-v4-pro`) may be valid (routed through LiteLLM to DeepSeek API), but the PROVIDER name must match a configured provider in config.yaml. `deepseek` as a standalone provider only exists if explicitly added to `custom_providers` or `providers` in config.yaml.

**Scope (this session):** 16 replacements in plan2.md. Also added `kimi` as a custom provider in config.yaml (was missing — `provider: custom:kimi` in agent file had no matching config entry).

### Layer 3: Service Health

**Symptom:** Pre-Flight Gate `contracts` check fails. All services return exit code 7 (connection refused) or 22 (HTTP error).

**Diagnostic:**
```bash
python3 "$HERMES_HOME/scripts/orchestrator_gate.py" --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for c in d['checks']:
    if not c['passed']:
        print(f'FAIL: {c[\"name\"]}')
        print(c.get('detail','')[:200])
"
```

**Common service issues:**

| Service | Port | How to start | Common failure |
|---------|------|-------------|----------------|
| Neo4j | 7474/7687 | `docker start neo4j` | Container exited (OOM or manual stop) |
| LiteLLM | 4000 | Native: `source ~/litellm_venv/bin/activate && litellm --config ~/dev/llama/litellm-config.yaml --port 4000` | Docker exit 137 (OOM). Use native venv on ARM64. |
| Hermes API | 18649 | `hermes gateway run` | Was on :8643 in old configs — port changed |
| Voice proxy | 8647 | `python3 voice_proxy.py` | Optional — should not block pipeline |
| llama-servers | 8101-8103 | Pre-existing processes | If down, LiteLLM has no backends |

**LiteLLM auth:** LiteLLM with `api_key: sk-local` requires auth header on health checks:
```bash
# Wrong (returns 401):
curl -sf http://localhost:4000/health

# Correct:
curl -sf -H "Authorization: Bearer sk-local" http://localhost:4000/health
```

### Layer 4: Gate Script Accuracy

**Symptom:** Gate passes services that are up but fails on specific checks. Gate script has stale assumptions.

**Common gate script bugs (orchestrator_gate.py):**

| Bug | Symptom | Fix |
|-----|---------|-----|
| Stale port | Checks :8643 for Hermes API, actual port is :18649 | Update endpoint URL |
| Missing auth | LiteLLM health check returns 401 | Add `-H "Authorization: Bearer sk-local"` |
| `expanduser("~")` | Python resolves to `$HERMES_HOME/home/` not real home | Use `os.environ.get("HERMES_HOME")` |
| Optional service as blocker | Voice proxy down blocks entire pipeline | Mark as optional (WARN not FAIL) |

### Layer 5: Research Gate Artifacts

**Symptom:** `research_deep` check fails — GATE B/C/D return 0 scores.

**Root cause:** Gates expect structured `.json` artifacts (schema `research-output-v1.json`), but existing research files are `.md` only. This is expected if Phase 3 hasn't run with the structured output pipeline yet.

**Fix:** This is a process issue, not a code bug. Either:
- Run Phase 3 to generate `.json` artifacts (correct long-term fix)
- Skip `research_deep` check for legacy `.md`-only artifacts (acceptable for pre-existing research)

## Summary of Fixes Applied (2026-07-14)

| # | Problem | Files modified | Replacements |
|---|---------|----------------|-------------|
| 1 | `~/.hermes/` → `$HERMES_HOME/` | plan2.md, all_gates.yaml, orchestrator_gate.py | 38 + 7 + 1 |
| 2 | `provider: deepseek` → `custom:local` | plan2.md | 16 |
| 3 | Added `kimi` custom provider | config.yaml | +8 lines |
| 4 | Hermes API port 8643 → 18649 | orchestrator_gate.py | 1 |
| 5 | LiteLLM health check auth | orchestrator_gate.py | 1 |
| 6 | Voice proxy: BLOCKER → optional | orchestrator_gate.py | logic change |
| 7 | `expanduser("~")` → `HERMES_HOME` env | orchestrator_gate.py | 1 |
| 8 | Started Neo4j + LiteLLM | infrastructure | 2 services |

**Result:** Pre-Flight Gate went from 3/7 → 5/7 passing. Remaining 2 failures (observers, research_deep) are expected to resolve during actual plan2 cycle execution.
