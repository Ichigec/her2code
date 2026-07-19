---
name: hermes-cross-stack
description: "Add features to Hermes that span CLI + TUI gateway + Desktop app."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos]
---

# Hermes Cross-Stack Feature Development

When adding a feature that needs to work across CLI, TUI gateway (desktop app), and optionally the messaging gateway.

## Triple Command Dispatch — Critical Pitfall

Slash commands can be handled in **up to three separate places**. Which ones you need depends on the command's complexity and target platforms:

### 1. Registration (`hermes_cli/commands.py`) — ALWAYS needed
- `CommandDef` entry in `COMMAND_REGISTRY`
- Provides autocomplete, `/help` text, tab-completion of subcommands
- `GATEWAY_KNOWN_COMMANDS` frozenset is **auto-derived** from `COMMAND_REGISTRY` — any command where `not cmd.cli_only` is automatically gateway-known. No manual registration needed.
- Verify: `python3 -c "from hermes_cli.commands import resolve_command; print(resolve_command('yourcmd'))"`

### 2. CLI handler (`cli.py`) — needed for CLI + Desktop app
- `HermesCLI.process_command()` — long if/elif chain (~line 9026+)
- Add `elif canonical == "yourcmd": self._handle_yourcmd_command(cmd_original)` in the chain
- Add handler method: `def _handle_yourcmd_command(self, cmd: str):` — uses `_cprint()` for output
- **Desktop app uses this too**: the Electron app calls `slash.exec` RPC which spawns a `slash_worker` subprocess that runs `cli.process_command()`. So for simple commands (run a script, print output), the CLI handler is sufficient for desktop.
- The TUI gateway (`tui_gateway/server.py`) is only needed for commands that require special TUI-side handling (returning structured data, prefilling the composer, triggering agent responses via `command.dispatch`). See "TUI Slash Command Rendering — Two Paths" below.

### 3. Gateway handler (`gateway/run.py`) — needed for messaging platforms (Telegram, Discord, etc.)
- Dispatch chain in `GatewayRunner._handle_command()` (~line 8248+)
- Add `if canonical == "yourcmd": return await self._handle_yourcmd_command(event)` in the chain
- Add handler method: `async def _handle_yourcmd_command(self, event: MessageEvent) -> str:`
- **Returns a string** (unlike CLI which uses `_cprint`) — the string is sent as the chat reply
- Access args via `event.get_command_args().strip().lower()`
- Use `_hermes_home` (Path object) for file paths, not `~/.hermes` hardcoded

### Quick reference: which dispatch points to touch

| Command type | `commands.py` | `cli.py` | `gateway/run.py` | `tui_gateway/server.py` |
|---|---|---|---|---|
| Simple (run script, print) | ✅ | ✅ | ✅ (for TG/Discord) | ❌ |
| Needs structured TUI response | ✅ | ✅ | ✅ | ✅ (via `command.dispatch`) |
| CLI-only (terminal tools) | ✅ (`cli_only=True`) | ✅ | ❌ (skipped) | ❌ |

## Desktop App Changes

When modifying the desktop Electron app:

| File | Purpose |
|------|---------|
| `apps/desktop/src/store/layout.ts` | Atoms + persistence keys |
| `apps/desktop/src/app/chat/sidebar/index.tsx` | Sidebar UI components |
| `apps/desktop/src/app/desktop-controller.tsx` | Event handlers, wiring |
| `apps/desktop/src/app/shell/model-menu-panel.tsx` | Model dropdown |
| `apps/desktop/src/app/command-palette/index.tsx` | Cmd+K palette |

### Build + Restart

```bash
cd apps/desktop && npm run build     # rebuild frontend (tsc + vite + stage-native-deps)
# Then restart: hermes gui
```

### Desktop GUI Build Pipeline (full)

The `npm run build` script chains three stages:

1. **`tsc -b`** — TypeScript type-check across workspace (`apps/desktop` + `apps/shared`). Fails on any type error.
2. **`vite build`** — bundles React/Vite frontend into `dist/` (single ~22MB JS bundle + ~277KB CSS + KaTeX fonts).
3. **`stage-native-deps.cjs`** — copies `node-pty` native binary into `build/native-deps/` for the target architecture. This is the ONLY native dependency in the desktop app.

