# Observer Panel Frontend — Data Flow & Architecture

## Architecture

```
ObserverPanel (React, statusbar dropdown)
    │
    ├── $observerSessions atom — observer-tagged sessions from state.db
    │   ↑ populated by refreshObserverSessions() in desktop-controller.tsx
    │   ↑ fetches via listAllProfileSessions(..., {source: 'observer'})
    │
    └── /api/observers/recent REST endpoint — Neo4j findings (AuditFindings + CriticFindings)
        ↑ called via window.hermesDesktop.api() or slash.exec('observer_json')
```

## API Approaches Tried (in order of increasing reliability)

### 1. `window.hermesDesktop.api()` — RECOMMENDED
```ts
window.hermesDesktop.api<ObserverData>({
    path: `/api/observers/recent?limit=20&session_id=${sessionId}`,
    timeoutMs: 10000
})
```
Goes through Electron IPC → main process → HTTP. No CORS issues.
Requires endpoint in `public_paths.py` for unauthenticated access.

### 2. `fetch()` — BLOCKED by CORS
```ts
fetch(`http://127.0.0.1:9120/api/observers/recent?session_id=${sessionId}`)
```
Dashboard returns `access-control-allow-origin: http://localhost:5174` only.
Electron renderer uses `file://` or `app://` origin → CORS rejection.

### 3. `slash.exec` RPC — RELIABLE but JSON-special
```ts
requestGateway<{output: string}>('slash.exec', {
    session_id: sessionId,
    command: 'observer_json'
})
```
Uses gateway WebSocket. No CORS, no auth issues. Requires:
- `observer_json` as alias in `commands.py`
- JSON-specific handler in `cli.py` that uses `sys.stdout.write()`
- Client-side parsing: strip ANSI codes, parse JSON

### 4. XHR (XMLHttpRequest) — WORKS if public
```ts
const xhr = new XMLHttpRequest()
xhr.open('GET', `http://127.0.0.1:9120/api/observers/recent?...`)
xhr.send()
```
Less strict CORS than `fetch()` in Electron context, but still unreliable.

## Rebuild Cycle (TypeScript changes)

```bash
cd apps/desktop
npm run pack   # tsc → vite build → electron-builder → app.asar
# Then restart: hermes gui
```

Key file: `release/linux-arm64-unpacked/resources/app.asar` — the Electron app loads from this archive.
Check `app.asar` timestamp to verify rebuild succeeded.
Check compiled JS with: `strings app.asar | grep observer`

## Statusbar Item Pattern

```tsx
const observerItem = useMemo<StatusbarItem>(() => ({
    icon: <Eye className="size-3" />,
    id: 'observer-panel',
    menuClassName: 'w-64',
    menuContent: <ObserverPanel sessionId={activeSessionId} requestGateway={requestGateway} />,
    title: 'Observer activity',
    variant: 'menu'  // renders as dropdown trigger in statusbar
}), [activeSessionId, requestGateway])  // re-create when session or gateway changes
```

Passed to `useStatusbarItems({observerItem, ...})` which inserts it into `coreLeftStatusbarItems`:
```ts
const coreLeftStatusbarItems = [
    {id: 'command-center', ...},
    {id: 'gateway-health', ...},
    {id: 'agents', ...},
    {id: 'cron', ...},
    ...(observerItem ? [observerItem] : []),    // ← inserted here, left of Agents
    ...(agentPresetsItem ? [agentPresetsItem] : []),
    ...quickAgentItems
]
```

## Finding click → chat insert

When a finding is clicked, insert it into the chat composer:
```ts
const insertIntoChat = (text: string) => {
    const el = document.querySelector('[data-composer="true"]') as HTMLTextAreaElement | null
    if (el) {
        el.value = (el.value ? el.value + '\n' : '') + text
        el.focus()
        el.dispatchEvent(new Event('input', { bubbles: true }))
    }
}
```
User can then send the finding as a message and discuss it with the agent.
