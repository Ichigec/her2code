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

### DO NOT call `requestGateway` with a non-existent method

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

## Adding a Slash Command\n\nTwo files to touch:\n\n### 1. Register in `hermes_cli/commands.py`\n\n```python\nCommandDef(\"agent\", \"Switch agent preset (build|plan|review|safe)\", \"Configuration\",\n           args_hint=\"[build|plan|review|safe]\",\n           subcommands=(\"build\", \"plan\", \"review\", \"safe\")),\n```\n\nInsert alphabetically among existing entries in `COMMAND_REGISTRY`.\n\n### 2. Add handler in `cli.py`\n\nTwo changes in the `HermesCLI` class:\n\n**Dispatch** (in `process_command`, ~line 9060):\n```python\nelif canonical == \"agent\":\n    self._handle_agent_command(cmd_original)\n```\n\n**Handler method**:\n```python\ndef _handle_agent_command(self, cmd: str):\n    \"\"\"Switch agent preset — changes toolsets and reasoning atomically.\"\"\"\n    presets = {\n        \"build\": {\"label\": \"Build\", \"toolsets\": [\"terminal\",\"file\",\"web\",\"browser\",\"delegation\"], \"reasoning\": \"high\"},\n        \"plan\":  {\"label\": \"Plan\",  \"toolsets\": [\"web\",\"file\",\"search\",\"browser\"],             \"reasoning\": \"medium\"},\n        \"review\":{\"label\": \"Review\",\"toolsets\": [\"file\",\"terminal\",\"web\"],                      \"reasoning\": \"minimal\"},\n        \"safe\":  {\"label\": \"Safe\",  \"toolsets\": [\"web\",\"file\",\"search\"],                        \"reasoning\": \"minimal\"},\n    }\n    parts = cmd.strip().split(maxsplit=1)\n    name = parts[1].strip().lower() if len(parts) > 1 else \"\"\n    preset = presets.get(name)\n    if not preset:\n        print(f\"  Unknown agent '{name}'. Available: {', '.join(presets.keys())}\")\n        return\n\n    # Switch toolsets on both CLI and agent\n    self.enabled_toolsets = preset[\"toolsets\"]\n    if hasattr(self, \"agent\") and self.agent:\n        self.agent.enabled_toolsets = preset[\"toolsets\"]\n        from tools.registry import get_tool_definitions\n        self.agent.tools = get_tool_definitions(\n            enabled_toolsets=preset[\"toolsets\"],\n            quiet_mode=getattr(self.agent, \"quiet_mode\", False),\n        )\n\n    # Switch reasoning\n    self.reasoning_effort = preset[\"reasoning\"]\n    if hasattr(self, \"agent\") and self.agent:\n        self.agent.reasoning_effort = preset[\"reasoning\"]\n        from hermes_constants import parse_reasoning_effort\n        self.agent.reasoning_config = parse_reasoning_effort(preset[\"reasoning\"])\n\n    print(f\"  ✓ {preset['label']}  tools: {', '.join(preset['toolsets'])}  ·  reasoning: {preset['reasoning']}\")\n```\n\n### Rebuild after source changes\n\nAfter editing TypeScript, always rebuild before testing:\n\n```bash\ncd ~/.hermes/hermes-agent/apps/desktop && npm run build\n```\n\nThen restart the desktop app (`hermes gui`). Python changes take effect on next agent restart — no separate compile step needed (verify with `python3 -c \"import py_compile; py_compile.compile('cli.py', doraise=True)\"`).\n\n## Key Imports Already Available in sidebar/index.tsx

- `SidebarGroup`, `SidebarGroupContent`, `SidebarMenu`, `SidebarMenuItem`, `SidebarMenuButton` from `@/components/ui/sidebar`
- `SidebarPanelLabel` from `../../shell/sidebar-label`
- `DisclosureCaret` from `@/components/ui/disclosure-caret`
- `Codicon` from `@/components/ui/codicon`
- `cn` from `@/lib/utils`
