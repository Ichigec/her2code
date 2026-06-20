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

## Dual Command Dispatch — Critical Pitfall

Slash commands are handled in **two separate places** — missing either one causes "not a quick/plugin/skill command" errors:

### 1. CLI (`cli.py`)
- `HermesCLI.process_command()` — long if/elif chain
- Handles terminal CLI (`hermes` command)

### 2. TUI Gateway (`tui_gateway/server.py`)
- `def _(rid, params: dict)` inside a `@method` decorator
- Separate if/elif chain with `if name == "..."` blocks
- This is what the **Desktop Electron app** uses
- Returns `_ok(rid, {...})` or `_err(rid, code, msg)` dicts
- Last line before fallthrough: `return _err(rid, 4018, f"not a quick/plugin/skill command: {name}")`

### Also need to register:
- `hermes_cli/commands.py` — `CommandDef` in `COMMAND_REGISTRY` for autocomplete/help

## Files to Touch (Typical Cross-Stack Feature)

| Layer | File | What |
|-------|------|------|
| Registration | `hermes_cli/commands.py` | `CommandDef` entry |
| CLI handler | `cli.py` | `elif canonical == "..."` + handler method |
| TUI handler | `tui_gateway/server.py` | `if name == "..."` block before fallthrough |
| (Optional) Gateway | `gateway/run.py` | Messaging platform command handler |

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
cd apps/desktop && npm run build     # rebuild frontend
# Then restart: hermes gui
```

### Sidebar Section Pattern

Follow existing patterns exactly. Sidebar uses nanostores (`$atom`, `useStore`), shadcn sidebar components, and `SidebarPanelLabel`. Look at `SidebarCronJobsSection` as a template for collapsible sections.

### Desktop Controller Safety

Event handlers in `desktop-controller.tsx` must not throw or crash. A bad `requestGateway()` call with a nonexistent method breaks the React event loop and kills all buttons (including Stop). Use safe patterns:
- `void promise.catch(() => undefined)` for fire-and-forget
- For composer insertion: `import('@/app/chat/composer/focus').then(...)` dynamic import

## Pitfalls

- **Dual dispatch**: always check both `cli.py` AND `tui_gateway/server.py`
- **Desktop controller handlers**: never call `requestGateway` with nonexistent methods — it crashes the UI
- **TypeScript null checks**: `onSwitchPreset?.()` not `onSwitchPreset()` when prop is optional
- **Build required**: TypeScript changes need `npm run build` + app restart
- **Python compile check**: `python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"` before shipping
