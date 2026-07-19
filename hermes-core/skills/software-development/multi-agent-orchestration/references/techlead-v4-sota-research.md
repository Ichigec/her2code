# Tech Lead v4 — SOTA Coding Agent Research & Improvement Proposals

Research conducted 2026-07-03. Deep analysis of plan2/plan3 Tech Lead architecture
against SOTA coding agent papers (2024-2026). Identifies 7 structural blind spots
and proposes v4 improvements with academic backing.

## SOTA Papers Analyzed

| Paper | Year | Key Insight | Tech Lead Application |
|-------|------|-------------|----------------------|
| **DynTaskMAS** (arXiv:2503.07675) | 2025 | Dynamic Task Graph Generator (DTGG) — DAG updates in real-time | Replace static DAG with live, feedback-responsive DAG |
| **Anthropic 2026 Agentic Coding Trends** | 2026 | Context engineering = 55% faster, 40% fewer errors | Context as first-class system with layers, compaction, routing |
| **Google ADK** (developers.googleblog.com) | 2025 | Context stack: compaction + routing + governance | 4-layer context model (static/dynamic/episodic/semantic) |
| **SpecRover** (ICSE 2025, arXiv:2408.02232) | 2025 | Specification inference from existing code before planning | Tech Lead reads code, infers current spec, creates delta-based StandardWork |
| **RLEF** (ICML 2025) | 2025 | RL on execution feedback → 18-30% better iterative improvement | Close the feedback loop: test results → plan revision |
| **Loop Engineering** (explainx.ai) | 2026 | "A loop with nothing to push back is the agent agreeing with itself" | 5 loop guards: max iterations, max retries, budget cap, loop detection, plan revision |
| **Darwin Godel Machine** (ICLR 2026) | 2026 | Agent modifies own code → 40%+ improvement over static | Tech Lead self-evolution: Neo4j metrics → pattern mining → self-modification |
| **AgentCoder** (arXiv:2312.13010) | 2023 | Adversarial test designer (no impl access) → +23% coverage | Separate Test Designer agent from Developer |
| **SWE-agent** (2024) | 2024 | Agent-Computer Interface structure > tool selection | ACI Protocol: structured file/verify/navigate operations |
| **HyperAgent** (arXiv:2409.16299) | 2024 | 4 specialized agents: Planner, Navigator, Code Editor, Executor | Code Navigator agent provides semantic map before coding |
| **AutoCodeRover** (2024) | 2024 | AST-based code search, not grep | Interface compatibility check via AST parsing |
| **MetaGPT** (ICLR 2024) | 2024 | ProjectManager creates tasks + tracks progress (not just plans) | Tech Lead = sub-orchestrator (already in v3, validated) |
| **ChatDev** (2023) | 2023 | CTO dispatches to Programmer, reviews design | Review Swarm pattern (already in v3) |
| **OpenHands SDK** (arXiv:2511.03690) | 2025 | Event stream architecture, typed events, sandboxed execution | Typed Context Contracts (JSON schema) instead of free-form handoffs |
| **Microsoft Conductor** (May 2026) | 2026 | YAML deterministic + LLM adaptive hybrid | Tech Lead: deterministic DAG/gates + adaptive routing/revisions |

## 7 Structural Blind Spots (v3 → v4)

### 1. Static DAG vs Dynamic Reality
DAG is built in Phase 5, never updated in Phase 6. Developer finds new dependencies,
interface changes ripple, reuse opportunities discovered — DAG stays stale.
**Fix:** DynTaskMAS pattern — DAG as live JSON object with update protocol triggered by:
- Developer finds dependency not in DAG → add node + edge
- Interface change (Protocol modified) → recompute dependents
- Reuse potential > 0.7 → merge tasks
- Budget overrun > 150% → split task
- 3 consecutive failures → redesign StandardWork

### 2. Context Engineering — THE Differentiator
Anthropic 2026: context engineering = 55% faster, 40% fewer errors. Current system:
no context lifecycle management, no compaction, no routing. All agents get everything.
**Fix:** 4-layer context stack:
- Static (AGENTS.md, architecture) — cycle-wide, all agents
- Dynamic (StandardWork, DAG state, feedback) — per-phase, task-specific
- Episodic (Code Navigator bundle, test results) — per-task, developer + Jidoka
- Semantic (Neo4j graph, session history) — on-demand, Tech Lead + Navigator

Context budget per agent: Developer 50K, Jidoka 30K, Reviewer 20K, Tech Lead 100K.

### 3. Specification Drift
Tech Lead creates StandardWork from architecture doc (Phase 4) without reading existing
code. SpecRover shows: infer spec from code first, then create delta-based tasks.
**Fix:** Step 0.3 — Spec Inference: read_file target files, query Neo4j for callers,
compare current vs target spec, create StandardWork as delta (not "create from scratch").

### 4. Execution Feedback Loop is Open
Jidoka FAIL → developer escalation. But feedback never returns to Tech Lead for plan
revision. Same StandardWork template goes to next developer with same gaps.
**Fix:** Phase 6.5 — Feedback Loop Closure:
- Collect structured feedback per StandardWork (attempts, failures, tokens, coverage)
- Pattern detection: recurring failures → update StandardWork template
- Budget overruns → upgrade model for that complexity
- Import contract failures → add verification step to ALL handoffs
- Loop guards: max 3 iterations/SW, max 2× total retries, 150% budget cap

