# graph_tool — Готовый код для Hermes

## Что принято: MCP server extension (а не Hermes native tool)

**Решение и 5 причин:**
1. **Переиспользование** — любой агент (Hermes, OpenCode) через MCP
2. **Hot-reload** — независимый процесс, перезапуск без рестарта агента
3. **Уже подключено** — `claw-graph` MCP в `config.yaml:596`
4. **Connection pool** — переиспользуется между вызовами
5. **Batch-операции** — cron/скрипты вызывают напрямую

**Исключение:** Education Agent — как Hermes MemoryProvider (непрерывный фон), но поиск — через MCP.

---

## Как использовать

### 1. Установка зависимостей

```bash
# MCP сервер (Node.js)
cd graph_tool/mcp && npm install

# Python (hybrid search, education, GNN)
cd graph_tool/python && pip install -e .
# Для GNN:
pip install -e ".[gnn]"
```

### 2. MCP сервер — hybrid search + graph traverse

Добавить в `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  # Существующий claw-graph — ОСТАЁТСЯ
  claw-graph:
    args:
      - /home/user/.hermes/plugins/claw-neo4j/mcp-server.mjs
    command: node
    enabled: true
    env:
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      NEO4J_URI: bolt://127.0.0.1:7687
      NEO4J_USER: neo4j

  # НОВЫЙ graph-tool — hybrid search + graph enrichment
  graph-tool:
    command: node
    args:
      - /home/user/projects/graph_tool/mcp/mcp-server.mjs
    enabled: true
    env:
      NEO4J_URI: bolt://127.0.0.1:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
```

### 3. Education Graph — инициализация

```bash
# Создать БД education и применить схему
python -m graph_tool.python.graph.init_education

# Или пересоздать с нуля
python -m graph_tool.python.graph.init_education --drop-first
```

### 4. Education Agent — интеграция с Hermes

**Как MemoryProvider (рекомендуется):**

Создать файл `~/.hermes/hermes-agent/plugins/memory/education_neo4j/__init__.py`:

```python
from graph_tool.python.education import EducationAgent, EducationConfig

class MemoryProvider(ABC):
    async def sync_turn(self, session_id, user_msg, assistant_msg):
        await self.agent.ingest(
            f"User: {user_msg}\nAssistant: {assistant_msg}",
            source_id=session_id,
            source_type="session"
        )
    
    async def prefetch(self, query):
        results = await self.agent.search_knowledge(query)
        return f"<memory-context>\nRelevant knowledge:\n{results}\n</memory-context>"
```

### 5. Когда запускать GNN

```bash
# Первичное обучение (граф >= 50 нод с DEPENDS_ON рёбрами)
python -m graph_tool.python.gnn.train_gnn --epochs 5 --hidden 1024

# Только оценка (без переобучения)
python -m graph_tool.python.gnn.train_gnn --eval-only

# Переобучение (граф вырос > 2x)
python -m graph_tool.python.gnn.train_gnn --epochs 10 --hidden 2048 --output ./output_v2
```

**Триггеры для переобучения:**
- Количество нод выросло > 2x
- Новые типы отношений добавлены
- MRR упал > 10% на тестовом сплите

---

## Структура проекта

```
graph_tool/
├── ANALYSIS.md                       # Глубокий анализ архитектуры
├── README.md                         # Этот файл
├── mcp/                              # MCP сервер (Node.js)
│   ├── package.json
│   ├── mcp-server.mjs                # stdio MCP server
│   ├── search.js                     # BM25 + Cosine + RRF + graph enrichment
│   └── neo4j_client.js               # Neo4j connection pool
└── python/                           # Python пакет
    ├── pyproject.toml
    ├── requirements.txt
    ├── hybrid_searcher.py            # BM25 + Cosine + RRF search
    ├── graph_enricher.py             # CO_OCCURS_WITH, transitive deps, cross-link
    ├── gnn/
    │   ├── __init__.py
    │   ├── train_gnn.py              # GAT training on Neo4j graph
    │   └── gnn_reranker.py           # Inference re-ranker
    ├── education/
    │   ├── __init__.py
    │   ├── education_agent.py        # Core education agent
    │   ├── triple_extractor.py       # TXT2KG-style triple extraction
    │   ├── security_validator.py     # 4-layer security validation
    │   └── README.md                 # Education agent docs
    └── graph/
        ├── education_graph.cypher    # Education graph schema
        └── init_education.py         # Graph initialization
```

---

## Ключевые архитектурные решения

### Почему BM25 + Cosine (а не только эмбеддинги):
- BM25 ловит точные совпадения (названия тулов, команд)
- Cosine ловит семантику (описания, контекст)
- RRF fusion (k=60) — из MS GraphRAG paper [2404.16130]

### Почему GAT, а не предобученная GNN:
- Tool graph — уникальный домен, не Wikipedia
- Графы маленькие (~100-1000 нод) — pre-trained overkill
- Attention heads учат конкретные паттерны: зависимости, co-use кластеры
- Переобучение < 5 минут, можно часто

### Почему отдельный граф education (не claw):
- Namespace изоляция (разные constraints)
- Разные политики безопасности
- Нельзя случайно повредить claw инструменты
- Можно дропнуть/пересоздать без потерь

### Почему security validation — отдельный блокирующий шаг:
- Prompt injection в граф знаний → инжектится в system prompt → атака на агента
- Multi-layer: signature (<1ms) → heuristic (<1ms) → LLM gate (~500ms) → cybersec
- MEDIUM+ severity → полный REJECT
- Аудит всех попыток (включая заблокированные) через SecurityAssessment ноды
