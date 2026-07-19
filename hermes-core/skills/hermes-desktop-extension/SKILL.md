---
name: hermes-desktop-extension
description: "Extend the Hermes Electron desktop app: add sidebar sections, UI elements, safe RPC handlers."
version: 1.0.0
category: software-development
metadata:
  hermes:
    tags: [hermes, desktop, electron, sidebar, extension, ui, react]
    related_skills: [hermes-agent]
---

# Hermes Desktop Extension

Extend the Hermes Electron desktop app (`apps/desktop/`) — sidebar sections, UI controls, and safe gateway RPC patterns.

## Architecture

```
apps/desktop/
├── src/
│   ├── store/layout.ts          ← sidebar state (atoms + localStorage persistence)
│   ├── app/
│   │   ├── desktop-controller.tsx  ← main controller, wires sidebar + chat + overlays
│   │   ├── chat/sidebar/index.tsx   ← sidebar UI (sessions, cron, nav items)
│   │   ├── shell/                  ← shell chrome (titlebar, statusbar, menus)
│   │   └── settings/               ← settings pages
│   └── components/ui/              ← shared UI primitives
```

## Adding a Sidebar Section

### 1. Add state to `store/layout.ts`

```ts
// Storage key
const SIDEBAR_PRESETS_OPEN_STORAGE_KEY = 'hermes.desktop.sidebarPresetsOpen'

// Atom (default true = open on first visit)
export const $sidebarPresetsOpen = atom(storedBoolean(SIDEBAR_PRESETS_OPEN_STORAGE_KEY, true))

// Persist subscription
$sidebarPresetsOpen.subscribe(open => persistBoolean(SIDEBAR_PRESETS_OPEN_STORAGE_KEY, open))

// Setter
export function setSidebarPresetsOpen(open: boolean) {
  $sidebarPresetsOpen.set(open)
}
```

### 2. Add section to `chat/sidebar/index.tsx`

Import the new state, then insert the section in the sidebar JSX tree. The pattern:

```tsx
{sidebarOpen && !trimmedQuery && (
  <SidebarGroup className="shrink-0 p-0 pb-1">
    <div className="group/section flex shrink-0 items-center justify-between pb-1 pt-1.5">
      <button
        className="group/section-label flex w-fit items-center gap-1 bg-transparent text-left leading-none"
        onClick={() => setSidebarPresetsOpen(!presetsOpen)}
        type="button"
      >
        <SidebarPanelLabel>{'Section Title'}</SidebarPanelLabel>
        <span className="text-[0.6875rem] font-medium text-(--ui-text-quaternary)">
          {String(itemCount)}
        </span>
        <DisclosureCaret
          className="text-(--ui-text-tertiary) opacity-0 transition group-hover/section-label:opacity-100"
          open={presetsOpen}
        />
      </button>
    </div>
    {presetsOpen && (
      <div className="flex flex-col gap-px px-1 pb-1">
        {/* Row items with hover highlight */}
        <div className="group/preset flex items-center gap-1 rounded-md pr-1 hover:bg-(--ui-control-hover-background)">
          <button className="flex flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-xs ..." onClick={...}>
            ...
          </button>
          {/* Optional gear icon, visible on row hover */}
          <button className="shrink-0 rounded p-0.5 opacity-0 group-hover/preset:opacity-100 ...">
            <Codicon name="gear" size="0.625rem" />
          </button>
        </div>
      </div>
    )}
  </SidebarGroup>
)}
```

### 3. Wire handler in `desktop-controller.tsx`

Add the `onXxx` prop to `<ChatSidebar>` and implement the handler.

### 4. Adding action buttons (ADD / DELETE) to an existing section

To add a **header ADD (+)** button or **per-row DELETE (trash)** buttons to a
section that already renders, use the patterns in the reference:

→ `references/sidebar-action-buttons.md` — reusable patterns for ADD header
button, two-stage DELETE confirmation (trash → "Delete"), protected-item
gating, state management (`pendingDelete`, `deletingId`), and wiring in
`desktop-controller.tsx`.

## Pitfalls

### `npm run build` does NOT update the running app

The desktop app loads from `release/linux-arm64-unpacked/resources/app.asar`, NOT from `dist/`. Running `npm run build` compiles TypeScript to `dist/` but does NOT repackage the asar. Always use `npm run pack` when you need the changes to take effect on the next `hermes gui` restart.

