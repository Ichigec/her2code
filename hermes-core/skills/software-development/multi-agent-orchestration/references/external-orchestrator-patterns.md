# External Orchestrator Patterns: Claude Code, Cursor IDE, Codex, L-TPS

Research session 2026-06-24. Detailed source files: `/home/user/coding_agent_architecture_research.md`, `/home/user/research-multi-agent-best-practices.md`.

---

## 1. Claude Code — Coordinator 4-Phase

**4-phase workflow (the gold standard for plan2):**

```
Phase 1: RESEARCH     Phase 2: SYNTHESIS    Phase 3: IMPLEMENT    Phase 4: VERIFY
[Worker A] [Worker B] → [COORDINATOR]     → [Worker C] [Worker D] → [Verify E] [Verify F]
 (parallel, read-only)  (не делегирует       (parallel, write)      (adversarial testers —
                         понимание!)                                "твоя работа НЕ подтвердить,
                                                                   а СЛОМАТЬ")
```

**Key rules:**
- Coordinator MUST synthesize itself — never delegate understanding
- Explore Agent: read-only, Haiku (cheap), codebase search
- Verification Agent: adversarial tester, 6 required verification steps, anti-rationalization rules
- Continue vs Spawn decision: high context overlap → continue; low → fresh spawn
- CLAUDE.md memory hierarchy (4 levels): managed → user → project → local, @include directives, 40K char limit

**Context management:**
- Static/dynamic prompt boundary with caching
- 3 compaction strategies: full, partial(recent), partial(older) + micro-compaction
- 8 required summary sections: Primary Request, Key Concepts, Files/Code, Errors/Fixes, Problem Solving, All User Messages, Pending Tasks, Current Work

**Tool safety:**
- Permission-first: 4 modes (default/plan/bypass/auto)
- Fail-closed defaults: isConcurrencySafe=false, isReadOnly=false
- AST-based Bash analysis for security
- Permission explainer: side-query showing risk before user approval

---

## 2. Cursor IDE — Recursive Ownership Model

**5-iteration evolution to final design:**

```
Root Planner → Subplanner A → [W1] [W2] [W3]
             → Subplanner B → [W4] [W5] [W6]

Handoff propagation: worker returns findings + concerns + deviations + feedback
```

**Key properties:**
- Recursive ownership: each subplanner OWNS its slice of the task
- Handoff propagation: information flows up naturally without global synchronization
- Worker isolation: each worker has its own repo copy (no shared state, no locks)
- Commitment correctness tradeoff: accept small error rate for throughput, final reconciliation pass

**Scale achieved:**
- ~1,000 commits/hour, 10M tool calls over 1 week
- Hundreds of agents on single large VM
- Zero human intervention once started

**Dynamic Context Discovery (5 techniques):**
1. Long tool outputs → files (agent calls `tail`, reads if needed)
2. Chat history → files during summarization (agent can grep to recover lost details)
3. Agent Skills: name+description in static context, agent discovers via grep/semantic search
4. MCP tools synced to files: -46.9% agent tokens in A/B test
5. Terminal outputs → files (agent grep for relevant lines)

**Harness engineering:**
- Model-specific tool formats: patch-based (OpenAI) vs string-replacement (Anthropic)
- Keep Rate metric: fraction of agent code remaining after time intervals
- LM-based semantic evaluation of user responses
- Anomaly detection on tool call errors per-tool, per-model

---

## 3. OpenAI Codex — Fragment Trait System

**Context management (gold standard for plan2):**
- 30+ specialized `ContextualUserFragment` traits
- RULES: No unbounded items, hard 10K token cap per item, no history rewrite, avoid cache misses
- Two token scopes: Total + BodyAfterPrefix
- Auto-compact with configurable token limits

**Sub-agent system:**
- Code Mode: exec/wait for sub-agent delegation
- Agent Jobs: CSV-driven batch, up to 64 concurrent agents
- Agent graph store for tracking relationships

**Tool orchestration:**
- Approval → Sandbox → Attempt → Retry escalation
- Multi-layer sandbox: bubblewrap+Landlock (Linux), Seatbelt (macOS)
- Guardian review system for sensitive operations

---

## 4. L-TPS — Toyota Production System for Agents

