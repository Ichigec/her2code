MATCH (t:Tool {id: $start_id})
OPTIONAL MATCH (t)-[:DUPLICATE_OF*1..2]->(dup:Tool)
RETURN t.id AS tool_id, collect(DISTINCT dup.id) AS duplicate_ids
