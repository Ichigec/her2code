// ============================================================================
// Cross-Graph Query Templates for ClawAnalyzer
// Neo4j: localhost:7474 (neo4j:<YOUR_NEO4J_PASSWORD>)
// 10 ready-to-use Cypher templates for cross-graph analysis
// ============================================================================

// ---------------------------------------------------------------------------
// 1. CLAW GRAPH — Find Tools related to a task
// ---------------------------------------------------------------------------
MATCH (t:Tool)
WHERE t.name CONTAINS $query OR t.description CONTAINS $query
OPTIONAL MATCH (t)-[r:DEPENDS_ON]->(dep:Tool)
OPTIONAL MATCH (t)-[co:CO_OCCURS_WITH]->(related:Tool)
RETURN t.name AS tool, t.description,
       collect(DISTINCT dep.name) AS depends_on,
       collect(DISTINCT related.name) AS related_tools
ORDER BY t.name LIMIT 20;

// ---------------------------------------------------------------------------
// 2. CODEBASE GRAPH — Find CodeFile implementing a Tool
// ---------------------------------------------------------------------------
MATCH (t:Tool {name: $tool_name})-[:CODED_IN]->(cf:CodeFile)
MATCH (cf)-[:CONTAINS]->(fn:CodeFunction)
OPTIONAL MATCH (cf)-[:CONTAINS]->(cc:CodeClass)
RETURN cf.path AS file_path, cf.name AS file_name,
       collect(DISTINCT fn.signature) AS functions,
       collect(DISTINCT cc.name) AS classes
LIMIT 10;

// ---------------------------------------------------------------------------
// 3. CROSS-GRAPH IMPACT ANALYSIS — Who calls functions from this Tool?
// ---------------------------------------------------------------------------
MATCH (t:Tool {name: $tool_name})-[:CODED_IN]->(cf:CodeFile)
MATCH (cf)-[:CONTAINS]->(fn:CodeFunction)
MATCH (caller:CodeFunction)-[:CALLS]->(fn)
MATCH (caller_file:CodeFile)-[:CONTAINS]->(caller)
WHERE caller_file.path <> cf.path
RETURN t.name AS tool, cf.name AS impl_file,
       fn.signature AS called_function,
       caller.signature AS caller,
       caller_file.path AS caller_file,
       caller.start_line AS line
ORDER BY caller_file.path LIMIT 50;

// ---------------------------------------------------------------------------
// 4. EVIDENCE TRAIL — Past errors with this Tool
// ---------------------------------------------------------------------------
MATCH (t:Tool {name: $tool_name})<-[:ABOUT]-(e:Evidence)
OPTIONAL MATCH (e)-[:OBSERVED_IN]->(s:Session)
RETURN e.type, e.description, e.severity,
       s.title AS session, e.timestamp
ORDER BY e.timestamp DESC LIMIT 20;

// ---------------------------------------------------------------------------
// 5. EDUCATION GRAPH — Knowledge entities by topic
// ---------------------------------------------------------------------------
CALL db.index.fulltext.queryNodes('entitySearch', $query)
YIELD node AS ke, score WHERE ke:KnowledgeEntity
OPTIONAL MATCH (ke)-[r:RELATES_TO]->(related:KnowledgeEntity)
RETURN ke.name, ke.type, ke.description, score,
       collect(DISTINCT {entity: related.name, predicate: r.predicate}) AS related
ORDER BY score DESC LIMIT 15;

// ---------------------------------------------------------------------------
// 6. FULL CROSS-GRAPH TRAVERSAL
// ---------------------------------------------------------------------------
MATCH path = (t:Tool {name: $tool_name})-[:CODED_IN]->(cf:CodeFile)
             -[:CONTAINS]->(fn:CodeFunction)-[:CALLS*1..3]->(callee:CodeFunction)
MATCH (callee_file:CodeFile)-[:CONTAINS]->(callee)
RETURN t.name, cf.name AS tool_file, fn.signature AS entry,
       callee.signature AS reaches, callee_file.name AS in_file,
       length(path) AS hops
ORDER BY hops, callee_file.name LIMIT 100;

// ---------------------------------------------------------------------------
// 7. ORPHAN DETECTION — Tools without implementation
// ---------------------------------------------------------------------------
MATCH (t:Tool)
WHERE NOT (t)-[:CODED_IN]->(:CodeFile)
RETURN t.name AS orphan_tool, t.description
ORDER BY t.name LIMIT 50;

// ---------------------------------------------------------------------------
// 8. DEAD CODE — Uncalling functions
// ---------------------------------------------------------------------------
MATCH (cf:CodeFile)-[:CONTAINS]->(fn:CodeFunction)
WHERE NOT ()-[:CALLS]->(fn)
  AND NOT (cf)-[:HAS_ENTRY_POINT]->(:CodeEntryPoint)
RETURN cf.path, collect(fn.name) AS unused_functions,
       count(fn) AS unused_count
ORDER BY unused_count DESC LIMIT 30;

// ---------------------------------------------------------------------------
// 9. SYSTEM TOPOLOGY — Services and dependencies
// ---------------------------------------------------------------------------
MATCH (s:Service)
OPTIONAL MATCH (s)-[:DEPLOYED_ON]->(h:Host)
OPTIONAL MATCH (s)-[:EXPOSES_PORT]->(p:Port)
OPTIONAL MATCH (s)-[:DEPENDS_ON]->(dep:Service)
RETURN s.name, s.status, h.name AS host,
       collect(DISTINCT p.number) AS ports,
       collect(DISTINCT dep.name) AS depends_on
ORDER BY s.name;

// ---------------------------------------------------------------------------
// 10. CROSS-GRAPH: Tool + Education Connection
// ---------------------------------------------------------------------------
MATCH (t:Tool {name: $tool_name})-[:CODED_IN]->(cf:CodeFile)
MATCH (cf)-[:CONTAINS]->(fn:CodeFunction)
MATCH (ke:KnowledgeEntity)
WHERE ke.description CONTAINS t.name OR ke.name CONTAINS t.name
RETURN t.name, ke.name AS knowledge, ke.type, ke.description
LIMIT 10;