**7 TPS concepts → 7 modules:**

| TPS Concept | L-TPS Module | plan2 Equivalent |
|-------------|-------------|------------------|
| Jidoka (autonomation) | `JidokaEvaluator` — separate LLM, skepticism-tuned | Phase 6.5 Verification + Phase 8.5 Tester |
| Kaizen (continuous improvement) | `KaizenLedger` — failure → permanent rule | Auditor + cross-cycle patterns |
| Andon (stop-the-line) | `AndonMonitor` — stop, retry with feedback, escalate | Quality gates (FAIL → return to agent) |
| Standard Work | `StandardWork` — define "done" BEFORE work | Phase 1 Requirements + Phase 5 Plan |
| Kanban (visual board) | `KanbanLog` — append-only event log + checkpoints | `.observations/checkpoint-NN.md` |
| Poka-yoke (mistake-proofing) | `PokayokeRunner` — pre/post worker hooks with rule injection | Context injection (memory → agent) |
| Heijunka (leveling) | `heijunka_reset()` — context reset between phases | Compaction between phases |

**Design principles (directly applicable to plan2):**
1. **Evaluation separation is the strongest lever.** Self-evaluation = confident praise for mediocre work.
2. **Every failure should make the system better.** Kaizen ledger ensures no mistake repeats silently.
3. **State belongs outside the engine.** ProductionLine is stateless; all state in KanbanLog.
4. **Ports over implementations.** LLM, I/O, storage are Protocol-based — swap without engine changes.

**Crash recovery:**
- Append-only event log
- Periodic checkpoints: DAG state + retry counts
- `resume(task_id)` reconstructs from last checkpoint

**What plan2 NOW HAS from L-TPS (implemented 2026-06-24):**
- ✅ **StandardWork contracts** — `techlead-agent.md` v2 (393 lines): acceptance criteria + verification + budget per task
- ✅ **Jidoka evaluator** — `jidoka-evaluator.md` (201 lines): independent skeptical evaluator, checks each acceptance criterion by name
- ✅ **Ownership matrix + Import contracts** — explicit file→dev mapping + consumer→producer contracts, grep-verifiable by DevOps Engineer
- ✅ **Structured developer handoff** — StandardWork + import contracts + Kaizen rules + budget + handoff template
- ✅ **Cost-aware routing** — L1-L2 → Kimi K2.7, L3-L5 → DeepSeek V4 Pro
- ✅ **Dependency DAG** — ReWOO-style parallel groups identified in plan
- ✅ **KanbanLog** — append-only event log with checkpoints (`.hermes/kanban/<slug>.log`)
- ✅ **Kaizen ledger** — failure → permanent rule → Poka-yoke injection (`.hermes/kaizen/<slug>.ledger`)

**What's deferred to next iteration:**
- Durable crash recovery with resume() from KanbanLog checkpoint
- Andon severity escalation (CRITICAL/HIGH/MEDIUM with different actions)
- Poka-yoke hook runner (currently manual context injection)
- Post-deploy Kaizen migration to Education Graph (Neo4j)

---

## 5. ReWOO — Parallel Execution Pattern

**Core idea:** Decouple planning from execution. Generate FULL plan with placeholders → execute ALL tool calls in parallel → fill placeholders → answer.

**Advantage over ReAct:** 5× token efficiency, 2 LLM calls instead of N.

**Direct application in plan2:** Phase 3 Research — spawn all RQ subagents in parallel (already done in this session, 613s for 5 agents vs ~2500s sequential).

---

## 6. $47K Post-Mortem — The Triple Guard

**Incident:** Two agents in unmediated chat loop → $47K API bill before noticed (11 days).

**Three independent safety mechanisms (ALL required):**
1. `MAX_STEPS` per conversation (hard cap)
2. Per-conversation USD budget gate (`BudgetGate` class)
3. Duplicate tool-input hash detector (`LoopDetector`, SHA256 of tool+args, threshold=2)

**Additional learnings:**
- Self-loops visible in OTel traces: agent.iterations > N, same tool.input_hash > 2
- Token counts are abstract; dollars are not. Budget in USD, not tokens.
- A green dashboard means nothing without cost tracking. Monitor per-conversation spend.
