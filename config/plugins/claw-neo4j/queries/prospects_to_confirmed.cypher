MATCH (p:Prospect)
WHERE p.score >= 0.7
  AND ($start_id IS NULL OR p.id = $start_id OR p.id STARTS WITH $start_id)
OPTIONAL MATCH (cp:Checkpoint)-[:SUGGESTS]->(p)
OPTIONAL MATCH (cp)-[:FOUND]->(t:Tool)
RETURN p.id AS prospect_id, p.score AS score, collect(DISTINCT t.id) AS confirmed_tool_ids
LIMIT 50
