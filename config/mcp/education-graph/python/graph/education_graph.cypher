// Education Knowledge Graph schema — отдельная БД `education`.
// Не пересекается с claw platform графом (namespace изоляция).
// Все statement идемпотентны (IF NOT EXISTS).

// --- KnowledgeEntity (сущности знаний) ---
CREATE CONSTRAINT knowledge_entity_name IF NOT EXISTS
FOR (ke:KnowledgeEntity) REQUIRE ke.name IS UNIQUE;

CREATE CONSTRAINT learning_source_id IF NOT EXISTS
FOR (ls:LearningSource) REQUIRE ls.id IS UNIQUE;

CREATE CONSTRAINT security_assessment_id IF NOT EXISTS
FOR (sa:SecurityAssessment) REQUIRE sa.id IS UNIQUE;

CREATE CONSTRAINT fact_key IF NOT EXISTS
FOR (f:Fact) REQUIRE (f.subject, f.predicate, f.object, f.source) IS UNIQUE;

// --- Индексы ---
CREATE INDEX knowledge_entity_type IF NOT EXISTS
FOR (ke:KnowledgeEntity) ON (ke.type);

CREATE INDEX knowledge_entity_confidence IF NOT EXISTS
FOR (ke:KnowledgeEntity) ON (ke.confidence);

CREATE INDEX security_assessment_entity IF NOT EXISTS
FOR (sa:SecurityAssessment) ON (sa.entity_name);

CREATE INDEX fact_confidence IF NOT EXISTS
FOR (f:Fact) ON (f.confidence);

// --- Fulltext index для BM25 поиска ---
CREATE FULLTEXT INDEX entitySearch IF NOT EXISTS
FOR (ke:KnowledgeEntity) ON EACH [ke.name, ke.description, ke.type];

// --- Векторный индекс для cosine similarity (dim=384, all-MiniLM-L6-v2) ---
// Требует Neo4j >= 5.15
CREATE VECTOR INDEX entityEmbeddings IF NOT EXISTS
FOR (ke:KnowledgeEntity) ON (ke.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }
};

// --- Индексы для связей ---
CREATE INDEX learning_source_type IF NOT EXISTS
FOR (ls:LearningSource) ON (ls.type);

CREATE INDEX security_severity IF NOT EXISTS
FOR (sa:SecurityAssessment) ON (sa.has_prompt_injection);
