# Idea Generator Checkpoint #4 — Phase 4 (Architecture)

> **Project:** `hermes-p0-memory_20260615_232649`
> **Phase 4 artifact:** `docs/architecture/hermes-p0-memory.md` (1330 строк)
> **Date:** 2026-06-15
> **Observer:** Idea Generator #12
> **Methodology:** Cross-reference architecture claims against real codebase in `~/.hermes/hermes-agent/`

---

## 1. Неслышанные идеи / Упущенные связи

### 1.1 `add_system_provider()` не существует в реальном коде — архитектура предполагает несуществующую инфраструктуру

**Артефакт утверждает:**
> `MemoryManager.add_system_provider()` — separate path from `add_provider()`. System providers are always active, not subject to `_has_external` limit.

**Реальный код (`agent/memory_manager.py:258`):**
```python
def add_provider(self, provider: MemoryProvider) -> None:
    is_builtin = provider.name == "builtin"
    if not is_builtin:
        if self._has_external:
            logger.warning("Rejected memory provider '%s'...")
            return
        self._has_external = True
    self._providers.append(provider)
```

**Проблема:** Метод `add_system_provider()` **не существует**. Единственный путь регистрации — `add_provider()`, который имеет guard `_has_external` для всего, кроме `name="builtin"`. SegTreeMem (name="segtree") будет заблокирован, если уже зарегистрирован любой external провайдер (Honcho, Mem0, etc.).

**Необходимо:** Либо добавить реальный `add_system_provider()`, либо расширить guard в `add_provider()` списком исключений (системные провайдеры: builtin + segtree). Без этого фикса архитектурное решение D1 (SegTreeMem = system provider) нереализуемо.

### 1.2 ConsolidationManager дублирует существующий ContextCompressor

**Артефакт:** `ConsolidationManager` — новый компонент с LLM-суммаризацией, structured prompts, бюджетом токенов.

**Реальный код:** `agent/context_compressor.py` — `ContextCompressor(ContextEngine)` уже делает:
- LLM-суммаризацию разговора (structured, iterative summary updates)
- Бюджетирование токенов (`max_summary_tokens`, `tail_token_budget`)
- Protection head/tail messages
- `on_session_end()` хук для flush'а состояния
- Интеграцию с `MemoryProvider.on_pre_compress()`

**Архитектура ни разу не упоминает `ContextCompressor`.** Это критическое упущение — два компонента будут делать LLM-суммаризацию параллельно, потенциально конфликтуя за LLM-бюджет и создавая дублирующиеся сводки.

**Рекомендация:** ConsolidationManager должен либо интегрироваться с ContextCompressor (переиспользовать его prompting/LLM-клиент), либо архитектура должна явно объяснить, почему нужен отдельный пайплайн.

### 1.3 Plugin discovery блокирует второй активный провайдер

**Реальный код (`plugins/memory/__init__.py:13`):**
> «Only ONE provider can be active at a time, selected via `memory.provider` in config.yaml.»

**Артефакт:** SegTreeMem как system provider должен работать **одновременно** с external провайдером.

**Проблема:** Plugin discovery + `agent_init.py` загружает ровно один провайдер через `load_memory_provider("honcho")`. SegTreeMem как «всегда активный» должен загружаться отдельно от конфига `memory.provider`. Текущая архитектура загрузки не поддерживает два одновременных провайдера на уровне инициализации агента.

### 1.4 `on_session_end` — неоднозначность триггера

В кодовой базе существует **два разных** `on_session_end`:

1. **Plugin hook** (`agent/conversation_loop.py:4943-4959`): Вызывается плагин-системой в конце **каждого вызова** `run_conversation()` (per-turn). Это хук для плагинов (cleanup, flushing).

2. **Memory provider lifecycle** (`run_agent.py:2881-2906`): `shutdown_memory_provider()` вызывает `memory_manager.on_session_end(messages)` только на **реальных границах сессии** (CLI exit, /reset, gateway timeout).

**Артефакт говорит:** «MemoryManager.on_session_end() → triggers ConsolidationManager.consolidate() in background thread.»

**Проблема:** Если consolidation триггерится через provider `on_session_end` (границы сессии) — консолидация происходит редко. Если через plugin `on_session_end` (per-turn) — слишком часто. Архитектура не уточняет, какой именно hook используется. Вероятно, правильный ответ: **per-session** (через `shutdown_memory_provider`), но это означает, что консолидация не произойдёт для сессий, которые forked/branched (они используют `commit_memory_session`, не `shutdown_memory_provider`).

