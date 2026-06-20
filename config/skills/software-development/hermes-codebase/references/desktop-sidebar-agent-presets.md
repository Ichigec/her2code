# Desktop Sidebar: Agent Presets Section

Exact working code for adding an `AgentPresetsSection` between Sessions and Cron in `apps/desktop/src/app/chat/sidebar/index.tsx`. Built and type-checked June 2026.

## Location

Between sessions (ends ~line 791) and cron (starts ~line 821):

```tsx
        // Sessions section ends
        )}

        // ← INSERT AGENT PRESETS HERE ←

        // Cron section starts
        {sidebarOpen && !trimmedQuery && cronJobs.length > 0 && (
          <SidebarCronJobsSection ... />
```

## Store Addition (`store/layout.ts`)

Add **one** storage key, one atom, one persist subscription, and one setter — following the exact same pattern as `sidebarCronOpen`:

```ts
// Storage key (next to SIDEBAR_CRON_OPEN_STORAGE_KEY)
const SIDEBAR_PRESETS_OPEN_STORAGE_KEY = 'hermes.desktop.sidebarPresetsOpen'

// Atom (next to $sidebarCronOpen — default TRUE so presets are visible)
export const $sidebarPresetsOpen = atom(storedBoolean(SIDEBAR_PRESETS_OPEN_STORAGE_KEY, true))

// Persist subscription (next to $sidebarCronOpen.subscribe)
$sidebarPresetsOpen.subscribe(open => persistBoolean(SIDEBAR_PRESETS_OPEN_STORAGE_KEY, open))

// Setter (next to setSidebarCronOpen)
export function setSidebarPresetsOpen(open: boolean) {
  $sidebarPresetsOpen.set(open)
}
```

Import `$sidebarPresetsOpen` and `setSidebarPresetsOpen` in the sidebar's import block from `@/store/layout`.

## Sidebar Import Additions

Add to existing import block in `sidebar/index.tsx`:

```tsx
  $sidebarPresetsOpen,
  // ...
  setSidebarPresetsOpen,
```

Also ensure `DisclosureCaret` is imported (usually already present from existing sections):
```tsx
import { DisclosureCaret } from '@/components/ui/disclosure-caret'
```

## Actual Section Code

Uses the **exact same pattern** as `SidebarCronJobsSection` header:

```tsx
{sidebarOpen && !trimmedQuery && onSwitchPreset && (
  <SidebarGroup className="shrink-0 p-0 pb-1">
    <div className="group/section flex shrink-0 items-center justify-between pb-1 pt-1.5">
      <button
        className="group/section-label flex w-fit items-center gap-1 bg-transparent text-left leading-none"
        onClick={() => setSidebarPresetsOpen(!presetsOpen)}
        type="button"
      >
        <SidebarPanelLabel>{'Agent Presets'}</SidebarPanelLabel>
        <span className="text-[0.6875rem] font-medium text-(--ui-text-quaternary)">
          {String(AGENT_PRESETS.length)}
        </span>
        <DisclosureCaret
          className="text-(--ui-text-tertiary) opacity-0 transition group-hover/section-label:opacity-100"
          open={presetsOpen}
        />
      </button>
    </div>
    {presetsOpen && (
      <div className="flex flex-col gap-px px-1 pb-1">
        {AGENT_PRESETS.map(preset => (
          <button
            key={preset.id}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-(--ui-text-secondary) hover:bg-(--ui-control-hover-background) hover:text-foreground"
            onClick={() => onSwitchPreset(preset.id)}
            type="button"
          >
            <span className="text-[0.7rem]">{preset.emoji}</span>
            <span className="font-medium">{preset.label}</span>
            <span className="ml-auto text-[0.6rem] text-(--ui-text-tertiary)">{preset.model}</span>
          </button>
        ))}
      </div>
    )}
  </SidebarGroup>
)}
```

## Preset Definitions

Hardcoded in `sidebar/index.tsx` after `SIDEBAR_NAV` constant — can move to config later:

```ts
interface AgentPreset {
  id: string
  label: string
  emoji: string
  model: string
  toolsets: string[]
  reasoning: string
}

const AGENT_PRESETS: AgentPreset[] = [
  { id: 'build',   label: 'Build',   emoji: '🔨', model: 'sonnet-4',  toolsets: ['terminal','file','web','browser','delegation'], reasoning: 'high' },
  { id: 'plan',    label: 'Plan',    emoji: '🧠', model: 'gpt-5.5',   toolsets: ['web','file','search','browser'],             reasoning: 'medium' },
  { id: 'review',  label: 'Review',  emoji: '🔍', model: 'haiku-4',   toolsets: ['file','terminal','web'],                      reasoning: 'minimal' },
  { id: 'safe',    label: 'Safe',    emoji: '🛡️', model: 'haiku-4',   toolsets: ['web','file','search'],                        reasoning: 'minimal' },
]
```

## Props & Wiring

Add to `ChatSidebarProps` interface:

```tsx
onSwitchPreset?: (presetId: string) => void
```

Destructure in `ChatSidebar` function params, consume with `useStore($sidebarPresetsOpen)`.

In `desktop-controller.tsx`, wire the handler:

```tsx
onSwitchPreset={presetId => {
  void requestGateway('model.switch', { preset: presetId }).catch(() => undefined)
}}
```

## Pitfalls

- `SidebarPanelLabel` extends `React.ComponentProps<'span'>` — it has NO `label`, `meta`, `open`, or `onToggle` props. Only `children`, `className`, `dotClassName`. The label text goes as children. Use `DisclosureCaret` + a wrapping `<button>` for toggle behavior, exactly as `cron-jobs-section.tsx` does.
- Always verify with `npx tsc --noEmit` from `apps/desktop/` before declaring done.
- `SidebarGroup` and `SidebarGroupContent` are already imported from `@/components/ui/sidebar` — no new imports needed for those.
- **The `/agent` slash command needs a gateway handler.** The desktop controller inserts `/agent <preset>` into the composer, and when the user sends it, it goes through `gateway/run.py`, not `cli.py`. Without `_handle_agent_command` in gateway dispatch (~line 8200-8440 of `gateway/run.py`), the command silently falls through to the LLM as plain text — the preset switch never takes effect. The command definition in `hermes_cli/commands.py` and the CLI handler in `cli.py` are not enough for the desktop app.
- The gear icon (⚙️) on each preset row has no `onClick` handler — it shows a "coming soon" tooltip. It's intentionally non-functional pending preset configuration UI.
