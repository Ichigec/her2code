# KARMA Observer Architecture — Verification Mechanisms for Hermes Observers

> **Source session:** Knowledge Curator v2 design (2026-07-01)
> **Based on:** KARMA: Leveraging Multi-Agent LLMs for Automated Knowledge Graph Enrichment (arXiv:2502.06472, 2025)

Full architecture document: `/home/user/dev/codemes/knowledge-curator-v2/karma-observer-architecture.md`

## Key Concepts

KARMA is a multi-agent framework for KG enrichment with three innovations applicable to Hermes observers:

1. **Modular Specialized Agents** — Entity Discovery, Relationship Extraction, Domain-Adaptive Prompting agents (Hermes already has 4 specialized observers: Auditor, Critic, Idea Generator, Knowledge Curator)
2. **LLM-Based Verification** — Every extraction verified by a separate LLM pass before ingestion
3. **Domain-Adaptive Prompting** — Prompts adapt based on entity type, relationship context, and source domain

## Five-Tier Verification Pipeline

Proposed for Hermes Observer Orchestrator (Phase 5 after observer spawning):

| Gate | What | Check |
|------|------|-------|
| **1. Evidence** | Does finding quote specific session turn? | `session_search(sid)` → match finding to message |
| **2. Contradiction** | Does any other observer disagree? | Cross-reference Auditor↔Critic↔IG↔KC |
| **3. Calibration** | Is confidence supported by evidence? | 2+ sources → +0.1, contradiction → -0.2, no evidence → REJECT |
| **4. Schema** | Do entities/relations match Neo4j schema? | Name length ≤80, predicate in allowed set, constraint violations |
| **5. Cross-Cycle** | Does finding contradict prior cycles? | MATCH similar findings → escalate recurring to CRITICAL |

## Verdicts

- **ACCEPT** (conf ≥ 0.8): Write to Neo4j normally
- **FLAG** (conf < 0.8): Write with warning marker
- **REJECT** (no evidence): Discard

## New Agent

`~/.hermes/agents/verifier.md` — KARMA-style verification agent (not yet created).

## Domain-Adaptive Prompting

Observers adapt style based on session type: code/implementation, research/architecture, config/infrastructure, cron/observer-self. Templates in `~/.hermes/agents/templates/{observer}-{type}.md`.

## Integration

Observer Orchestrator gets new Phase 5 (Verify) between Phase 4 (Collect findings) and Phase 6 (Apply verdicts). Verifier is a leaf agent (`role="leaf"`), cannot spawn further observers — no verification cascades.