### New dashboard API endpoints need auth bypass

When adding a new GET endpoint to `web_server.py` that the desktop frontend calls via `window.hermesDesktop.api()`, add it to the public paths allowlist in `hermes_cli/dashboard_auth/public_paths.py`:

```python
PUBLIC_API_PATHS: frozenset[str] = frozenset({
    ...
    "/api/your/new/endpoint",
})
```

Without this, the endpoint returns 401 Unauthorized even for localhost calls through the Electron IPC bridge, because the auth header routing differs between REST and JSON-RPC paths.

### Agent activation: `switchAgentPreset` NOT `requestComposerInsert`

When building dropdown buttons that select agents (like sub-agent lists), NEVER use
`requestComposerInsert` — it only inserts text into the composer (`/agent plan3/dev-agent`)
and does NOT activate the agent. The user has to press Enter, which is slow and unreliable.

ALWAYS use `switchAgentPreset(agentId)` which calls `requestGateway('agents.activate', { id })`:
the agent is activated INSTANTLY on click, the statusbar updates, and the preset takes effect.

```tsx
// ✅ CORRECT — instant activation
onClick={() => switchAgentPreset('plan3/developer-agent')}

// ❌ WRONG — just types text, no activation
onClick={() => requestComposerInsert('/agent plan3/developer-agent')}
```

The `switchAgentPreset` function is available in `desktop-controller.tsx` (created via
`useCallback` around `requestGateway('agents.activate', ...)`). Pass it as a prop to any
component that needs to switch agents. For components inside dropdowns, name the prop
`onSwitchPreset` to match the convention used by `RolePanel`.

### SubagentDropdown pattern

For multi-agent orchestrator dropdowns where sub-agents are grouped by model type,
use the `SubagentDropdown` component pattern at `apps/desktop/src/app/shell/subagent-dropdown.tsx`.

It accepts:
- `orchestrator`: orchestrator agent ID (top-level "Full Cycle" button)
- `agents`: `SubagentInfo[]` array with `{id, label, model, modelIcon}`
- `onSwitchPreset`: callback for instant agent activation
- `footerActions`: optional `ReactNode` rendered below agent groups with a separator — use for profile controls, routing status, or additional actions

Agents are auto-grouped by model type (🧠 Reasoning / 🤖 Coding / 🔮 Simulation) with
section headers. The orchestrator gets a "🚀 Full Cycle" button at the top.

**FooterActions pattern (plan3 profile integration):**

```tsx
const plan3Item = useMemo<StatusbarItem>(() => ({
  icon: <span className="text-[0.7rem]">🧬</span>,
  id: 'plan3-subagents',
  label: 'P3',
  menuClassName: 'w-64',  // wider for footer content
  variant: 'menu',
  menuContent: (
    <SubagentDropdown
      orchestrator="plan3"
      agents={PLAN3_AGENTS}
      onSwitchPreset={switchAgentPreset}
      footerActions={
        <div className="flex flex-col gap-0.5 px-0.5 pb-0.5">
          <div className="px-2 py-0.5 text-[0.625rem] text-(--ui-text-quaternary)
                        uppercase tracking-wider">
            ⚙️ Profile &amp; Routing
          </div>
          <button
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs
                       hover:bg-(--ui-control-hover-background) transition-colors"
            onClick={() => {
              selectProfile('plan3')
              switchAgentPreset('plan3')
            }}
          >
            <span>🧠 Plan3 Profile</span>
            <span className="ml-auto text-[0.625rem] text-(--ui-text-tertiary)">agents-a1</span>
          </button>
          <div className="flex gap-1 px-2">
            <button onClick={() => selectProfile('plan3')}>📋 Profile</button>
            <button onClick={() => selectProfile('default')}>🏠 Default</button>
          </div>
          <div className="px-2 pt-0.5 text-[0.5625rem] text-(--ui-text-quaternary)">
            🔒 Routing enforced via pre_tool_call hook
          </div>
        </div>
      }
    />
  ),
  title: 'Plan3 Subagents — Fully Local',
}), [switchAgentPreset])
```