### 5. No Self-Evolution
Tech Lead saves Kaizen rules to memory but doesn't modify own process. Darwin Godel
Machine: self-modifying agents outperform static by 40%+.
**Fix:** Phase 11 — Self-Evolution:
- Save CycleMetric nodes to Neo4j per StandardWork
- Pattern mining queries: which complexity×model combos overrun? which fail?
- Self-modification: routing changes, template updates, new acceptance criteria
- Template evolution: StandardWork template gains Kaizen rules from last cycle

### 6. Interface Compatibility — grep is not enough
Current Jidoka checks imports via grep. Doesn't verify:
- Signature compatibility (parse(str) vs parse(bytes))
- Protocol conformance (all methods actually implemented)
- Return type contracts (Optional[T] but caller doesn't check None)
**Fix:** AST-based interface verification in Jidoka:
- `ast.parse()` → extract methods → compare against Protocol
- Check return type annotations match contract
- Runtime import test (not just grep): `python3 -c "from x import Y"`

### 7. Cost-Aware Execution Tracking
No mechanism to track real cost per StandardWork. Can't optimize routing across cycles.
**Fix:** Per-SW budget tracking in DAG state JSON:
```json
{
  "sw_id": "SW#3",
  "budget": {"tokens": 50000, "time": 120, "cost_usd": 0.15},
  "actual": {"tokens": 52000, "time": 145, "cost_usd": 0.16},
  "variance": {"tokens": "+4%", "time": "+21%"},
  "alert": "time_overrun"
}
```
Tech Lead monitors via delegate_task polling. Overrun > 120% → investigate + act.

## New Agents Proposed (v4)

| Agent | Role | Model | Toolsets | SOTA Source |
|-------|------|-------|----------|-------------|
| **Code Navigator** (#6n) | AST-aware semantic map before coding | kimi-k2.7-code | terminal, search_files, skills | HyperAgent Navigator, AutoCodeRover |
| **Test Designer** (#6t) | Adversarial tests without seeing impl | deepseek-v4-pro | file_ro, terminal | AgentCoder |
| **Integration Checker** | Per-module orphan detection (<30s) | kimi-k2.7-code | terminal, search_files | Devin continuous integration |

## Priority Matrix

| Priority | Improvement | Effort | Impact | Risk |
|:--------:|------------|:------:|:------:|:----:|
| P0 | Closed-Loop Feedback (6.5) | Medium | Critical | Low |
| P0 | Dynamic DAG | Medium | Critical | Medium |
| P1 | Context Engineering Stack | Medium | High | Low |
| P1 | Interface Compatibility (Jidoka) | Low | High | Low |
| P2 | Spec Inference | Low | Medium | Low |
| P2 | Self-Evolution Engine | High | High | Medium |
| P3 | Cost-Aware Tracking | Low | Medium | Low |

## Comparison: v2 → v3 → v4 → SOTA

| Capability | v2 | v3 | v4 (proposed) | SOTA |
|------------|:--:|:--:|:-------------:|:----:|
| DAG | Static | Static | Dynamic (DynTaskMAS) | Dynamic |
| Context | Free-form | JSON contracts | Context Engineering Stack | Google ADK |
| Spec | From arch | From arch | Spec Inference from code | SpecRover |
| Feedback | One-way | One-way | Closed-loop (RLEF) | RLEF |
| Interface check | grep | grep + call | AST + Protocol + Runtime | AutoCodeRover |
| Self-evolution | Kaizen memory | Kaizen memory | Neo4j metrics + self-mod | Darwin Godel |
| Cost tracking | None | None | Per-SW budget tracking | — |
| Loop guards | 3 retries | 3 retries | 5 guard types | Loop Eng |
| Plan revision | Never | Never | Pattern-triggered | Adaptive |
| Template evolution | Manual | Manual | Data-driven | Self-evolving |

## DAG State Schema (proposed)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "cycle_id": "string",
  "tasks": [{
    "sw_id": "string",
    "status": "pending|in_progress|pass|fail|blocked",
    "attempts": 0,
    "current_stage": "skeptic|pragmatic|creative|maverick",
    "budget": {"tokens": 0, "time": 0, "cost_usd": 0},
    "actual": {"tokens": 0, "time": 0, "cost_usd": 0},
    "feedback": [],
    "dag_updates": [],
    "dependencies": [],
    "dependents": []
  }],
  "patterns_detected": [],
  "plan_revisions": []
}
```

## Neo4j CycleMetric Schema (for self-evolution)

```cypher
CREATE (m:CycleMetric {
  cycle_id: $pid,
  sw_id: "SW#3",
  model: "kimi-k2.7-code",
  complexity: "L3",
  tokens: 52000,
  time_s: 145,
  attempts: 2,
  escalation: "Pragmatic",
  coverage: 87,
  verdict: "PASS",
  confidence: 0.82,
  navigator_reuse: 0.6,
  import_issues: 1,
  timestamp: timestamp()
})
```

Pattern mining queries:
```cypher
// Which complexity levels consistently overrun?
MATCH (m:CycleMetric) WHERE m.tokens > m.budget * 1.5
RETURN m.complexity, avg(m.tokens), count(*) AS occurrences
ORDER BY occurrences DESC

// Which models are best for which tasks?
MATCH (m:CycleMetric)
RETURN m.model, m.complexity, avg(m.attempts) AS avg_attempts, avg(m.coverage) AS avg_cov
ORDER BY m.complexity, avg_attempts
```
