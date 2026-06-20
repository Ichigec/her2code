# Memory Pre-Flight Check — Detailed Reference

> 5-layer scan. MANDATORY before Phase 1. Prevents re-discovery.
> From session `20260613_190349_08cd2b` — 16-25h wasted on known facts.

## The 5 Layers

### 1. Context Layer — `read_file("~/.hermes/AGENTS.md")`
What it contains: environment, global pitfalls, port maps, tool locations, build commands.
**This session's failure:** AGENTS.md had `api_server.port: 8643` but was never read.
Result: built `unified_proxy.py` to proxy to LiteLLM → Qwen, when Hermes Gateway
was already configured.

### 2. Project Layer — `read_file("~/dev/codemes/<project>/AGENTS.md")`
Per-project: tech stack, specific pitfalls, build commands, key files.
**If missing:** ask user 6 questions before starting work:
1. Language/stack? (Kotlin/Compose? Python? TypeScript?)
2. Where deployed? (phone? server? Docker?)
3. Ports needed? (avoid conflicts with existing projects!)
4. Build commands? (`./gradlew assembleDebug`? `npm build`?)
5. Dependencies on other projects? (LiteLLM? OpenCode+?)
6. Existing codebase? Where?

### 3. Procedural Layer — `skill_view("<relevant-skill>")`
Workflows, how-to, API endpoints. **28 skills exist but skill-router was OFF.**
Enable: `HERMES_SKILL_ROUTER=1` or manually `skill_view()` for the task domain.

### 4. Relational Layer — Neo4j search
```
MATCH (p:Project {name: "<project>"})-[:HAS_PITFALL]->(pit:Pitfall)-[:SOLVED_BY]->(sol:Solution)
RETURN pit.title, sol.description
```
Neo4j schema: `(:Project)-[:USES]->(:Technology)`, `(:Project)-[:HAS_PITFALL]->(:Pitfall)-[:SOLVED_BY]->(:Solution)`.

### 5. Session Layer — `session_search("<keywords>")`
FTS5 over SQLite state.db. Past decisions, patterns, pitfalls encountered.

## Root Cause Over Band-Aids

User's explicit rule: when a symptom appears, find the ROOT CAUSE, don't patch.
Example from this session:
- **Symptom:** Qwen doesn't know it's Hermes
- **Band-aid (rejected):** Add system prompt "You are Hermes" in ChatViewModel.kt
- **Root cause:** Hermes Gateway API not running (port conflict with proxy)
- **Fix:** Kill proxy, launch `hermes gateway run` on 8643

**The orchestrator's job:** when a sub-agent proposes a band-aid, escalate to Phase 2
(System Analysis) or Phase 6.5 (Verification Gate). Do NOT accept cosmetic fixes.

## Workspace Convention

All projects live under `~/dev/codemes/`. Each has its own `AGENTS.md`.
The universal `~/dev/codemes/AGENTS.md` holds shared environment config.
`~/.hermes/AGENTS.md` holds cross-cutting conventions and lifecycle rules.

**File placement rule (enforced by `enforce-workspace.py` hook):**
```
write_file / patch allowed ONLY in:
  ~/dev/codemes/   — workspace projects
  ~/.hermes/        — config, skills, agents, hooks
  /tmp/             — temporary files
  ~/dev/Opencode/   — Android sources (legacy)
  ~/cursor/         — OpenCode+ project
```

## Quick Pre-Flight Script (orchestrator runs this mentally)

1. `read_file(~/.hermes/AGENTS.md)` — scan Known Pitfalls table
2. Detect project from user message keywords
3. `read_file(~/dev/codemes/<project>/AGENTS.md)` — project pitfalls
4. `skill_view(<relevant>)` — load procedural knowledge
5. `session_search(<keywords>)` — past experience
6. Pass ALL findings in `context` field of `delegate_task`
