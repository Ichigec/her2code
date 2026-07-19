MATCH (s:Session {id: $start_id})
OPTIONAL MATCH (s)-[:OBSERVED|HAS_CHECKPOINT]->(x)-[:FOUND|SUGGESTS*0..1]->(t:Tool)
RETURN DISTINCT t.id AS tool_id, t.name AS name, t.type AS type, t.target AS target
LIMIT 50