Full profile integration pattern with `selectProfile` import from `@/store/profile`:
`references/profile-button-integration.md`.
const plan3Item = useMemo<StatusbarItem>(() => ({
  icon: <span className="text-[0.7rem]">🧬</span>,
  id: 'plan3-subagents',
  label: 'P3',
  variant: 'menu',
  menuContent: (
    <SubagentDropdown
      orchestrator="plan3"
      agents={PLAN3_AGENTS}
      onSwitchPreset={switchAgentPreset}
    />
  ),
  title: 'Plan3 Subagents',
}), [switchAgentPreset])
```

### Quick-access buttons: `variant: 'action'`

For single-agent quick-access buttons (like Claw Orchestrator 🦞), use `variant: 'action'`
with `onSelect`. These are one-click — no dropdown:

```tsx
const clawItem = useMemo<StatusbarItem>(() => ({
  icon: <span className="text-[0.7rem]">🦞</span>,
  id: 'claw-orchestrator',
  onSelect: () => switchAgentPreset('claw-orchestrator'),
  title: 'Claw Orchestrator — 5-phase maintenance cycle',
  variant: 'action',
}), [switchAgentPreset])
```

Pass it to `useStatusbarItems` and add it to `coreLeftStatusbarItems` alongside other items.

### DO NOT use `execute_code` + `write_file` for file editing

`read_file()` through `execute_code` returns content WITH line number prefixes
(`1|content\n2|content`). When you pass this content to `write_file()`, the line numbers
become part of the file — corrupting it. This is how `desktop-controller.tsx` was
truncated from 1189 to 500 lines in this session.

ALWAYS use the `patch` tool for file edits — it operates on the real file on disk.
For creating new files, use `write_file` directly (not through `execute_code`).
For multi-file operations, use raw `terminal` with `cat > file << 'EOF'`.

```tsx
// ❌ CRASHES EVENT LOOP — breaks all buttons including Stop
onSwitchPreset={presetId => {
  void requestGateway('model.switch', { preset: presetId }).catch(() => undefined)
}}
```

An RPC call to a method the gateway doesn't recognize throws synchronously and can corrupt React's event handling. **ALL buttons stop working.**

Fix: do something safe and synchronous instead. For example, insert text into the composer:

```tsx
// ✅ Safe — inserts text into the chat input
onSwitchPreset={presetId => {
  import('@/app/chat/composer/focus').then(({ requestComposerInsert, requestComposerFocus }) => {
    requestComposerInsert(`/agent ${presetId}`)
    requestComposerFocus()
  }).catch(() => undefined)
}}
```

### SidebarPanelLabel has no `meta` prop

`SidebarPanelLabel` extends `React.ComponentProps<'span'>` — it only accepts `children`, `className`, `dotClassName`. Put the count in `children` as part of the label string: `label={`Section (${count})`}`.

### Agent preset buttons do NOT reflect active state

The 🧠 Agents dropdown and quick-access buttons (🤖 General, 🧠 Plan) are
**command inserters** — clicking inserts `/agent <id>` into the composer.
They do NOT indicate which agent preset is currently running. There is no
`activeAgentPreset` nanostore atom; the frontend has no knowledge of the
active preset. The actual switch happens when the user sends the `/agent`
message (handled by `cli.py::_handle_agent_command` → `apply_agent()`).

Full breakdown: `references/agent-preset-buttons.md`.

### Active preset indicator disappears by itself ($activeAgentPresetId)

`$activeAgentPresetId` (from `store/session.ts`) drives the statusbar 🧠 button
label. It is persisted to localStorage and updated from `session.info` events.
The backend's `_session_info()` (in `tui_gateway/server.py`) always included
`agent_id` in the payload — even as empty string when no override was active.
The frontend's `use-message-stream.ts` handler then set the atom to `""`,
**clearing the user's locally-tracked preset**.

**Root cause:** two bugs combined:
1. `_session_info()` unconditionally emitted `agent_id` (even empty)
2. `use-message-stream.ts` set `$activeAgentPresetId` on ANY string, including `""`

**Fix (two places):**
- `tui_gateway/server.py` `_session_info()`: only include `agent_id` key when non-empty
- `use-message-stream.ts`: guard with `&& payload.agent_id` — skip empty values

The backend's `_agent_overrides` dict (module-level in `tui_gateway/server.py`) is
**in-memory only** — it does NOT survive TUI gateway restarts. After a restart the
override is lost. The frontend fix above stops the UI from clearing its indicator,
but the backend must still receive a fresh `agents.activate` RPC to
re-establish the override. Full lifecycle: `references/agent-preset-lifecycle.md`.

### Section order in the sidebar

Sections render in JSX source order inside `<SidebarContent>`:
1. SIDEBAR_NAV (top nav buttons)
2. Search field
3. Search results
4. Pinned sessions
5. Sessions / Agents
6. **Your new section** ← insert here
7. Cron jobs
8. Profile rail

### Adding a new i18n key

When you add a new user-visible string to any component, you must add the key to
**all locale files** or `npx tsc -b` will fail with `TS2741` (property missing):

1. `apps/desktop/src/i18n/types.ts` — add the key to the interface
2. `apps/desktop/src/i18n/en.ts` — English (mandatory fallback)
3. `apps/desktop/src/i18n/ja.ts`, `zh.ts`, `zh-hant.ts` — other locales
4. Run `cd apps/desktop && npx tsc -b` to verify

### Rebuild after source changes

### `execute_code` + `write_file` CORRUPTS files — use `patch` or raw `terminal`

**CRITICAL — discovered 2026-07-01.** `read_file()` called through `execute_code` returns
content WITH line number prefixes (`1|content\n2|content\n`). When you pass this to
`write_file()`, the line numbers become part of the file — corrupting it silently.
`desktop-controller.tsx` was truncated from 1189 to 500 lines this way.

**ALWAYS use the `patch` tool for file edits** — it operates on the real file on disk
and never adds line numbers. For creating new files, use `write_file` directly (not
through `execute_code`). For multi-line insertions via terminal, use
`cat > file << 'EOF'` (heredoc never corrupts).

```python
# ❌ CORRUPTS FILES — line numbers become data
content = read_file(path).get("content","")  # "1|code\n2|code\n"
write_file(path, modified_content)           # writes line numbers!