### 1.5 `memory_consolidations` не интегрирована с FTS5/search

**Артефакт добавляет:** `memory_consolidations` таблицу с `content` колонкой.
**Артефакт НЕ добавляет:** FTS5 индекс на `memory_consolidations.content`.

**Проблема:** Когда пользователь делает `session_search("June 2026 deployment")`, поиск идёт только по `messages` (FTS5). Консолидированные сводки невидимы для поиска. Запрос «чем я занимался в июне 2026?» не найдёт monthly narrative.

**Решение:** Добавить FTS5 виртуальную таблицу для `memory_consolidations` ИЛИ расширить существующий FTS5 индекс на `messages` включением consolidated summaries. Также нужно модифицировать `session_search` для поиска в обоих источниках.

### 1.6 TemporalScorer vocabulary — stale после консолидации

**Артефакт:** `TemporalScorer.build_vocabulary(messages)` при `initialize()`. Vocabulary строится из активных сообщений один раз.

**Проблема:** После консолидации сообщения становятся `active=0`. Vocabulary остаётся построенным на старых данных. TF-IDF scoring будет использовать термины из уже неактивных сообщений — IDF (inverse document frequency) будет некорректным. Новые сообщения, добавленные после initialize(), не попадут в vocabulary.

**Решение:** Periodic rebuild vocabulary (на cron daily) или инкрементальное обновление IDF при каждой консолидации.

### 1.7 SegmentTree thread safety не рассмотрен

**Артефакт:** SegmentTree — in-memory структура. ConsolidationManager работает в background thread. MemoryManager читает дерево из main thread.

**Проблема:** Concurrent read (prefetch) + write (rebuild после консолидации?) не защищены. Если consolidation меняет `active=0` и нужно перестроить дерево — read path может увидеть inconsistent state.

**Решение:** Либо read-only дерево (перестройка = создание нового с атомарным swap), либо `threading.RLock`.

---

## 2. Оптимизации пайплайна

### 2.1 Объединить LLM-вызовы ConsolidationManager и ContextCompressor

ContextCompressor уже делает структурированную суммаризацию с похожими параметрами. Вместо двух параллельных LLM-пайплайнов:
- ConsolidationManager использует существующий `AuxiliaryClient` (тот же, что ContextCompressor)
- Результат консолидации подаётся в ContextCompressor как pre-computed summary → compressor пропускает уже обработанные сообщения
- Экономия: 1 LLM вызов вместо 2 на overlapping сообщения

### 2.2 Lazy segment tree — не строить для всех сессий

**Текущий дизайн:** `initialize()` перестраивает дерево из ВСЕХ `active=1` сообщений (100K+).

**Оптимизация:** Строить дерево только для session_id, которые активны (текущая сессия + недавние). Исторические сессии (>30 дней) загружать lazy при первом temporal запросе.

**Выигрыш:** Warmup <50ms вместо <200ms для 100K сообщений, если активных сессий мало.

### 2.3 Parallel tier consolidation

**Текущий дизайн:** daily → weekly → monthly последовательно.

**Оптимизация:** daily и weekly consolidation могут идти параллельно (разные LLM-вызовы, разные message buckets). Только monthly зависит от weekly результатов (roll-up).

**Выигрыш:** ~40% сокращение времени консолидации (2 параллельных LLM вызова вместо 3 последовательных).

### 2.4 Оптимизация SQL запроса в consolidate()

**Текущий дизайн:** `consolidate()` читает ВСЕ active сообщения для сессии, затем bucketing по возрасту.

**Оптимизация:** Один SQL запрос с GROUP BY возрасту:
```sql
SELECT
  CASE
    WHEN (CAST(strftime('%s','now') AS REAL) - timestamp) < 86400 THEN 'recent'
    WHEN (CAST(strftime('%s','now') AS REAL) - timestamp) < 604800 THEN 'daily'
    WHEN (CAST(strftime('%s','now') AS REAL) - timestamp) < 2592000 THEN 'weekly'
    ELSE 'monthly'
  END as tier,
  COUNT(*) as msg_count
FROM messages WHERE session_id = ? AND active = 1
GROUP BY tier;
```
→ Пропустить LLM вызов, если eligible bucket пуст.

### 2.5 Batch cross-session consolidation

