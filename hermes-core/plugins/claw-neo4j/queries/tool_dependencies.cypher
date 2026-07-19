MATCH (t:Tool {id: $start_id})
OPTIONAL MATCH path = (t)-[:DEPENDS_ON*1..3]->(dep:Tool)
RETURN t.id AS start_id, dep.id AS dependency_id, length(path) AS depth
ORDER BY depth
