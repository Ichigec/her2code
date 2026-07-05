# Hermes Stack — Open-Source Release

> 🧹 Sanitized copy of the full Hermes Agent stack. Ready for GitHub publication.
> All personal data, tokens, keys, and user-specific paths have been replaced with placeholders.

## What's Inside

| Component | Directory | Description |
|-----------|-----------|-------------|
| **Hermes Agent Core** | `hermes-agent/` | AI agent framework (Python): CLI, tools, gateway, plugins, skills, providers |
| **Android Client** | `opencode-android/` | Hermes GUI Android app (Kotlin + Jetpack Compose) |
| **OpenCode+** | `opencode-plus/` | Local LLM infrastructure: LiteLLM proxy, llama.cpp, OpenCode web UI configs |
| **Extensions** | `config/` | Agents, skills, hooks, plugins, scripts, cron templates, Neo4j compose |
| **Education Graph** | `config/mcp/education-graph/` | Neo4j MCP server: knowledge entities, hybrid search, codebase graph |
| **Claw Agent** | `config/claw-agent/` | Claw + Composter agents: discovery, compaction, Neo4j sync |
| **Architecture** | `docs/architecture/` | C4 diagrams, data flows, sequence diagrams, component catalog |

## Quick Start

### Prerequisites
- Linux (x86_64 or ARM64)
- Python 3.11+
- Docker (optional, for Neo4j)

### 1. Install Hermes Agent

```bash
cd hermes-agent
python3 -m venv venv && source venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
# Copy and edit the example config
mkdir -p ~/.hermes
cp config/config.yaml.example ~/.hermes/config.yaml
cp config/.env.example ~/.hermes/.env

# Edit .env — add at least one API key:
#   DEEPSEEK_API_KEY=<your-key>
#   OPENAI_API_KEY=<your-key>
#   ANTHROPIC_API_KEY=<your-key>
```

### 3. Run

```bash
# CLI mode (interactive)
hermes

# Gateway mode (API server + multi-platform)
hermes gateway run

# Docker mode
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d
```

### 4. (Optional) Start Neo4j for Knowledge Graph

```bash
docker compose -f config/compose.neo4j.yml up -d
# Neo4j Browser: http://localhost:7474 (neo4j/changeme)
```

### 5. (Optional) Build Android Client

```bash
cd opencode-android
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

## Architecture

See `docs/architecture/` for detailed diagrams:
- `logical.puml` — C4 Level 2 container diagram (37 components)
- `functional.puml` — Data flow diagrams (chat, voice, MCP, SSE)
- `sequence.puml` — End-to-end sequence: User → Hermes → LLM → Tools
- `COMPONENTS.md` — Full component catalog with ports, technologies, dependencies

## Port Map

| Port | Service | Required |
|------|---------|:--------:|
| 8648 | Hermes API Server | For API clients |
| 7474 | Neo4j HTTP | For graph UI |
| 7687 | Neo4j Bolt | For MCP servers |
| 4000 | LiteLLM proxy | For OpenCode+ |
| 3400 | OpenCode Web UI | Browser access |
| 8647 | Voice proxy | STT/TTS |

## What Was Removed (Sanitization)

See `SANITIZATION_LOG.md` for the complete list. Summary:

| Category | Items | Replacement |
|----------|:-----:|-------------|
| API keys | 7 | `<YOUR_*_KEY>` |
| IP addresses | 6 | `<YOUR_VPS_IP>`, etc. |
| Paths `{HOME}/user/` | ~50 | `/home/user/` |
| Telegram IDs | 4 | `<YOUR_CHAT_ID>`, etc. |
| Phone ID | 1 | `<YOUR_PHONE_ID>` |
| VLESS UUID | 1 | `<YOUR_VLESS_UUID>` |
| Tunnel URLs | 4 | `<YOUR_TUNNEL_URL>` |
| Database contents | 5 DBs | Schema-only |
| Session data | 47 files | Deleted |
| Log files | 15 files | Deleted |
| Personal skill | 1 | `user-environment` removed |
| VPN config | 1 | `sing-box-vpn-setup.md` removed |

## Android App 🚧

Android-приложение для Hermes Agent находится в разработке.
Репозиторий:  (будет добавлен позже).

## License

MIT — see LICENSE file.

## Contributing

This is a sanitized snapshot of a development environment. To contribute:
1. Fork the repository
2. Follow the Quick Start to set up
3. See `AGENTS.md` for project conventions
4. Submit PRs against the main branch
