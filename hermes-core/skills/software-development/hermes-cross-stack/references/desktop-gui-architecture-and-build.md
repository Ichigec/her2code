# Desktop GUI Architecture and Cross-Architecture Build

Session: 2026-07-07 — deep analysis of Hermes Desktop GUI architecture,
cross-architecture build capability, and comparison with `hermes_portable`
architectural artifacts.

## GUI Architecture (Split Design)

The Hermes Desktop GUI uses a three-layer split architecture:

```
┌─────────────────────────────────────────────────────────┐
│  CLIENT LAYER                                           │
│  Electron Desktop App (apps/desktop/, v0.15.1)          │
│  ├── electron/main.cjs (209KB) — Electron main process  │
│  ├── electron/preload.cjs — IPC bridge                  │
│  ├── electron/connection-config.cjs — WS URL, auth      │
│  ├── electron/bootstrap-runner.cjs — first-launch install│
│  ├── electron/gateway-ws-probe.cjs — WS connectivity    │
│  ├── electron/backend-probes.cjs — hermes CLI detection │
│  ├── electron/hardening.cjs — security helpers          │
│  ├── src/ (60+ TS/TSX files) — React/Vite frontend      │
│  │   ├── app/desktop-controller.tsx — main controller   │
│  │   ├── app/chat/ — chat UI                            │
│  │   ├── app/shell/ — statusbar, panels, dropdowns      │
│  │   ├── app/gateway/hooks/ — boot + request hooks      │
│  │   ├── store/ — nanostores (session, gateway, clarify)│
│  │   └── lib/ — gateway-events, gateway-ws-url, etc.    │
│  └── @hermes/shared (apps/shared/) — shared TS types    │
└──────────────────┬──────────────────────────────────────┘
                   │ WebSocket /api/ws?token=...
                   │ (or ?ticket= for OAuth mode)
┌──────────────────┴──────────────────────────────────────┐
│  MIDDLEWARE LAYER                                       │
│  Dashboard (Python, local venv)                         │
│  Port 9120-9199 (auto-allocated by Electron main)      │
│  ├── Routes LLM calls to gateway                        │
│  ├── Loads plugins (on_session_start, post_llm_call)   │
│  └── Session management                                 │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTP
┌──────────────────┴──────────────────────────────────────┐
│  BACKEND LAYER                                          │
│  Hermes Gateway (Python)                                │
│  Port 8643 (default, configurable via API_SERVER_PORT) │
│  ├── AIAgent (run_agent.py) — conversation loop        │
│  ├── Tool execution (30+ tools)                         │
│  ├── Memory + Skills                                    │
│  └── Subagent delegation                                │
└─────────────────────────────────────────────────────────┘
```

### Key architectural facts

- **Dashboard loads plugins** from local venv's `plugins/` — plugin hooks register HERE
- **Conversation loop runs inside the gateway** — plugins registered in dashboard are NOT visible to the gateway's conversation loop
- **Gateway hooks** (`~/.hermes/hooks/`) only fire for messaging platforms (Telegram, Discord), NOT for GUI sessions
- **HERMES_HOME** in Docker = `/opt/data` (not `/opt/hermes`)
- **Electron 40.9.3**, Node ^20.19.0 || >=22.12.0, Vite + TypeScript 5.x

### Connection flow

1. Electron main process (`main.cjs`) starts → spawns Dashboard (Python) on port 9120-9199
2. Dashboard connects to Gateway on port 8643 (via `api_server` platform adapter)
3. Electron renderer (React) connects to Dashboard via WebSocket `/api/ws`
4. Auth modes: `token` (legacy, `?token=` query param) or `oauth` ( HttpOnly cookies + `?ticket=` single-use)

### Process model (observed on live system)

| Process | PID | Port | Role |
|---------|-----|------|------|
| `hermes gui` (launcher) | — | — | Spawns Electron + Dashboard |
| `Hermes` (Electron main) | — | — | GUI window, IPC, native PTY |
| `hermes gateway run` | — | 8643 | API server, conversation loop |
| `hermes dashboard` | — | 9120+ | Middleware: routes LLM calls |
| `tui_gateway.slash_worker` | — | — | Per-session slash command subprocess |

## Cross-Architecture Build Capability

### Answer: YES — GUI can be built on any architecture

The desktop app is fully cross-platform. The only constraint is `node-pty`
(the native PTY module for the embedded terminal), which needs either a
prebuild (macOS/Windows) or compilation from source (Linux).

### Build matrix

