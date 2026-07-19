# Observer Cleanup Queries — Removing Obsolete Findings

After fixing bugs that observers diagnosed, delete the corresponding Neo4j
findings so only fresh, unfixed issues remain. This prevents stale findings
from cluttering `/obs`, the ObserverPanel, and future analysis.

## Pattern: Match findings by keyword → delete in batches

### Step 1: Identify findings related to the fix

Use content-matching to find nodes whose `finding` field mentions the fixed issue:

```python
import json, urllib.request, base64

NEO4J = "http://127.0.0.1:7474/db/neo4j/tx/commit"
AUTH=*** " + base64.b64encode(b"neo4j:<YOUR_NEO4J_PASSWORD>").decode()

def q(stmt, params=None):
    payload = json.dumps({"statements": [{"statement": stmt, "parameters": params or {}}]}).encode()
    req = urllib.request.Request(NEO4J, data=payload, headers={
        "Content-Type": "application/json", "Authorization": AUTH
    })
    resp = json.loads(urllib.request.urlopen(req).read())
    res = resp["results"][0]
    return res.get("data") or []

# Match findings by keyword patterns
patterns = [
    # Identity injection fix → delete findings about agent not knowing itself
    "agent preset", "own state", "what agent", "identity question",
    "own configuration", "self-referential",
    # Observer resilience fix → delete silent death findings
    "died silently", "ZERO findings", "produced ZERO output", "failed to produce ANY",
    # session_search fixes → delete truncation/lineage findings
    "truncat", "lineage", "scroll reject", "197K", "FTS5 discovery", "message ID",
    # Persistence fix → delete localStorage findings
    "localStorage", "NO persistence", "activeAgentPresetId", "no storage key",
]
```

### Step 2: Collect matching node IDs

Iterate across all finding types — `AuditFinding`, `CriticFinding`, `Idea`, `Mutation`:

```python
ids = set()

# AuditFindings
for kw in ["agent preset", "died silently", "truncat", "localStorage", ...]:
    for r in q(f"MATCH (f:AuditFinding) WHERE coalesce(f.finding,'') CONTAINS '{kw}' RETURN id(f) AS nid"):
        ids.add(r["row"][0])

# CriticFindings — scan full text
for r in q("MATCH (f:CriticFinding) RETURN id(f) AS nid, f.finding AS txt"):
    txt = (r["row"][1] or "").lower()
    if any(kw in txt for kw in ["agent preset", "localstorage", "session_search", "observer"]):
        ids.add(r["row"][0])

# Ideas — scan full text
for r in q("MATCH (i:Idea) RETURN id(i) AS nid, i.idea AS txt"):
    txt = (r["row"][1] or "").lower()
    if any(kw in txt for kw in ["agent preset", "self-awareness", "observer", "session_search"]):
        ids.add(r["row"][0])

# Implemented mutations
for r in q("MATCH (m:Mutation) WHERE m.status IN ['implemented'] RETURN id(m) AS nid"):
    ids.add(r["row"][0])
```

### Step 3: Delete in batches of 50

```python
id_list = list(ids)
for i in range(0, len(id_list), 50):
    batch = id_list[i:i+50]
    q("MATCH (n) WHERE id(n) IN $ids DETACH DELETE n", {"ids": batch})
    print(f"  Batch {i//50+1}: {len(batch)} deleted")
```

### Step 4: Verify

```python
for label in ["AuditFinding", "CriticFinding", "Idea", "Mutation"]:
    rows = q(f"MATCH (n:{label}) RETURN count(n) AS cnt")
    print(f"  Remaining {label}: {rows[0]['row'][0] if rows else 0}")
```

## Pitfalls

### AUTH redaction in shell one-liners

When writing Neo4j auth with inline Python `-c` commands, the `***` redaction
mechanism corrupts lines like `AUTH=***' + base64...`. ALWAYS write the script
to a temp file with `write_file` first, then run with `python3 /tmp/script.py`.

The `write_file` tool correctly writes the base64-encoded auth header — only
the tool's output display shows `***`.

### When NOT to delete

- Findings about general agent behavior patterns (e.g. "agent doesn't answer
  user questions") — these persist across sessions and need separate fixes.
- Findings whose recommendation was NOT implemented — don't delete unless the
  underlying bug is definitively fixed.

### Verification after deletion

Run the `observer-analysis-queries.md` pattern to verify remaining findings
are about unfixed issues, not fixed ones that evaded keyword matching.
