---
name: hermes-api-troubleshooting
description: Diagnose Hermes provider/API issues — HTTP errors, rate limits, auth, endpoint mismatches.
version: 1.0.0
---

# Hermes API Troubleshooting

Systematic diagnosis when a provider/model stops working in Hermes. Follow this
pipeline before touching config files — most failures are transient or on the
provider side.

## Diagnostic Pipeline

### 0. Multi-instance topology check (DO THIS FIRST for "unknown agent" / "model not in picker")

When the user reports "unknown agent" after `/agent <name>`, or a model is
missing from the `/model` picker, the cause may be that **Electron is connected
to a DIFFERENT Hermes instance** than the one you're debugging. This wastes
hours if you patch code/config that the running instance never sees.

**Step-by-step — run ALL of these before touching code:**

```bash
# 1. Where does Electron actually connect?
cat ~/.config/Hermes/connection.json   # or ~/.hermes/home/.config/Hermes/connection.json
# Look for: remote.url → which port? :9120 (local) vs :9123 (Docker)?

# 2. Which process serves that port?
ss -tlnp | grep -E '9120|9123|9122|18648|18649'

# 3. What HERMES_HOME does that process use?
cat /proc/<PID>/environ | tr '\0' '\n' | grep HERMES_HOME
# Local:  HERMES_HOME=/home/user/.hermes
# Docker: HERMES_HOME=/opt/data (= a host volume mount, e.g. ~/.hermes-portable-dash)

# 4. If Docker, check the container's actual volume mount:
docker inspect <container_id> --format '{{range .Mounts}}{{.Source}} → {{.Destination}}{{println}}{{end}}'

# 5. Does that HERMES_HOME have agents/?
ls <HERMES_HOME>/agents/*.md 2>/dev/null | wc -l
# If 0 → agents are invisible to this instance → "unknown agent"

# 6. Does that HERMES_HOME's config.yaml have the model you expect?
python3 -c "import yaml; c=yaml.safe_load(open('<HERMES_HOME>/config.yaml')); print(c.get('model')); print([k for k in c.get('providers',{}).keys()])"
```

**Key insight — code isolation:** Docker containers run code baked into the
image at `/opt/hermes/`, NOT the host's `~/.hermes/hermes-agent/`. Patches to
the local codebase are invisible to Docker. To verify:
```bash
docker exec <container_id> grep -c 'provider' /opt/hermes/agent/agents.py
# Compare with local:
grep -c 'provider' ~/.hermes/hermes-agent/agent/agents.py
```
If counts differ → Docker has unpatched code. You must rebuild the image or
apply patches inside the container (lost on restart).

See `hermes-docker-deploy` skill → `references/multi-instance-topology-debug.md`
for a full session example.

### 1. Check logs FIRST

```bash
# Rate limits, auth errors, timeouts
grep -i "error\|429\|401\|403\|500\|timeout" ~/.hermes/logs/errors.log | tail -30

# Full request lifecycle (base_url, model, retries)
grep -i "provider=\|base_url=\|HTTP [45]" ~/.hermes/logs/agent.log | tail -30
```

The log line format is:
```
ERROR [...] agent.conversation_loop: API call failed after N retries. HTTP 429: <msg> | provider=zai model=glm-5.2 msgs=N tokens=~N
```

Key fields: `error_type`, `base_url`, `model`, `tokens` (growing tokens = snowball).

### 2. Verify provider resolution

```bash
# Check what base_url Hermes actually uses (from agent.log, NOT config)
grep "OpenAI client created" ~/.hermes/logs/agent.log | tail -5
```

Compare with the provider profile:
```bash
cat ~/.hermes/hermes-agent/plugins/model-providers/<name>/__init__.py
```

### 3. Test API directly

```bash
KEY=$(grep "^GLM_API_KEY=*** ~/.hermes/.env | cut -d= -f2-)
python3 - "$KEY" << 'PYEOF'
import json, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

key = sys.argv[1]
url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
payload = {"model": "glm-5.2", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}

data = json.dumps(payload).encode()
req = Request(url, data=data, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
try:
    resp = urlopen(req, timeout=15)
    body = json.loads(resp.read())
    print(f"HTTP {resp.status} tokens={body.get('usage',{}).get('total_tokens','?')}")
except HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()[:300]}")
PYEOF
```

## Pitfalls

### Secret redaction corrupts inline Python

