# Desktop Slash Command Development

## Architecture

Desktop slash commands pass through THREE layers:

```
User types /obs → Desktop composer (TypeScript)
    → isDesktopSlashCommand("/obs")?  ← desktop-slash-commands.ts
    → YES → requestGateway('slash.exec', {session_id, command})
    → Gateway (Python, tui_gateway/server.py)
    → SlashWorker (tui_gateway/slash_worker.py)
    → HermesCLI.process_command("/obs")  ← cli.py
    → _resolve_cmd("obs")  ← hermes_cli/commands.py
    → handler → _handle_observer_command()
```

## Adding a new slash command

### Layer 1: CLI registry (`hermes_cli/commands.py`)
```python
CommandDef("obs", "Show observer findings...", "Info",
           aliases=("observers", "observer", "findings")),
```

### Layer 2: CLI handler (`cli.py`)
```python
elif canonical in ("obs", "observers", "observer", "findings"):
    self._handle_observer_command()
```

### Layer 3: Desktop allowlist (`apps/desktop/src/lib/desktop-slash-commands.ts`)
```ts
['/obs', 'Show observer findings for this session'],
```

**CRITICAL**: Without Layer 3, `isDesktopSlashCommand("/obs")` returns `false` because:
1. `DESKTOP_COMMANDS.has("/obs")` → `false` (not in list)
2. `isKnownHermesSlashCommand("/obs")` → `true` (it IS in CLI registry)
3. Result: `false || !true` = `false`
4. Desktop sends `/obs` as raw user message to the AI agent

## Alias resolution bug

When using aliases, `_resolve_cmd("observer_json")` returns the primary `CommandDef` with `.name = "obs"`. The `canonical` variable is the primary name, NOT the alias. So `canonical == "observer_json"` is always `false`.

**Fix**: Check the original command word (`cmd_lower`), not the canonical:
```python
elif canonical in ("obs", "observers", "observer", "findings"):
    if cmd_lower.startswith("/observer_json"):
        self._handle_observer_json_command()
    else:
        self._handle_observer_command()
```

## Rich Console interference

The slash_worker redirects output through Rich Console (width=120). For JSON or structured output, bypass Rich entirely:

```python
import sys as _sys
_sys.stdout.write(json.dumps(data) + "\n")  # Raw stdout, no wrapping
```

## Rebuild cycle

- Python changes → restart `hermes gui` (starts new dashboard + slash_worker)
- TypeScript changes → `npm run pack` in `apps/desktop/` → restart `hermes gui`
- Kill stale slash_worker if it's caching old code: `kill <PID>`