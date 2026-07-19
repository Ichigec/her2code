# Orchestrator File Evolution — plan → plan2 → plan3

> Generated: 2026-07-09. Based on file mtime analysis + session 20260701_195714_424c97.

## Files (live, NOT git-versioned)

`~/.hermes/agents/` has **no git repo**. Files exist only as current versions on disk. Only snapshot: `/home/user/dev/codemes/codewar/hermes-core/agents/` (copy from 2026-07-06, ~44 bytes smaller per file due to NEO4J_PASSWORD sanitization CHANGEME).

| File | Lines | Bytes | Last modified | Label | Model |
|------|-------|-------|---------------|-------|-------|
| `plan.md` | 1067 | 59,585 | 2026-06-29 22:16 | Plan 🎻 | deepseek-v4-pro |
| `plan2.md` | 1228 | 68,500 | 2026-07-03 18:37 | Plan2 🎻 | deepseek-v4-pro |
| `plan3.md` | 1286 | 72,873 | 2026-07-04 01:20 | Plan3 🧬 | qwen3.6-35b (local) |

## Timeline

| Date | Event |
|------|-------|
| 2026-06-20 | `orchestrator-transformation.md` plan: Research Orchestra (5+ agents), Pre-Flight Gate, Progressive Dev Pipeline, Code RAG, Agent Network Topology |
| 2026-06-29 | `plan.md` — Orchestrator v2 base (post-transformation). Cloud deepseek-v4-pro. `/agent plan` trigger. |
| 2026-07-01 | Session `20260701_195714_424c97`: deep research on 3 models (Huihui-AgentWorld-35B, Nex-N2-mini, Huihui4-48B). User confirmed DGX Spark 128GB → plan3 designed for local multi-model stack. SubagentDropdown.tsx created for GUI. observer.py patched with plan3 mutations. |
| 2026-07-03 | `plan2.md` — +179 lines / -18 lines vs plan.md. Added: Capability Gate (Phase 0.2/0.3), PEP/PDP Stage-Gate (Cooper 1990), Circuit Breakers, Fabrication Guard, GAP Propagation, Observer Feedback Loop, Tech Lead v3 sub-orchestrator for Phase 6, dag-state.json, RLEF feedback loop. |
| 2026-07-04 | `plan3.md` — +129 lines / -71 lines vs plan2.md. Changed: identity (🎻→🧬, deepseek→local qwen), Multi-Model Router table (Reasoning→Qwen3.6, Coding→Nex, Simulation→AgentWorld), Pipeline Modes (Full/Fugu/Fusion), structured JSON research output (`.json` PRIMARY + `.md` auto-gen), auto-routing by `routing_target` field, Phase 6 returned to orchestrator-direct (removed Tech Lead sub-orchestrator). |

## Diff: plan.md → plan2.md (+179 / -18)

5 blocks of change:
1. **Metadata**: label/trigger renamed plan→plan2
2. **Capability Gate** (Phase 0.2 + 0.3): `capability_gate.py` before any phase. Inject capability constraints into all sub-agent context.
3. **Tech Lead v3 sub-orchestrator**: entire Phase 6 delegated to Tech Lead via `delegate_task(role='orchestrator')`. Fallback: orchestrator direct.
4. **DAG + RLEF**: `dag-state.json` artifact. Pattern detection after every 2nd SW. Loop guards (max 3 attempts/SW, 2× retries, 150% budget).
5. **PEP/PDP Stage-Gate** (88 lines): Go/Kill/Hold/Recycle semantics. 15 per-phase gates. Circuit Breakers (CLOSED→OPEN→cooldown→HALF_OPEN). Fabrication Guard. GAP Propagation. Retrospective Learning (G8). Observer Feedback Loop (CRITICAL→Hold).

## Diff: plan2.md → plan3.md (+129 / -71)

6 blocks of change:
1. **Identity**: Plan2→Plan3, 🎻→🧬, Orchestrator v2→v3, deepseek-v4-pro→qwen3.6-35b, deepseek→local
2. **Multi-Model Router** (40 lines): Reasoning→qwen3.6-35b (GPQA 86.0), Coding→nex-n2-mini (SWE-Bench 74.4), Simulation→agentworld (AgentWorldBench 56.39). Rule: NEVER delegate coding to Qwen3.6, NEVER delegate reasoning to Nex.
3. **Pipeline Modes**: Full Cycle (default, 10 phases), Fugu («быстро»: Thinker→Worker→Verifier→Synthesizer), Fusion («сравни»: Qwen∥Nex→Synthesizer)
4. **Structured Research Output**: `.md` (prose) → `.json` (structured, PRIMARY) + `.md` (auto-gen view). Schema `research-output-v1.json`. All GATE B/C/D now run on `.json`. GATE C expanded to 7 structured completeness checks. Who-reads-what table added.
5. **Auto-routing by `routing_target`**: findings flow to correct agent based on structured metadata field. `must_see: true` = hard constraint on Tech Lead. Data-driven delivery replaces prompt-based routing instructions.
6. **Phase 6 reverted to orchestrator-direct**: removed Tech Lead v3 sub-orchestrator delegation. DAG-driven execution with RLEF feedback. Research delivery to developers via structured filtering (`research_filter.py`, EXIT-style matching, `must_see` always included, `unstructured_notes` never to developers).

## Key architectural difference

| Aspect | plan2 | plan3 |
|--------|-------|-------|
| Model | 1 cloud (deepseek) | 3 local (Qwen+Nex+World) |
| Research format | `.md` prose | `.json` structured + `.md` view |
| Phase 6 | Tech Lead sub-orchestrator | Orchestrator direct + DAG |
| Routing | One table for all | Per-role model assignment |
| Pipeline modes | Full only | Full / Fugu / Fusion |
| Deployment target | Cloud API | DGX Spark local (128GB) |

## How to regenerate diffs

```bash
# Full unified diff (compact)
diff --unified=0 ~/.hermes/agents/plan.md ~/.hermes/agents/plan2.md
diff --unified=0 ~/.hermes/agents/plan2.md ~/.hermes/agents/plan3.md

# Line counts
diff plan.md plan2.md | grep -c '^>'  # added
diff plan.md plan2.md | grep -c '^<'  # removed
```