After `npm run build`, the Electron app is packaged with `electron-builder`:

```bash
# Build only (no launch) — used by `hermes gui --build-only`
npm run builder -- --dir          # unpacked dir: release/linux-<arch>-unpacked/

# Full distribution artifacts
npm run dist:linux                # AppImage + deb + rpm
npm run dist:mac                  # dmg + zip (requires macOS for signing)
npm run dist:win                  # nsis + msi
```

**Via hermes CLI** (preferred — handles workspace deps + build + package):
```bash
hermes gui --build-only --force-build    # rebuild without launching
hermes gui --skip-build                  # launch existing build without rebuilding
hermes gui                               # build (if needed) + launch
```

#### node-pty: the only native dep

`node-pty` (v1.1.0, N-API based) ships prebuilts under `prebuilds/<platform>-<arch>/`:

| Platform | Arch | Prebuild | Status |
|----------|------|----------|--------|
| macOS | arm64 | ✅ `pty.node` + `spawn-helper` | Ready |
| macOS | x64 | ✅ `pty.node` + `spawn-helper` | Ready |
| Windows | x64 | ✅ `conpty.node` + `conpty/` | Ready |
| Windows | arm64 | ✅ `conpty.node` + `conpty/` | Ready |
| Linux | arm64 | ❌ No prebuild | **Compile from source** (`python3 make g++`) |
| Linux | x64 | ❌ No prebuild | **Compile from source** (`python3 make g++`) |

On Linux, `node-pty` compiles to `node_modules/node-pty/build/Release/pty.node` (~81KB). The `stage-native-deps.cjs` script copies this into `build/native-deps/node-pty/build/Release/pty.node` for packaging.

**Cross-compile ARM64 → x64** (or vice versa) via Docker:
```bash
docker run --rm --platform linux/amd64 \
  -v ~/.hermes/hermes-agent:/repo \
  node:22-bookworm-slim \
  bash -c "cd /repo/apps/desktop && npm install && npm run build && npm run builder -- --dir"
```

#### Build artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Frontend bundle | `apps/desktop/dist/` | Vite output (JS + CSS + fonts) |
| Install stamp | `apps/desktop/build/install-stamp.json` | commit, branch, builtAt, dirty flag |
| Native deps | `apps/desktop/build/native-deps/node-pty/` | Per-arch pty.node |
| Electron app | `apps/desktop/release/linux-<arch>-unpacked/Hermes` | Packaged binary (~195MB) |
| Builder config | `apps/desktop/release/builder-effective-config.yaml` | Resolved electron-builder config |

#### Backup + rollback pattern

Before a risky rebuild, back up the working build:
```bash
BACKUP=~/dev/codemes/gui-backup-v1
cp -r apps/desktop/release/linux-arm64-unpacked "$BACKUP/electron-app"
cp -r apps/desktop/dist "$BACKUP/dist"
cp -r apps/desktop/build "$BACKUP/build"
# Record metadata: commit, PID, ports, version
```

Rollback (frontend only — backend untouched):
```bash
cp -r "$BACKUP/electron-app"/* apps/desktop/release/linux-arm64-unpacked/
cp -r "$BACKUP/dist"/* apps/desktop/dist/
# Backend NOT restarted — only GUI changes
```

**Key insight**: the running Electron process loads code into memory at launch. A rebuild on disk does NOT affect the running GUI until it's restarted. This means you can rebuild safely while the current session continues working.

### Running Multiple Backends Simultaneously

To test a GUI build against two different backends (e.g. `.hermes` local vs `.hermes-docker` fork):

1. **Create a separate HERMES_HOME** with its own `.env`:
```bash
mkdir -p /tmp/hermes-backend2
cp ~/.hermes-docker/config.yaml /tmp/hermes-backend2/
cp ~/.hermes-docker/.env /tmp/hermes-backend2/
# Change the API server port in .env (NOT just the env var — .env overrides)
sed -i 's/API_SERVER_PORT=8643/API_SERVER_PORT=18648/' /tmp/hermes-backend2/.env
```

2. **Start the second gateway** with the custom HERMES_HOME:
```bash
HERMES_HOME=/tmp/hermes-backend2 hermes gateway run &
```

