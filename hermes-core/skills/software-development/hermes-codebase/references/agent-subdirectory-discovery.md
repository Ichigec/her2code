# Agent Subdirectory Discovery

**FIXED as of 2026-07-02.** Verified working 2026-07-03.

## Current behavior (working)

`agent/agents.py:_load_disk_agents()` (line 399) uses `rglob("*.md")` — recursively
finds agents in `~/.hermes/agents/` and all subdirectories. Agent IDs are derived
from the relative path:

```python
for path in sorted(agents_dir.rglob("*.md")):
    # e.g. plan3/developer-agent.md -> id: plan3/developer-agent
    rel = str(path.relative_to(agents_dir)).replace("\\", "/")
    agent_id = rel.rsplit(".", 1)[0].strip().lower()
```

Subdirectory agents (`plan2/*.md`, `plan3/*.md`) are discovered automatically.
No code changes needed to add new agent groups — just create the directory and
markdown files.

## Adding a new agent group

1. Create `~/.hermes/agents/<group>/<name>.md` with YAML frontmatter:
   ```yaml
   ---
   label: <Group> · <Name>
   model: <model-name>
   provider: <provider>
   mode: primary
   reasoning: high
   toolsets: [clarify]
   ---
   <system prompt body>
   ```
2. Backend auto-discovers via `rglob` — no backend code changes needed.
3. For desktop UI dropdown: add entries to `PLAN2_AGENTS` / `PLAN3_AGENTS` in
   `apps/desktop/src/app/shell/subagent-dropdown.tsx` with matching `<group>/<name>` IDs.
4. Ensure `switchAgentPreset` in `desktop-controller.tsx` recognizes the prefix:
   add `presetId.startsWith('<group>/')` to the known-check.

## Cache pitfall

`load_agents()` caches results in `_registry_cache`. After modifying agent files
on disk, restart the gateway/dashboard process or call `reset_cache()` before
`load_agents(force=True)`.

## Verification

```python
from agent.agents import load_agents, reset_cache
reset_cache()
agents = load_agents(force=True)
plan2 = [k for k in agents if k.startswith('plan2/')]
plan3 = [k for k in agents if k.startswith('plan3/')]
print(f'plan2/: {len(plan2)}, plan3/: {len(plan3)}')
```
