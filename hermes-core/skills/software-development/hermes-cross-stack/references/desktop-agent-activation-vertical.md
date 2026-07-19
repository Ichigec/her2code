# Desktop Agent Activation — Verified Vertical (2026-07-03)

End-to-end verified flow for agent preset switching in the Hermes Desktop GUI.
All code locations confirmed by `read_file` against actual source.

## The Activation Vertical

```
User clicks P3/Claw/P2 button (statusbar)
  → desktop-controller.tsx: switchAgentPreset(presetId)
    → $activeAgentPresetId.set(presetId)  [optimistic UI update]
    → requestGateway('agents.activate', { id, session_id? })
      → tui_gateway/server.py:3266  agents.activate handler
        → If session exists:
            _agent_overrides[session_key] = agent_id
            apply_agent(agent_obj, agent_def)  [immediate]
            _emit("session.info", session_id, info)  [with agent_id]
        → If no session (fresh draft):
            _agent_overrides["__pending_desktop__"] = agent_id  [staging]
      ← Returns { activated, label, emoji, pending: bool }
    → On success: $activeAgentPresetId stays
    → On error: $activeAgentPresetId.set('')  [revert]
```

## Key Files & Locations

| Component | File | Lines | Notes |
|---|---|---|---|
| `switchAgentPreset()` | `apps/desktop/src/app/desktop-controller.tsx` | 253-285 | No bail-out for missing session. Optimistic UI + RPC. Must add `plan2/` and `plan3/` prefix fallback. |
| `agents.activate` RPC | `tui_gateway/server.py` | 3266-3325 | Supports `__pending_desktop__` staging. Emits `session.info`. |
| `session.create` transfer | `tui_gateway/server.py` | 3141-3147 | Pops `__pending_desktop__` → session key. |
| `_make_agent` override | `tui_gateway/server.py` | 2727-2728 | `_apply_agent_override_if_any(agent, key)`. |
| `useMessageStream` agent_id | `apps/desktop/src/app/session/hooks/use-message-stream.ts` | 685-687 | Sets `$activeAgentPresetId` from `payload.agent_id`. Does NOT clear on empty string. |
| `ActiveAgentIndicator` | `apps/desktop/src/app/chat/active-agent-indicator.tsx` | 1-70 | Reads `$activeAgentPresetId`. Shows emoji + label badge. |
| `SubagentDropdown` | `apps/desktop/src/app/shell/subagent-dropdown.tsx` | 1-122 | Groups agents by model. `onSwitchPreset` callback. |
| Statusbar items | `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx` | 238-319 | `coreLeftStatusbarItems` includes P2/P3/Claw/observer/presets. |
| Agent discovery | `agent/agents.py` | 399-419 | `rglob("*.md")` from `~/.hermes/agents/`. ID = relative path without extension. |
| `load_agents()` | `agent/agents.py` | 476-485 | Merges built-in < disk < config. Cached (`_registry_cache`). Use `force=True` to refresh. |

## Agent Directory Structure

```
~/.hermes/agents/
├── *.md                    # root-level agents (general.md, plan2.md, plan3.md, ...)
├── plan2/                  # Plan2 sub-agents (Kimi K2.7)
│   ├── requirements-agent.md    → ID: plan2/requirements-agent
│   ├── techlead-agent.md        → ID: plan2/techlead-agent (v3 sub-orchestrator)
│   ├── developer-agent.md       → ID: plan2/developer-agent
│   └── ... (20 agents total)
├── plan3/                  # Plan3 sub-agents (Qwen3.6 + Nex + AgentWorld)
│   ├── requirements-agent.md    → ID: plan3/requirements-agent
│   └── ... (18 agents total)
├── dev/                    # Developer stage agents
│   ├── dev-skeptic.md
│   ├── dev-pragmatic.md
│   ├── dev-creative.md
│   └── dev-maverick.md
├── review/                 # Review swarm agents
│   ├── style-reviewer.md
│   ├── bug-reviewer.md
│   └── ...
└── registry.json           # Config-level agent overrides (model, provider, tools)
```

## Known Gaps

### 1. ChatHeader returns null for fresh draft (UNFIXED)

`chat/index.tsx` line 126-128:
```tsx
if (!selectedSessionId && !activeSessionId && !isRoutedSessionView) {
  return null  // ActiveAgentIndicator is INSIDE ChatHeader, so it's never shown
}
```

**Impact:** When user selects an agent preset before starting a conversation, no indicator appears.

### 2. PLAN2_AGENTS model labels (FIXED 2026-07-03)

All 20 Plan2 agents now correctly use `plan2/` prefixed IDs and Kimi K2.7 model labels.
`groupByModel()` updated with `kimi` key in `MODEL_GROUPS`.

### 3. Claw button has no dropdown (UNFIXED)

`desktop-controller.tsx`: `clawOrchestratorItem` is `variant: 'action'` — plain button, no model selection.

## Critical Pitfalls (learned the hard way)

### `groupByModel` silently hides agents

**Symptom:** Dropdown opens, shows only "🚀 Full Cycle", no sub-agents visible.

**Cause:** `SubagentDropdown` groups agents by model name. `groupByModel()` checks:
```typescript
if (model.includes('qwen')) key = 'qwen3.6'
else if (model.includes('nex')) key = 'nex'
else if (model.includes('agentworld')) key = 'agentworld'
// MISSING: 'kimi' → falls to 'other' → MODEL_GROUPS['other'] doesn't exist → return null
```