3. **Verify both backends**:
```bash
curl http://127.0.0.1:8643/health   # Backend A (local)
curl http://127.0.0.1:18648/health  # Backend B (docker fork)
```

**Pitfall — `.env` overrides env vars**: setting `API_SERVER_PORT=18648` as a shell env var does NOT work if the `.env` file in HERMES_HOME also sets `API_SERVER_PORT=8643`. The `.env` file is loaded by Hermes and takes precedence. You MUST edit the `.env` file in the custom HERMES_HOME directory.

**Pitfall — shared venv**: `.hermes-docker/hermes-agent/venv` may be a symlink to `.hermes/hermes-agent/venv`. Both backends use the same Python installation but different HERMES_HOME directories, so they have separate configs, sessions, and state databases.

### Atom-Driven Statusbar Icon Pattern

When a statusbar button needs to reflect dynamic state (e.g. ON/OFF), use a nanostore atom shared between the controller and the panel component:

1. **Define the atom** in `store/session.ts` (or relevant store file):
   ```ts
   export interface ObserverConfigState {
     enabled: boolean; inline: boolean; deep: boolean; deep_interval: number; session_end: boolean
   }
   export const $observerConfig = atom<ObserverConfigState>({ enabled: true, ... })
   ```

2. **Read in the controller** to build dynamic `StatusbarItem`:
   ```tsx
   const cfg = useStore($observerConfig)
   const item = useMemo<StatusbarItem>(() => ({
     icon: cfg.enabled ? <Eye /> : <EyeOff />,
     className: cfg.enabled ? 'text-green-400' : 'opacity-50',
     label: cfg.enabled ? undefined : 'OFF',
     ...
   }), [cfg.enabled])
   ```

3. **Write from the panel** on toggle:
   ```tsx
   $observerConfig.set({ ...cfg, enabled: !cfg.enabled })
   ```

4. **Fetch on mount** via gateway method:
   ```tsx
   const refreshConfig = useCallback(async () => {
     const r = await requestGateway<{ config: ObserverConfigState }>('observer.status', {})
     if (r?.config) $observerConfig.set(r.config)
   }, [requestGateway])
   ```

5. **Type imports**: use `type ObserverConfigState` (inline type import) in TypeScript to avoid runtime import issues:
   ```ts
   import { $observerConfig, type ObserverConfigState } from '../store/session'
   ```

**Key insight**: the atom is the single source of truth. Controller reads it for the icon; panel writes to it on toggle. No prop-drilling, no callback chains. The icon updates instantly because both components subscribe to the same atom.

### Agent Preset Switching (Statusbar Buttons → Backend)

Agent activation buttons in the statusbar use `switchAgentPreset()` which calls the `agents.activate` RPC. The backend supports staging without an active session via `__pending_desktop__`. Full verified vertical with code locations, known gaps, and the reusable `SubagentDropdown` pattern:

→ `references/desktop-agent-activation-vertical.md`

Key components:
- `switchAgentPreset()` — `desktop-controller.tsx:253-285` (no bail-out, optimistic UI)
- `agents.activate` RPC — `tui_gateway/server.py:3266-3325` (`__pending_desktop__` staging)
- `ActiveAgentIndicator` — `chat/active-agent-indicator.tsx` (reads `$activeAgentPresetId`)
- `SubagentDropdown` — `shell/subagent-dropdown.tsx` (groups agents by model, reusable)
- **Gap:** `ChatHeader` returns `null` for fresh draft → `ActiveAgentIndicator` not visible until session starts

### Agent Directory Pattern (`~/.hermes/agents/<prefix>/`)

The backend (`agent/agents.py:399`) auto-discovers agent definitions via `rglob("*.md")` starting from `~/.hermes/agents/`. Agent IDs are derived from the **relative path** — e.g. `plan3/requirements-agent.md` → ID `plan3/requirements-agent`. This enables organized agent groups without config changes.

**To add a new agent group (e.g. plan2/):**

