# Network Isolation via systemd IPAddressDeny

How to block external internet access for Hermes (and all child processes) without root, using systemd's BPF cgroup filter.

## Why This Approach

| Approach | Root needed? | Covers all children? | Bypassable? |
|---|---|---|---|
| **systemd IPAddressDeny** | ❌ No | ✅ Yes (cgroup BPF) | ❌ No (kernel-level) |
| nftables cgroup match | ✅ Yes | ✅ Yes | ❌ No |
| iptables cgroup match | ✅ Yes | ✅ Yes | ❌ No |
| Network namespace | ✅ Yes | ✅ Yes | ❌ No |
| HTTP proxy env var | ❌ No | ❌ No (Chromium/MCP ignore it) | ✅ Yes |
| Toolset disable (`hermes tools disable web`) | ❌ No | ❌ No (terminal curl still works) | ✅ Yes |

systemd `IPAddressDeny` wins: no root, kernel-enforced, covers the entire process tree.

## How It Works

1. Launch Hermes inside a systemd user **scope**: `systemd-run --user --scope --unit=hermes hermes gui`
2. All child processes (Electron, slash_workers, subagents, terminal commands, browser) inherit the scope's cgroup
3. `systemctl --user set-property --runtime hermes.scope IPAddressDeny=any IPAddressAllow=127.0.0.0/8 ...` attaches a BPF program to the cgroup
4. The BPF program drops packets to non-allowlisted destinations at the socket level — before they leave the process

## Prerequisites

- Linux with cgroup v2 (`mount | grep cgroup2`)
- systemd user instance (default on modern Linux)
- Hermes launched via `systemd-run --user --scope --unit=hermes` (NOT bare `hermes gui`)

**Check**: `cat /proc/self/cgroup` — if it shows `0::/user.slice/user-1000.slice/user@1000.service/...` you have a user systemd instance with cgroup v2.

**Verify BPF support**: 
```bash
systemd-run --user --unit=test --remain-after-exit /bin/bash -c 'sleep 5'
systemctl --user set-property --runtime test.service IPAddressDeny=any IPAddressAllow=127.0.0.0/8
systemctl --user show test.service -p IPAddressDeny --value
# Should show: ::/0 0.0.0.0/0
systemctl --user stop test.service
```

## Implementation: netcut.sh

Script location: `~/.hermes/scripts/netcut.sh`

### Key design decisions

1. **Local CIDR allowlist**: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `::1/128`, `fe80::/10`, `fc00::/7` — preserves LiteLLM, Neo4j, MCP, Docker host gateway
2. **`--runtime` flag**: properties are NOT persisted to disk — they reset on reboot/restart. This is intentional (fail-open on restart).
3. **Unit name via env var**: `HERMES_NETCUT_UNIT` defaults to `hermes.scope` but can be overridden for testing
4. **Toggle default**: `netcut.sh` with no args = toggle (flips current state)

### Toggle logic

```bash
# Block:
systemctl --user set-property --runtime hermes.scope \
  IPAddressDeny=any \
  IPAddressAllow=127.0.0.0/8 \
  IPAddressAllow=10.0.0.0/8 \
  IPAddressAllow=172.16.0.0/12 \
  IPAddressAllow=192.168.0.0/16 \
  IPAddressAllow=::1/128 \
  IPAddressAllow=fe80::/10 \
  IPAddressAllow=fc00::/7

# Unblock:
systemctl --user set-property --runtime hermes.scope \
  IPAddressDeny= \
  IPAddressAllow=
```

### Status check

```bash
deny=$(systemctl --user show hermes.scope -p IPAddressDeny --value 2>/dev/null)
# Non-empty deny = blocked; empty = open
```

## Scope Wrapper: hermes-scope.sh

Script location: `~/.hermes/scripts/hermes-scope.sh`

Launches Hermes in a named scope so all child processes are in one cgroup:

```bash
exec systemd-run --user --scope --unit=hermes --same-dir --collect hermes "$@"
```

- `--same-dir`: preserve current working directory
- `--collect`: garbage-collect the scope when Hermes exits
- Usage: `~/.hermes/scripts/hermes-scope.sh gui` instead of `hermes gui`

## Slash Command Wiring (3 files)

### 1. `hermes_cli/commands.py` — register

```python
CommandDef("netcut", "Toggle internet kill switch (systemd IPAddressDeny, kernel-level)",
           "Configuration",
           args_hint="[on|off|status|toggle]",
           subcommands=("on", "off", "status", "toggle")),
```

