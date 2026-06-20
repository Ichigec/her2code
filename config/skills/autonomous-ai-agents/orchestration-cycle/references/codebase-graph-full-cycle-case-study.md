# Codebase Graph Memory — Full 10-Phase Cycle Case Study

> **Project:** `codemes_neo4j_repo-graph_20260617_002228`
> **Date:** 2026-06-17
> **Reference for:** `orchestration-cycle`, `multi-agent-orchestration`

## Cycle Summary

Task: Build Neo4j-based codebase graph memory for `/home/user/dev/codemes` (Jetson ARM64, Neo4j CE).
Depth: balanced (3 devs). Result: 35,278 nodes, 27,270 relationships, working deployment.

## Phase Results

| Phase | Agent | Artifact | Quality | Finding |
|:---:|-------|----------|:---:|---------|
| 1 | #1 Requirements | 315 lines | A | 6 SMART ACs, 8 NFRs, explicit constraints |
| 2 | #2 System Analyst | 693 lines | A | 5 Whys, WSM/AHP with sensitivity, precise Dev Task Spec |
| 3 | #3 Researcher | 631 lines | B+ | 6 RQs with benchmarks, but **census error: 113 vs actual 1,429 files (12.7×)** |
| 4 | #4 Architect | 1,680 lines | A | 4 architectures compared, Architecture B selected, Module Contracts |
| 5 | #5 Tech Lead | 2,426 lines | B | 13 TDD cycles, file ownership, but 4 devs vs 3 dev depth mode |
| 6 | #6 Developers | 7 files | C | ~50% scope. Three orphan modules not wired. |
| 7 | #7 Security | 157 lines | A | 1 blocking finding (hardcoded password) → fixed |
| 8 | #9 Deployment | report | B+ | Created missing run_watcher.py, but introduced BUG-1 |
| 8.5 | #8 Tester | 1,250 lines | A+ | 30 tests, 25 PASS / 4 FAIL, real evidence |
| 9 | #3 Researcher | 315 lines | A+ | 12 findings, evidence quality 1.92/2.0, SD-2 priority shift |
| 10 | Observers | 3 reports | A | Auditor (process), Critic (10.8× bloat), Idea Generator (24 proposals) |

## Key Learnings

### 1. Integration Ownership Void (CRITICAL)

The Plan assigned per-FILE ownership but NO ONE owned integration points.
Three modules built in isolation, none wired together:

| Module | Built by | Imported by orchestrator? | Result |
|--------|----------|:---:|--------|
| `codebase_scanner.py` (TreeSitterParser) | Dev #1 | ❌ | Dead code — tree-sitter parser never used |
| `codebase_parser.py` (TreeSitterParserL2) | Dev #2 | ❌ | Dead code — L2/L3 parser never used |
| `codebase_embeddings.py` (EmbeddingGenerator) | Dev #2 | ❌ | Dead code — 0 embeddings in Neo4j |
| `codebase_indexer.py` (regex parser) | Dev #3 | ✅ (self) | Production path uses regex, not tree-sitter |

Root cause: ownership matrix is per-FILE, not per-CAPABILITY. Integration is nobody's
file → nobody builds it.

### 2. 10.8× Bloat

- Documentation: 5,745 lines
- Code: ~2,700 lines
- Ratio: **2.1:1** (healthy: 0.2:1–0.5:1)
- Essential MVP: **~780 SLOC** instead of ~8,400

The Critic identified: three parsers for the same job, duplicate dataclasses in 3 files,
two `UpdateReport` dataclasses with different fields, L2/L3 AST analysis never used,
Architecture A & C (~780 lines) in the doc — neither chosen or built.

### 3. SD-2 Overturned Priorities

Research predicted embedding throughput: 102.8 emb/s.
Post-deploy measured: **595 emb/s — 5.8× faster.**
This shifted Phase 2 priorities from "optimize embeddings" to "just integrate them now."
Pre-deployment benchmarks can be significantly off; post-deploy measurement is authoritative.

### 4. Model Fallback Pattern: GPT-5.5 → DeepSeek for Observers

Phase 10 triple report attempted with GPT-5.5 → quota exceeded.
Retried with DeepSeek V4 Pro → all three reports successful:
- Auditor: 155s, deep process analysis, agent accountability scorecard
- Critic: 144s, 10.8× bloat quantification, concrete DELETE list
- Idea Generator: 196s, 24 proposals, 4 prioritization tiers

DeepSeek is a proven observer fallback when Kimi is unavailable or GPT-5.5 quota exhausted.

### 5. Delegate_task Timeout with Large Files

Architect (#4) wrote 1680-line/97KB file. API timed out at summary generation.
`delegate_task` returned `max_iterations` but file was on disk, complete.
**Verify file existence before re-spawning** — check `tool_trace` for `write_file` calls.

### 6. Research Census Error — 12.7× Underestimation

Research (Phase 3) census found 113 Python files. Reality: 1,429 files.
Root cause: deep-nested project directories not traversed.
**Prevention:** Ground-truth census with `find /path -name '*.py' | wc -l` before Architecture.

## Metrics

- Full scan: 1,429 files, 94.5s wall clock, 0 errors
- Graph: 35,278 nodes, 27,270 relationships
- Neo4j CE limits: far below (35K nodes vs 2³⁵ node limit, ~70MB RAM)
- BM25 search: 25ms, 3-hop traversal: 14ms
- Acceptance: 25 PASS / 4 FAIL / 0 UNTESTABLE
- Total cost: ~$0.80 (DeepSeek × 3 turns, Kimi × 1 tester turn)

## Phase 2 Priorities (from Idea Generator)

| P0 | Fix BUG-1 (driver-close) + .venv exclusion + MCP registration + embedding integration | 3-5 hours |
| P1 | Batch MERGE + replace regex with tree-sitter + cross-link KnowledgeEntity | 3-5 days |
| P2 | ONNX CUDA embeddings + Diff-Based Indexing + Configuration Graph | 1-2 weeks |