1. Create `~/.hermes/agents/plan2/` directory
2. Copy agent `.md` files from an existing group (e.g. `plan3/`), updating `model:` and `provider:` in YAML frontmatter
3. Update `PLAN2_AGENTS` in `subagent-dropdown.tsx` with `id: 'plan2/<agent-name>'` prefix
4. Add `presetId.startsWith('plan2/')` to `switchAgentPreset` known-preset check in `desktop-controller.tsx`
5. **CRITICAL:** Add the model key to `MODEL_GROUPS` and `groupByModel()` in `subagent-dropdown.tsx` — otherwise agents are silently hidden
6. Build: `cd apps/desktop && npm run build`
7. Verify: `python3 -c "import sys; sys.path.insert(0, '...'); from agent.agents import load_agents; print([k for k in load_agents(force=True) if k.startswith('plan2/')])"`

### Statusbar Button Integration (4-Point Sync)

When adding a new agent dropdown button to the desktop statusbar (e.g. `P1` between `Claw` and `P2`), you must edit **three files in sync** — missing any one produces a silent failure or TypeScript error:

**File 1: `shell/subagent-dropdown.tsx`**
- Add a new export `PLAN1_AGENTS: SubagentInfo[]` with `{ id: 'plan1/<agent-name>', ... }` entries
- **CRITICAL:** Add the model key to `MODEL_GROUPS` dict AND `groupByModel()` function — otherwise agents are silently hidden (see pitfall above)
- For new model names (e.g. `'glm'`, `'deepseek'`), add a group entry and a matching `includes()` check

**File 2: `desktop-controller.tsx`**
- Import the new agent array: `import { ..., PLAN1_AGENTS } from './shell/subagent-dropdown'`
- Define the statusbar item:
  ```tsx
  const plan1SubagentsItem = useMemo<StatusbarItem>(
    () => ({
      icon: <span className="text-[0.7rem] leading-none">🚀</span>,
      id: 'plan1-subagents',
      label: 'P1',
      menuClassName: 'w-56',
      menuContent: (
        <SubagentDropdown orchestrator="plan1" agents={PLAN1_AGENTS} onSwitchPreset={switchAgentPreset} />
      ),
      title: 'Plan1 Subagents (...)',
      variant: 'menu'
    }),
    [switchAgentPreset]
  )
  ```
- Pass it to `useStatusbarItems({ ..., plan1SubagentsItem, ... })`

**File 3: `shell/hooks/use-statusbar-items.tsx`** — 4 coordinated edits:
1. Add `plan1SubagentsItem?: StatusbarItem` to `StatusbarItemsOptions` interface
2. Add `plan1SubagentsItem,` to function destructuring params
3. Add `...(plan1SubagentsItem ? [plan1SubagentsItem] : []),` to `coreLeftStatusbarItems` array **at the desired position** (ordering in the array = ordering in the statusbar)
4. Add `plan1SubagentsItem,` to the `useMemo` dependency array

**Statusbar item ordering** is controlled by position in the `coreLeftStatusbarItems` spread chain:
```tsx
...(clawOrchestratorItem ? [clawOrchestratorItem] : []),    // 🦞
...(plan1SubagentsItem ? [plan1SubagentsItem] : []),        // 🚀 P1
...(plan2SubagentsItem ? [plan2SubagentsItem] : []),        // 🎻 P2
...(plan3SubagentsItem ? [plan3SubagentsItem] : []),        // 🧬 P3
```

**Verify:** `npx tsc --noEmit` (must pass), then `npm run pack` to rebuild.

**Agent file format** (YAML frontmatter + markdown body):
```yaml
---
label: Plan2 · Requirements
description: Сборщик требований
mode: primary  # or 'subagent' for leaf agents
model: kimi-k2.7-code
provider: custom:kimi
emoji: 📋
reasoning: high
toolsets: [clarify]
---
# Agent body — system prompt for this role
```

**Sub-orchestrator agents** (can spawn their own children): set `mode: primary` and include `delegation` in toolsets. When activated via `delegate_task(role='orchestrator')`, the agent can spawn leaf agents up to `max_spawn_depth=2`.

### Sidebar Section Pattern

Follow existing patterns exactly. Sidebar uses nanostores (`$atom`, `useStore`), shadcn sidebar components, and `SidebarPanelLabel`. Look at `SidebarCronJobsSection` as a template for collapsible sections.

### Desktop Controller Safety

Event handlers in `desktop-controller.tsx` must not throw or crash. A bad `requestGateway()` call with a nonexistent method breaks the React event loop and kills all buttons (including Stop). Use safe patterns:
- `void promise.catch(() => undefined)` for fire-and-forget
- For composer insertion: `import('@/app/chat/composer/focus').then(...)` dynamic import