Not `cli_only=True` → automatically in `GATEWAY_KNOWN_COMMANDS`.

### 2. `cli.py` — CLI + desktop handler

```python
# In process_command() dispatch chain:
elif canonical == "netcut":
    self._handle_netcut_command(cmd_original)

# Handler method:
def _handle_netcut_command(self, cmd: str):
    import subprocess, os
    from hermes_constants import get_hermes_home
    parts = cmd.strip().split(maxsplit=1)
    arg = parts[1].strip().lower() if len(parts) > 1 else "toggle"
    script = os.path.join(get_hermes_home(), "scripts", "netcut.sh")
    result = subprocess.run(["bash", script, arg], capture_output=True, text=True, timeout=10)
    for line in result.stdout.strip().split("\n"):
        _cprint(f"  {line}")
```

### 3. `gateway/run.py` — messaging platform handler

```python
# In _handle_command() dispatch chain:
if canonical == "netcut":
    return await self._handle_netcut_command(event)

# Handler method:
async def _handle_netcut_command(self, event: MessageEvent) -> str:
    import subprocess
    args = event.get_command_args().strip().lower() or "toggle"
    script = _hermes_home / "scripts" / "netcut.sh"
    result = subprocess.run(["bash", str(script), args], capture_output=True, text=True, timeout=10)
    return result.stdout.strip() or "(no output)"
```

## Testing

End-to-end verification (no Hermes restart needed — use a test scope):

```bash
# Create test scope
systemd-run --user --unit=test-nc --remain-after-exit /bin/bash -c 'sleep 120'

# Test with HERMES_NETCUT_UNIT=test-nc.service
HERMES_NETCUT_UNIT=test-nc.service ~/.hermes/scripts/netcut.sh on
HERMES_NETCUT_UNIT=test-nc.service ~/.hermes/scripts/netcut.sh status

# Verify external blocked, local works:
systemd-run --user --wait --pipe \
  --property=IPAddressDeny=any \
  --property=IPAddressAllow=127.0.0.0/8 \
  curl -s --max-time 3 -o /dev/null -w "%{http_code}" https://httpbin.org/get
# Expected: 000 (timeout)

systemd-run --user --wait --pipe \
  --property=IPAddressDeny=any \
  --property=IPAddressAllow=127.0.0.0/8 \
  curl -s --max-time 3 -o /dev/null -w "%{http_code}" http://127.0.0.1:4000/v1/models
# Expected: 401 (LiteLLM responding, auth required)

# Cleanup
HERMES_NETCUT_UNIT=test-nc.service ~/.hermes/scripts/netcut.sh off
systemctl --user stop test-nc.service
```

## Desktop GUI Button (RPC + Statusbar)

The slash command is sufficient for CLI/gateway, but the desktop app needs an
RPC method the frontend can call, plus a statusbar button wired to it.

### 4. `tui_gateway/server.py` — custom RPC method

Register a `@method("netcut.toggle")` handler that the desktop frontend calls
via `requestGateway()`. This is the pattern for ANY backend action the GUI
needs to trigger with structured return data:

```python
@method("netcut.toggle")
def _(rid, params: dict) -> dict:
    """Toggle internet kill switch via systemd IPAddressDeny."""
    import subprocess, os
    from hermes_constants import get_hermes_home

    action = str(params.get("action", "toggle") or "toggle").lower()
    script = os.path.join(get_hermes_home(), "scripts", "netcut.sh")

    result = subprocess.run(["bash", script, action], capture_output=True, text=True, timeout=10)
    output = result.stdout.strip()
    if result.returncode != 0 and result.stderr.strip():
        output = (output + "\n" + result.stderr.strip()).strip()

    blocked = "BLOCKED" in output.upper()
    return _ok(rid, {"blocked": blocked, "message": output})
```

Key conventions:
- `_ok(rid, result_dict)` / `_err(rid, code, msg)` — JSON-RPC response helpers
- `@method("name")` registers into `_methods` dict at import time — **requires gateway restart** to take effect
- The desktop frontend calls this via `requestGateway<T>('netcut.toggle', { action: 'toggle' })`

### 5. Desktop statusbar button (3 files)

**Store atom** (`apps/desktop/src/store/netcut.ts`):
```ts
import { atom } from 'nanostores'
export const $netcutBlocked = atom(false)
export const setNetcutBlocked = (next: boolean) => $netcutBlocked.set(next)
```