# ✅ SAFE — operates on disk file
patch(path, old_string, new_string)
```

### `git checkout` loses uncommitted work — observerItem disappeared

The `observerItem` StatusbarItem was added AFTER the last git commit in plan2 work.
When `git checkout desktop-controller.tsx` was used to recover from corruption,
`observerItem` was silently lost because it existed only in the working tree.

**Full restore checklist:** `references/observer-restore-checklist.md` — imports,
code blocks, `useStatusbarItems` call, and `excludeSources` fix.

**Before `git checkout`:** always `git diff` first to see what will be lost.

### MODEL_GROUPS must include ALL model types

When building a `SubagentDropdown` with agents grouped by model, the
`MODEL_GROUPS` Record must include an entry for EVERY model type used by
the agent list. Missing groups silently don't render — agents simply disappear
from the dropdown with no error.

```tsx
// ❌ P2 agents are invisible — 'Kimi K2.7' has no group
const MODEL_GROUPS = {
  'qwen3.6':  { ... },
  'nex':      { ... },
  'agentworld': { ... },
}

// ✅ All model types covered
const MODEL_GROUPS = {
  'qwen3.6':  { icon: '🧠', label: 'Reasoning — Qwen3.6' },
  'nex':      { icon: '🤖', label: 'Coding — Nex-N2-mini' },
  'agentworld': { icon: '🔮', label: 'Simulation — AgentWorld' },
  'kimi':     { icon: '☁️', label: 'Cloud — Kimi K2.7' },
  'deepseek': { icon: '🔍', label: 'Cloud — DeepSeek V4' },
}
```

The `groupByModel()` function in SubagentDropdown maps `model.toLowerCase()` to
one of these keys. Unmatched models go to `'other'` which is NOT rendered.

## Subagent Dropdown Pattern

For multi-agent orchestrators that need a statusbar dropdown listing sub-agents grouped by model type (🧠 reasoning / 🤖 coding / 🔮 simulation), use the `SubagentDropdown` component. Full pattern with wiring instructions: `references/subagent-dropdown-pattern.md`.

## Adding a Statusbar Item with Dropdown Panel

Statusbar items live in the bottom bar (5px footer). Dropdown panels are
triggered from statusbar menu items — the same pattern used for 🧠 Agents,
👁 Observers, and the model selector.

### 1. Create the panel component

Create a new file in `app/shell/` (e.g., `observer-panel.tsx`). The component
renders inside a `DropdownMenuContent`. Follow the RolePanel pattern:

```tsx
import { useStore } from '@nanostores/react'
import { $yourAtom } from '@/store/session'

