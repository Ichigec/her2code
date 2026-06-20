# GRAPH_TOOL — Глубокий анализ и архитектурные решения

## 0. Ответ на главный вопрос: MCP vs Hermes Tool

### Решение: **РАСШИРЕНИЕ MCP СЕРВЕРА** (claw-graph)

**Мотивация (5 причин):**

| Критерий | MCP extension (claw-graph) | Hermes native tool |
|---|---|---|
| **Переиспользование** | Любой агент (Hermes, OpenCode, Claude) через MCP | Только Hermes |
| **Жизненный цикл** | Независимый процесс, hot-reload без рестарта агента | Привязан к сессии Hermes |
| **Существующая интеграция** | Уже подключен в `config.yaml:596` (claw-graph) | Нужно писать toolset с нуля |
| **Кэширование** | Connection pool Neo4j переиспользуется | Новое подключение на каждый turn |
| **Batch-операции** | Можно вызывать из cron/скриптов напрямую | Только через агента |

**Единственное исключение — Education Agent:** он должен быть **Hermes MemoryProvider** (постоянный фон), но поиск через него — через MCP.

### Почему не встроенный tool Hermes:
- Hermes tool живёт в сессии: умрёт при `/reset`, потеряет connection pool
- Ограничен tool schema (нет стриминга для batch GNN)
- Не может работать асинхронно в фоне (education agent)

---

## 1. Архитектура поиска: BM25 + Cosine + Graph Enrichment

### Почему BM25 + Cosine, а не только эмбеддинги?

| Подход | False positives | Recall по редким терминам | Память |
|---|---|---|---|
| **Только BM25** | Низкие | Отличный (exact match) | ~O(N) |
| **Только cosine** | Средние | Хороший (семантика) | O(N×D) |
| **BM25 + Cosine (RRF)** | **Минимальные** | **Отличный (оба мира)** | O(N×D) + индекс |

