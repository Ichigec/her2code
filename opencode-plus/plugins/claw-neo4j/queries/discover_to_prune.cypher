MATCH (t:Tool {id: $start_id})
OPTIONAL MATCH (rs:RegistrySnapshot)-[:RECORDS]->(t)
OPTIONAL MATCH (a:CompactionAction)-[:TARGETS]->(t)
WHERE a.op IN ['prune', 'mcp-dedupe']
RETURN rs.path AS registry_path, collect({id: a.id, op: a.op, ts: a.ts, human_gate: a.human_gate}) AS actions
