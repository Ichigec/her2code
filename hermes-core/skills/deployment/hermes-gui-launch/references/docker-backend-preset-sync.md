# Docker Backend Preset Sync

> When agent presets fail in the Electron GUI, the Docker dashboard backend
> is out of sync with local code/config/agents. This reference covers the full
> diagnostic, fix procedure, and the 5 code patches needed inside the container.

## Architecture: Two Independent Hermes Instances

```
Electron GUI
  └─ connection.json → localhost:9123 (Docker hermes-dashboard)
       └─ Code:    /opt/hermes/ (image-baked, NOT ~/.hermes/hermes-agent/)
       └─ Config:  /opt/data/config.yaml (volume: ~/.hermes-portable-dash/config.yaml)
       └─ Agents:  /opt/data/agents/ (volume: ~/.hermes-portable-dash/agents/)
       └─ HERMES_HOME=/opt/data

Local Hermes (used by CLI, TUI, this agent session — NOT by GUI)
  └─ Code:    ~/.hermes/hermes-agent/ (+7 carried patches)
  └─ Config:  ~/.hermes/config.yaml
  └─ Agents:  ~/.hermes/agents/
  └─ HERMES_HOME=~/.hermes
```

**Critical implication:** Patching `~/.hermes/hermes-agent/agent/agents.py` fixes
the CLI and local sessions but has ZERO effect on the Docker dashboard that the
GUI actually connects to. The Docker container has its own copy at
`/opt/hermes/agent/agents.py`.

## 5 Root Causes When Presets Fail

| # | Cause | Check |
|---|-------|-------|
| 1 | Docker volume missing `agents/` dir | `ls ~/.hermes-portable-dash/agents/*.md` → 0 = missing |
| 2 | Docker config points to dead port | `docker exec hermes-dashboard cat /opt/data/config.yaml` |
| 3 | Docker config missing API key | Config has `key_env: SOME_VAR` but `.env` doesn't set it |
| 4 | Docker code unpatched (no `provider` field) | `docker exec hermes-dashboard grep -c provider /opt/hermes/agent/agents.py` |
| 5 | Docker can't reach LLM backend | `docker exec hermes-dashboard curl -s http://localhost:4000/v1/models` |

## Fix Procedure

### Step 1: Copy agents to Docker volume

```bash
cp -r ~/.hermes/agents ~/.hermes-portable-dash/agents
ls ~/.hermes-portable-dash/agents/*.md | wc -l  # verify count matches
```

### Step 2: Update Docker config.yaml

The Docker volume config is at `~/.hermes-portable-dash/config.yaml`.
Key changes vs the typical stale config:

| Field | Stale (wrong) | Correct |
|-------|---------------|---------|
| `model.provider` | `custom:llama-local` | `custom:local` |
| `model.default` | `qwen3.6-35b-heretic` | `agents-a1-abliterated` |
| `custom_providers[0].name` | `llama-local` | `local` |
| `custom_providers[0].base_url` | `http://localhost:8092/v1` (dead) | `http://localhost:4000/v1` (LiteLLM) |
| `custom_providers[0].api_key` | missing or `key_env: LLAMA_CPP_API_KEY` (unset) | `sk-local` (inline) |

Template for the model/provider section:

```yaml
model:
  provider: custom:local
  default: agents-a1-abliterated
  context_length: 262144

custom_providers:
  - name: local
    base_url: http://localhost:4000/v1
    api_mode: chat_completions
    api_key: sk-local
    models:
      agents-a1-abliterated:
        context_length: 262144
      nex-n2-mini:
        context_length: 262144
      agentworld:
        context_length: 262144
      qwen3.6-35b-heretic:
        context_length: 262144
```

**Important:** Use `api_key:` (inline) NOT `key_env:` when the env var is not set
in the container's `.env`. The container `.env` at `/opt/data/.env` typically only
has `HERMES_DASHBOARD_SESSION_TOKEN` — no LLM API keys.

### Step 3: Apply 5 code patches in Docker container

These patches add `provider` field support to `AgentDef` so that
`provider: custom:local` in agent `.md` frontmatter is parsed and applied.
Without these, the provider is silently dropped and `switch_model()` fails
with `TypeError: missing required positional argument 'new_provider'`.

```bash
# Patch 1: Add provider field to AgentDef class
docker exec hermes-dashboard sed -i \
  's/    model: Optional\[str\] = None/    model: Optional[str] = None\n    provider: Optional[str] = None/' \
  /opt/hermes/agent/agents.py

# Patch 2: Add "provider" to _FRONTMATTER_FIELDS whitelist
docker exec hermes-dashboard sed -i \
  's/"reasoning", "toolsets", "tools", "permission", "prompt", "system_prompt",/"reasoning", "toolsets", "tools", "permission", "prompt", "system_prompt", "provider",/' \
  /opt/hermes/agent/agents.py

# Patch 3: Read provider in _coerce_agent_def
docker exec hermes-dashboard sed -i \
  's/        permission=data.get("permission"),/        provider=(str(data["provider"]) if data.get("provider") else None),\n        permission=data.get("permission"),/' \
  /opt/hermes/agent/agents.py

# Patch 4: Pass new_provider to switch_model in apply_agent
docker exec hermes-dashboard sed -i \
  's/agent_obj.switch_model(new_model=agent_def.model)/agent_obj.switch_model(new_model=agent_def.model, new_provider=agent_def.provider or agent_obj.provider)/' \
  /opt/hermes/agent/agents.py

# Patch 5: Add provider to to_full_dict for desktop config overlay
docker exec hermes-dashboard sed -i \
  's/"temperature": self.temperature,/"provider": self.provider,\n                "temperature": self.temperature,/' \
  /opt/hermes/agent/agents.py
```