export function YourPanel() {
  const items = useStore($yourAtom)
  // ...render with Tailwind classes matching RolePanel styling
}
```

Key styling conventions: `w-52` / `w-56` width, `text-[0.6875rem]` for headings,
`text-xs` for rows, `text-(--ui-text-tertiary)` for muted text.

### 2. Add state atoms (if needed)

If your panel needs data from the backend, add atoms to `store/session.ts`:

```ts
export const $yourSessions = atom<SessionInfo[]>([])
export const YOUR_SECTION_LIMIT = 20
export const setYourSessions = (next: Updater<SessionInfo[]>) => updateAtom($yourSessions, next)
```

### 3. Add fetch + statusbar item in desktop-controller.tsx

**Fetch** — add a `refreshYourSessions` callback (follow `refreshCronSessions` pattern):

```ts
const refreshYourSessions = useCallback(async () => {
  try {
    const { sessions } = await listAllProfileSessions(YOUR_SECTION_LIMIT, 1, 'exclude', 'recent', 'all', {
      source: 'your-source-tag'
    })
    setYourSessions(prev => /* dedup */ sessions)
  } catch { /* non-fatal */ }
}, [])
```

Call it alongside other refreshes:
```ts
void refreshCronSessions()
void refreshYourSessions()  // ← add here
void refreshCronJobs()
```

**Statusbar item** — create a `useMemo<StatusbarItem>` with `variant: 'menu'` and `menuContent`:

```ts
const yourItem = useMemo<StatusbarItem>(() => ({
  icon: <YourIcon className="size-3" />,
  id: 'your-panel',
  label: undefined,
  menuClassName: 'w-52',
  menuContent: <YourPanel />,
  title: 'Your panel tooltip',
  variant: 'menu'
}), [])
```

Pass it to `useStatusbarItems`: `observerItem={yourItem}`.

### 4. Wire into useStatusbarItems

Add `yourItem?: StatusbarItem` to the `StatusbarItemsOptions` interface in
`shell/hooks/use-statusbar-items.tsx`. Destructure it from the function
params. Insert it into `coreLeftStatusbarItems` alongside the existing items:

```tsx
...(yourItem ? [yourItem] : []),
...(agentPresetsItem ? [agentPresetsItem] : []),
```

Add it to the dependency array at the bottom of the `useMemo`.

### 5. Filter from main session list

If your sessions use a dedicated `source` tag, add it to `excludeSources`:

```ts
excludeSources: ['cron', 'your-source-tag']
### Rebuild after source changes

## Pitfall: Statusbar dropdown panels hide errors on click

Statusbar items with `variant: 'menu'` render their `menuContent` inside a `DropdownMenuContent`. When the user clicks a button inside the panel (e.g., «Deep Analyze Now»), the dropdown **closes immediately**. Any error state (`setError()`) rendered inline inside the panel is invisible to the user.

**Fix:** always pair inline error state with a toast notification:

```tsx
import { notifyError, notify } from '@/store/notifications'

const runAction = async () => {
  try {
    const result = await requestGateway('some.method', params)
    if (result?.ok) {
      notify({ title: 'Success', message: `Got ${result.count} items` })
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e ?? 'Failed')
    setError(msg)
    notifyError(new Error(msg), 'Action failed')  // ← user sees this
  }
}
```

### DO NOT call requestGateway with possibly-undefined gateway

The `requestGateway` prop passed to statusbar panel components is typed optional (`requestGateway?:`). If the gateway connection drops or hasn't initialized yet, clicking a button silently returns early:

```tsx
const runAction = async () => {
  if (!requestGateway || !activeSid || analyzing) return  // ← silent!
```

Fix: guard each condition separately with a toast:

```tsx
if (!requestGateway) {
  notifyError(new Error('Gateway not connected'), 'Feature unavailable')
  return
}
if (!activeSid) {
  notifyError(new Error('No active session'), 'Feature unavailable')
  return
}
```

### Rebuild after source changes

### 6. Build

```bash
cd apps/desktop && npm run pack     # ~15s — builds dist + repackages asar
```

Restart Hermes desktop to see the new statusbar button.

`npm run build` alone (~3s) is useful for quick TypeScript check but does NOT update the running app.

### Pitfall: switchAgentPreset must use agents.activate RPC

The `switchAgentPreset` function in `desktop-controller.tsx` controls agent activation from statusbar buttons and dropdowns. It MUST call `requestGateway('agents.activate', { id: presetId })` for instant activation — NOT `requestComposerInsert('/agent ...')` which merely types text into the composer.