**Reciprocal Rank Fusion (RRF)** — доказанная формула из [arXiv:2404.16130](https://arxiv.org/abs/2404.16130) (Microsoft GraphRAG):
```python
score = Σ α_i / (k + rank_i)   # k=60, α_BM25=0.3, α_cosine=0.7
```

### Pipeline поиска:
```
Query → BM25 (top-50) + Cosine (top-50)
      → RRF fusion → top-20
      → Graph enrichment (1-hop neighbors, DEPENDS_ON, CO_OCCURS_WITH)
      → Re-rank by graph connectivity score
      → Final top-10 with context
```

---

## 2. GNN: почему GAT, а не предобученная модель

### Почему НЕ предобученная модель (типа ULTRA, GraphSAGE pre-trained):

| Фактор | GAT с нуля | Pre-trained GNN |
|---|---|---|
| **Специфика графа** | Инструменты ПК/ОС — уникальная доменная область | Обучены на generic графах (Wikipedia, биология) |
| **Размер графа** | ~100-1000 нод (маленький) | Предобучены на миллионах нод — overkill |
| **Edge типы** | DEPENDS_ON, CO_OCCURS_WITH, DUPLICATE_OF — специфичные | Не матчатся с generic отношениями |
| **Скорость inference** | <10ms на графе из 1000 нод | Те же ~10ms (GNN inference быстрый) |
| **Адаптация** | Можно дообучать на новых данных | Fine-tune рискованный на малом графе |

### Выбор GAT (Graph Attention Network) — почему:

1. **Attention heads** (heads=4) — каждая голова учит свой паттерн: одна — зависимости, другая — ко-встречаемость
2. **Лучше чем GCN** для гетерогенных графов: attention weight-ит важность соседей
3. **Лучше чем GraphSAGE** для маленьких графов: attention более выразителен на малых выборках
4. **Архитектура из NVIDIA GRetriever** (`dgx-spark-txt2kg`) — проверена на задаче KG+RAG

### Когда и как запускать GNN:

```bash
# 1. Обучение (разово или при значительном росте графа >2x)
python -m graph_tool.python.gnn.train_gnn \
  --epochs 5 --hidden 1024 --layers 4 --heads 4

# 2. Инференс (через MCP или Python)
# Автоматически вызывается при search_tools_hybrid с параметром use_gnn=true
```

**Триггеры для переобучения:**
- Количество нод выросло >2x с последнего обучения
- Добавлены новые типы отношений
- Падение accuracy на тестовом сплите >10%

---

## 3. Education Agent — дизайн

### Отдельный граф `education` — почему:

| Причина | Детали |
|---|---|
| **Namespace изоляция** | Claw — инструменты и сессии. Education — знания и связи |
| **Разные constraints** | Claw: tool_id UNIQUE. Education: entity_name UNIQUE |
| **Разные политики безопасности** | Education требует prompt injection validation на каждую запись |
| **Разные индексы** | Education: entitySearch (fulltext), entityEmbeddings (vector) |
| **Независимый lifecycle** | Education граф можно дропнуть/пересоздать без потери claw данных |

### Структура графа education:

```cypher
// === НОДЫ ===
(:KnowledgeEntity {         // Сущность знания
  name: STRING,             // Уникальное имя
  type: STRING,             // tool|concept|command|file|service|vulnerability
  description: STRING,
  embedding: LIST<FLOAT>,   // 384-dim (all-MiniLM-L6-v2)
  confidence: FLOAT,        // 0.0-1.0
  source: STRING,           // session_id, doc_path, url
  created_at: DATETIME,
  updated_at: DATETIME
})

(:SecurityAssessment {      // Оценка безопасности
  id: STRING,
  entity_name: STRING,
  has_prompt_injection: BOOLEAN,
  injection_severity: STRING,  // none|low|medium|high|critical
  injection_patterns: LIST<STRING>,
  cybersecurity_risk: STRING,  // none|info|warning|critical
  cve_references: LIST<STRING>,
  validated_by: STRING,        // model name
  validated_at: DATETIME
})

(:Fact {                    // Извлечённый факт (triple)
  subject: STRING,
  predicate: STRING,
  object: STRING,
  confidence: FLOAT,
  source: STRING,
  extracted_at: DATETIME
})

(:LearningSource {          // Источник обучения
  id: STRING,
  type: STRING,             // session|document|url|tool_output
  path: STRING,
  ingested_at: DATETIME,
  triple_count: INTEGER
})

// === СВЯЗИ ===
(:KnowledgeEntity)-[:RELATES_TO {
  predicate: STRING,
  confidence: FLOAT,
  source: STRING
}]->(:KnowledgeEntity)

(:KnowledgeEntity)-[:HAS_ASSESSMENT]->(:SecurityAssessment)
(:LearningSource)-[:PRODUCED]->(:Fact)
(:Fact)-[:ABOUT]->(:KnowledgeEntity)
(:Fact)-[:ABOUT_OBJECT]->(:KnowledgeEntity)
(:KnowledgeEntity)-[:EQUIVALENT_TO {confidence: FLOAT}]->(:KnowledgeEntity)
(:KnowledgeEntity)-[:SUPERSEDES {at: DATETIME}]->(:KnowledgeEntity)
(:KnowledgeEntity)-[:SECURITY_RELEVANT]->(:KnowledgeEntity)
```

### Конвейер Education Agent:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INGESTION: сообщение/документ/вывод тула                │
│    ↓                                                        │
│ 2. SECURITY VALIDATION (ОТДЕЛЬНЫЙ ШАГ)                     │
│    ├── Prompt Injection Detection (regex + LLM)             │
│    ├── Cybersecurity Risk Assessment                       │
│    └── Если injection_severity >= "medium" → REJECT         │
│    ↓                                                        │
│ 3. TRIPLE EXTRACTION (аналог TXT2KG)                       │
│    LLM: extract (subject, predicate, object, confidence)    │
│    ↓                                                        │
│ 4. ENTITY RESOLUTION + DEDUP                                │
│    Cosine similarity > 0.85 → MERGE                         │
│    ↓                                                        │
│ 5. MERGE в Neo4j education граф                            │
│    Новые связи, обновление confidence, timestamp            │
│    ↓                                                        │
│ 6. TRANSITIVE INFERENCE (фоном, при idle)                   │
│    A → B → C ⇒ A → C                                       │
│    ↓                                                        │
│ 7. EMBEDDING UPDATE (только для изменённых нод)             │
└─────────────────────────────────────────────────────────────┘
```

### Prompt Injection Detection (шаг 2 детально):

```python
SECURITY_PIPELINE = [
    # Уровень 1: Сигнатурный анализ (быстрый, regex)
    ("signature", detect_known_injection_patterns()),  # <1ms
    
    # Уровень 2: Эвристический (быстрый, rules)
    ("heuristic", detect_suspicious_encoding()),        # <1ms
    
    # Уровень 3: LLM-based (медленный, но точный)
    ("llm_gate", llm_injection_judge()),               # ~500ms
    
    # Уровень 4: Cybersecurity classification
    ("cybersec", classify_cybersecurity_risk()),        # ~300ms
]
```

---

## 4. Интеграция с Hermes

### MCP конфигурация (добавить в config.yaml):

```yaml
mcp_servers:
  claw-graph:          # существующий — остаётся
    ...
  graph-tool:          # НОВЫЙ — hybrid search + education
    command: python
    args:
      - -m
      - graph_tool.python.mcp_server
    enabled: true
    env:
      NEO4J_URI: bolt://127.0.0.1:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      NEO4J_DATABASE: platform
      EDUCATION_DATABASE: education
```

### Education Agent как Hermes MemoryProvider:

```yaml
# В config.yaml Hermes
memory:
  provider: education_neo4j  # новый провайдер
```

---

## 5. Бенчмарки и метрики

| Метрика | Target | Измерение |
|---|---|---|
| Precision@10 (hybrid) | >0.85 | Ручная разметка 200 запросов |
| Recall@10 (hybrid) | >0.90 | Полнота покрытия известных тулзов |
| MRR (hybrid) | >0.80 | Mean Reciprocal Rank |
| Prompt injection F1 | >0.95 | Набор из 500 injection примеров |
| Triple extraction precision | >0.75 | Ручная валидация 100 троек |
| GNN re-rank improvement | >+5% MRR | A/B тест с/без GNN |

---

## 6. arXiv references

| Бумага | Что используем |
|---|---|
| [2404.16130](https://arxiv.org/abs/2404.16130) — MS GraphRAG | RRF fusion + community detection (Phase 2) |
| [2312.10997](https://arxiv.org/abs/2312.10997) — GRetriever | GAT + LLM для KGQA |
| [2409.18563](https://arxiv.org/abs/2409.18563) — Prompt Injection Taxonomy | Security validation уровни |
| [2407.21783](https://arxiv.org/abs/2407.21783) — Hybrid Search RRF | BM25 + Dense retrieval fusion |
| [2308.07134](https://arxiv.org/abs/2308.07134) — Graph of Thoughts | Transitive inference patterns |

---

## 7. Roadmap реализации

| Phase | Что | Файлы | Статус |
|---|---|---|---|
| **1** | MCP server с hybrid search | `mcp/` | ✅ Готово |
| **2** | Python hybrid searcher | `python/hybrid_searcher.py` | ✅ Готово |
| **3** | Graph enrichment | `python/graph_enricher.py` | ✅ Готово |
| **4** | Education graph schema | `python/graph/education_graph.cypher` | ✅ Готово |
| **5** | Education Agent core | `python/education/` | ✅ Готово |
| **6** | Security validator | `python/education/security_validator.py` | ✅ Готово |
| **7** | GNN trainer | `python/gnn/train_gnn.py` | ✅ Готово |
| **8** | GNN re-ranker | `python/gnn/gnn_reranker.py` | ✅ Готово |
