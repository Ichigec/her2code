# Knowledge.md — указатель по графам знаний (agent skill)

> Короткий agent-readable указатель: какие графы есть, какими MCP-инструментами их
> звать, когда какой граф нужен. Полный гайд:
> [`../../docs/graphrag/knowledge-graphs-guide.md`](../../docs/graphrag/knowledge-graphs-guide.md).
> Архитектура памяти: [`../../docs/graphrag/memory-architecture.md`](../../docs/graphrag/memory-architecture.md).
> Модель данных и инварианты: [`AGENTS.md §12–13`](./AGENTS.md).

---

## 1. Граф → когда звать → инструмент

| Граф (DB) | Когда нужен | Чем звать |
|-----------|-------------|-----------|
| `platform` | Вопрос про инструменты / MCP / интеграции; история compaction; траектории и успех/провал ответов | MCP `claw-graph`: `search_tools`, `graph_traverse`, `tool_detail`; REST `graphrag` `/memory/*` |
| `domain` *(Phase 2)* | Вопрос по документам (ADR, runbooks, A2A): сущности, обзоры, тренды | REST `graphrag` `/profiles/adr-corpus/query` |
| `agent_memory` *(Phase 2)* | «Что было верно в момент T», эволюция факта | REST `graphrag` `/profiles/agent-memory/query?as_of=T` |

## 2. Слои памяти (граф `platform`)

| Слой | Узлы | Операция записи (REST `graphrag`) |
|------|------|-----------------------------------|
| STM | `TurnEpisode` | `POST /memory/episodes` |
| MTM | `Checkpoint`, `QAOutcome`, `Trajectory`, `CompactionAction` | `POST /memory/{checkpoints,qa-outcomes,trajectories,compaction-actions}` |
| LTM | `Tool`, `Prospect`, `DomainEntity` | `POST /memory/promote` |

Решения «оставить / изменить / удалить» = рёбра `KEEP` / `UPDATE` / `DELETE`
(типизация осей compaction). См. memory-architecture.md §2.

## 3. Порядок запроса (как у composter)

1. **Граф через MCP/REST** — `claw-graph` (`search_tools` / `graph_traverse` /
   `tool_detail`) или `graphrag` `/memory/search`. Цитируй `evidence` анкеры.
2. **`knowledge/*.json`** — fallback, когда `NEO4J_ENABLED=0` или граф недоступен.
3. **`log.jsonl` + `summaries/`** — editorial-история (только `composter`,
   `claw` читать НЕ может — HARD-инвариант AGENTS.md §7).

## 4. Методы поиска (кратко)

- **fulltext** — известны ключевые слова → `search_tools`.
- **named traversal** — известна стартовая точка → `graph_traverse(pattern, start_id)`.
- **vector** — семантика по тексту → PGVector (`domain`, Phase 2).
- **temporal** — «как было раньше» → Graphiti `as_of` (`agent_memory`, Phase 2).
- **GNN multi-hop** — ULTRA, Phase 2, только при росте графа.

## 5. Создать новый граф

Перед онтологией ответь на вопросы из
[knowledge-graphs-guide.md §3.1](../../docs/graphrag/knowledge-graphs-guide.md):
цель → источник → гранулярность узла → ключ идентичности → темпоральность → объём →
изоляция. Рёбра: направление от владельца к ресурсу, `UPPER_SNAKE`, provenance
`evidence[]`/`sha256` на каждом факте, запись через `MERGE`. Полный чек-лист — §3.3.

---

**Никогда не выдумывай метаданные графа** — цитируй `evidence` анкеры или
`sha256` источника. Произвольный Cypher агентам запрещён — только именованные
traversals (`queries/*.cypher`).
