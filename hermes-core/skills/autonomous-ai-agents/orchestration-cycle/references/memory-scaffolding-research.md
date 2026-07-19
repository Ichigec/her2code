# Memory Scaffolding Research — Key Findings (2026-06-15)

> Condensed from 348-line research report produced by research-loop subagent (8 iterations, 33 sources).
> Full report: `/home/user/dev/codemes/hermes-memory-scaffolding_20260615_225957/docs/research/memory-scaffolding.md`
> Previous research: session `20260614_154200_c6a3d4` (27 papers, 4-level taxonomy)
> **P0 implementation results:** see `references/p0-memory-implementation.md`

## 5-Layer Canonical Memory Stack

```
L4: Meta-Memory       — self-reflection, drift detection, skill evolution (Curator, auditor_memory.md)
L3: Consolidation     — recurrence compress, temporal-hierarchical merge (TiMem, RecMem)
L2: Structured        — Knowledge Graph, relational, procedural (Neo4j, Hindsight KG)
L1: Semantic          — Vector DB, embeddings, facts (Mem0, OpenViking, Holographic)
L0: Episodic          — Sessions, messages, raw events (state.db, session_search)
```

## 8 Best Practices

1. **Separate storage from retrieval.** Backend ≠ retrieval strategy.
2. **Context Fencing mandatory.** Memory context explicitly separated from user input.
3. **Temporal > Semantic for execution state.** Event order matters more than semantic proximity.
4. **Provenance grounding.** Every memory must have source reference (Eywa).
5. **Trust scoring.** Without feedback, memory degrades (Holographic asymmetric: +0.05/-0.10).
6. **Silence is a feature.** Not all memories should be injected (RBI-Eval).
7. **Memory wire format.** Standardization for interoperability (memorywire).
8. **Latent memory as complement.** Saves tokens vs text-space memory (ElasticMem).

## 5 Key Trends (June 2026)

1. **Semantic → Temporal/Causal/Provenance retrieval** — Beyond Similarity (2606.06054), SegTreeMem (2606.04555), Eywa (2605.30771)
2. **Cognitive hierarchies** — DCPM (2606.09483): raw→facts→beliefs→abstractions
3. **Memory budget & silence** — Engram (2606.09900): 10-15% context beats full history
4. **Wire format standardization** — memorywire (2606.01138)
5. **Safety governance** — SSGM (2603.11768), memory poisoning attacks (2605.29960)

## Hermes Gap Analysis (Priority-Ordered)

### P0 — Critical ✅ IMPLEMENTED (2026-06-16, cycle `hermes-p0-memory_20260615_232649`)
| Gap | Fix | Effort | Result |
|-----|-----|:------:|--------|
| Temporal Retrieval | `prefetch_temporal()` → ABC, SegTreeMem on state.db | Medium | 252ms on 20K messages, zero-config system provider |
| Consolidation Pipeline | `ConsolidationManager` + `provider.consolidate()` hook | High | TiMem 4-tier, HMAC, `_call_consolidation_llm` hook (9.4s DeepSeek) |

P0 deployed: 7 files, ~1900 LOC, 323 tests. `memory_consolidations` table live. Known: NFR7 warmup 1531ms (deferred).

### P1 — Important
| Gap | Fix | Effort |
|-----|-----|:------:|
| Provenance Grounding | YAML frontmatter in MEMORY.md, `memory_trace(fact)` | Medium |
| Memory Budget & Silence | `prefetch()` returns relevance_score, silence gate | Medium |
| Multi-Provider Merge | Remove single-provider restriction, type-based routing | High |

### P2 — Desirable
| Gap | Fix |
|-----|-----|
| Wire Format | `export_memories()` / `import_memories()` |
| Safety Governance | HMAC audit trail, drift detection |

### P3 — Optional
| Gap | Fix |
|-----|-----|
| Latent Memory | `LatentMemoryProvider`, hybrid text+latent |

## Current Hermes State (post-P0, 2026-06-16)

| Component | Status |
|-----------|:------:|
| MemoryProvider ABC + 8 plugins | ⭐ Excellent |
| MemoryManager (single external provider, context fencing) | ⭐ Excellent |
| state.db + session_search (FTS5, 4 modes) | ⭐ Excellent |
| **SegTreeMem — temporal retrieval** | ✅ NEW (P0) — 252ms, system provider |
| **ConsolidationManager — TiMem pipeline** | ✅ NEW (P0) — LLМ hook live |
| **memory_consolidations table** | ✅ NEW (P0) — HMAC-SHA256 |
| **session_search temporal filters** | ✅ NEW (P0) — after_ts/before_ts |
| MEMORY.md (built-in, security scanning) | ✅ Good |
| Skills + Curator | ✅ Good |
| Neo4j graphs (Education: 2942 entities) | ✅ Good |
| auditor_memory.md | 🌱 1 cycle observed |

## Top Papers (June 2026)

| Paper | arxiv | Key Idea |
|-------|-------|----------|
| DCPM: Dual-Process Cognitive Memory | 2606.09483 | raw→facts→beliefs→abstractions |
| Engram: Bi-Temporal Memory Engine | 2606.09900 | 10-15% context beats full |
| SegTreeMem: Temporal Order Matters | 2606.04555 | Segment trees for temporal memory |
| Beyond Similarity: Trustworthy Search | 2606.06054 | Semantic similarity ≠ trustworthy |
| RBI-Eval: When Memory Stays Silent | 2606.06055 | Not all memories should be shown |
| Organize then Retrieve | 2606.11680 | Hierarchical navigation before retrieval |
| memorywire: Wire Format | 2606.01138 | Vendor-neutral memory protocol |
| Eywa: Provenance-Grounded Memory | 2605.30771 | Evidence before belief |