**Broken (composer text only):**
```tsx
void import('@/app/chat/composer/focus')
  .then(({ requestComposerInsert, requestComposerFocus }) => {
    requestComposerInsert(`/agent ${presetId}`)  // ❌ just types text
    requestComposerFocus()
  })
```

**Correct (instant RPC activation):**
```tsx
void requestGateway('agents.activate', { id: presetId }).catch(() => undefined)
```

**Guard clause pitfall:** Do NOT restrict `switchAgentPreset` to a hardcoded list of known agent IDs. Subdirectory agents (`plan3/developer-agent`) and dynamically created presets must pass through. The `agents.activate` RPC already validates on the server side.

### Pitfall: SubagentDropdown must use onSwitchPreset, not requestComposerInsert

The `SubagentDropdown` component receives an `onSwitchPreset` callback from the parent. It must call this directly — NOT fall back to `requestComposerInsert`. The `requestComposerInsert` path only inserts text and does NOT activate the agent.

**Correct:**
```tsx
export function SubagentDropdown({ orchestrator, agents, onSwitchPreset }: SubagentDropdownProps) {
  const handleSelect = (agentId: string) => {
    if (onSwitchPreset) { onSwitchPreset(agentId) }  // ✅ instant RPC activation
  }
}
```

### Deep dive: agent activation lifecycle

For the full root-cause analysis of why statusbar agent buttons required manual Enter, how `agents.activate` stages presets without an active session (`__pending_desktop__`), and how to keep the chat indicator in sync with `session.info.agent_id`, see:

→ `references/desktop-agent-activation-deep-dive.md`

### Pitfall: MODEL_GROUPS must include all model types

When SubagentDropdown groups agents by model, the `MODEL_GROUPS` map must cover every model in the agent lists. Missing entries (e.g., 'kimi' for plan2 agents) silently hide agents because the 'other' catch-all group is not rendered. Add an entry for every model type used in PLATFORM_AGENTS arrays.

- `SidebarGroup`, `SidebarGroupContent`, `SidebarMenu`, `SidebarMenuItem`, `SidebarMenuButton` from `@/components/ui/sidebar`
- `SidebarPanelLabel` from `../../shell/sidebar-label`
- `DisclosureCaret` from `@/components/ui/disclosure-caret`
- `Codicon` from `@/components/ui/codicon`
- `cn` from `@/lib/utils`

## SubagentDropdown Pattern

For model-grouped agent choice dropdowns in the statusbar with direct RPC activation via `switchAgentPreset`, see `references/subagent-dropdown-pattern.md`. Used in plan2/plan3 sub-agent selectors.

## Creating Backend Agent Files for a New Orchestrator Preset

When adding a new orchestrator (e.g., plan2, plan4), you need BOTH the frontend
dropdown AND backend agent files. The frontend `SubagentDropdown` calls
`switchAgentPreset('plan2/agent-name')` — the backend resolves this ID by
looking for `~/.hermes/agents/plan2/agent-name.md`.

### 1. Create the agent directory

```bash
mkdir -p ~/.hermes/agents/<preset>/
```

### 2. Create agent .md files

Each agent file has YAML frontmatter + markdown body. Copy from an existing
preset (e.g., `plan3/`) and replace `model` and `provider`:

```yaml
---
label: Plan2 · Requirements
description: Сборщик требований — задаёт уточняющие вопросы
mode: primary
model: kimi-k2.7-code           # ← change per preset
provider: custom:kimi           # ← change per preset
emoji: 📋
reasoning: high
toolsets: [clarify]
---
```

### 3. Update PLAN2_AGENTS in subagent-dropdown.tsx

Use the `plan2/` prefix for all agent IDs:

```tsx
{ id: 'plan2/requirements-agent', label: '📋 Requirements', model: 'Kimi K2.7', modelIcon: '☁️' }
```

### 4. Add prefix fallback to switchAgentPreset

The `known` check in `switchAgentPreset` must accept prefixed IDs:

```tsx
const known =
  agentPresets.some(p => p.id === presetId) ||
  ['general', 'build', 'plan', 'plan2', 'plan3', ...].includes(presetId) ||
  presetId.startsWith('plan2/') ||
  presetId.startsWith('plan3/')
```

