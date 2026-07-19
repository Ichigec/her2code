# Model Not in Menu / Agent Not Picking Up Local Model — Diagnostic

When a local model doesn't appear in `/model` menu or an agent preset fails
to use a local model, check all three layers of model name resolution.

## The Three Layers

```
config.yaml (providers.local.models)   ← what Hermes shows in /model menu
        ↓ must match
LiteLLM proxy (:4000) model list       ← what LiteLLM serves
        ↓ must match
llama-server (--alias) on :810x        ← what the actual backend responds to
```

A model must be present and consistently named in ALL THREE layers.

## Diagnostic Checklist

### Layer 1: llama-server (direct ports)

```bash
# Each model runs on its own port with --alias
ps aux | grep llama-server | grep -v grep
# Shows: --alias nex-n2-mini --port 8101, --alias agents-a1 --port 8102, etc.

# Verify each port responds and what model name it reports:
curl -s http://localhost:8101/v1/models | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"
curl -s http://localhost:8102/v1/models | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"
curl -s http://localhost:8103/v1/models | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"
```

The `id` field is the model name the llama-server reports. This is set by `--alias`.

### Layer 2: LiteLLM proxy (:4000)

```bash
# LiteLLM may rename or map models differently than the direct ports
curl -s -H "Authorization: Bearer *** http://localhost:4000/v1/models \
  | python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"
```

Key: LiteLLM model IDs may differ from llama-server aliases. E.g.:
- llama-server alias: `agents-a1`
- LiteLLM model ID: `qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-quality`

This mismatch is a common cause of "model not found" errors.

### Layer 3: config.yaml providers section

```bash
grep -A30 '^providers:' ~/.hermes/config.yaml
```

The `models:` list under `providers.local` determines what appears in the
`/model` menu. If a model name is NOT here, it won't show up — even if
LiteLLM and llama-server serve it correctly.

### Layer 4: Agent files (for preset routing issues)

```bash
# Check what model/provider the agent preset declares
grep -E '^(model|provider):' ~/.hermes/agents/AGENT_NAME.md

# Check registry.json for delegation routing
python3 -c "
import json
with open('$HOME/.hermes/agents/registry.json') as f:
    reg = json.load(f)
for name, cfg in reg.get('agents', {}).items():
    m, p = cfg.get('model',''), cfg.get('provider','')
    if 'local' in p or 'local' in m:
        print(f'{name}: model={m} provider={p}')
"
```

## Layer 5: Network/Firewall (Docker→Host Connectivity)

A model can appear in ALL three layers above AND in the `/v1/models` listing,
yet still fail when you actually use it. The `/v1/models` endpoint returns
LiteLLM's static config — it does NOT verify backend reachability. Only
`/v1/chat/completions` makes a real connection to the backend.

**Symptom**: `litellm.InternalServerError: Connection error` when sending a
chat completion, even though `GET /v1/models` lists the model.

**Diagnostic — test actual chat completion through LiteLLM:**
```bash
curl -s -H "Authorization: Bearer KEY" -H "Content-Type: application/json" \
  -d '{"model":"MODEL_NAME","messages":[{"role":"user","content":"hi"}],"max_tokens":10}' \
  http://localhost:4000/v1/chat/completions
# Connection error = Docker can't reach llama-server on host
```

**Diagnostic — test port reachability from inside the container:**
```bash
docker exec litellm python3 -c "
import socket
s = socket.socket(); s.settimeout(3)
ip = socket.gethostbyname('host.docker.internal')
r = s.connect_ex((ip, 8102))  # 8101=nex, 8102=agents-a1, 8103=world
print(f'{ip}:8102 -> {\"OPEN\" if r == 0 else \"CLOSED\"} (errno {r})')
s.close()
"
```

**Fix**: Allow Docker bridge subnet → host ports in the firewall:
```bash
sudo iptables -I INPUT 1 -s 172.17.0.0/16 -p tcp --dport 8101:8103 -j ACCEPT
```

⚠️ Rules don't survive reboot. The `start-llama.sh` script has `inject_ufw_rules()`
but it requires passwordless sudo and uses the `ufw-user-input` chain (not `INPUT`).
If sudo was unavailable at launch time, the rules were silently skipped.

See `references/local-llama-server-provider.md` → "Docker→Host Firewall (UFW)" for details.

## Common Failure Modes

### 0. Model listed but Connection error (network/firewall)
Model appears in `/model` menu and `/v1/models` but fails on chat completion
with `Connection error`. Root cause: Docker container cannot reach llama-server
on host ports 8101-8103 due to iptables/UFW blocking the docker bridge subnet.
See Layer 5 above.

### 1. Model in config.yaml but not in LiteLLM
Model appears in `/model` menu but errors when selected. Fix: add model
mapping to LiteLLM config.

### 2. Model in LiteLLM but not in config.yaml
Model works if you type the full name but doesn't appear in menu. Fix: add
model name to `providers.local.models` list in config.yaml.

### 3. Agent file uses a name that exists nowhere
Agent frontmatter or body references `agents-a1-abliterated` but no layer
has that name. Fix: use the actual name from config.yaml/LiteLLM, or add
an alias in LiteLLM mapping the friendly name to the real backend.

### 4. Sub-provider invented in agent file
Agent file says `provider: custom:local:nex` but only `custom:local` exists.
Sub-providers per port are NOT auto-created from a single `providers.local`
entry. Fix: either add separate providers (one per port) or change agent to
use `custom:local` with the correct model name.

### 5. Frontmatter vs registry.json disagreement
Frontmatter says `provider: local`, registry.json says `provider: custom:local`.
Session-level model uses frontmatter; delegate_task routing uses registry.json.
Fix: align both to the same format.

### 6. delegate_task body blocks reference stale cloud models (20260710)
Agent `.md` body contains Python `delegate_task(model="deepseek-v4-pro", provider="deepseek")`
code blocks. These are PROMPT INSTRUCTIONS — the orchestrator LLM reads them and passes
the model/provider to every `delegate_task()` call. A "fully local" plan with 15-25 cloud
references silently routes all delegations to cloud APIs.

**Two syntax variants to check:**
```python
# equals syntax (delegate_task kwargs)
model="deepseek-v4-pro", provider="deepseek"

# colon syntax (dict in tasks=[] batch)
model: "deepseek-v4-pro", provider: "deepseek"
```

**Fix:** Use `patch` with `replace_all=true` per variant:
```
patch(path, old='model="deepseek-v4-pro", provider="deepseek"',
      new='model="agents-a1-abliterated", provider="custom:local"',
      replace_all=True)
```

Run the automated checker: `scripts/verify-agent-model-consistency.py --agent NAME --expect-local`

## Fix: Adding a model alias to make it appear in menu

If you want `agents-a1` to appear in the menu but it's currently listed
under a long name:

```yaml
# config.yaml
providers:
  local:
    models:
    - nex-n2-mini
    - agents-a1              # ← add the friendly alias
    - agentworld
    # ... existing entries remain
```

Then ensure LiteLLM maps `agents-a1` to the correct backend port:
```yaml
# LiteLLM config.yaml
- model_name: agents-a1
  litellm_params:
    model: openai/agents-a1
    api_base: http://host.docker.internal:8102/v1
    api_key: sk-local
```