## Pitfalls

- **Triple dispatch**: check which of `cli.py`, `gateway/run.py`, and `tui_gateway/server.py` you need (see table above). For simple commands, `cli.py` + `gateway/run.py` is enough — the desktop app calls `cli.process_command()` via `slash.exec`.
- **Gateway handler returns string, not `_cprint`**: CLI handlers use `_cprint()` for output; gateway handlers must `return` a string that becomes the chat reply. If you copy a CLI handler to gateway, convert `_cprint(f"...")` → `return "..."`.
- **`GATEWAY_KNOWN_COMMANDS` is auto-derived**: don't try to manually add your command to this frozenset — it's computed from `COMMAND_REGISTRY` at import time. Any `CommandDef` without `cli_only=True` is automatically included.
- **Desktop controller handlers**: never call `requestGateway` with nonexistent methods — it crashes the UI
- **TypeScript null checks**: `onSwitchPreset?.()` not `onSwitchPreset()` when prop is optional
- **Build required**: TypeScript changes need `npm run build` + app restart
- **Python compile check**: `python3 -c "compile(open('file.py').read(), 'file.py', 'exec')"` before shipping
- **Patch tool indentation corruption near multi-line tuples**: when using `patch` to replace a `CommandDef` or similar entry that sits right after a multi-line `subcommands=(...)` tuple, the fuzzy matcher can insert the new content INSIDE the preceding tuple at the wrong indentation level — producing `SyntaxError: closing parenthesis ']' does not match opening parenthesis '('`. **Always include the closing `)),` of the preceding entry in your `old_string`** so the replacement anchors at the correct nesting level. After patching, verify with `python3 -c "import ast; ast.parse(open('file').read())"`.
- **Patch tool escape-drift**: the `patch` tool can reject multi-line replacements that contain escaped quotes (`\\\"`) with "Escape-drift detected". Workaround: use a Python heredoc script via `terminal` to do the replacement directly. Verify with `read_file` before and after, and run a Python `compile()` check on the target file.
  ```python
  python3 << 'PYEOF'
  path = "/path/to/file.py"
  with open(path) as f: content = f.read()
  assert old in content, "Old string not found!"
  content = content.replace(old, new, 1)
  with open(path, "w") as f: f.write(content)
  PYEOF
  ```
- **`groupByModel` silently hides agents**: `SubagentDropdown` groups agents by model name. If a model string (e.g. `'Kimi K2.7'`) doesn't match any key in `MODEL_GROUPS` (which checks `model.includes('qwen')`, `model.includes('nex')`, `model.includes('agentworld')`), the agent falls into `'other'` and `if (!group) return null` silently drops it. **Symptom:** dropdown opens but shows only "🚀 Full Cycle" — no sub-agents. **Fix:** add the missing model key to both `MODEL_GROUPS` dict and `groupByModel()` function in `subagent-dropdown.tsx`.
- **YAML colon-in-description breaks frontmatter parsing**: `agent/agents.py:_parse_frontmatter()` uses `yaml.safe_load()` to parse the YAML block between `---` markers. If a `description:` value contains an unquoted colon (`description: Validates module wiring: verifies every component...`), `safe_load` throws `ScannerError: mapping values are not allowed here` at the second colon. The `except` clause silently returns `{}`, so the agent registers with `model=None`, `label=None` — no error logged. **Symptom:** `load_agents()` shows the agent ID but with `(inherit)` or `(NONE)` for model. **Debug:** `python3 -c "import yaml; yaml.safe_load(open('<file>'))"` to reproduce the error. **Fix:** quote the description value: `description: "Validates module wiring - verifies every component..."` (also replace the colon with a dash to avoid future ambiguity). Always run `python3 -c "from agent.agents import load_agents; a=load_agents(force=True); print(a.get('<id>'))"` after creating agent files to verify frontmatter parsed correctly.
- **Agent file line-number corruption**: `read_file` returns content with `N|` prefixes. If this output is written back via `write_file` or piped through `sed`, the prefixes become part of the file content. **Symptom:** YAML frontmatter starts with `1|1|1|---` instead of `---`. **Fix:** strip prefixes with `re.sub(r'^(?:\d+\|)+', '', line)` before writing. Always verify agent files with `head -5 <file>` after creation. **Root cause note:** the `execute_code` tool's `hermes_tools.read_file()` wrapper returns line-numbered content; use `terminal` with raw Python `open(path).read()` for file manipulation to avoid this entirely.
- **sed batch frontmatter modification unreliable**: a batch `sed -i 's/^model: qwen3.6-35b/model: glm-5.2/'` script appears to succeed (exit 0) but silently misses files whose frontmatter has a different model value (e.g. `nex-n2-mini`, `kimi-k2.7-code`, `deepseek-v4-pro`). **Symptom:** some agent files keep their old model after batch sed. **Fix:** use a Python script via `terminal` that reads each file, replaces ALL possible model values, and writes back with raw `open()`:
  ```python
  python3 << 'PYEOF'
  import os
  for f in os.listdir(BASE):
      if not f.endswith('.md'): continue
      path = os.path.join(BASE, f)
      with open(path) as fh: c = fh.read()
      # Replace ALL model variants
      for old_model in ['qwen3.6-35b', 'nex-n2-mini', 'kimi-k2.7-code', 'agentworld', 'deepseek-v4-pro']:
          c = c.replace(f'model: {old_model}', f'model: {new_model}')
      with open(path, 'w') as fh: fh.write(c)
  PYEOF
  ```
  Then verify ALL files with a loop: `for f in $BASE/*.md; do sed -n 's/^model: //p' "$f"; done`
