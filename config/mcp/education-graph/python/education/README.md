"""
Education Agent — README.

## Назначение

Education Agent — это MemoryProvider, который непрерывно наполняет граф знаний
`education` (отдельный от claw `platform`) из сообщений агента, документов
и выводов инструментов.

## Ключевые принципы

1. **Отдельный граф `education`** — не смешивается с claw Tool графом.
   Кросс-линковка делается отдельно через `graph_enricher.cross_link_knowledge_to_tools()`.

2. **Security first** — каждая запись проходит 4-уровневую валидацию:
   - Сигнатурный анализ (regex, <1ms)
   - Эвристический анализ (encoding detection, <1ms)
   - LLM gate (если есть подозрения, ~500ms)
   - Cybersecurity classification (CVE, RCE, XSS, ~300ms)

3. **Prompt injection — отдельный блокирующий шаг.** Если severity >= MEDIUM,
   весь входной текст ОТВЕРГАЕТСЯ полностью. Результат аудита записывается
   в `SecurityAssessment` ноду для аудита.

4. **Triple extraction** как в NVIDIA txt2kg: (subject, predicate, object, confidence).

5. **Entity resolution** — cosine similarity > 0.85 → merge.

## Интеграция с Hermes

### Вариант A: Как MemoryProvider (непрерывный фон)

```python
# hermes_memory_provider.py
from graph_tool.python.education.education_agent import EducationAgent

class EducationMemoryProvider(MemoryProvider):
    async def sync_turn(self, session_id, user_msg, assistant_msg):
        await self.agent.ingest(
            f"User: {user_msg}\nAssistant: {assistant_msg}",
            source_id=session_id,
            source_type="session",
        )

    async def prefetch(self, query):
        results = await self.agent.search_knowledge(query)
        return format_as_memory_context(results)
```

### Вариант B: Как MCP tool (ручной вызов)

Добавить в `graph-tool` MCP сервер:
```json
{
  "name": "education_ingest",
  "description": "Ingest text into the education knowledge graph"
}
```

### Вариант C: Как cron job (периодический)

```bash
# Каждые 6 часов — транзитивное замыкание
0 */6 * * * python -m graph_tool.python.education.education_agent --infer

# Каждые 24 часа — кросс-линк с claw
0 2 * * * python -m graph_tool.python.graph_enricher --cross-link-knowledge
```

## Структура графа `education`

```
(:KnowledgeEntity)                    // Сущность знания
    ↓ RELATES_TO {predicate, conf}    // Связь между сущностями
(:KnowledgeEntity)

(:Fact)                               // Извлечённый факт (аудит)
    ↓ ABOUT / ABOUT_OBJECT            // Связь факта с сущностями
(:KnowledgeEntity)

(:LearningSource)                     // Источник обучения
    ↓ PRODUCED                        // Что произвёл источник
(:Fact)

(:SecurityAssessment)                 // Оценка безопасности
    ↓ (связана с KnowledgeEntity по entity_name)
(:KnowledgeEntity)
```

## Безопасность

### Почему важна валидация на prompt injection:

Education Agent накапливает знания, которые позже впрыскиваются в system prompt агента.
Если злоумышленник внедрит вредоносную запись в граф знаний (через веб-поиск,
загрузку документа, или через пользовательское сообщение), она может быть использована
для атаки на агента.

### Как это предотвращается:

1. Каждая запись валидируется ДО попадания в граф
2. `SecurityAssessment` записывается даже для заблокированных записей (аудит)
3. При `prefetch()` — контекст помечается как "authoritative reference data" (как в Hermes)
4. LLM gate использует отдельную модель для оценки injection

## Использование

```bash
# Инициализация графа
python -m graph_tool.python.graph.init_education

# Ингест из stdin
echo "Docker depends on containerd for container runtime" | \
  python -m graph_tool.python.education.education_agent --ingest --json

# Поиск
python -m graph_tool.python.education.education_agent --search "docker container" --json

# Транзитивное замыкание
python -m graph_tool.python.education.education_agent --infer
```
