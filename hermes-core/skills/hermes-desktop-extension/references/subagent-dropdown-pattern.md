# Subagent Dropdown Pattern

Full pattern for adding a model-grouped sub-agent dropdown to the Hermes desktop statusbar.

## Component: `subagent-dropdown.tsx`

```tsx
import { requestComposerFocus, requestComposerInsert } from '@/app/chat/composer/focus'

interface SubagentInfo {
  id: string
  label: string
  model: string       // e.g. 'Qwen3.6'
  modelIcon: string    // e.g. '🧠'
}

interface SubagentDropdownProps {
  orchestrator: string         // orchestrator agent ID (for "Full Cycle" button)
  agents: SubagentInfo[]       // sub-agent list
  onSwitchPreset?: (presetId: string) => void  // RPC activation callback
}
```

## MODEL_GROUPS must cover ALL model types

```tsx
const MODEL_GROUPS: Record<string, { icon: string; label: string }> = {
  'qwen3.6':  { icon: '🧠', label: 'Reasoning — Qwen3.6' },
  'nex':      { icon: '🤖', label: 'Coding — Nex-N2-mini' },
  'agentworld': { icon: '🔮', label: 'Simulation — AgentWorld' },
  'kimi':     { icon: '☁️', label: 'Cloud — Kimi K2.7' },
  'deepseek': { icon: '🔍', label: 'Cloud — DeepSeek V4' },
}
```

Missing groups → agents silently disappear. The `groupByModel()` function maps unrecognized models to `'other'` which is NOT rendered.

## Wiring in desktop-controller.tsx

```tsx
// 1. Import
import { SubagentDropdown, PLAN3_AGENTS } from './shell/subagent-dropdown'

// 2. Create StatusbarItem with variant:'menu' and onSwitchPreset
const plan3Item = useMemo<StatusbarItem>(() => ({
  icon: <span className="text-[0.7rem] leading-none">🧬</span>,
  id: 'plan3-subagents',
  label: 'P3',
  variant: 'menu',
  menuClassName: 'w-56',
  menuContent: (
    <SubagentDropdown orchestrator="plan3" agents={PLAN3_AGENTS} onSwitchPreset={switchAgentPreset} />
  ),
  title: 'Plan3 Subagents',
}), [switchAgentPreset])

// 3. Pass to useStatusbarItems
useStatusbarItems({ plan3SubagentsItem: plan3Item, ... })

// 4. Add to StatusbarItemsOptions interface in use-statusbar-items.tsx
// 5. Add to coreLeftStatusbarItems: ...(plan3SubagentsItem ? [plan3SubagentsItem] : []),
```

## Pitfall: ACTIVATION method

- `switchAgentPreset(agentId)` → `requestGateway('agents.activate', {id, session_id})` — INSTANT
- `requestComposerInsert('/agent ' + agentId)` → types text — USER MUST PRESS ENTER

## Pitfall: session_id required

`agents.activate` RPC needs `session_id` to apply to the current session. Without it, the override is stored for future sessions only (`__pending_desktop__`). Always pass `activeSessionId`.

## Pitfall: Subdirectory agents

Agents in `plan3/developer-agent.md` require `_load_disk_agents()` to use `rglob("*.md")` and derive `agent_id` from `path.relative_to(agents_dir)`. Without this, `agents.activate` returns 4018 "unknown agent".
