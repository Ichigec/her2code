# Deep Plan Research — Implementation Reference

> Full implementation plan: `/home/user/dev/codemes/deep-plan-research/implementation-plan-v2.md` (32 KB)
> Created: 2026-06-23. Updated: 2026-06-23 (standalone merged into deep-plan-researcher).

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `~/.hermes/agents/deep-plan-researcher.md` | 290 | Main agent: 2 modes (plan2 + standalone), 4 subphases, Cost Gate, GATE A–D, developer query |
| `~/.hermes/agents/research/citation-agent.md` | 142 | CitationAgent: URL verification, grouping [N], semantic matching |
| `~/.hermes/scripts/research_quality_gate.py` | 333 | GATE B: LLM-as-judge (5 Anthropic criteria) |
| `~/.hermes/scripts/research_completeness_gate.py` | 322 | GATE C: 5 completeness checks |
| `~/.hermes/scripts/citation_enforcement_gate.py` | 351 | GATE D: citation verification + grouping + 20% URL spot-check |

## Files Modified

| File | Change |
|------|--------|
| `~/.hermes/agents/plan2.md` | Lifecycle: 3.0–3.3 subphases. GATE A–D. Debate mode. Developer query. 7 Pre-Flight checks. |
| `~/.hermes/AGENTS.md` | Deep Plan Research section added |
| `~/.hermes/agents/registry.json` | +deep-plan-researcher, +citation-agent (34 total) |
| `~/.hermes/scripts/orchestrator_gate.py` | +check_research_deep (7th check) |
| `~/.hermes/agents/researcher.md` | Renamed to researcher_old.md (deprecated) |

## Agent Architecture

```
Phase 3: Deep Plan Research (inside plan2 or standalone)
  │
  ├─ 3.0 PLAN
  │   ├─ Read System Analysis artifact
  │   ├─ Query Education Graph (Neo4j)
  │   ├─ Read claw summaries (#research-needed)
  │   ├─ Formulate 3-7 Research Questions
  │   ├─ Cost Gate: single vs multi-agent
  │   └─ GATE A: User Approval (clarify)
  │
  ├─ 3.1 EXECUTE
  │   ├─ 5 standard subagents (academic, code, community, vendor-docs, claw-analyzer)
  │   ├─ +2 optional (codebase-analyzer, education-graph-analyzer)
  │   ├─ Debate mode: 2 agents on HIGH-priority RQs (different models)
  │   ├─ Adaptive RQ discovery: subagents propose new RQs
  │   └─ GATE B: Source Quality (LLM-as-judge)
  │
  ├─ 3.2 SYNTHESIS
  │   ├─ Collect all findings + debate diff
  │   ├─ Dedup by URL
  │   ├─ Citation mapping: claim → source[index]
  │   ├─ Pre-group sequential same-source claims
  │   └─ GATE C: Completeness (5 checks)
  │
  └─ 3.3 CITATIONS
      ├─ Spawn CitationAgent (separate pass)
      ├─ Verify ≥90% citations valid
      ├─ Group sequential facts → single [N]
      ├─ Sample 20% URLs via curl
      └─ GATE D: Citation Enforcement
```

## One Agent, Two Modes

`deep-plan-researcher.md` handles both modes:
- **Mode A (plan2):** receives System Analysis context, returns artifact for Phase 4
- **Mode B (standalone):** receives bare question, formulates RQs autonomously, GATE A via clarify
- **Mode B' (developer query):** receives structured context from developer, returns mini-report (500-2000 words, 3-5 min)

## Plan vs Plan2

- **`/agent plan`** → `plan.md` — **LEGACY, NOT TOUCHED.** Basic research.
- **`/agent plan2`** → `plan2.md` — Advanced orchestrator with Deep Plan Research.
- `researcher_old.md` — deprecated, kept as fallback.