**Controller** (`desktop-controller.tsx`) — build `StatusbarItem` with dynamic icon:
```tsx
const netcutBlocked = useStore($netcutBlocked)

const toggleNetcut = useCallback(async () => {
  try {
    const result = await requestGateway<{ blocked: boolean; message: string }>(
      'netcut.toggle', { action: 'toggle' }
    )
    setNetcutBlocked(result.blocked)
  } catch {
    // Fallback: query status to stay in sync
    try {
      const status = await requestGateway<{ blocked: boolean; message: string }>(
        'netcut.toggle', { action: 'status' }
      )
      setNetcutBlocked(status.blocked)
    } catch { /* gateway not ready */ }
  }
}, [requestGateway])

// Fetch initial state on mount
useEffect(() => {
  requestGateway<{ blocked: boolean; message: string }>('netcut.toggle', { action: 'status' })
    .then(r => setNetcutBlocked(r.blocked))
    .catch(() => undefined)
}, [requestGateway])

const netcutItem = useMemo<StatusbarItem>(() => ({
  icon: <span className="text-[0.7rem] leading-none">{netcutBlocked ? '🔒' : '🌐'}</span>,
  id: 'netcut',
  onSelect: () => void toggleNetcut(),
  title: netcutBlocked ? 'Internet: BLOCKED — click to restore' : 'Internet: open — click to cut off',
  variant: 'action'
}), [netcutBlocked, toggleNetcut])
```

**Hook** (`use-statusbar-items.tsx`) — add `netcutItem?` to interface, destructure, insert into `coreLeftStatusbarItems`:
```tsx
...(netcutItem ? [netcutItem] : [])
```

Pass `netcutItem={netcutItem}` from the controller to `useStatusbarItems()`.

### Build

```bash
cd apps/desktop && npm run build   # ~3s — TypeScript compilation
```

RPC method takes effect on next gateway/dashboard restart (the `@method()` decorator runs at import time).

## Limitations

- **Requires scope launch**: Hermes must be started via `systemd-run --user --scope`. A bare `hermes gui` from terminal scatters processes across different cgroups (vte-spawn-*, app-org.chromium.*) — the BPF filter only applies to processes in the target scope.
- **Runtime-only**: `--runtime` properties don't survive reboot. Intentional — fail-open on restart.
- **IPv6**: allowlist includes `::1/128`, `fe80::/10` (link-local), `fc00::/7` (ULA). If using public IPv6, add it to the allowlist.
- **Docker containers**: containers have their own network namespace. IPAddressDeny on the host scope does NOT affect Docker containers like LiteLLM — but they're reachable via localhost which IS allowlisted.
- **No model switching**: this is pure firewall. If the LLM is cloud-hosted (e.g. Z.AI, OpenRouter), Hermes can't call it while blocked. Switch to a local model (LiteLLM :4000) before or simultaneously with enabling netcut.
- **Gateway restart for RPC**: the `@method("netcut.toggle")` decorator registers at import time. The running gateway won't have it until restarted.

## Diagnostics & Pitfalls

### Button clicks but internet stays on

**Symptom**: Desktop statusbar button toggles 🌐↔🔒, but external sites remain reachable. The RPC call completes without errors (or errors are silently caught by the frontend's try/catch).

**Root cause**: `hermes.scope` does not exist. Verify:
```bash
systemctl --user is-active hermes.scope
# → "inactive" or "unknown" → scope was never created
```

The script's `do_on()`/`do_off()` exit with error messages ("Unit hermes.scope is not active"), but the desktop frontend's `requestGateway()` fallback silently catches the exception — the user sees a working button icon but no actual internet blocking.

**Fix**: Launch Hermes inside a scope:
```bash
systemd-run --user --scope --unit=hermes --same-dir --collect hermes gui
```
Or use the wrapper: `~/.hermes/scripts/hermes-scope.sh gui`

After this, `systemctl --user is-active hermes.scope` shows "active" and netcut works.

### Bare `hermes gui` — why it doesn't work

When launched as `hermes gui` (no systemd-run), Hermes processes scatter across multiple cgroups:
```
app-hermes-XXXX.scope   — main process
app-org.chromium-XXXX.scope  — Electron/Chromium
vte-spawn-XXXX.scope    — terminal/slash_workers
```
`IPAddressDeny` on `hermes.scope` doesn't exist, and even if it did, Chromium and child processes are in separate scopes — the BPF filter wouldn't cover them. Only `systemd-run --scope` puts the full process tree under one cgroup.