`security.redact_secrets: true` scrubs API keys from terminal output, but it
also corrupts **inline Python code** in terminal commands and `write_file`.
Patterns like `if line.startswith("GLM_API_KEY=*** break because `***` replaces the actual key
value, creating unterminated string literals or syntax errors.

**DO NOT** write API keys inline in Python strings within terminal commands or
`write_file` calls. Instead:

```bash
# ✅ Pass key via shell variable
KEY=$(grep "^GLM_API_KEY=*** ~/.hermes/.env | cut -d= -f2-)
python3 - "$KEY" << 'PYEOF'
import sys
key = sys.argv[1]
# ... use key
PYEOF

# ✅ Use source + environ
source ~/.hermes/.env 2>/dev/null
python3 -c "import os; key = os.environ['GLM_API_KEY']; ..."
```

For `write_file`, write the script first, verify it's clean, then run separately.

### Rate limit snowball with heavy presets

When a provider returns HTTP 429 and Hermes retries with exponential backoff
(2s → 4s → 6s), the conversation context **grows** between retries because
failed attempts + tool output accumulate. With heavy presets (Plan2 = ~16K
system tokens), this creates a snowball: each retry is bigger → more likely to
get 429 again.

**Symptoms**: `tokens=~6,000` → `tokens=~17,000` across retries, all failing.

**Mitigation**:
- Don't use heavy presets for test messages
- If rate-limited, wait (it's usually transient)
- Hermes auto-switches to a fallback model after exhausting retries

### GLM_BASE_URL override works (confirmed)

Despite the zai provider only declaring `env_vars=("GLM_API_KEY", ...)` in its
profile, Hermes DOES pick up `GLM_BASE_URL` from `.env`. Verified in logs:
`base_url=https://api.z.ai/api/coding/paas/v4` (user override) vs
`base_url=https://api.z.ai/api/paas/v4` (provider default).

## Diffusion Model Timeout Diagnosis

When a diffusion model (DiffusionGemma, dLLM) appears to hang or timeout, the
root cause is fundamentally different from standard AR model issues. Diffusion
models generate tokens in parallel canvas blocks (256 tokens × 48 denoising
steps), and thinking mode adds HIDDEN reasoning tokens that inflate latency.

**Diagnostic pipeline → `references/diffusion-timeout-case-study.md`**
— full 5-step pipeline: timeline reconstruction, vLLM log analysis, gateway stability
check, LiteLLM bypass detection, root cause identification. With real case study
(session 20260714_224339_0e8a46: 350s delay caused by thinking mode + 15K system prompt).

**Quick check:** If `enable_thinking: true` + heavy system prompt → disable thinking
first before deeper investigation. This single change resolves ~60% of timeout cases.

### Registry model routing mismatch — models exist in config but NOT in LiteLLM

When an agent file or registry.json references a model that isn't registered in
the serving layer, sub-agent delegation fails with HTTP 400: `Invalid model name
passed in model=X`. This commonly happens after forking a plan preset (e.g.,
plan2 → plan3) — frontmatter copies model names that the new environment doesn't
have.

**Diagnostic:**
```bash
# What models does LiteLLM actually serve?
curl -s http://localhost:4000/v1/models \
  -H 'Authorization: Bearer sk-local' | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"

# Cross-check: does every model in registry.json exist in LiteLLM?
python3 -c "
import json
reg = json.load(open('$HOME/.hermes/agents/registry.json'))
# paste or fetch the LiteLLM model list
available = {'nex-n2-mini','agents-a1-abliterated','agentworld','deepseek-v4-pro','glm-5.2'}  # ← update
for name, a in reg['agents'].items():
    if a.get('model') and a['model'] not in available:
        print(f'MISSING: {name:30s} → {a[\"model\"]}')
"
```

**Common pattern:** `kimi-k2.7-code` referenced after plan2→plan3 fork, but Kimi
provider was removed from config.yaml. Replace with available models
(`deepseek-v4-pro`, `agents-a1-abliterated`, `nex-n2-mini`, `glm-5.2`).

### Hermes API port mismatch — orchestrator_gate checks wrong port

When `orchestrator_gate.py` (Phase 5.5 Pre-Flight Gate) or other health-check
scripts fail with `Hermes API unreachable`, check: they likely probe the **wrong
port**.

**Diagnostic — find the real API port:**
```bash
# Hermes Gateway serves the API on one of these:
curl -s http://localhost:8643/health     # → {"status":"ok","platform":"hermes-agent"}
curl -s http://localhost:9123/health     # → HTML dashboard (not a health endpoint)
curl -s http://localhost:9120/health     # → {"error":"Frontend not built"}
```

**Common mismatches resolved:**
| Script | Checks | Real port | Fix |
|--------|--------|-----------|-----|
| `orchestrator_gate.py:63` | `:18649/health` | `:8643/health` | Replace `18649` → `8643` |
| `orchestrator_gate.py:65` | `http://localhost:4000/health` | `/v1/models` | Replace `/health` → `/v1/models` |

LiteLLM `/health` endpoint **hangs/times out** — use `/v1/models` with auth header instead.

### capability_gate.py JSON serialization crash

`capability_gate.py` crashes on `--json` with:
```
TypeError: Object of type Severity is not JSON serializable
```
**Root cause:** The script calls `json.dumps()` without a custom encoder, but
the output dict contains `Severity` enum objects (line ~830).

**Fix:** Add a custom encoder class and pass `cls=_CapabilityEncoder` to both
`json.dumps()` calls:
```python
class _CapabilityEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        return str(obj)
```

### Agent file path mismatch — `agents/dev/` vs `agents/`

Plan presets reference agent files at `$HERMES_HOME/agents/dev/dev-skeptic.md` etc.,
but the `agents/dev/` subdirectory is **empty**. The actual files live at the parent
level (`$HERMES_HOME/agents/dev-skeptic.md`). This causes `read_file()` failures
when the orchestrator tries to load Dev Skeptic/Dev Pragmatic/Dev Creative/Dev
Maverick instructions. The fix is to copy the dev agent files into `agents/dev/`
or update all preset paths.

## Verification

After diagnosis, confirm with a quick smoke test:
```bash
# Small payload → should return 200
python3 /tmp/test_glm.py

# Full Pre-Flight Gate
python3 $HERMES_HOME/scripts/orchestrator_gate.py --json 2>&1 | python3 -m json.tool | grep passed

# Capability Gate
python3 $HERMES_HOME/scripts/capability_gate.py --task "test" --json 2>&1 | head -5
```