**Fix:** Add the model key to BOTH `MODEL_GROUPS` dict AND `groupByModel()`:
```typescript
const MODEL_GROUPS = {
  'qwen3.6': { icon: '🧠', label: 'Reasoning — Qwen3.6' },
  'nex': { icon: '🤖', label: 'Coding — Nex-N2-mini' },
  'agentworld': { icon: '🔮', label: 'Simulation — AgentWorld' },
  'kimi': { icon: '☁️', label: 'Cloud — Kimi K2.7' },  // ← ADD THIS
}

function groupByModel(agents) {
  // ...
  else if (model.includes('kimi')) key = 'kimi'  // ← ADD THIS
  // ...
}
```

### `switchAgentPreset` rejects nested agent IDs

**Symptom:** Clicking a sub-agent in the dropdown does nothing (silent fail).

**Cause:** The known-preset check in `desktop-controller.tsx` doesn't recognize `plan2/` prefixed IDs:
```typescript
const known = agentPresets.some(p => p.id === presetId) ||
  ['general', 'build', 'plan', 'plan2', 'plan3', ...].includes(presetId)
// 'plan2/requirements-agent' is NOT in this list → known=false → return early
```

**Fix:** Add prefix fallback:
```typescript
const known = agentPresets.some(p => p.id === presetId) ||
  ['general', 'build', 'plan', 'plan2', 'plan3', ...].includes(presetId) ||
  presetId.startsWith('plan2/') ||
  presetId.startsWith('plan3/')
```

### Agent file line-number corruption

**Symptom:** Agent `.md` files have `1|1|1|---` instead of `---` in frontmatter.

**Cause:** `read_file` returns content with `N|` line-number prefixes. If this output is written back via `write_file` or piped through `sed`, the prefixes become part of the file.

**Fix:** Strip prefixes before writing:
```python
import re
prefix_re = re.compile(r'^(?:\d+\|)+')
new_lines = [prefix_re.sub('', line) for line in lines]
```

**Verify after creation:**
```bash
python3 -c "
with open('path/to/agent.md') as f:
    print(repr(f.readline()))  # Should be '---\\n', not '1|1|1|---\\n'
"
```

## Desktop Build Verification

After `npm run build`, the new code is packaged into `app.asar`. Verify:

```python
# Check dist/ (source build output)
with open('apps/desktop/dist/assets/index-*.js', 'rb') as f:
    data = f.read()
    print(f'plan2/ in dist: {data.count(b"plan2/")} times')

# Check app.asar (what Electron actually loads)
with open('apps/desktop/release/linux-arm64-unpacked/resources/app.asar', 'rb') as f:
    data = f.read()
    print(f'plan2/ in asar: {data.count(b"plan2/")} times')
```

If dist has the code but asar doesn't → rebuild failed. Check `npm run build` output for errors.

## Sub-orchestrator Pattern (Tech Lead v3)

An agent can become a sub-orchestrator by:
1. Setting `mode: primary` in frontmatter (not `subagent`)
2. Including `delegation` in `toolsets`
3. Being called via `delegate_task(role='orchestrator')`

This gives the agent the ability to spawn its own children (up to `max_spawn_depth=2`).

**Example: Tech Lead v3 manages Phase 6 Dev Pipeline:**
```
Orchestrator (depth 0)
  └─ Tech Lead v3 (depth 1, role='orchestrator')
       ├─ Developer: Skeptic (depth 2, leaf)
       ├─ Reviewer: Style (depth 2, leaf)
       ├─ Reviewer: Bug (depth 2, leaf)
       └─ ... (up to 5 parallel)
```

Tech Lead creates the plan (Phase 5), then executes it (Phase 6) by spawning
developers, managing escalation (Skeptic→Pragmatic→Creative→Maverick), running
Review Swarm (5 reviewers per PASS), and merging results.

Based on MetaGPT ProjectManager pattern (ICLR 2024) + hierarchical orchestration
(Google ADK, CrewAI).

## SubagentDropdown Pattern (reusable)

For any orchestrator that needs a dropdown of sub-agents grouped by model:

```tsx
// Define agent list with model grouping
const AGENTS: SubagentInfo[] = [
  { id: 'agent-id', label: 'Display Name', model: 'Model Name', modelIcon: '🧠' },
]

// Use in statusbar item
const dropdownItem = useMemo<StatusbarItem>(() => ({
  icon: <span className="text-[0.7rem] leading-none">🎯</span>,
  id: 'my-orchestrator',
  label: 'My',
  menuClassName: 'w-56',
  menuContent: <SubagentDropdown orchestrator="my-orch" agents={AGENTS} onSwitchPreset={switchAgentPreset} />,
  title: 'My Orchestrator',
  variant: 'menu'  // NOT 'action' — 'menu' opens dropdown
}), [switchAgentPreset])
```

`SubagentDropdown` automatically:
- Shows "🚀 Full Cycle" button (activates orchestrator itself)
- Groups agents by model key (qwen3.6, nex, deepseek, kimi, agentworld)
- Renders group headers with icon + label
- Calls `onSwitchPreset(agentId)` on click

**CRITICAL:** Every model string used in `SubagentInfo[]` must have a matching key
in `MODEL_GROUPS` and `groupByModel()`. Unmatched models are silently dropped.