**Текущий дизайн:** `consolidate_daily()` — последовательная per-session консолидация.

**Оптимизация:** Собрать ВСЕ daily-eligible сообщения из всех сессий → один batch LLM вызов с секциями по сессиям → один SQL INSERT (bulk). Для weekly roll-up: все daily summaries одной недели → один LLM вызов.

**Выигрыш:** N LLM вызовов → 1 для daily consolidation; консолидация 100 сессий за один cron cycle вместо риска таймаута.

---

## 3. Связи (кого с кем связать)

### 3.1 ConsolidationManager → ContextCompressor
**Пропущено:** Архитектура не упоминает существующий компрессор. Связь:
- `ConsolidationManager._call_llm()` должен использовать тот же `AuxiliaryClient`, что и `ContextCompressor`
- `on_pre_compress()` хук на MemoryProvider — естественный мост для pre-consolidation extraction
- Consolidated summaries могут подаваться в compressor как pre-digested context → compressor сжимает меньше

### 3.2 ConsolidationManager → Auditor / auditor_memory.md
**Пропущено:** Research идентифицирует «auditor_memory.md (0 cycles observed)» как embryonic. Консолидация — идеальный источник данных для Auditor:
- Consolidation facts/decisions → `auditor_memory.md` entries
- Cross-session patterns (weekly digest) → Auditor pattern detection
- HMAC verification failures → security incidents для Auditor

### 3.3 memory_consolidations → session_search discover mode
**Пропущено:** `session_search` должен искать consolidated summaries:
- Добавить FTS5 на `memory_consolidations.content`
- В discover mode: UNION результатов из `messages_fts` и `consolidations_fts`
- Приоритет: consolidated summaries выше raw messages в результатах (более релевантны для «что я делал в прошлом месяце?»)

### 3.4 ConsolidationManager → Neo4j Knowledge Graph
**Пропущено:** Weekly/monthly consolidated summaries — естественные кандидаты для Neo4j:
- Weekly digest → `(:Week {content, facts, decisions})` node
- Cross-session connections → `(:Session)-[:CONSOLIDATED_INTO]->(:Week)` edges
- Monthly narratives → `(:Month)` nodes с aggregated knowledge

### 3.5 SegTreeMem → FTS5 в session_search
**Пропущено:** SegTreeMem использует TF-IDF для content matching. Но `session_search` уже имеет FTS5 с BM25. Связь:
- `prefetch_temporal()` должен использовать FTS5 для content filtering ПЕРЕД temporal scoring
- Не нужно дублировать TF-IDF — FTS5 BM25 качественнее и быстрее (индексирован)
- SegTreeMem: FTS5 query → candidate message_ids → SegmentTree temporal filter → TemporalScorer ranking

### 3.6 ConsolidationManager → cron подсистема Hermes
**Пропущено:** Артефакт показывает гипотетический YAML, но не реальную интеграцию:
- Реальный cron: `cron/jobs.py` + `cron/scheduler.py`
- `consolidate_daily()` должен быть зарегистрирован как cron job с правильным `hermes_home` и профилем
- ConsolidationManager должен запускаться в контексте агента (нужен доступ к LLM), не как standalone скрипт

### 3.7 on_session_end → commit_memory_session (fork/branch protection)
**Пропущено:** Когда сессия форкается (`/branch`), вызывается `commit_memory_session()`, который тоже вызывает `memory_manager.on_session_end()`. Если consolidation триггерится на каждый `on_session_end`, то форки будут создавать дублирующиеся консолидации. Нужен dedup: проверка, была ли эта сессия уже законсолидирована (`SELECT COUNT(*) FROM memory_consolidations WHERE session_id = ?`).

---

## 4. Источники (где взять недостающую информацию)

### 4.1 Реальные файлы, которые архитектура должна цитировать

| What architecture references | Real file to verify against |
|------------------------------|------------------------------|
| `MemoryProvider(ABC)` with lifecycle hooks | `agent/memory_provider.py` (296 строк) |
| `MemoryManager.add_provider()` with `_has_external` | `agent/memory_manager.py:258-321` |
| `MemoryManager.on_session_end()` | `agent/memory_manager.py:507-516` |
| `shutdown_memory_provider()` lifecycle | `run_agent.py:2881-2906` |
| `commit_memory_session()` lifecycle | `run_agent.py:2908-2931` |
| Plugin `on_session_end` (per-turn) | `agent/conversation_loop.py:4943-4959` |
| `ContextCompressor` class | `agent/context_compressor.py:522-2078` |
| Plugin discovery (ONE provider limit) | `plugins/memory/__init__.py:13` |
| `search_messages()` in `hermes_state.py` | `hermes_state.py` — метод SessionDB.search_messages |
| Cron subsystem | `cron/jobs.py`, `cron/scheduler.py` |
| Agent initialization (memory loading) | `agent/agent_init.py:1140` |

