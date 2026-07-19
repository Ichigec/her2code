# Observer Analysis Queries — Neo4j Bulk Analysis

Battle-tested Cypher queries for deep analysis of observer findings. Use these when asked to "analyze observer findings," "show what observers found," or "give me the state of the observer system."

All queries assume Neo4j at `http://127.0.0.1:7474/db/neo4j/tx/commit`, auth `neo4j:<YOUR_NEO4J_PASSWORD>`.

## 1. Global Statistics

```python
import json, urllib.request

NEO4J = "http://127.0.0.1:7474/db/neo4j/tx/commit"
AUTH=*** " + __import__('base64').b64encode(b"neo4j:<YOUR_NEO4J_PASSWORD>").decode()

def neo4j_query(statements):
    payload = json.dumps({"statements": statements}).encode()
    req = urllib.request.Request(NEO4J, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": AUTH
    })
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

stats = neo4j_query([
    {"statement": "MATCH (f:AuditFinding) RETURN count(f) AS total"},
    {"statement": "MATCH (f:CriticFinding) RETURN count(f) AS total"},
    {"statement": "MATCH (i:Idea) RETURN count(i) AS total"},
    {"statement": "MATCH (m:Mutation) RETURN count(m) AS total"},
    {"statement": "MATCH (f:AuditFinding) WHERE f.recommendation IS NOT NULL AND f.recommendation <> '' RETURN count(f) AS with_rec"},
    {"statement": "MATCH (f:AuditFinding) RETURN count(f) AS total"},
])
```

Run via: `write_file` the script → `terminal('python3 /tmp/script.py')`. Do NOT use `execute_code` — the sandbox mangles certain string patterns in heredoc-style Auth headers.

### Python execution template (copy-paste, change queries only)

Neo4j returns rows as `{"row": [...], "meta": [...]}` — NOT bare lists. The `q()` helper below handles this:

```python
import json, urllib.request, base64

NEO4J = "http://127.0.0.1:7474/db/neo4j/tx/commit"
AUTH=*** " + base64.b64encode(b"neo4j:<YOUR_NEO4J_PASSWORD>").decode()

def q(statement, params=None):
    """Return (columns, rows) for a single Cypher statement. Rows are plain lists."""
    payload = json.dumps({"statements": [{"statement": statement, "parameters": params or {}}]}).encode()
    req = urllib.request.Request(NEO4J, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": AUTH
    })
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    results = data.get("results", [])
    if results:
        cols = results[0].get("columns", [])
        rows = [r["row"] for r in results[0].get("data", [])]  # <-- THE FIX: r["row"], not r
        return cols, rows
    return [], []

# --- Paste queries below, use q() for each ---
cols, rows = q("MATCH (f:AuditFinding) RETURN count(f) AS total")
for row in rows:
    print(f"AuditFindings: {row[0]}")

# Multi-statement: call q() for each
for stmt, label in [
    ("MATCH (f:AuditFinding) RETURN count(f) AS total", "AuditFinding"),
    ("MATCH (f:CriticFinding) RETURN count(f) AS total", "CriticFinding"),
]:
    _, rows = q(stmt)
    for row in rows:
        print(f"  {label}: {row[0]}")

# Sanitize finding text (Neo4j stores literal newlines as chr(10)/chr(13))
finding = (row[col_index] or "").replace(chr(10), " ").replace(chr(13), "").strip()
```

**Pitfall: heredoc base64 encoding.** When writing the script with `write_file`, the `AUTH = "Basic " + base64...` line can be mangled if the tool confuses `"""` boundaries. If `write_file` produces `AUTH=*** "` (commented-out), use `patch` to fix that single line — the rest of the script stays intact. The triple-quote string in the auth line is a known write_file edge case.

## 2. Severity Distribution

```cypher
MATCH (f:AuditFinding)
RETURN f.severity, count(f) AS cnt
ORDER BY cnt DESC
```

Expect mixed casing: `CRITICAL`, `critical`, `HIGH`, `high`, `MEDIUM`, `medium`, `MED`, `LOW`, `low`, `INFO`, `info`. Normalize with CASE WHEN for accurate aggregation.

## 3. Top CRITICAL/HIGH Findings (Filtered for non-cascade)

```cypher
MATCH (f:AuditFinding)
WHERE f.severity IN ['CRITICAL', 'critical', 'HIGH', 'high']
  AND NOT coalesce(f.finding, '') CONTAINS 'cascade'
  AND NOT coalesce(f.finding, '') CONTAINS 'recursion'
  AND NOT coalesce(f.finding, '') CONTAINS 'ObserverSessionMonitor'
RETURN f.severity AS severity, f.finding AS finding, 
       f.recommendation AS rec, f.session_id AS sid
ORDER BY 
  CASE f.severity 
    WHEN 'CRITICAL' THEN 0 WHEN 'critical' THEN 1
    WHEN 'HIGH' THEN 2 WHEN 'high' THEN 3
    ELSE 4
  END
LIMIT 20
```

Note: `CONTAINS` with a space-delimited word may still catch partial matches. Use `NOT (coalesce(f.finding,'') CONTAINS 'cascade' OR coalesce(f.finding,'') CONTAINS 'recursion' ...)` for broader filtering, but accept that ~10% false negatives is acceptable for a first pass. For precise filtering, post-process in Python.

## 4. Theme Categorization (Recurring Patterns)

