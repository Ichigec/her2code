# Codebase Graph Architecture Cycle — Methodology & Findings

> Condensed from full 4-phase cycle `codemes_neo4j_repo-graph_20260617_002228`
> 1,680-line architecture artifact at `docs/architecture/codebase-graph-memory.md`

## Key Research Methodology (reproducible)

When doing code-graph / Neo4j / codebase-as-knowledge-graph work, run these BEFORE designing:

### 1. Live Neo4j Ground-Truth Census
```bash
# NEVER trust documented counts — query live
curl -s -u neo4j:changeme -d '{"statements":[{"statement":"MATCH (n) RETURN labels(n) AS label, count(*) AS cnt"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```
**Finding:** Documented 55 KnowledgeEntity → reality 3,165 (57× discrepancy).

### 2. Codebase Census on Target Directory
```bash
find /target/dir -type f | wc -l                          # total files
find /target/dir -name '*.py' | wc -l                      # Python
find /target/dir -name '*.js' -o -name '*.mjs' | wc -l    # JavaScript
# Average imports per Python file:
grep -E '^\s*(import |from )' /target/dir/**/*.py | wc -l
```
**Finding:** Expected 500 code files → reality 113 (101 Python, 10 JS, 2 MJS). Changed embedding budget from 15s to 3s.

### 3. Tree-sitter Benchmarks on Target Hardware
```python
import tree_sitter_python as tspython
from tree_sitter import Language, Parser
parser = Parser(Language(tspython.language()))
# Time parse for real files + synthetic (100/500/1000 lines)
```
**Finding:** 260-345K lines/sec on Jetson ARM64. Parsing NOT the bottleneck.

### 4. Embedding Benchmarks on Target Hardware
```python
from sentence_transformers import SentenceTransformer
import time
model = SentenceTransformer('all-MiniLM-L6-v2')
# Test batch sizes 1/4/8/16/32, 3 reps each, with real code snippets
# Measure cold-start model load time separately
```
**Finding:** 102.8 emb/s @ batch=32. Loading model = 4.5s. Embedding IS the bottleneck.

### 5. Graph Tool Reuse Analysis
Read existing MCP server code, Neo4j client, RRF implementation. Identify what's directly reusable vs needs adaptation. List specific files, functions, and adaptation points.

## Architecture Spectrum (4 designs, 1,680 lines)

| | A: Flat Graph | **B: Hierarchical Hybrid ★** | C: Event-Sourced | D: Multi-Modal |
|---|:---:|:---:|:---:|:---:|
| **Nodes** | 5 types | 9 types | 10 + Snapshot | 12 + LLM |
| **Relations** | 4 types | 8 types | 8 types | 14 (6 cross-graph) |
| **AST levels** | 1 | 3 (hierarchical) | 3 | 3 |
| **Embeddings** | ❌ | ✅ 384-dim | ✅ 384-dim | ✅ 384-dim |
| **Search** | BM25 only | BM25+Cosine+RRF | BM25+Cosine+RRF | 3-graph RRF |
| **History** | ❌ | ❌ | ✅ SQLite Event Log | ❌ |
| **LLM enrichment** | ❌ | ❌ | ❌ | ✅ Patterns+Knowledge |
| **Cold start** | <5s | 25-32s | 28-35s | 25-32s + 19min |
| **Increment** | <500ms | <3s | ~5s | <3s + 30s |
| **SLOC** | ~800 | ~4,000 | ~6,000 | ~8,000 |
| **Devs** | 2 | 4 | 6 | 8 |
| **TDD cycles** | 5-6 | 13 | 18 | 23 |
| **Evolvability** | ★★ | ★★★★★ | ★★★★★ | ★★★★★ |

★ = Recommended (WSM 4.35/5.00)

### Key Architecture Decision: Hierarchical AST Levels
User requirement: 3 levels, hierarchical search (1→2→3), level-tagged nodes, deep levels optionally disabled.

| Level | Content | Node labels | Search priority |
|:---:|---------|------------|:---:|
| 1 | Functions, classes, imports, calls | CodeFunction, CodeClass, CodeImport, CodeCall | First |
| 2 | Packages, modules, __init__.py | CodePackage, CodeModule, PART_OF | Second |
| 3 | Type annotations, data flow, generics | CodeTypeAnnotation, CodeDataFlow | Third |

### Neo4j Schema (Architecture B — recommended)
```
CodeProject {name, root_path}
CodeFile {path, language, size, hash, last_modified, status}
CodeFunction {name, signature, start_line, end_line, level, embedding}
CodeClass {name, start_line, end_line, level, embedding}
CodeImport {source_module, imported_names}
CodeCall {caller_function, callee_function, line}
CodePackage {name, level}
CodeModule {name, level}
CodeEntryPoint {type, command}

(:CodeFile)-[:PART_OF]->(:CodeProject)
(:CodeFile)-[:CONTAINS]->(:CodeFunction|CodeClass)
(:CodeFile)-[:IMPORTS]->(:CodeImport)
(:CodeFunction)-[:CALLS]->(:CodeFunction)
(:CodeClass)-[:INHERITS]->(:CodeClass)
(:Tool)-[:CODED_IN]->(:CodeFile)
(:CodeFile)-[:HAS_ENTRY_POINT]->(:CodeEntryPoint)
(:CodeFunction)-[:INFERRED_DEPENDS_ON {inferred: true}]->(:CodeFunction)

INDEXES:
  codeSearch   — fulltext on CodeFile, CodeFunction, CodeClass
  codeEmbeddings — vector(384, cosine) on CodeFunction.embedding, CodeClass.embedding
```

## Critical Pitfalls Discovered

1. **Documentation drift (57×):** Never trust documented Neo4j counts. KnowledgeEntity went from 55 (documented) to 3,165 (live). Query live before any design.
2. **500→113 files reality check:** Codebase census changed embedding budget from 15s to 3s — cold-start estimates dropped from 32s to 20s.
3. **Migration non-issue:** Assumed `education` DB needed migration to `neo4j` — live query showed everything already in `neo4j`. CE single-DB limitation accidentally solved the problem.
4. **Delegate_task timeout ≠ failure:** Architect wrote 97KB/1,680-line file, then API timed out on summary. File was complete. Always check `tool_trace` for `write_file` before re-spawning after timeout.
5. **Bottleneck inversion:** Expected tree-sitter to be slow → reality: <2s. Expected embeddings to be fast → reality: 102.8/s, primary bottleneck. Focus optimization on embedding caching, not parsing.