| Target | Arch | node-pty | Build command | Notes |
|--------|------|----------|---------------|-------|
| macOS | arm64 | Prebuild | `npm run dist:mac` | M1/M2 native |
| macOS | x64 | Prebuild | `npm run dist:mac -- --x64` | Intel |
| Windows | x64 | Prebuild | `npm run dist:win` | |
| Windows | arm64 | Prebuild | `npm run dist:win -- --arm64` | |
| Linux | arm64 | Compile | `npm run dist:linux` | Needs `python3 make g++` |
| Linux | x64 | Compile | `npm run dist:linux -- --x64` | Cross-compile via Docker |

### electron-builder configuration (package.json `build` field)

- `electronVersion: 40.9.3`
- Targets: macOS (dmg+zip), Windows (nsis+msi), Linux (AppImage+deb+rpm)
- `asar: true` with `asarUnpack: ["**/*.node", "**/prebuilds/**"]`
- `extraResources`: install-stamp.json, native-deps/, icon.ico
- `beforePack`/`afterPack` hooks for platform-specific staging
- `stage-native-deps.cjs` copies per-arch node-pty into `build/native-deps/`

### Cross-compile via Docker (ARM64 host → x64 target)

```bash
docker run --rm --platform linux/amd64 \
  -v ~/.hermes/hermes-agent:/repo \
  -w /repo/apps/desktop \
  node:22-bookworm-slim \
  bash -c "npm install && npm run build && npm run builder -- --linux AppImage --x64"
```

QEMU emulation makes this 5-10× slower than native, but produces correct
x64 binaries. Cannot verify GPU-dependent features inside QEMU.

## hermes_portable Architectural Artifacts Gap

### Finding: 35 architectural artifacts do NOT describe the GUI layer

The `hermes_portable` package (70 files, 35 architectural artifacts including
C4 Level 1-4, D2 diagrams, 10 ADRs, 6 fitness functions) describes ONLY the
backend architecture. The GUI layer (Desktop Electron, Dashboard, TUI Gateway)
is completely absent:

| Artifact | Mentions of desktop/electron/gui/dashboard |
|----------|---------------------------------------------|
| C4 Level 1 (Context) | 0 |
| C4 Level 2 (Container) | 0 |
| C4 Level 3 (Component) | 0 |
| C4 Level 4 (Code) | 0 |
| D2: agent-loop | 0 |
| D2: gateway-architecture | 0 |
| D2: plugin-system | 2 (observer mentions only) |
| D2: configuration-flow | 0 |
| D2: transport-layer | 0 |
| ADR-001..010 | 0 (ADR-007: 1 mention "observer") |

### What hermes_portable describes vs what exists

```
hermes_portable describes:       Reality:
┌─────────────────────┐          ┌──────────────────────────────────┐
│ CLI (TUI)           │          │ Desktop Electron App (GUI)  ← GAP │
│ Gateway (API)       │          │ Dashboard :9120            ← GAP │
│ AIAgent             │          │ CLI (TUI)                       │
│ Tool Registry       │          │ Gateway (API) :8643             │
│ Plugins             │          │ AIAgent                          │
│                     │          │ Tool Registry                   │
│                     │          │ Plugins                          │
│                     │          │ TUI Gateway (JSON-RPC)    ← GAP │
│                     │          │   tui_gateway/server.py (346KB) │
│                     │          │ Shared TS package          ← GAP │
│                     │          │   apps/shared/                  │
└─────────────────────┘          └──────────────────────────────────┘
```

### Recommendation

Architectural artifacts should be extended with:
1. C4 Level 2: add "Desktop Electron App" and "Dashboard" containers
2. C4 Level 3: add components for Electron main, React renderer, WS transport
3. New ADR: "Desktop GUI Split Architecture" (Electron → Dashboard → Gateway)
4. New D2 diagram: "desktop-gui-architecture.d2"
5. Fitness function: verify `apps/desktop/` is covered in architecture docs

## .hermes vs .hermes-docker Diff Summary

| Aspect | .hermes (local) | .hermes-docker (fork) |
|--------|-----------------|----------------------|
| Last commit | `beeb744a` (+7 carried) | `173df353` |
| Observer system | ✅ `observer.py` + `observer_manager.py` (529 lines) | ❌ Absent |
| Plan2/Plan3 UI | ✅ SubagentDropdown, ActiveAgentIndicator | ❌ Absent |
| Netcut | ✅ `store/netcut.ts` | ❌ Absent |
| codebase_read_tool | ✅ `tools/codebase_read_tool.py` | ❌ Absent |
| Desktop controller | `agents.activate` RPC (direct) | `/agent` insert (indirect) |
| observer-hook plugin | ✅ `plugins/observer-hook/` | ❌ Absent |
| Desktop build | Newer (2026-07-07T12:05) | Older (2026-07-06T10:44) |