**Verify after patching:**
```bash
docker exec hermes-dashboard python3 -c "import agent.agents; print('OK')"
docker exec hermes-dashboard grep -c "provider" /opt/hermes/agent/agents.py
# Should be >= 6 (field, whitelist, coerce, switch_model, to_full_dict, summary)
```

### Step 4: Restart and verify

```bash
docker restart hermes-dashboard
sleep 10  # wait for health check

# Full verification
docker exec hermes-dashboard python3 -c "
from hermes_cli.config import load_config
from agent.agents import load_agents

c = load_config()
m = c.get('model', {})
cp = c.get('custom_providers', [{}])[0]
print(f'Config: provider={m.get(\"provider\")} default={m.get(\"default\")}')
print(f'  base_url={cp.get(\"base_url\")} api_key={\"set\" if cp.get(\"api_key\") else \"MISSING\"}')

a = load_agents()
p3 = a.get('plan3')
print(f'Agents: {len(a)} total')
if p3:
    print(f'plan3: model={p3.model}, provider={p3.provider}')
else:
    print('plan3: NOT FOUND')
"

# Verify Docker can reach LiteLLM
docker exec hermes-dashboard python3 -c "
import urllib.request, json
req = urllib.request.Request('http://localhost:4000/v1/models', headers={'Authorization':'Bearer sk-local'})
d = json.loads(urllib.request.urlopen(req, timeout=3).read())
print(f'LiteLLM: {len(d[\"data\"])} models reachable')
"
```

### Step 5: Verify via WebSocket (end-to-end RPC test)

```python
import json, asyncio, websockets

async def test():
    uri = "ws://localhost:9123/api/ws?token=sk-docker-b"
    async with websockets.connect(uri, open_timeout=5) as ws:
        await ws.recv()  # gateway.ready

        # agents.list
        await ws.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"agents.list","params":{}}))
        data = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        agents = data.get("result",{}).get("agents",[])
        print(f"{len(agents)} agents via RPC")

        # agents.activate plan3 (without session = pending)
        await ws.send(json.dumps({"jsonrpc":"2.0","id":2,"method":"agents.activate","params":{"id":"plan3"}}))
        data2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        r = data2.get("result",{})
        print(f"activate: activated={r.get('activated')} pending={r.get('pending')}")

asyncio.run(test())
```

## Survival: Patches Don't Survive Container Rebuild

These `docker exec sed -i` patches modify the running container's filesystem
layer. They survive `docker restart` but NOT `docker rm` + `docker run` (rebuild
from image).

**Three options for permanent fix:**

1. **Rebuild the Docker image** with patches baked into Dockerfile:
   ```dockerfile
   # In hermes-dashboard Dockerfile:
   RUN sed -i 's/...' /opt/hermes/agent/agents.py
   ```

2. **Mount local code as volume** (development mode):
   ```yaml
   # docker-compose.yml
   volumes:
     - ~/.hermes/hermes-agent/agent:/opt/hermes/agent:ro
   ```
   **Warning:** this couples Docker to local code version — if local code has
   uncommitted changes that break, Docker breaks too.

3. **Sync script** — run after every container rebuild:
   ```bash
   #!/bin/bash
   # docker-sync-patches.sh
   # Run after: docker rm hermes-dashboard && docker compose up -d hermes-dashboard
   docker exec hermes-dashboard sed -i \
     's/    model: Optional\[str\] = None/    model: Optional[str] = None\n    provider: Optional[str] = None/' \
     /opt/hermes/agent/agents.py
   # ... (all 5 patches)
   docker exec hermes-dashboard python3 -c "import agent.agents; print('OK')"
   echo "Patches applied"
   ```

## agent_overrides.json Staleness

After `docker restart hermes-dashboard`, the `agent_overrides.json` in the Docker
volume (`~/.hermes-portable-dash/agent_overrides.json`) may contain stale session
IDs from before the restart. These don't match the new session IDs, so
`agents.activate` for those sessions silently fails to match.

**Fix:** Clean stale overrides after restart:
```bash
echo '{}' > ~/.hermes-portable-dash/agent_overrides.json
```

## Session History

- **2026-07-10:** Full diagnostic + fix. GUI presets were broken because Docker
  dashboard had no `agents/` directory, config pointed to dead port :8092, and
  Docker code lacked the `provider` field patch. Fixed by copying agents,
  updating config to LiteLLM :4000, applying 5 sed patches in container.
