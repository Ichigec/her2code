# Codebase Graph Memory — Full Cycle Case Study

**Date:** 2026-06-17  
**Project:** `codemes_neo4j_repo-graph_20260617_002228`  
**Cycle:** 10 phases, balanced depth (3 dev)  
**Orchestrator:** Hermes `/agent plan`

## The Integration Ownership Void

The single most expensive failure pattern in this cycle: the Plan assigned per-FILE ownership (Dev #1 owns `codebase_scanner.py`, Dev #3 owns `codebase_indexer.py`) but **nobody owned the integration points** — how `codebase_indexer.py._parse_file()` calls `codebase_scanner.TreeSitterParser.parse()`.

### What happened

1. **Dev #1** built `TreeSitterParser` (657 lines, tree-sitter, extracts functions/classes/imports/calls)
2. **Dev #2** built `TreeSitterParserL2` (684 lines, tree-sitter L2-L3, packages/modules/types/dataflow)
3. **Dev #3** built `CodebaseIndexer` with its OWN regex parser `_parse_python()` (140 lines, regex-only)
4. **Dev #4** built `EmbeddingGenerator` (136 lines, sentence-transformers, LRU cache)

Result: `codebase_indexer.py._parse_file()` calls `_parse_python()` (regex), never imports `TreeSitterParser`. Three modules exist as orphaned files. Same dataclass (`ParsedFile`) defined in 3 incompatible copies. Same method (`_is_path_excluded()`) creates a full `FileWatcher` with no-op callback just to do a pattern match.

### Cost

| Metric | Before fix | After fix |
|--------|-----------|-----------|
| CALLS relationships in Neo4j | **0** | **1,976** |
| Embeddings on functions | **0** | **1,135** (100%) |
| Full scan duration | 94.5s (1,429 files) | 53.4s (128 files, .venv excluded) |
| Dead code | ~2,150 lines (80%) | fixable |
| Doc-to-code ratio | 2.1:1 (5,745 doc / 2,700 code) | target: 0.3:1 |
| Essential MVP | ~780 SLOC | instead of ~8,400 |

### Root cause (5 Whys)

1. Why were CALLS = 0? — Parser only extracted functions/classes/imports
2. Why? — `_parse_file()` called regex `_parse_python()`, not tree-sitter
3. Why? — `TreeSitterParser` from `codebase_scanner.py` was never imported by `codebase_indexer.py`
4. Why? — Each developer built their module in isolation. Nobody owned integration
5. Why? — Plan had file ownership but no integration ownership. Tech Lead never ran `grep -r "from codebase_scanner import" codebase_indexer.py`

### Fix applied

- **BUG-1:** `run_watcher.py:34-36` — `driver.close()` after connection test → replaced with `with driver.session()`
- **Tree-sitter integration:** `_parse_file()` now imports `TreeSitterParser` with lazy-init + regex fallback
- **Embeddings:** `EmbeddingGenerator` lazy-init, batch-encode in `full_scan()`, stored on `CodeFunction`/`CodeClass` nodes
- **.venv exclusion:** added to `exclude_patterns`, files dropped from 1,429 to 128 (venv packages excluded)
- **_is_path_excluded():** replaced `FileWatcher` instantiation with `fnmatch.fnmatch()`

### Prevention (added to orchestrator)

- **DevOps Engineer (#10):** owns integration points, runs Phase 6a Integration Gate
- **Integration Gate:** 4 mechanical checks (import verification, dataclass compatibility, orphan detection, smoke test)
- **Pitfall in `multi-agent-orchestration` skill:** "Integration ownership void (v2.14)"

### Auditor findings

- **Phase 1-5 quality:** Exceptional (average 1,160 lines/artifact, structured, evidence-based)
- **Phase 6 quality:** Weak (~50% scope, three orphan modules)
- **Phase 8.5 quality:** Gold standard (1,250 lines, 30 tests, real terminal output)
- **Overall:** B+ cycle. Process framework sound; execution needs integration gate.
- **5 proposed mutations** in audit report

### Critic findings

- **10.8× bloat:** 8,400 lines → 780-line MVP
- **Three parsers** for one job (regex, TreeSitterParser, TreeSitterParserL2)
- **Duplicate dataclasses** (`ParsedFile` in 3 files, `UpdateReport` in 2)
- **Unused module:** `codebase_embeddings.py` (136 lines, never called)
- **Architecture doc bloat:** 780 lines for never-chosen architectures A and C

### Idea Generator findings

- **SD-2 overturned priorities:** embeddings 5.8× faster than research predicted (595 vs 102.8 emb/s)
- **24 proposals** (8 P0, 8 P1, 8 P2-P3)
- **Critical insight:** bottleneck is Neo4j MERGE, not parsing
- **Configuration Graph:** 95 YAML/JSON files are structure, not noise
- **Cross-graph ecosystem:** codebase + education + claw = unified graph

## Key artifacts

```
docs/requirements/codebase-graph-memory.md
docs/system-analysis/codebase-graph-memory.md
docs/research/codebase-graph-memory.md
docs/architecture/codebase-graph-memory.md
docs/security/sast-report.md
docs/deployment/codebase-graph-memory.md
docs/tests/codebase-graph-memory.md
docs/research-post/codebase-graph-memory.md
~/.hermes/plans/2026-06-17_060000-codebase-graph-memory.md
```