```cypher
MATCH (f:AuditFinding)
WHERE f.severity IN ['CRITICAL', 'HIGH']
RETURN 
  CASE 
    WHEN coalesce(f.finding, '') CONTAINS 'Neo4j' OR coalesce(f.finding, '') CONTAINS 'Cypher' THEN 'Neo4j Issues'
    WHEN coalesce(f.finding, '') CONTAINS 'session' OR coalesce(f.finding, '') CONTAINS 'Session' THEN 'Session Management'
    WHEN coalesce(f.finding, '') CONTAINS 'observer' OR coalesce(f.finding, '') CONTAINS 'Observer' THEN 'Observer Architecture'
    WHEN coalesce(f.finding, '') CONTAINS 'execute_code' OR coalesce(f.finding, '') CONTAINS 'tool call' THEN 'Tool Usage'
    WHEN coalesce(f.finding, '') CONTAINS 'fix' OR coalesce(f.finding, '') CONTAINS 'implement' THEN 'Fix Gap'
    ELSE 'Other'
  END AS theme, count(f) AS cnt
ORDER BY cnt DESC
```

This catches the dominant cluster. Expect "Observer Architecture" to dominate CURRENT findings due to the cascade — the diverse findings are in the "Other" and "Neo4j Issues" buckets.

## 5. Mutation Status Distribution (The Fix Gap)

```cypher
MATCH (m:Mutation)
RETURN coalesce(m.status, 'no_status') AS status, count(m) AS cnt
ORDER BY cnt DESC
```

Key insight: the ratio of `no_status` + `proposed` vs `implemented` + `accepted` + `verified` + `applied` reveals the **fix gap** — how many diagnoses vs how many actual fixes. As of 2026-06-29: ~511 no_status, ~368 proposed, ~16 actionable.

## 6. Sessions with Most Findings

```cypher
MATCH (f:AuditFinding)
WITH f.session_id AS sid, count(f) AS cnt
RETURN sid, cnt ORDER BY cnt DESC LIMIT 15
```

Also get unique session count:
```cypher
MATCH (f:AuditFinding)
RETURN count(DISTINCT f.session_id) AS unique_sessions
```

## 7. NULL Session ID Detection

```cypher
MATCH (f:AuditFinding)
WHERE f.session_id IS NULL OR f.session_id = 'N/A'
RETURN f.severity, count(f) AS cnt
ORDER BY cnt DESC
```

Findings without session_id cannot be traced to any session — an audit gap.

## 8. Most Actionable Diverse Findings (has recommendation, non-cascade)

```cypher
MATCH (f:AuditFinding)
WHERE f.severity IN ['CRITICAL', 'critical', 'HIGH', 'high']
  AND f.recommendation IS NOT NULL AND f.recommendation <> ''
  AND NOT coalesce(f.finding, '') CONTAINS 'recursion'
  AND NOT coalesce(f.finding, '') CONTAINS 'cascade'
RETURN f.severity AS sev, left(f.finding, 200) AS finding, 
       left(f.recommendation, 250) AS rec
LIMIT 12
```

## 9. Implemented/Accepted Mutations

```cypher
MATCH (m:Mutation)
WHERE m.status IN ['implemented', 'accepted', 'verified', 'applied', 'active']
RETURN m.status AS status, m.change AS change, 
       m.rationale AS rationale, m.expected_impact AS impact
LIMIT 15
```

## 10. Full Summary (all entity types)

```cypher
MATCH (n)
WHERE n:AuditFinding OR n:CriticFinding OR n:Idea OR n:Mutation OR n:KnowledgeEntity
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC
```

Note: KnowledgeEntity count includes ALL entities (14K+), not just observer-created ones. The observer-specific entities are AuditFinding + CriticFinding + Idea + Mutation (~5K).

## Presentation Pattern

**CRITICAL: Lead with narrative, not statistics.** Pavel rejected a stats-first presentation in 2026-06-29 as «ничего не понятно». Observer findings span multiple interconnected sessions — they tell a story, not a dashboard. The narrative format («Акт 1. Павел спрашивает... Акт 2. Наблюдатели попытались...») was received well. Stats, tables, and bar charts should support the story, not replace it.

### Narrative-first structure (use this):

1. **Story arc** — trace what happened chronologically across sessions. Connect the dots: how did session A's failure trigger session B's observer failure, which in turn revealed pattern C? Group findings into narrative "acts" with clear causal links. Each act should answer: *what was attempted, what failed, and why?*
2. **Recurring patterns** — after the story, extract the 3-5 cross-cutting patterns that explain the root causes. Present each as a named problem with concrete examples pulled from the story above. Statistics serve as evidence here, not as the lead.
3. **What didn't get fixed** — highlight the fix gap explicitly. How many diagnoses vs how many implementations? Which proposed mutations are blocking resolution of the patterns above?
4. **Priority actions** — ranked by severity × recurrence × dependency. What should be fixed first to unblock the rest?

### Pitfall: stats-first dump

```
❌ WRONG (rejected 2026-06-29):
   "134 AuditFindings, 120 CriticFindings..." → table → severity chart → theme bar chart
   User: «ничего не понятно, опиши подробнее находки»

✅ RIGHT (accepted 2026-06-29):
   "Сегодня произошёл каскадный провал. Акт 1: Павел спросил агента 'кто я?'..."
   → full finding texts as evidence within the narrative → stats only as summary at end
```

### Format rules

- Use full finding text (no truncation to 200 chars) for the key narrative beats — Pavel wants detail, not excerpts
- `█` bar charts are fine as visual density in the "recurring patterns" section, never as the lead
- Data-driven with real Cypher output, not synthesized claims
- Russian language for the narrative, English only for technical terms and code