- **`switchAgentPreset` rejects nested agent IDs**: The hardcoded known-preset list in `desktop-controller.tsx` (`['general', 'build', 'plan', 'plan2', 'plan3', ...]`) doesn't include `plan2/` or `plan3/` prefixed IDs. Subagent dropdown clicks silently fail (function returns early). **Fix:** add `presetId.startsWith('plan2/') || presetId.startsWith('plan3/')` to the known-preset check.
- **Desktop build verification**: After `npm run build`, verify the new code is in `app.asar` (not just `dist/`). The running Electron app loads from `release/linux-arm64-unpacked/resources/app.asar`. Check with: `python3 -c "data=open('app.asar','rb').read(); print(data.count(b'plan2/requirements-agent'))"`. If 0, the build didn't package correctly.
- **Running Electron process not affected by rebuild**: The running Electron app loads code into memory at launch. Rebuilding `dist/` or `release/` on disk does NOT update the running GUI — it continues using the old code until restarted. This is safe (you can rebuild while a session is active) but means you must restart `hermes gui` to pick up changes.
- **`.env` overrides shell env vars for API_SERVER_PORT**: When running a second backend with `API_SERVER_PORT=18648 hermes gateway run`, the shell env var is IGNORED if the HERMES_HOME's `.env` file also sets `API_SERVER_PORT=8643`. The `.env` file is loaded by Hermes and takes precedence. Fix: create a separate HERMES_HOME directory with its own `.env` that has the desired port.
- **node-pty has no Linux prebuilds**: macOS and Windows have prebuilt `pty.node` binaries. Linux (arm64 and x64) must compile from source — requires `python3 make g++` installed. If `npm install` fails with a node-gyp error on Linux, install build tools first.

## TUI Slash Command Rendering — Two Paths

Slash command output renders through one of two paths. The default path produces dim, unstyled system text. For proper chat messages use `command.dispatch` with `type: "send"`.

### Path 1: `slash.exec` → dim system text (DEFAULT)

```
frontend → gw.request('slash.exec', ...)
         → slash_worker subprocess
         → cli.process_command() writes to stdout
         → captured, returned as {output: "..."}
         → frontend: sys(text) or page(text)  ← GRAY, DIM
```

Rendered by `messageLine.tsx` as `kind: 'slash'` with `t.color.muted`.

### Path 2: `command.dispatch` → proper chat message

```
frontend → .catch() on slash.exec error
         → gw.request('command.dispatch', ...)
         → server.py handler returns {type: "send", message: "..."}
         → frontend: send(message)  ← NORMAL CHAT BUBBLE, markdown
```

