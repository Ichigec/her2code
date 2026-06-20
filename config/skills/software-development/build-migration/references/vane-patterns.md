# Vane Architecture Patterns → Build-Migration

Source: [Vane](https://github.com/ItzCrazyKns/Vane) — 35k★ AI-powered answering engine (TypeScript/Next.js).
Analyzed: 2026-06-11. Agent pipeline: Classifier → [Research || Widgets] → Writer.

## 9 Patterns Applicable to Build-Migration

### 1. Mode-Based Complexity (Speed / Balanced / Quality)

```typescript
maxIteration = mode === 'speed' ? 2 : mode === 'balanced' ? 6 : 25
```

Each mode changes: max iterations, planning requirement, tool call limits, research depth.

**Build-migration application:**
- `quick` — 1-2 phases for trivial changes (config edits, typos)
- `standard` — current 7-phase lifecycle
- `deep` — 7 phases + threat modeling, performance review, extended analysis

### 2. Classification-Triage (Pre-Phase Decision)

```typescript
const classification = await classify({query, chatHistory, enabledSources, llm});
// Output: {skipSearch, personalSearch, academicSearch, discussionSearch, widget flags, standaloneFollowUp}
```

Classifier determines what phases/actions are needed BEFORE entering the pipeline.

**Build-migration application:**
Add a pre-phase classifier that decides:
- Skip architecture for config-only changes?
- Skip deployment phase for artifact-only?
- Which security scanners to run?
- Is this a research task or implementation task?

### 3. Reasoning Preamble (Plan Before Every Action)

```typescript
// Balanced/Quality: MUST call __reasoning_preamble BEFORE every tool call
// Pattern: reason → act → reason → act → ... → done
// "Okay, the user wants to..." — natural language, no tool names
```

**Build-migration application:**
In Phase 4 (Implement), add micro-planning before each implementation step:
```
Micro-plan: "Implementing the health check endpoint. I'll add the route handler,
then the test, then verify both pass."
→ Write code
→ Micro-plan: "Tests pass. Now adding monitoring metrics for the endpoint."
→ Write code
```

### 4. Anti-Patterns in Prompts (`<mistakes_to_avoid>`)

```xml
<mistakes_to_avoid>
1. Over-assuming: Don't assume things exist — look them up
2. Verification obsession: Don't waste calls verifying existence
3. Endless loops: If 2-3 calls don't find it, report and move on
4. Ignoring task context: If user wants a calendar event, don't just search
5. Overthinking: Keep reasoning simple and tool calls focused
6. Skipping the reasoning step (balanced/quality only)
</mistakes_to_avoid>
```

Each mode has its own anti-pattern list.

**Build-migration application:**
Add `<anti_patterns>` section to each phase prompt:
- Phase 1 (Requirements): scope creep, over-engineering NFRs, skipping actors
- Phase 4 (Implement): batch-editing without tests, premature optimization, skipping checkpoint audits
- Phase 5 (Quality): self-reviewing own code, skipping SAST, ignoring warnings

### 5. Iteration Budget with Done Signal

```typescript
// Prompt includes: "Iteration 3 of 25. Call `done` when finished."
// Loop terminates: explicit `done` tool OR max iterations reached
```

**Build-migration application:**
Add explicit step tracking to Phase 4 (Implement) loop:
```
Step 2 of 7 — adding route handler
Step 3 of 7 — adding tests
...
Step 7 of 7 — final checkpoint audit → DONE
```

### 6. Sidecar Widgets (Parallel Checks)

```typescript
const [widgetOutputs, searchResults] = await Promise.all([widgetPromise, searchPromise]);
// Widgets run parallel to main flow, provide context, not cited
```

**Build-migration application:**
Run parallel during Phase 4 (Implement):
- Main flow: TDD implementation
- Sidecar A: SAST scan on current diff
- Sidecar B: Lint check
- Sidecar C: Complexity metrics

### 7. Action Registry (Contextual Phase Enablement)

```typescript
class ActionRegistry {
  static getAvailableActions({classification, mode, sources}): ResearchAction[]
  // Each action has enabled(config) → boolean
}
```

**Build-migration application:**
Phases/skills become contextually enabled:
- `architecture-design` — skip for config changes
- `deployment-operations` — skip for artifact-only
- `sast-audit` — skip for documentation-only changes

### 8. Block-Based Progress Streaming

```typescript
session.emitBlock({id, type: 'research', data: {subSteps: []}});
session.updateBlock(id, [{op: 'replace', path: '/data/subSteps', value: [...]}]);
```

**Build-migration application:**
Structured phase progress tracking with incremental updates, enabling:
- Real-time progress display
- Resumable workflows
- Audit trail of agent decisions

### 9. Tool Abstraction Layer

```typescript
interface ResearchAction<TSchema> {
  name: string;
  schema: z.ZodObject;                    // Runtime validation
  getToolDescription: (config) => string; // LLM-facing short description
  getDescription: (config) => string;     // Rich prompt description
  enabled: (config) => boolean;           // Contextual availability
  execute: (params, config) => Promise<ActionOutput>; // Implementation
}
```

**Build-migration application:**
Formalize skill interface:
- Each skill has: name, input schema, LLM prompt, enablement condition, execute function
- Skills are dynamically loaded based on task classification

## Related Analyses

### Alook (325★ AI workforce platform, April 2026)

[Alook](https://github.com/alookai/alook) is a collaboration layer for AI agents — daemon-based always-on agents with email, kanban, calendar, and persistent memory. Key patterns relevant to build-migration:

| Pattern | Alook Implementation | Build-Migration Application |
|---------|---------------------|---------------------------|
| **Timeline jsonl** | `.context_timeline/YYYY-MM-DD.jsonl` — grep-able task history | Replace complex session DB with grep-able per-day jsonl task records |
| **Session runner as detached process** | `spawn('bun', ['run', 'session-runner.ts', task])` — survives daemon restarts | Subagents as independent processes, not in-process delegate_task |
| **Plan-driven development** | `plans/` directory required BEFORE implementation — "I will reject your implementation without a plan" | Enforce `.hermes/plans/` as mandatory gate, not optional |
| **Memory index pattern** | `memory.md` (short facts, ≤140 chars) + `experiences/` (long workflows) | Structured memory: index file + experience directory instead of flat memory tool |
| **Agent backends as plugins** | `interface AgentBackend { execute(prompt, options): AgentSession }` — Claude/Codex/OpenCode/Hermes | Agent backend registry for build/general/research agents |
| **Daemon poll loop** | `while(true) { tasks = poll(); for(t of tasks) spawn(t); sleep(interval); }` | Autonomous mode: poll for tasks instead of webhook-only |

### General Agent 9-Phase Pipeline (Comparison)

The `general` agent extends the build agent's 7 phases with two research phases:

| Phase | Build (7) | General (9) |
|-------|-----------|-------------|
| 1 | Requirements | Requirements |
| 2 | Architecture | **Deep Analysis (Research)** ← NEW |
| 3 | Plan | Architecture |
| 4 | Implement | Plan |
| 5 | Quality | Implement |
| 6 | Deploy | Quality |
| 7 | Iterate | Deploy |
| 8 | — | **Post-Deploy Analysis** ← NEW |
| 9 | — | Iterate |

**Research phases (2 & 8):**
- Education graph query (Neo4j) for bootstrap context
- Research loop subagent via `delegate_task` with searchbox MCP (15 engines)
- Hypothesis formulation and testing
- Post-deploy metrics collection and hypothesis verification

**Agent definitions:**
- `build` agent: `~/.hermes/agents/build.md` (192 lines, system prompt for LLM)
- `build-migration` agent: `~/.hermes/agents/build-migration.md` (467 lines, migration guide for other platforms)
- `general` agent: `~/.hermes/personas/default.md` (the current persona)

## Priority for Build-Migration

| Priority | Pattern | Impact |
|----------|---------|--------|
| 🔴 HIGH | Mode-based complexity | Dramatically reduces overhead for small tasks |
| 🔴 HIGH | Classification-triage | Prevents running unnecessary phases |
| 🔴 HIGH | Anti-patterns in prompts | Directly improves agent behavior quality |
| 🔴 HIGH | Reasoning preamble | Ensures explainable, auditable implementation |
| 🟡 MEDIUM | Iteration budget + done | Prevents infinite loops, enables progress tracking |
| 🟡 MEDIUM | Sidecar widgets | Parallelizes quality checks, reduces latency |
| 🟡 MEDIUM | Action registry | Clean skill enablement architecture |
| 🟢 LOW | Block-based streaming | UI improvement, not functional |
| 🟢 LOW | Tool abstraction layer | Architectural cleanup, not urgent |