### 4.2 Проверить ссылки на arxiv

Системный анализ цитирует:
- `arxiv:2601.02845` — TiMem
- `arxiv:2606.04555` — SegTreeMem

**Предупреждение:** Это future-dated papers (2026). Возможно, это галлюцинации LLM — arxiv ID'ы могут не существовать. Research фаза должна была верифицировать, но research-документ отсутствует в проекте.

### 4.3 Необходимые источники для implementation

| Вопрос | Где искать ответ |
|--------|-----------------|
| Как добавить второй always-active провайдер? | `agent/agent_init.py:1140` — изменить логику загрузки: загружать `memory.provider` + всегда загружать system providers |
| Как зарегистрировать cron job? | `cron/jobs.py` — формат регистрации cron jobs |
| Как FTS5 ищет по messages? | `hermes_state.py` — `_init_db()` для понимания FTS5 схемы |
| Как работает `AuxiliaryClient`? | `agent/auxiliary_client.py` — для LLM вызовов из ConsolidationManager |
| Как плагины получают `hermes_home`? | `hermes_constants.py:get_hermes_home()` |

### 4.4 Отсутствующий research-документ

Проект ссылается на `docs/research/memory-scaffolding.md`, но этот файл **отсутствует** в рабочей директории проекта (`hermes-p0-memory_20260615_232649`). Research есть только в виде конденсированного референса в `orchestration-cycle/references/memory-scaffolding-research.md`. Без полного research-документа архитектура не может верифицировать источники, цитируемые в System Analysis.

---

## 5. Критические риски для следующей фазы (Phase 5 — Plan)

1. **SegTreeMem не может быть загружен одновременно с external провайдером** без изменений в `agent_init.py` и `MemoryManager`. Это блокирующий риск.

2. **ConsolidationManager должен знать о ContextCompressor** — иначе двойная LLM-суммаризация. Архитектура должна быть дополнена секцией «Integration with Existing ContextCompressor».

3. **`on_session_end` ambiguity** — разработчик должен точно знать, какой hook триггерит consolidation. Если ошибочно использовать per-turn plugin hook — consolidation будет вызываться на каждом ходу. Если использовать только `shutdown_memory_provider` — consolidation пропустит fork/branch сессии.

4. **FTS5 integration** — без FTS5 на `memory_consolidations` пользователь не сможет искать consolidated summaries. Это критический пробел в UX.

5. **Thread safety** — SegmentTree + ConsolidationManager в разных потоках без спецификации locking strategy → race conditions.

---

## 6. Рекомендации для доработки архитектуры

| # | Recommendation | Priority | Section to add/modify |
|---|---------------|----------|----------------------|
| R1 | Добавить реальную имплементацию `add_system_provider()` или расширить guard в `add_provider()` | 🔴 P0 | §2.4 MemoryManager |
| R2 | Добавить секцию «Integration with ContextCompressor» — объяснить, почему нужен отдельный ConsolidationManager | 🔴 P0 | §6 Fault Tolerance или новая § |
| R3 | Уточнить trigger для consolidation: `shutdown_memory_provider()` + `commit_memory_session()` с dedup-проверкой | 🔴 P0 | §3.2 Consolidation Flow |
| R4 | Добавить FTS5 индекс на `memory_consolidations.content` и интеграцию с `session_search` | 🟡 P1 | §2.5 session_search, §2.6 migration |
| R5 | Добавить thread safety спецификацию для SegmentTree | 🟡 P1 | §2.2 SegTreeMem |
| R6 | Интеграция с Neo4j Knowledge Graph как future extension point | 🟢 P2 | §8 Module Dependency Graph |
| R7 | Обновить deployment steps — добавить изменение `agent_init.py` для загрузки system provider | 🟡 P1 | §4.2 Deployment Steps |

---

*End of Idea Generator checkpoint #4. Next: deliver to orchestrator for Phase 5 plan adjustments.*
