# Profile Button Integration in Statusbar Dropdowns

How to add Hermes profile switching to statusbar agent dropdowns (plan3 pattern, 2026-07-15).

## Architecture

Statusbar items with `variant: 'menu'` render `menuContent` inside a `DropdownMenuContent`.
The `SubagentDropdown` component now supports a `footerActions?: ReactNode` prop —
rendered below the agent list with a separator line.

## Imports Needed

```tsx
// In desktop-controller.tsx
import {
  $profileScope,
  ALL_PROFILES,
  normalizeProfileKey,
  selectProfile,        // ← add this
  refreshActiveProfile
} from '../store/profile'
```

## Pattern: Profile + Agent Combo Button

The primary action button switches BOTH profile and agent preset:

```tsx
<button
  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs
             hover:bg-(--ui-control-hover-background) transition-colors"
  onClick={() => {
    selectProfile('plan3')         // switch Hermes profile
    switchAgentPreset('plan3')     // activate orchestrator agent
  }}
  title="Switch to plan3 profile + activate plan3 orchestrator"
>
  <span>🧠 Plan3 Profile</span>
  <span className="ml-auto text-[0.625rem] text-(--ui-text-tertiary)">agents-a1</span>
</button>
```

## Pattern: Profile-Only / Default Buttons

Secondary buttons for fine-grained control:

```tsx
<div className="flex gap-1 px-2">
  <button
    className="flex-1 flex items-center justify-center gap-1 rounded-md px-1.5 py-1 text-[0.625rem]
               hover:bg-(--ui-control-hover-background) transition-colors
               text-(--ui-text-quaternary)"
    onClick={() => selectProfile('plan3')}
    title="Switch to plan3 profile only (does not change agent)"
  >
    📋 Profile
  </button>
  <button
    className="flex-1 ..."
    onClick={() => selectProfile('default')}
    title="Switch back to default profile"
  >
    🏠 Default
  </button>
</div>
```

## What selectProfile() Does

`selectProfile(name)` from `@/store/profile`:
1. Sets `$newChatProfile` to the target profile
2. Requests a fresh session (`requestFreshSession()`)
3. Calls `ensureGatewayProfile(target)` to open the backend

This means: after `selectProfile('plan3')`, the NEXT user message goes to the plan3 profile's backend, which uses `model.default=agents-a1-abliterated`.

## Dependency Array

`selectProfile` is an imported function (stable reference) — does NOT need to be in the `useMemo` dependency array. The `useMemo` only needs `[switchAgentPreset]`.

## Menu Width

When adding footer content, increase `menuClassName` from `'w-56'` to `'w-64'` to accommodate wider buttons and the routing status line.

## Rebuild

```bash
cd apps/desktop && npm run build   # ~4-5s for TypeScript check only
# For the running app to pick up changes:
cd apps/desktop && npm run pack    # ~15s — repackages asar
```
