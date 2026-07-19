# Hermes Port Architecture (verified 2026-07-15)

Definitive map of what listens where on a running Hermes system. Verified via
`ss -tlnp`, `/proc/<pid>/{cmdline,environ,cwd}`, PPID chains, and systemd units.

## Port Map

| Port | Bind | Process | Component | HERMES_HOME | Purpose |
|------|------|---------|-----------|-------------|---------|
| **8643** | `0.0.0.0` | systemd `hermes-gateway.service` | **Native Gateway** | `~/.hermes-native-gateway` | External API for bots (Telegram, Discord, WhatsApp). SSH-tunneled to VPS (`<YOUR_VPS_IP>:8643`). OpenAI-compatible HTTP + SSE. |
| **9120** | `127.0.0.1` | `hermes` (child of Electron) | **Desktop Agent** | `~/.hermes` | Local HTTP backend for the Electron desktop app. This is where plan2/plan3 presets run. Dynamic port (base 9119 + offset). |
| **9121** | `127.0.0.1` | (transient) | Secondary desktop agent | `~/.hermes` | Parallel session or subagent from desktop. Ephemeral — comes and goes. |
| **9123** | `127.0.0.1` | Docker container (s6) | **Dashboard** | `/opt/hermes` (container) | `hermes dashboard --host 127.0.0.1 --port 9123`. Separate venv (Python 3.13). Web UI for monitoring. |
| **4000** | `0.0.0.0` | LiteLLM proxy | **Model Proxy** | N/A | Routes model names to backends. Local: `:8101` (agents-a1-abliterated), `:8102` (nex-n2-mini/reasoning), `:8103` (agentworld/simulation). External: deepseek-v4-pro, glm-5.2, gpt-4.1. API key: `sk-local`. |
| **7474** | `127.0.0.1` | Neo4j | **Neo4j HTTP** | N/A | Cypher queries via REST API. User: `neo4j`, pass: `changeme`. |
| **7687** | `127.0.0.1` | Neo4j | **Neo4j Bolt** | N/A | Binary protocol for MCP servers and Python drivers. |
| **8647** | varies | Voice proxy | **Voice Proxy** | N/A | STT/TTS relay. Optional — gate marks as WARNING when down. |
| **18649** | NOT LISTENING | (configured but inactive) | API_SERVER (env var) | `~/.hermes` | `API_SERVER_PORT=18649` is in the desktop process env but no listener. Historical artifact from portable Docker deploy. Do NOT use for health checks. |

## Component Relationships

```
┌──────────────────────────────────────────────────────────────┐
│  Desktop GUI (Electron)                                      │
│    ├── :9120 → Desktop Agent (THIS Hermes, presets run here) │
│    ├── :9123 → Dashboard (Docker, monitoring only)           │
│    └── ObserverPanel toggle → config.yaml observer.enabled   │
│                                                               │
│  :8643 → Native Gateway (bots: Telegram/Discord)             │
│           SSH tunnel → http://<YOUR_VPS_IP>:8643              │
│                                                               │
│  :4000 → LiteLLM → :8101 agents-a1-abliterated (0.2s)        │
│                    :8102 nex-n2-mini (reasoning)              │
│                    :8103 agentworld (simulation)              │
│                    External: deepseek-v4-pro, glm-5.2         │
│                                                               │
│  :7474/:7687 → Neo4j (27K+ entities, codebase graph)         │
└──────────────────────────────────────────────────────────────┘
```

## Key Distinctions

### Gateway (:8643) vs Desktop Agent (:9120) vs Dashboard (:9123)

- **Gateway** = external-facing API. Bots, mobile clients, SSH tunnels connect here.
  Has its OWN `HERMES_HOME` (`~/.hermes-native-gateway`) with separate config, state.db,
  and channel directory. Runs as systemd user service.
- **Desktop Agent** = the local session you interact with in the Electron GUI.
  Uses `~/.hermes` as HERMES_HOME. This is where `/agent plan2` runs.
- **Dashboard** = a separate Docker-containerized Hermes instance for web monitoring.
  Has its own venv at `/opt/hermes/.venv`. The `--skip-build` flag means its web frontend
  may not be built (returns raw JSON or 404 for some routes).

### "Frontend not built" on :9120/:9121

The Desktop Agent has an optional web-SPA (React) served alongside the JSON-RPC API.
If `npm run build` wasn't run in the web directory, HTTP requests get:
`{"error":"Frontend not built. Run: cd web && npm run build"}`

This does NOT affect Electron — the Electron app uses its own renderer (not the web SPA).
It only matters if you want to use the agent's chat from a browser tab.

### LiteLLM Health Check

LiteLLM's `/health` endpoint hangs indefinitely (known issue). Use `/v1/models` instead:
```bash
curl -sf http://localhost:4000/v1/models -H "Authorization: Bearer *** > /dev/null && echo "OK"
```

## MCP Server Registration

MCP servers are configured in `config.yaml → mcp_servers`. Currently registered:

| Server | Script | Tools |
|--------|--------|-------|
| `codebase-graph` | `~/cursor/first/graph_tool/mcp/codebase-server.mjs` | `codebase_search`, `codebase_traverse`, `codebase_impact_analysis`, `codebase_entry_points`, `codebase_stats` |
| `education-graph` | `~/cursor/first/graph_tool/mcp/education-server.mjs` | Education graph search/traverse |

Test before registering:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | \
  NEO4J_URI="bolt://127.0.0.1:7687" NEO4J_USER="neo4j" NEO4J_PASSWORD=changeme \
  timeout 10 node ~/cursor/first/graph_tool/mcp/codebase-server.mjs
```

Register via Python (preserves YAML formatting):
```python
import yaml
with open(config_path) as f:
    cfg = yaml.safe_load(f)
cfg.setdefault("mcp_servers", {})["codebase-graph"] = {
    "command": "node",
    "args": ["/home/user/cursor/first/graph_tool/mcp/codebase-server.mjs"],
    "enabled": True,
    "env": {"NEO4J_URI": "bolt://127.0.0.1:7687", "NEO4J_USER": "neo4j", "NEO4J_PASSWORD": "changeme"}
}
with open(config_path, "w") as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
```

## Model Availability (verified 2026-07-15)

```bash
curl -s http://localhost:4000/v1/models -H 'Authorization: Bearer *** | python3 -c "
import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data']]
"
```

Available: `agents-a1-abliterated`, `nex-n2-mini`, `qwen3.6-35b`, `agentworld`,
`deepseek-v4-pro`, `deepseek-chat`, `deepseek-reasoner`, `deepseek-v4-flash`,
`glm-5.2`, `gpt-4.1`, `gpt-4.1-mini`, `diffusiongemma-abliterated`,
`huihui-nex-n2-mini-abliterated-apex-quality`, `superqwen-apex-i-quality-v3`,
`qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-quality`.

**NOT available** (common stale references): `kimi-k2.7-code`, `kimi-coding`,
any model not in the list above.