To use Path 2 for a slash command:
1. Add the command name to `_PENDING_INPUT_COMMANDS` in `tui_gateway/server.py` (this makes `slash.exec` reject it with error 4018)
2. Add a handler in `command.dispatch` (the `@method("command.dispatch")` function)
3. Return `_ok(rid, {"type": "send", "message": markdown_text})` or `_ok(rid, {"type": "send", "notice": "...", "message": "..."})`

Supported dispatch types and their frontend behavior:
| `type` | Frontend action | Use case |
|--------|----------------|----------|
| `"send"` | `send(message)` — triggers agent response | Observer findings, queued prompts |
| `"skill"` | `send(message)` — triggers agent | Skill invocation messages |
| `"exec"` | `sys(output)` — gray system text | Quick command output |
| `"plugin"` | `sys(output)` — gray system text | Plugin command output |
| `"alias"` | recursive `handler(target)` | Command aliases |
| `"prefill"` | `composer.setInput(message)` | Pre-fill composer |

### Frontend handler location

`ui-tui/src/app/createSlashHandler.ts` — lines 77-137. The `.catch()` fallback at line 89 triggers `command.dispatch`.

### Color fix for slash output

If slash output must go through Path 1, the color is controlled in `ui-tui/src/components/messageLine.tsx:134`:
```tsx
// Before: gray/dim
<Text color={t.color.muted}>{msg.text}</Text>
// After: normal text color
<Text color={t.color.text}>{msg.text}</Text>
```

### Neo4j timestamp normalization

When querying Neo4j for findings with timestamps, some nodes have ISO strings (`"2026-06-27T..."`) while others have epoch integers. Before sorting, normalize all to strings:
```python
for f in findings:
    ts = f.get("timestamp", "")
    if ts is not None and not isinstance(ts, str):
        ts = str(ts)
    f["timestamp"] = ts or ""
findings.sort(key=lambda f: f.get("timestamp", ""), reverse=True)
```

### Network Isolation via systemd IPAddressDeny

When a feature needs to block external network access for Hermes processes (kill switch, air-gap mode, sandboxing), use systemd `IPAddressDeny`/`IPAddressAllow` on a user scope. This works **without root** via BPF cgroup filters and covers all child processes. Requires launching Hermes via `systemd-run --user --scope`.

Full implementation pattern (netcut.sh script, scope wrapper, slash command wiring, RPC method, desktop GUI button):
→ `references/systemd-network-isolation.md`

→ `references/desktop-gui-architecture-and-build.md` — full GUI architecture (Electron → Dashboard → Gateway split), cross-architecture build matrix, node-pty native dep handling, `.env`-overrides-env-var pitfall for multiple backends, `hermes_portable` artifacts gap analysis, `.hermes` vs `.hermes-docker` diff summary.

→ `references/multi-agent-orchestrator-variants.md` — the 4 orchestrator variants (plan/plan1/plan2/plan3), their model routing strategies (GLM+DeepSeek vs all-DeepSeek vs local multi-model), what was ported between them, and the procedure for creating a new variant.

## Custom RPC Method Pattern (`tui_gateway/server.py`)

When the desktop GUI needs to trigger a backend action and get structured data
back (beyond what slash commands provide), register a custom RPC method using
the `@method()` decorator. The frontend calls it via `requestGateway()`.

### Registration

```python
@method("your.action")
def _(rid, params: dict) -> dict:
    """Your action description."""
    result = do_something(params.get("key"))
    return _ok(rid, {"data": result})
    # or: return _err(rid, 5001, "error message")
```

- `_ok(rid, result_dict)` / `_err(rid, code, msg)` — JSON-RPC response helpers (defined at top of `server.py`)
- `@method("name")` registers into `_methods` dict at **import time** — requires gateway/dashboard restart
- Signature: `def _(rid, params: dict) -> dict` — `rid` is the JSON-RPC request ID, `params` is the params object

### Frontend call

```tsx
const result = await requestGateway<{ data: SomeType }>('your.action', { key: 'value' })
```

### When to use RPC vs slash command

| Need | Use |
|------|-----|
| User types `/command` in chat | Slash command (commands.py + cli.py + gateway/run.py) |
| GUI button triggers backend action with structured return | Custom RPC method (`@method()` in server.py) |
| Both (chat + GUI button) | Both — slash command for chat, RPC method for GUI |

The netcut feature uses both: `/netcut` slash command for chat, `netcut.toggle` RPC method for the desktop statusbar button.
