# Multi-Instance Topology Debug — "Unknown Agent" / "Model Not in Picker"

> Session 2026-07-10: Debugging why `/agent plan3` returned "unknown agent" and
> `agents-a1-abliterated` was missing from the model picker, despite both
> existing in `~/.hermes/`.

## Root Cause

Electron desktop connected to **Docker** (:9123), not the **local** Hermes
(:9120). The Docker dashboard container mounted `~/.hermes-portable-dash/` as
`/opt/data`. That volume:

1. Had **no `agents/` directory** → only 8 built-in agents visible → `plan3`
   = "unknown agent"
2. Had a **stale config.yaml** → provider `custom:llama-local` on port `:8092`
   with 4 qwen/heretic models → `agents-a1-abliterated` invisible
3. Ran **code baked into the Docker image** at `/opt/hermes/` → patches applied
   to `~/.hermes/hermes-agent/agent/agents.py` were invisible to Docker

All three layers (agents dir, config, code) must exist in the volume/path that
the **connected instance** actually reads.

## Topology Map (this machine)

```
Electron Desktop (PID 936715)
  └─ connection.json → http://localhost:9123 (Docker dashboard)
       │
       ├─ Docker Dashboard :9123 (PID 942127)
       │    HERMES_HOME=/opt/data
       │    Volume: ~/.hermes-portable-dash → /opt/data
       │    ❌ agents/ MISSING
       │    ❌ config.yaml: llama-local:8092 (stale, wrong provider)
       │    ❌ Code: /opt/hermes/ (unpatched, baked in image)
       │
       ├─ Docker Gateway :18649 (PID 941899)
       │    HERMES_HOME=/opt/data
       │    Volume: ~/.hermes-portable → /opt/data
       │    (separate volume from dashboard by design — see SKILL.md)
       │
       └─ Local Hermes :9120 (PID 936829) ← IGNORED by Electron
            HERMES_HOME=/home/user/.hermes
            ✅ agents/ with 108 agents including plan3
            ✅ config.yaml: local provider via LiteLLM :4000, 8 models
            ✅ Code: ~/.hermes/hermes-agent/ (patched)
```

## Fix

Three things must be synced to the Docker dashboard volume:

### 1. Copy agents/ to dashboard volume

```bash
cp -r ~/.hermes/agents ~/.hermes-portable-dash/agents
```

### 2. Update config.yaml in dashboard volume

Replace `~/.hermes-portable-dash/config.yaml` with the local config that has
the LiteLLM provider and `agents-a1-abliterated`:

```bash
# Copy the working local config (adjust provider/models as needed)
cp ~/.hermes/config.yaml ~/.hermes-portable-dash/config.yaml
```

Or manually ensure the dashboard volume's config has the right provider:

```yaml
model:
  provider: custom:local
  default: agents-a1-abliterated

providers:
  local:
    name: DGX Spark (via LiteLLM :4000)
    base_url: http://localhost:4000/v1
    api_key: sk-local
    models:
      - nex-n2-mini
      - qwen3.6-35b
      - agentworld
      - agents-a1-abliterated
      # ... etc
```

**⚠️ Docker `localhost` = host network:** Since the container uses
`--network host`, `localhost:4000` reaches the host's LiteLLM. No
`host.docker.internal` needed.

### 3. Restart dashboard container

```bash
docker restart hermes-dashboard
```

### 4. (If code patches needed) Rebuild Docker image

Patches to `~/.hermes/hermes-agent/` do NOT propagate to the Docker image.
Options:

- **Rebuild image:** `docker build -t hermes-agent ~/.hermes/hermes-agent/`
- **Hot-patch inside container:** `docker cp file.py hermes-dashboard:/opt/hermes/`
  (lost on `docker rm`, survives `docker restart`)
- **Switch Electron to local Hermes:** change `connection.json` to
  `http://localhost:9120` (where local code patches are active)

## Key Commands Summary

```bash
# Which instance is Electron using?
cat ~/.config/Hermes/connection.json 2>/dev/null || cat ~/.hermes/home/.config/Hermes/connection.json

# Which HERMES_HOME does each running instance use?
for pid in $(pgrep -f 'hermes (dashboard|gateway|gui)'); do
  home=$(cat /proc/$pid/environ 2>/dev/null | tr '\0' '\n' | grep '^HERMES_HOME=' | cut -d= -f2)
  cmd=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ' | cut -c1-80)
  echo "PID=$pid HERMES_HOME=$home CMD=$cmd"
done

# Docker volume mounts
for c in hermes-dashboard hermes-gateway; do
  echo "=== $c ==="
  docker inspect $c --format '{{range .Mounts}}{{.Source}} → {{.Destination}}{{println}}{{end}}' 2>/dev/null
done

# Does a specific instance see the agent?
docker exec hermes-dashboard python3 -c "
from agent.agents import load_agents
agents = load_agents(force=True)
print(f'Agents: {len(list(agents.keys()))}')
print('plan3' in agents)
"
```

## agent_overrides.json — stale session IDs

`agent_overrides.json` maps session IDs to agent names. When Hermes restarts,
old session IDs become stale but the file is not cleaned. Example:

```json
{"20260710_221028_ba1bcd": "plan3", "20260710_210815_c1e9fc": "plan2"}
```

If the override references a session that no longer exists, it can cause
confusion. To clean:

```bash
echo '{}' > ~/.hermes/agent_overrides.json
```

This file exists in EACH volume separately — check both:
- `~/.hermes/agent_overrides.json`
- `~/.hermes-portable-dash/agent_overrides.json`
