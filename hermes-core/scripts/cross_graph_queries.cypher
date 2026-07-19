// ============================================================================
// Cross-Graph Query Templates for ClawAnalyzer
// Neo4j: localhost:7474 (neo4j:<YOUR_NEO4J_PASSWORD>)
// Используется ClawAnalyzer agent-ом при research фазе
// ============================================================================

// ---------------------------------------------------------------------------
// 1. CLAW GRAPH — Найти все Tool связанные с задачей
// ---------------------------------------------------------------------------
// Используй: когда нужно понять что система УЖЕ умеет делать по теме
// Параметры: $query — поисковый запрос (подстрока)
MATCH (t:Tool)
WHERE t.name CONTAINS $query
   OR t.description CONTAINS $query
OPTIONAL MATCH (t)-[r:DEPENDS_ON]->(dep:Tool)
OPTIONAL MATCH (t)-[co:CO_OCCURS_WITH]->(related:Tool)
RETURN t.name AS tool,
       t.description AS description,
       collect(DISTINCT dep.name) AS depends_on,
       collect(DISTINCT related.name) AS related_tools
ORDER BY t.name
LIMIT 20;

// ---------------------------------------------------------------------------
// 2. CODEBASE GRAPH — Найти CodeFile который реализует Tool
// ---------------------------------------------------------------------------
// Используй: когда Tool найден и нужно понять КАК он реализован
// Параметры: $tool_name — имя Tool из claw graph
// ВАЖНО: используй CODED_IN связь между Tool и CodeFile (cross-graph!)
MATCH (t:Tool {name: $tool_name})-[:CODED_IN]->(cf:CodeFile)
MATCH (cf)-[:CONTAINS]->(fn:CodeFunction)
OPTIONAL MATCH (cf)-[:CONTAINS]->(cc:CodeClass)
RETURN cf.path AS file_path,
       cf.name AS file_name,
       collect(DISTINCT fn.signature) AS functions,
       collect(DISTINCT cc.name) AS classes
LIMIT 10;

// ---------------------------------------------------------------------------
// 3. CROSS-GRAPH IMPACT ANALYSIS — Кто вызывает функции из этого Tool?
// ---------------------------------------------------------------------------
// Используй: перед изменением Tool — понять кто сломается
// Параметры: $tool_name — имя Tool
MATCH (t:Tool {name: $tool_name})-[:CODED_IN]->(cf:CodeFile)
MATCH (cf)-[:CONTAINS]->(fn:CodeFunction)
MATCH (caller:CodeFunction)-[:CALLS]->(fn)
MATCH (caller_file:CodeFile)-[:CONTAINS]->(caller)
WHERE caller_file.path <> cf.path  // только внешние вызовы
RETURN t.name AS tool,
       cf.name AS impl_file,
       fn.signature AS function_called,
       caller.signature AS caller_signature,
       caller_file.path AS caller_file,
       caller.start_line AS caller_line
ORDER BY caller_file.path, caller.start_line
LIMIT 50;

// ---------------------------------------------------------------------------
// 4. EVIDENCE TRAIL — Какие ошибки были с этим Tool?
// ---------------------------------------------------------------------------
// Используй: чтобы не повторять прошлые ошибки
// Параметры: $tool_name — имя Tool
MATCH (t:Tool {name: $tool_name})<-[:ABOUT]-(e:Evidence)
OPTIONAL MATCH (e)-[:OBSERVED_IN]->(s:Session)
RETURN e.type AS evidence_type,
       e.description AS description,
       e.severity AS severity,
       s.title AS session,
       e.timestamp AS when
ORDER BY e.timestamp DESC
LIMIT 20;

