# Codebase Graph Schema (Neo4j)

Live census as of 2026-06-18. The codebase graph indexes Python source files under
`~/dev/codemes/` via AST parsing. Backed by MCP server `codebase-server.mjs`
(tool: `codebase_search`, `codebase_traverse`, `codebase_impact_analysis`,
`codebase_entry_points`, `codebase_stats`).

## Node Labels & Counts

| Label | Count | Description |
|-------|-------|-------------|
| `CodeFile` | 128 | Python source files indexed from workspace |
| `CodeFunction` | 1122 | Functions/methods with embeddings |
| `CodeImport` | 880 | Import statements |
| `CodeClass` | 190 | Class definitions |
| `CodeEntryPoint` | 100 | Entry points (shebang, `if __name__`) |

## Relationship Types & Counts

| Relationship | Count | Meaning |
|-------------|-------|---------|
| `CALLS` | 3636 | Function A calls function B |
| `CONTAINS` | 2662 | File contains class/function |
| `IMPORTS` | 880 | File imports module |
| `HAS_ENTRY_POINT` | 100 | File has entry point |

## Property Reference

### CodeFile
| Property | Type | Example |
|----------|------|---------|
| `path` | string | `/home/user/dev/codemes/_ac3_test_1781673080.py` |
| `name` | string | `_ac3_test_1781673080.py` |
| `ext` | string | `.py` |
| `hash` | string | `6139db2df11014c1` |
| `status` | string | `active` |
| `indexed_at` | ISO 8601 | `2026-06-17T20:12:08.430Z` |

**Pitfall:** The property is `path`, NOT `filePath`. Queries using `f.filePath` return null.

### CodeFunction
| Property | Type | Example |
|----------|------|---------|
| `name` | string | `hello_world` |
| `signature` | string | `_ac3_test_1781673080::hello_world` |
| `file_path` | string | `/home/user/dev/codemes/_ac3_test_1781673080.py` |
| `start_line` | int | 7 |
| `end_line` | int | 9 |
| `body_hash` | string | `61056a46316c...` (SHA-256) |
| `embedding` | float[] | 384-dim vector (all-MiniLM-L6-v2) |
| `is_entry_point` | bool | `false` |
| `level` | int | 1 (nesting depth) |

### CodeEntryPoint
| Property | Type | Values |
|----------|------|--------|
| `entry_type` | string | `shebang`, `main` |
| `command` | string | e.g. `#!/usr/bin/env python3` |
| `file_path` | string | Path to source file |
| `is_entry_point` | bool | `true` |

## Query Recipes

### Find all functions in a file
```cypher
MATCH (f:CodeFile {path: '/home/user/dev/codemes/some/file.py'})-[:CONTAINS]->(fn:CodeFunction)
RETURN fn.name, fn.start_line, fn.end_line ORDER BY fn.start_line
```

### Find callers of a function
```cypher
MATCH (caller:CodeFunction)-[:CALLS]->(callee:CodeFunction {name: 'tunnel_loop'})
RETURN caller.signature, caller.file_path
```

### Find all entry points
```cypher
MATCH (f:CodeFile)-[:HAS_ENTRY_POINT]->(e:CodeEntryPoint)
RETURN f.path, e.entry_type, e.command
```

### Get graph statistics
```cypher
MATCH (n) WHERE n:CodeFile OR n:CodeFunction OR n:CodeClass OR n:CodeImport OR n:CodeEntryPoint
RETURN labels(n)[0] AS label, count(*) AS cnt ORDER BY cnt DESC
```

## Indexing Scope

Current scope: `~/dev/codemes/` (Python files only). The indexer uses Python's `ast` module.
Entry points are detected via:
- Shebang line (`#!/usr/bin/env python3`)
- `if __name__ == "__main__":` blocks
