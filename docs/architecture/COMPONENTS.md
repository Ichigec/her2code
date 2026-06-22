# COMPONENTS.md — Hermes Stack Component Inventory

> **PID:** `SANITIZED_PID`
> **Phase:** 4 — Architecture
> **Author:** Architect Agent (#4)
> **Date:** 2026-06-19
> **Sources:** Research RQ1 (76 findings), System Analysis, Requirements

---

## Overview

The Hermes stack is a full-stack AI agent platform consisting of **37+ deployable components** organized into **5 subsystems**:

| # | Subsystem | Components | Description |
|---|-----------|------------|-------------|
| 1 | **Hermes Agent Core** | 12 | AI agent engine, CLI, gateway, tools, plugins, skills |
| 2 | **Android Client** | 4 | Mobile chat app with voice, SSE streaming |
| 3 | **OpenCode+ (LLM Serving)** | 5 | LLM proxy, local inference, web UI, observability |
| 4 | **MCP Servers** | 4 | Knowledge graph, web search, education, codebase tools |
| 5 | **Infrastructure** | 8 | Neo4j, web UIs, VPN, orchestration |

Additionally: **User Extensions** (8 components under `~/.hermes/`) and **Persistence** (4 databases).

---

## 1. Hermes Agent Core

### 1.1 AIAgent Engine (`run_agent.py`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Central dialog orchestration loop. Manages conversation state, loads skills/agents, dispatches prompts to LLM providers, coordinates tool calling, and emits SSE events. |
| **Technology** | Python 3.12, Rich (terminal formatting), Tenacity (retry logic) |
| **File** | `run_agent.py` (~234 KB) |
| **Ports** | None (internal Python module) |
| **Depends on** | Tool Orchestrator, Provider Adapters, Session DB, Gateway, Skills, Plugins, Memory, Hooks |
| **Key interfaces** | `agent.process(input, session_id, stream) → AsyncGenerator[SSEEvent]` |
| **Startup** | `hermes run` or internally via CLI/Gateway |

### 1.2 Tool Orchestrator (`model_tools.py`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Registry and dispatch system for all tools (file I/O, terminal, browser, web search, MCP servers, memory, skills). Validates tool calls against permission gates before execution. |
| **Technology** | Python, JSON Schema validation |
| **File** | `model_tools.py` (~55 KB) |
| **Ports** | None (Python call, spawns subprocesses for MCP) |
| **Depends on** | All tool implementations (20+ tools), MCP servers (via stdio/HTTP) |
| **Key interfaces** | `resolve_tool(name) → ToolDef`, `execute_tool(name, args) → ToolResult` |

### 1.3 CLI / TUI (`cli.py`, `ui-tui/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Interactive terminal interface with subcommands (`hermes run`, `hermes gateway run`, `hermes config`, etc.). TUI variant uses React (Ink) for rich terminal rendering. |
| **Technology** | Python (CLI: Fire), TypeScript + React/Ink (TUI), JSON-RPC backend |
| **File** | `cli.py` (~739 KB) |
| **Ports** | None (TUI uses internal JSON-RPC) |
| **Depends on** | AIAgent Engine, Gateway, Config |
| **Startup** | `hermes` (CLI) or `hermes tui` |

### 1.4 Session DB (`hermes_state.py`, `state.db`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Persistent storage for all conversation sessions, messages, and memory consolidations. Provides FTS5 full-text search across message history. |
| **Technology** | SQLite 3, FTS5, WAL mode |
| **File** | `state.db` (535 MB in production, ~100 MB schema-only) |
| **Ports** | None (file-based, local access only, 0600 permissions) |
| **Depends on** | None (standalone) |
| **Schema** | `sessions`, `messages`, `memory_consolidations`, FTS virtual tables |
| **Notes** | Production DB contains 498 sessions, 25,052 messages. Must be cleared to schema-only for open-source publication. |

### 1.5 Gateway (`gateway/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Multi-platform messaging gateway. Routes messages between Hermes Agent and external platforms (Telegram, Discord, Slack). Includes the API Server for HTTP-based access. Handles SSE streaming to connected clients. |
| **Technology** | Python, Starlette (SSE), python-telegram-bot, discord.py, slack-sdk |
| **File** | `gateway/` directory |
| **Ports** | `8643` — Hermes Gateway direct (SSE/API) |
| **Depends on** | AIAgent Engine, Session DB, External APIs (Telegram, Discord, Slack) |
| **Startup** | `hermes gateway run` |
| **Security** | API Server key (`API_SERVER_KEY` env var) for external access |

### 1.6 Core Plugins (`plugins/` — 18 built-in)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Modular plugin system for extending agent capabilities. Built-in plugins provide: memory providers (local, remote), model providers, Kanban board management, observability/metrics. |
| **Technology** | Python plugin architecture (fail-open design) |
| **File** | `plugins/` directory (18 subdirectories) |
| **Ports** | None |
| **Depends on** | Plugin framework, external services (per plugin) |
| **Notable** | `memory-providers/`, `model-providers/`, `kanban/`, `observability/` |

### 1.7 Core Skills (`skills/` — 50+ built-in)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Reusable, composable agent capabilities defined as Markdown files. Skills are loaded into the system prompt at runtime based on context triggers. Cover: autonomous AI agents, data science, deployment, git, software development, and more. |
| **Technology** | Markdown, YAML frontmatter, Python loader |
| **File** | `skills/` directory (50+ Markdown files) |
| **Ports** | None |
| **Depends on** | AIAgent Engine (loaded via skill router) |

### 1.8 Provider Adapters (`providers/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Adapter layer that normalizes LLM API calls across providers (OpenAI, Anthropic, DeepSeek, OpenRouter, Kimi/Moonshot, and others). Handles streaming, tool calling format differences, and error retry. |
| **Technology** | Python, openai SDK, httpx |
| **File** | `providers/` directory |
| **Ports** | None (outbound HTTPS to LLM providers; optionally HTTP to LiteLLM :4000 or llama.cpp :8092) |
| **Depends on** | API keys in environment variables (`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, etc.) |
| **Routing** | Direct → Cloud LLM; or via LiteLLM proxy → Cloud/Local LLM |

### 1.9 ACP Adapter (`acp_adapter/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Integration with Agent Communication Protocol (ACP) — enables Hermes Agent to function as a backend for editors: VS Code, Zed, JetBrains. |
| **Technology** | Python, ACP protocol |
| **File** | `acp_adapter/` directory |
| **Ports** | None (editor extension protocol) |
| **Depends on** | AIAgent Engine, editor extensions |

### 1.10 Cron Scheduler (`cron/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Scheduled task execution engine. Runs periodic jobs: knowledge curator (Neo4j integration), daily reminders, Claw graph maintenance. |
| **Technology** | Python, croniter |
| **File** | `cron/` directory, `cron/jobs.json` |
| **Ports** | None |
| **Depends on** | AIAgent Engine, Neo4j (for knowledge curator), Telegram (for delivery) |
| **Configuration** | `jobs.json` defines 4 default jobs with schedules, prompts, and delivery targets |

### 1.11 Docker Support

| Attribute | Value |
|-----------|-------|
| **Purpose** | Containerization of the entire Hermes Agent stack. Multi-stage Dockerfile with s6-overlay for process supervision. |
| **Technology** | Docker, s6-overlay, Docker Compose |
| **File** | `Dockerfile`, `docker-compose.yml` |
| **Ports** | Host network mode (all ports exposed) |
| **Depends on** | All core components, system dependencies (Python 3.11+, ripgrep, ffmpeg, ca-certificates) |
| **Startup** | `HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d` |

### 1.12 TUI Gateway (`tui_gateway/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | JSON-RPC backend for the React/Ink terminal UI. Bridges the TUI frontend with the AIAgent engine. |
| **Technology** | Python JSON-RPC, TypeScript React/Ink frontend |
| **File** | `tui_gateway/` |
| **Ports** | Internal (JSON-RPC over stdio) |
| **Depends on** | AIAgent Engine, TUI frontend |

---

## 2. Android Client (`~/dev/Opencode/`)

### 2.1 Android App (`app/src/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Native Android chat application for Hermes. Features: conversation UI, voice assistant (STT/TTS), real-time SSE streaming, Markdown rendering. |
| **Technology** | Kotlin, Jetpack Compose, Material 3, Hilt DI, Room DB, Retrofit + OkHttp, Moshi JSON, DataStore Preferences, EncryptedSharedPreferences |
| **File** | `app/src/` |
| **Ports** | Outbound: `8648` (API Server), `8643` (SSE Gateway), `8647` (Voice Proxy) |
| **Depends on** | Hermes API Server, Hermes Gateway (SSE), Voice Proxy |
| **Build** | `./gradlew assembleDebug` (Android SDK 26+, build-tools 34.0.0) |
| **Notes** | Requires `local.properties` with `sdk.dir`; `adb reverse` for local network connectivity |

### 2.2 Voice Proxy (`voice_proxy.py`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | HTTP proxy for speech-to-text (STT) and text-to-speech (TTS) conversion. Bridges the Android voice recorder/player with local inference engines. |
| **Technology** | Python, Faster-Whisper (STT), Piper TTS |
| **File** | `voice_proxy.py` |
| **Ports** | `8647` — HTTP API (STT/TTS endpoints) |
| **Depends on** | Faster-Whisper model, Piper TTS model |
| **Startup** | `python3 voice_proxy.py` (or via voice watchdog) |

### 2.3 TCP Proxy (`tcp_proxy.py`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | TCP tunnel for Android-to-Hermes connectivity when devices are on different subnets (e.g., phone on 10.4.x.x, Jetson on 192.168.x.x). Forwards TCP traffic with adb reverse. |
| **Technology** | Python, asyncio |
| **File** | `tcp_proxy.py` |
| **Ports** | Dynamic (forwards to :8648) |
| **Depends on** | ADB, Hermes API Server |

### 2.4 Voice Watchdog (`voice_proxy_watchdog.sh`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Auto-restart script for the voice proxy. Monitors the voice proxy process and restarts it if it crashes. |
| **Technology** | Bash |
| **File** | `voice_proxy_watchdog.sh` |
| **Ports** | None |
| **Depends on** | Voice Proxy |

---

## 3. OpenCode+ LLM Serving (`~/cursor/opencode+/`)

### 3.1 LiteLLM Proxy

| Attribute | Value |
|-----------|-------|
| **Purpose** | Multi-provider LLM proxy with unified API, cost tracking, rate limiting, and failover. Normalizes calls to OpenAI, Anthropic, DeepSeek, and local llama.cpp under a single OpenAI-compatible API. |
| **Technology** | Python, LiteLLM, Docker |
| **File** | `compose.phoenix.yml` (Docker), `configs/profiles/litellm-*.env` |
| **Ports** | `4000` — OpenAI-compatible API |
| **Depends on** | Cloud LLM API keys, Llama.cpp (:8092), Phoenix (:6006) |
| **Startup** | `docker compose -f compose.phoenix.yml up -d` |

### 3.2 Llama.cpp Server

| Attribute | Value |
|-----------|-------|
| **Purpose** | Local LLM inference server. Runs quantized models (Qwen 35B) on NVIDIA Jetson ARM64 with CPU-only inference (ctranslate2 without CUDA on aarch64). |
| **Technology** | C++, llama.cpp, GGUF model format |
| **File** | `start-llama-cpp.sh` |
| **Ports** | `8092` — OpenAI-compatible API |
| **Depends on** | GGUF model files (`~/models/` or `~/.lmstudio/models/`), NVIDIA GPU (optional, CPU fallback) |
| **Startup** | `./start-llama-cpp.sh` |
| **Notes** | Model paths must be configured via `<MODEL_PATH>` environment variable |

### 3.3 OpenCode Web UI

| Attribute | Value |
|-----------|-------|
| **Purpose** | Browser-based agent interface for OpenCode+. Provides a web UI for interacting with agents, viewing traces, and managing configurations. |
| **Technology** | Node.js, systemd service |
| **File** | `opencode_claw/`, `systemd/opencode-plus.service` |
| **Ports** | `3400` — Web UI |
| **Depends on** | LiteLLM Proxy (:4000) for LLM calls |
| **Startup** | `systemctl --user start opencode-plus` or `start-opencode.sh` |

### 3.4 Phoenix Observability

| Attribute | Value |
|-----------|-------|
| **Purpose** | LLM trace observability platform (Arize Phoenix). Collects spans, traces, and metrics from LiteLLM proxy for debugging and performance analysis. |
| **Technology** | Python, Arize Phoenix, Docker |
| **File** | `compose.phoenix.yml` |
| **Ports** | `6006` — Phoenix Dashboard |
| **Depends on** | LiteLLM Proxy (sends traces via gRPC/HTTP) |
| **Startup** | Via `compose.phoenix.yml` |

### 3.5 Start Scripts (`start-*.sh`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Orchestration scripts that start all OpenCode+ services in the correct order: Llama.cpp → LiteLLM → OpenCode Web UI. Handles port waiting, health checks, and graceful shutdown. |
| **Technology** | Bash (9 scripts) |
| **File** | `start-llama-cpp.sh`, `start-litellm.sh`, `start-opencode.sh`, `start-all.sh`, etc. |
| **Ports** | None (process orchestration) |
| **Depends on** | All OpenCode+ services |

---

## 4. MCP Servers (Tool Ecosystem)

### 4.1 Claw-Graph MCP (`claw-neo4j`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | MCP server providing knowledge graph query and traversal tools. Allows the agent to search the Claw knowledge graph in Neo4j for concepts, relationships, and contextual knowledge. |
| **Technology** | Node.js, MCP SDK, Neo4j JavaScript driver |
| **File** | `~/.hermes/plugins/claw-neo4j/mcp-server.mjs` |
| **Ports** | Outbound: `7687` (Neo4j Bolt) |
| **Transport** | stdio (MCP protocol) |
| **Depends on** | Neo4j database, `NEO4J_PASSWORD` env var |
| **Tools** | `graph_search`, `graph_traverse`, `graph_get_node` |

### 4.2 Searchbox MCP

| Attribute | Value |
|-----------|-------|
| **Purpose** | MCP server providing web search across 15+ search engines. Aggregates results from Google, Bing, DuckDuckGo, and specialized engines. Returns structured, deduplicated results. |
| **Technology** | Docker, OpenWebUI Searchbox |
| **Image** | `openwebui-searchbox:local` |
| **Ports** | `8024` — MCP HTTP endpoint |
| **Transport** | HTTP (MCP protocol over HTTP) |
| **Depends on** | Internet access, search engine APIs |
| **Tools** | `web_search`, `news_search`, `image_search` |

### 4.3 Education-Graph MCP

| Attribute | Value |
|-----------|-------|
| **Purpose** | MCP server for educational knowledge graph queries. Provides learning path traversal, concept search, and curriculum navigation from the education graph stored in Neo4j. |
| **Technology** | Python, graph_tool, Neo4j Python driver |
| **File** | `~/cursor/first/graph_tool/python/` |
| **Ports** | Outbound: `7687` (Neo4j Bolt) |
| **Transport** | stdio (MCP protocol) |
| **Depends on** | Neo4j database, `GRAPH_TOOL_DIR`, `PYTHON_BIN` env vars |
| **Tools** | `education_search`, `learning_path`, `concept_explore` |

### 4.4 Codebase-Graph MCP

| Attribute | Value |
|-----------|-------|
| **Purpose** | MCP server for codebase indexing and semantic search. Indexes source code into Neo4j for answering architectural questions, finding implementations, and tracing dependencies. |
| **Technology** | Python, Neo4j driver, AST parsing |
| **File** | `~/.hermes/plugins/codebase-graph/` (if present) |
| **Ports** | Outbound: `7687` (Neo4j Bolt) |
| **Transport** | stdio (MCP protocol) |
| **Depends on** | Neo4j database |
| **Tools** | `codebase_search`, `find_definition`, `trace_dependencies` |

---

## 5. Infrastructure

### 5.1 Neo4j Graph Database

| Attribute | Value |
|-----------|-------|
| **Purpose** | Graph database backbone for the entire stack. Stores: Claw knowledge graph, education graph, codebase index, MCP tool catalog. Powers all graph-based agent tools. |
| **Technology** | Neo4j 5 Community Edition, Docker |
| **File** | `compose.neo4j.yml` |
| **Ports** | `7474` — HTTP (Neo4j Browser), `7687` — Bolt protocol |
| **Credentials** | `neo4j` / `changeme` (default — must change in production) |
| **Startup** | `docker compose -f compose.neo4j.yml up -d` |
| **Depends on** | Docker, 2+ GB RAM |

### 5.2 OpenWebUI

| Attribute | Value |
|-----------|-------|
| **Purpose** | Alternative Web UI with RAG (Retrieval-Augmented Generation) capabilities. Provides a ChatGPT-like interface for interacting with LLMs through the LiteLLM proxy. |
| **Technology** | Docker, OpenWebUI (ghcr.io/open-webui/open-webui:main) |
| **File** | `compose.openwebui.yml` |
| **Ports** | `3000` — Web UI |
| **Depends on** | LiteLLM Proxy (:4000) |
| **Startup** | `docker compose -f compose.openwebui.yml up -d` |

### 5.3 OpenHands

| Attribute | Value |
|-----------|-------|
| **Purpose** | AI agent sandbox environment. Provides isolated containers for running AI-generated code, executing complex multi-step agent tasks, and experimenting safely. |
| **Technology** | Docker, OpenHands (docker.openhands.dev) |
| **File** | `docker-compose.yml` (OpenHands variant) |
| **Ports** | `12000` — OpenHands Web UI |
| **Startup** | `docker compose -f docker-compose.yml up -d` |

### 5.4 Gitea

| Attribute | Value |
|-----------|-------|
| **Purpose** | Self-hosted Git service. Used for private repositories, code sharing, and CI/CD integration within the local development environment. |
| **Technology** | Go binary, SQLite backend |
| **File** | `~/gitea/` (binary + config) |
| **Ports** | `3030` — Web UI + Git HTTP |
| **Credentials** | `user` / `changeme` (default — must change in production) |
| **Notes** | Not core Hermes — excluded from default `her2code/` package per System Analysis recommendation |

### 5.5 Sing-Box VPN

| Attribute | Value |
|-----------|-------|
| **Purpose** | VPN tunnel for secure remote access. Uses VLESS + Reality protocol to expose Hermes API Server through a VPS to the internet without port forwarding. |
| **Technology** | Sing-Box, VLESS, Reality (XTLS), systemd |
| **File** | `sing-box-vpn-setup.md` (documentation, not included in her2code/) |
| **Ports** | Outbound encrypted TCP to VPS |
| **Depends on** | VPS with public IP, sing-box server |
| **Notes** | Contains sensitive VPN secrets — excluded from open-source package |

### 5.6 Docker Compose (Orchestration)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Orchestration layer for the entire Hermes stack. Defines services, networks, volumes, and dependencies between containers. |
| **Technology** | Docker Compose v3+, YAML |
| **Files** | `compose.neo4j.yml`, `compose.openwebui.yml`, `compose.phoenix.yml`, `docker-compose.yml` (hermes-agent) |
| **Ports** | All service ports (see Port Table below) |
| **Depends on** | Docker Engine 24+, docker-compose plugin |

### 5.7 Voice Relay (WebSocket)

| Attribute | Value |
|-----------|-------|
| **Purpose** | OpenAI-compatible WebSocket relay for real-time bidirectional audio streaming between the voice proxy and clients. |
| **Technology** | Python, WebSocket, OpenAI Realtime API compat |
| **Ports** | `8089` — WebSocket endpoint |
| **Depends on** | Voice Proxy (:8647) |

### 5.8 Phoenix Dashboard

| Attribute | Value |
|-----------|-------|
| **Purpose** | UI for Arize Phoenix observability platform. Visualizes LLM traces, spans, token usage, and latency metrics. |
| **Technology** | Python, Arize Phoenix, Docker |
| **Ports** | `6006` — Web dashboard |
| **Depends on** | Phoenix collector (receives traces from LiteLLM) |

---

## 6. User Extensions (`~/.hermes/`)

### 6.1 Agent Definitions (`agents/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Role definitions for specialized agents in the development pipeline: Architect, Developer, Researcher, System Analyst, Security Agent, Tester, Deployment Agent, Tech Lead, Requirements Analyst, Auditor. |
| **Technology** | Markdown (14 `.md` files) |
| **File** | `~/.hermes/agents/` |
| **Depends on** | AIAgent Engine (loaded via agent system) |

### 6.2 User Skills (`skills/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Custom skills extending the agent's capabilities: `user-environment` (hardware specifics), `hermes-distribution`, `software-development/hermes-android-client`, and 21+ others. |
| **Technology** | Markdown with YAML frontmatter (24 directories) |
| **File** | `~/.hermes/skills/` |
| **Depends on** | AIAgent Engine (loaded via skill router) |

### 6.3 User Plugins (`plugins/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Custom plugins: `claw-neo4j` (Neo4j MCP server), `hermes-opencode` (OpenCode permission integration). |
| **Technology** | Node.js (claw-neo4j), Python (hermes-opencode) |
| **File** | `~/.hermes/plugins/` |
| **Depends on** | Neo4j (claw-neo4j), OpenCode+ (hermes-opencode) |

### 6.4 Hooks (`hooks/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Pre/post event hooks that intercept agent operations: workspace enforcement, AGENTS.md injection, skill router toggle, workspace boundary check. |
| **Technology** | Python (7 `.py` files) |
| **File** | `~/.hermes/hooks/` |
| **Depends on** | AIAgent Engine (hook system) |

### 6.5 Scripts (`scripts/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Utility scripts for Claw graph operations: discovery (finding new tools), processing (indexing), audit (quality checks), knowledge curation. |
| **Technology** | Python (7 `.py` files) |
| **File** | `~/.hermes/scripts/` |
| **Depends on** | Neo4j (for graph scripts), AIAgent Engine |

### 6.6 Cron Jobs (`cron/jobs.json`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Job definitions for the cron scheduler. 4 default jobs: knowledge curator (Neo4j sync), daily reminders, Claw daily maintenance. |
| **Technology** | JSON |
| **File** | `~/.hermes/cron/jobs.json` |
| **Depends on** | Cron Scheduler, Telegram (for delivery), Neo4j |

### 6.7 Memory (`memories/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Persistent agent memory. `MEMORY.md` stores agent context, `USER.md` stores user preferences. Loaded into system prompt at session start. |
| **Technology** | Markdown (~24 KB per file) |
| **File** | `~/.hermes/memories/MEMORY.md`, `USER.md` |
| **Depends on** | AIAgent Engine (loaded on session start) |

### 6.8 Plans (`plans/`)

| Attribute | Value |
|-----------|-------|
| **Purpose** | Project task plans in structured Markdown format. Define TDD tasks with exact file paths, verification commands, and acceptance criteria. |
| **Technology** | Markdown (8 plans, ~560 KB total) |
| **File** | `~/.hermes/plans/` |
| **Depends on** | AIAgent Engine (loaded for task context) |

---

## 7. Persistence Layer (Databases)

| DB File | Size | Purpose | Tables | Action for Publication |
|---------|------|---------|--------|------------------------|
| `state.db` | 535 MB | Session history, messages, FTS5 search | `sessions`, `messages`, `memory_consolidations`, FTS5 virtual tables | Schema only — delete all 498 sessions / 25,052 messages |
| `audit.db` | 229 KB | Audit pipeline (Agent Improvement) | 15 tables: `audit_summaries`, `tool_traces`, `waste_detections`, etc. | Clear all data |
| `kanban.db` | 115 KB | Kanban board management | `kanban_notify_subs`, `tasks`, `task_events` | Clear all data |
| `metrics.db` | 49 KB | Agent performance metrics | `agent_metrics`, `metric_trends` | Clear all data |
| `response_store.db` | 20 KB | Cached LLM responses | `conversations`, `responses` | Clear all data |

---

## 8. Port Table (Complete)

| Port | Service | Direction | Protocol | Required? | Notes |
|------|---------|-----------|----------|-----------|-------|
| **8648** | Hermes API Server | Inbound | HTTP/JSON | For API clients (Android, Web) | REST API |
| **8643** | Hermes Gateway (SSE) | Inbound | HTTP/SSE | For real-time streaming | Starlette SSE |
| **8647** | Voice Proxy | Inbound | HTTP | For voice (STT/TTS) | Audio streaming |
| **8089** | Voice Relay (WS) | Inbound | WebSocket | For real-time audio | OpenAI-compatible |
| **4000** | LiteLLM Proxy | Inbound | HTTP | For LLM routing | OpenAI-compatible API |
| **8092** | Llama.cpp Server | Inbound | HTTP | For local LLM inference | OpenAI-compatible API |
| **3400** | OpenCode Web UI | Inbound | HTTP | For browser access | Web UI |
| **6006** | Phoenix Dashboard | Inbound | HTTP | For LLM observability | Arize Phoenix |
| **3000** | OpenWebUI | Inbound | HTTP | Alternative Web UI | With RAG |
| **12000** | OpenHands | Inbound | HTTP | Agent sandbox | Code execution |
| **8024** | Searchbox MCP | Inbound | HTTP | For web search tools | MCP over HTTP |
| **7474** | Neo4j HTTP | Localhost | HTTP | Neo4j Browser | Admin only |
| **7687** | Neo4j Bolt | Localhost | Bolt | For all MCP servers | Binary protocol |
| **3030** | Gitea | Localhost | HTTP | Self-hosted Git | Excluded from package |

---

## 9. Dependency Map

```
AIAgent Engine
├── Tool Orchestrator
│   ├── Core Tools (20+: file, terminal, browser, web, memory, skills)
│   ├── MCP Servers
│   │   ├── claw-graph → Neo4j (:7687)
│   │   ├── searchbox → Web Search Engines
│   │   ├── education-graph → Neo4j (:7687)
│   │   └── codebase-graph → Neo4j (:7687)
│   └── Provider Adapters
│       ├── Cloud LLM (OpenAI, Anthropic, DeepSeek, OpenRouter)
│       ├── LiteLLM Proxy (:4000)
│       │   ├── Cloud LLM
│       │   └── Llama.cpp (:8092)
│       └── Llama.cpp (:8092) [direct]
├── Session DB (state.db)
├── Gateway
│   ├── Telegram API
│   ├── Discord API
│   ├── Slack API
│   └── API Server (:8648) + SSE (:8643)
├── Skills (Core + User)
├── Plugins (Core + User)
├── Hooks
├── Cron → Telegram API + Neo4j
├── Memory (MEMORY.md, USER.md)
├── Plans
└── Agents (role definitions)

Android App
├── API Server (:8648)
├── Gateway SSE (:8643)
└── Voice Proxy (:8647)
    ├── Faster-Whisper (STT)
    └── Piper TTS

OpenCode+
├── LiteLLM Proxy (:4000)
│   ├── Cloud LLM
│   ├── Llama.cpp (:8092)
│   └── Phoenix (:6006)
├── Llama.cpp (:8092)
├── OpenCode Web UI (:3400) → LiteLLM (:4000)
└── Phoenix (:6006)
```

---

## 10. External Dependencies (Binaries & Models)

| Dependency | How to Obtain | Included? |
|------------|---------------|-----------|
| `cloudflared` | `wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64` | ❌ Binary only |
| `tirith` | Built into Hermes Agent (security sandbox) | ❌ Binary only |
| `uv` / `uvx` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | ❌ Binary only |
| `opencode` | `curl -fsSL https://opencode.ai/install \| bash` | ❌ Binary only |
| `pip-audit` | `pip install pip-audit` | ❌ Install separately |
| `gitleaks` | `go install github.com/gitleaks/gitleaks/v8@latest` | ❌ Install separately |
| `semgrep` | `pip install semgrep` | ❌ Install separately |
| GGUF Models | HuggingFace / LM Studio | ❌ >10 GB, excluded |
| Faster-Whisper model | Auto-downloaded by voice_proxy.py | ❌ Downloaded at runtime |
| Piper TTS model | Downloaded separately | ❌ Downloaded separately |

---

## 11. Technology Stack Summary

| Layer | Technologies |
|-------|-------------|
| **Agent Core** | Python 3.12, SQLite FTS5, Rich, Prompt Toolkit, Pydantic, Fire, Jinja2, Tenacity, PyYAML |
| **API Layer** | FastAPI, Uvicorn, Starlette (SSE), PyJWT, HTTPX |
| **Android Client** | Kotlin, Jetpack Compose, Material 3, Hilt DI, Room DB, Retrofit, OkHttp, Moshi, DataStore, EncryptedSharedPreferences |
| **LLM Serving** | LiteLLM (Python), Llama.cpp (C++), Node.js (OpenCode Web UI) |
| **MCP Servers** | Node.js (claw-graph), Python (education-graph, codebase-graph), Docker (searchbox) |
| **Infrastructure** | Docker Compose, Neo4j 5, Sing-Box VPN, s6-overlay, systemd |
| **Observability** | Arize Phoenix (Python/Docker) |
| **Voice** | Faster-Whisper (CTranslate2), Piper TTS |

---

## 12. Security Boundaries

| Boundary | Enforcement |
|----------|-------------|
| **Credential Store** | `.env`, `auth.json` — blocked by Hermes defense-in-depth; NEVER copied |
| **API Key Validation** | `API_SERVER_KEY` env var checked by API Server on every request |
| **Tool Permission Gates** | Tool Orchestrator validates tool calls against permission configuration |
| **Database Access** | SQLite WAL mode, 0600 permissions, `PRAGMA foreign_keys=ON` |
| **HMAC Tamper-Evidence** | HMAC-SHA256 for audit trail integrity |
| **VPN** | Sing-Box VLESS+Reality — encrypted tunnel, no plaintext exposure |
| **Plugin Isolation** | Fail-open plugin architecture — plugin failure doesn't crash agent |

---

*Generated by Architect Agent (#4) as part of Phase 4 — Architecture Documentation.*
*PID: `SANITIZED_PID`*
