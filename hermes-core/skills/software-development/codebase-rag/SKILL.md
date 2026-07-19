---
name: codebase-rag
description: Retrieval-Augmented Generation for code — query Neo4j codebase graph to discover CALLS/IMPORTS/CONTAINS relationships, system topology, and cross-graph impact analysis
version: 1.0.0
tags: [neo4j, codebase, rag, impact-analysis, cross-graph]
---

# CODE RAG — Neo4j Codebase Graph Queries

Query the Neo4j codebase graph to understand code relationships, perform impact analysis,
find dead code, and map system topology — **before** making changes.

## Neo4j Connection

```bash
# All queries via HTTP API
NEO4J="curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' http://localhost:7474/db/neo4j/tx/commit"
```

## Available Graphs

| Graph | Nodes | Key Relationships |
|-------|-------|-------------------|
| Codebase | 128 CodeFile, 1122 CodeFunction, 190 CodeClass, 880 CodeImport, 100 CodeEntryPoint | CALLS (1826), CONTAINS (1331), IMPORTS (880) |
| System Topology | 39 Service, 31 Container, 3 Host, ports, tunnels | DEPLOYED_ON, EXPOSES_PORT, RUNS_IN, CONNECTS_TO, TUNNELS_TO |
| Claw | 78 Tool, 81 Evidence | DEPENDS_ON, CO_OCCURS_WITH, DUPLICATE_OF |
| Education | ~13K KnowledgeEntity (growing — cron ingestion active) | RELATES_TO, HAS_SOURCE |

> **Pitfall:** Node counts in this skill are snapshots. The Education graph grows autonomously via Knowledge Curator cron. **Always run the live census** from `neo4j-knowledge-graph` → "Live Ground-Truth Census" before relying on counts.

## MCP Tools (preferred over raw curl)

The `codebase-graph` MCP server is registered and active in `~/.hermes/config.yaml`. Prefer MCP tools over raw Cypher for most queries:

| MCP Tool | Use |
|----------|-----|
| `mcp_codebase_graph_codebase_search(query)` | Hybrid search (BM25+Cosine+RRF) over CodeFunction/CodeClass/CodeFile |
| `mcp_codebase_graph_codebase_traverse(path, depth)` | Multi-hop traversal from a file |
| `mcp_codebase_graph_codebase_impact_analysis(entity)` | Reverse traversal: who depends on this entity? |
| `mcp_codebase_graph_codebase_entry_points()` | List all entry points |
| `mcp_codebase_graph_codebase_stats()` | Aggregate graph statistics |

The raw curl queries below are still valid as fallbacks and for complex Cypher not covered by MCP tools.

## Query Templates

### 1. Who calls this function? (IMPACT ANALYSIS)

Before modifying or deleting a function, discover all callers.

```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (caller:CodeFunction)-[:CALLS]->(callee:CodeFunction) WHERE callee.name CONTAINS \"FUNC_NAME\" MATCH (caller_file:CodeFile)-[:CONTAINS]->(caller) RETURN caller.signature, caller_file.name, caller.start_line ORDER BY caller_file.name, caller.start_line"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```

**Replace** `FUNC_NAME` with the target function name (partial match supported via CONTAINS).

### 2. What does this file import?

Before adding a new import, check what's already imported.

```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (f:CodeFile {name: \"FILE_NAME\"})-[:IMPORTS]->(imp:CodeImport) RETURN imp.name ORDER BY imp.name"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```

**Replace** `FILE_NAME` with the exact file name (use `CONTAINS` if unsure).

### 3. What functions are defined in a file?

Get the full list of functions in a file with their signatures and line ranges.

```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (f:CodeFile {name: \"FILE_NAME\"})-[:CONTAINS]->(fn:CodeFunction) RETURN fn.name, fn.signature, fn.start_line, fn.end_line ORDER BY fn.start_line"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```

### 4. Cross-file calls (who from other files calls functions in this file?)

Discover external dependencies on this file's functions.

```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (f1:CodeFile)-[:CONTAINS]->(fn1:CodeFunction)-[:CALLS]->(fn2:CodeFunction)<-[:CONTAINS]-(f2:CodeFile) WHERE f1.name = \"FILE_NAME\" AND f1 <> f2 RETURN f2.name AS called_from, fn2.name AS function_called, fn1.name AS caller_function"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```

### 5. System topology — where does this code run?

Map services to hosts and exposed ports.

```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (s:Service)-[:DEPLOYED_ON]->(h:Host) OPTIONAL MATCH (s)-[:EXPOSES_PORT]->(p:Port) RETURN s.name, s.status, h.name, collect(p.number) AS ports ORDER BY s.name"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```

### 6. Dead code detection (uncalled functions that aren't entry points)

Find functions nobody calls — candidates for removal.

```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (cf:CodeFile)-[:CONTAINS]->(fn:CodeFunction) WHERE NOT ()-[:CALLS]->(fn) AND NOT (cf)-[:HAS_ENTRY_POINT]->(:CodeEntryPoint) RETURN cf.name, fn.name, fn.start_line ORDER BY cf.name, fn.start_line LIMIT 20"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```

## Usage Rules

| Scenario | Queries to run |
|----------|---------------|
| **Before modifying a file** | #1 (impact analysis — who will break?) |
| **Before deleting a function** | #1 + #6 (who calls it + is it orphaned?) |
| **Before adding an import** | #2 (already imported?) |
| **Architecture decisions** | #5 (where in the system topology?) |
| **Code review** | #4 (cross-file dependencies) |
| **Exploring a new file** | #3 (what's defined here?) + #2 (what imports?) |

## Important Properties & Pitfalls

- **Property names:** `CodeFile.path` (NOT `filePath`!), `CodeFunction.signature` = `"file::function_name"`
- **Relationships:** `CALLS` (NOT `CALLS_FROM`), `IMPORTS` (NOT `IMPORTS_FROM`), `CONTAINS`
- **Neo4j Community Edition** — no `CREATE DATABASE`, everything is in database `neo4j`
- **Password:** `changeme`
- **JSON formatting:** pipe through `python3 -m json.tool` for readable output
- **Partial name matching:** use `CONTAINS` in WHERE clauses when exact names are unknown
- **Cross-graph queries:** Codebase, System Topology, Claw, and Education graphs all live in the same `neo4j` database — you can join across them when needed

## Quick Alias (optional)

Set this in your shell for shorter commands:

```bash
alias n4q='curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H "Content-Type: application/json" -d'
# Usage: n4q '{"statements":[{"statement":"MATCH (n) RETURN count(n)"}]}' http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```
