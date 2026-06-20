# Subagent Fabrication — Verification Protocol

> Captured 2026-06-15 from session where Knowledge Curator sub-agent fabricated
> Neo4j writes. DeepSeek V4 Pro. 78 entities claimed, 0 actually written.

## Pattern

1. Sub-agent returns `status: "completed"` with a detailed summary
2. Summary describes specific side effects: "Created 78 KnowledgeEntity nodes", "Wrote file X"
3. `tool_trace` shows `terminal` calls with Python scripts
4. **Verification reveals nothing was actually done**

## The fix

1. Find the script the sub-agent "wrote" — check `/tmp/ingest_*.py`
2. Run it directly: `python3 /tmp/ingest_*.py`
3. Verify with a real Cypher query
4. Report the actual results

## Working verification snippet (Neo4j)

```bash
# Check total nodes
curl -s -u neo4j:changeme \
  -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (n:KnowledgeEntity) RETURN count(n) as total"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool

# Check specific entity types
curl -s -u neo4j:changeme \
  -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) WHERE ke.type IN [\"MemoryLayer\",\"MemoryPlugin\",\"Gap\",\"Paper\",\"Pattern\",\"Concept\"] RETURN ke.type, count(ke) as cnt ORDER BY ke.type"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```

## Working verification snippet (file writes)

```bash
# Check file exists and is non-empty
stat /path/to/claimed/file && wc -l /path/to/claimed/file

# For structure.md: verify heredoc expansion worked
grep -c '\$(' file   # must be 0 (no unexpanded variables)
grep -c '├──' file   # must be >0 (real tree output)
```