// ---------------------------------------------------------------------------
// 5. EDUCATION GRAPH — Найти KnowledgeEntity по теме
// ---------------------------------------------------------------------------
// Используй: чтобы найти концептуальные знания из education graph
// Параметры: $query — поисковый запрос
// Использует полнотекстовый индекс entitySearch
CALL db.index.fulltext.queryNodes('entitySearch', $query) YIELD node AS ke, score
WHERE ke:KnowledgeEntity
OPTIONAL MATCH (ke)-[r:RELATES_TO]->(related:KnowledgeEntity)
RETURN ke.name AS entity,
       ke.type AS type,
       ke.description AS description,
       score,
       collect(DISTINCT {entity: related.name, predicate: r.predicate}) AS related
ORDER BY score DESC
LIMIT 15;

// ---------------------------------------------------------------------------
// 6. FULL CROSS-GRAPH TRAVERSAL
// ---------------------------------------------------------------------------
// Используй: самый глубокий анализ — Tool → CodeFile → CALLS → другие CodeFile
// Параметры: $tool_name — имя Tool
MATCH path = (t:Tool {name: $tool_name})-[:CODED_IN]->(cf:CodeFile)-[:CONTAINS]->(fn:CodeFunction)-[:CALLS*1..3]->(callee:CodeFunction)
MATCH (callee_file:CodeFile)-[:CONTAINS]->(callee)
RETURN t.name AS tool,
       cf.name AS tool_file,
       fn.signature AS entry_point,
       callee.signature AS reaches,
       callee_file.name AS in_file,
       length(path) AS hops
ORDER BY hops, callee_file.name
LIMIT 100;

// ---------------------------------------------------------------------------
// 7. ORPHAN DETECTION — Какие Tool не имеют CODED_IN связи?
// ---------------------------------------------------------------------------
// Используй: найти инструменты без реализации (документация без кода)
MATCH (t:Tool)
WHERE NOT (t)-[:CODED_IN]->(:CodeFile)
RETURN t.name AS orphan_tool,
       t.description AS description
ORDER BY t.name
LIMIT 50;

// ---------------------------------------------------------------------------
// 8. DEAD CODE — Какие CodeFile нигде не вызываются?
// ---------------------------------------------------------------------------
// Используй: найти мёртвый код
MATCH (cf:CodeFile)-[:CONTAINS]->(fn:CodeFunction)
WHERE NOT ()-[:CALLS]->(fn)
  AND NOT (cf)-[:HAS_ENTRY_POINT]->(:CodeEntryPoint)
RETURN cf.path AS file_path,
       collect(fn.name) AS unused_functions,
       count(fn) AS unused_count
ORDER BY unused_count DESC
LIMIT 30;

// ---------------------------------------------------------------------------
// 9. SYSTEM TOPOLOGY — Все сервисы и их зависимости
// ---------------------------------------------------------------------------
// Используй: понять архитектуру системы
MATCH (s:Service)
OPTIONAL MATCH (s)-[:DEPLOYED_ON]->(h:Host)
OPTIONAL MATCH (s)-[:EXPOSES_PORT]->(p:Port)
OPTIONAL MATCH (s)-[:DEPENDS_ON]->(dep:Service)
RETURN s.name AS service,
       s.status AS status,
       h.name AS host,
       collect(DISTINCT p.number) AS ports,
       collect(DISTINCT dep.name) AS depends_on
ORDER BY service;

// ---------------------------------------------------------------------------
// 10. CROSS-GRAPH: Tool + Education Connection
// ---------------------------------------------------------------------------
// Используй: найти academic обоснование для выбора Tool
// Параметры: $tool_name — имя Tool
MATCH (t:Tool {name: $tool_name})-[:CODED_IN]->(cf:CodeFile)
MATCH (cf)-[:CONTAINS]->(fn:CodeFunction)
// Ищем KnowledgeEntity которые могут быть релевантны
MATCH (ke:KnowledgeEntity)
WHERE ke.description CONTAINS t.name
   OR ke.name CONTAINS t.name
RETURN t.name AS tool,
       ke.name AS knowledge,
       ke.type AS knowledge_type,
       ke.description AS knowledge_desc
LIMIT 10;