**Critical — corrected by user 2026-07-03.** When creating a preset, do not
only copy phase-worker agents (requirements, developer, tester, etc.).
You MUST also include the orchestrator agents that manage other agents:

| Agent | Role |
|-------|------|
| `deep-plan-researcher` | Phase 3 sub-orchestrator — spawns 5-7 sub-agents, debate mode, 4 gates |
| `aflow-orchestrator` | Phase 0/10a — MCTS search for alternative workflows |
| `observer-orchestrator` | Manages Auditor/Critic/Idea-Generator/Knowledge-Curator |
| `enterprise-architect` | Phase 4b — cross-project conflict validation |
| `project-architect` | Phase 4c — codebase impact analysis |

These exist as `.md` files in `~/.hermes/agents/` (root level). Copy them
into the preset subdirectory with model/provider replacement, same as
phase workers. Add them to the `PLAN2_AGENTS` array at the TOP (before
phase workers) so they appear first in the dropdown.

### 6. Verify MODEL_GROUPS covers all model types

See the `MODEL_GROUPS must include ALL model types` pitfall above.

### 7. Build + restart

```bash
cd apps/desktop && npm run build   # or npm run pack for running app
```

## GUI Connection Architecture, Rebuild & Multi-Backend Testing

For the full connection model (Electron → Dashboard → Gateway 3-layer split),
local vs remote mode, `connection.json` format, rebuild pipeline, cross-arch
builds, running a second backend, and process verification checklist:

→ **`references/gui-connection-and-rebuild.md`**

Quick reference:
- **GUI connects to Dashboard** (port 9120, `/api/ws`), NOT to Gateway directly
- **Dashboard** provides session management + plugin hooks; **Gateway** (port 8643) provides OpenAI-compatible REST API
- **Local mode**: `connection.json` = `{"mode": "local"}` — Electron spawns Dashboard
- **Remote mode**: `{"mode": "remote", "remote": {"url": "...", "authMode": "token", "token": "..."}}`
- Rebuild: `npm run build` → `hermes gui --build-only --force-build` → restart GUI
- node-pty is the only native dep (prebuilds for macOS/Windows, compile on Linux)
- **Remote token**: NOT in `/api/status` — extract from HTML (`window.__HERMES_SESSION_TOKEN__`) or set via `HERMES_DASHBOARD_SESSION_TOKEN` env var. See reference for full extraction recipe.

## Pitfall: Marking tasks "completed" before real verification

**Critical workflow lesson (2026-07-07).** A 4-step plan (save → test → rebuild+test
→ rollback) was marked fully "completed" when in reality:

1. New GUI build was compiled but **never launched or tested** — the old process kept running
2. "Both backends tested" was claimed but GUI never connected to the second backend
3. "Rollback not needed" was asserted without knowing if the new build worked

**Rule:** A step is NOT complete until you have **evidence** — actual tool output showing
the thing works. For GUI testing this means:
- New process started from the new binary (check PID start time vs build timestamp)
- A test message sent through the GUI and a response received
- For multi-backend: GUI actually connected to each backend and responded

Health check (`curl /health` → `{"status":"ok"}`) is necessary but NOT sufficient.
It only proves the gateway process is alive, not that the full GUI → Dashboard →
Gateway → LLM chain works. The ONLY real end-to-end test is sending a message
through the GUI and getting a response back.

## Troubleshooting & Debugging

When the desktop app crashes, hangs, or behaves unexpectedly:

→ **`references/desktop-crash-investigation.md`** — log locations, diagnostic commands, crash signatures (OOM kill `exitCode=9`, boot loops, WebSocket timeouts, context compression failures), recovery steps, and prevention tips.

→ **`references/oom-kill-case-study-20260702.md`** — worked example of a kernel OOM kill chain during concurrent `llama.cpp` benchmarks, including how to correlate `render-process-gone`, `gui.log` WebSocket drops, and `journalctl`/`dmesg` kill records.

→ **`references/clarify-gate-crash.md`** — clarify-gate plugin blocks ALL action tools after gateway restart because in-memory `_sessions` dict is lost. User message containing "hermes" re-triggers ambiguity detection. Symptoms: terminal/write_file/patch all return "⛔ AMBIGUITY NOT RESOLVED". Fix: remove broad terms from `AMBIGUOUS_PRODUCTS` in `~/.hermes/plugins/clarify-gate/__init__.py`.
