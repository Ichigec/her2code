# Agent Roles — полная таблица (v2.0)

## Сводка

| # | Фаза | Subagent | Что происходит | Сопровождает весь цикл? |
|---|------|----------|---------------|------------------------|
| 1 | Требования | `requirements-agent` | Задаёт уточняющие вопросы (среда, ограничения, пользователи, scope). НЕ делает предположений. Перезапускает цикл после ответов. Артефакт: `docs/requirements/<slug>.md` | Нет |
| 2 | Системный анализ | `system-analyst` | SMART → сбор данных → 5 Whys → дерево целей → ≥2 альтернативы → WSM/AHP-выбор → точная задача разработчику. Возвращает команду к целям. Делает фазу 6.5 (verification gate). Артефакт: `docs/system-analysis/<slug>.md` | **Да** |
| 3 | Глубокий анализ | `researcher` | Classification gate → research questions → literature review → hypotheses → iterative data collection (2/6/25 итераций) → dedup + quality scoring → structured citations. Создаёт sub-агентов для параллельного поиска. Артефакт: `docs/research/<slug>.md` | **Да** |
| 4 | Архитектура | `architect` | Топология, протоколы, границы модулей, интеграции. Верифицирует с пользователем. Лазит в education graph, memory, claw graph. Помогает команде. Артефакт: `docs/architecture/<slug>.md` | **Да** |
| 5 | Техлид | `techlead` | План (BDUF), управляет 7 разработчиками, код-ревью, KISS/DRY/YAGNI/SOLID. Консультируется с архитектором и аналитиком. Фиксирует лучшие практики после деплоя. Артефакт: `.hermes/plans/<ts>-<slug>.md` | Нет |
| 6 | Разработка | `developer-1…7` | RED → GREEN → REFACTOR. 1 баг = 1 фикс = 1 проверка. Может нарушать запреты (socat, qemu, rootfs). Не сдаётся. НЕ лазает во вне. Артефакт: код + тесты + lockfiles | Нет |
| 6.5 | Верификация | `system-analyst` | 4 проверки: spec conformance, goal tree, root cause, abstraction level. Deviation routing при расхождении | — |
| 7 | Безопасность | `security-agent` | SAST gate (semgrep/bandit/gitleaks/pip-audit/npm audit). Ищет пароли, ключи, утечки, угрозы КОМАНДЕ. Critical/High блокируют деплой. Артефакт: `docs/security/<slug>.md` | Нет |
| 8 | Деплой | `deployment-agent` | Deploy + health check. Не работает → возврат к фазе 1–2. Артефакт: `docs/deployment/<slug>.md` | Нет |
| 8.5 | **Приёмочное тестирование** 🧪 | **`tester-agent`** | Автономное тестирование развёрнутой системы. Сверка с 3 источниками требований: Requirements doc, System Analysis doc, user acceptance criteria. Traceability matrix (тест→требование). **НИКОГДА не делегирует тестирование пользователю.** Артефакт: `docs/tests/<slug>.md` | Нет |
| 9 | Пост-деплой | `researcher` | Evidence collection → hypothesis validation → statistical analysis → surprise discovery. Артефакт: `docs/research-post/<slug>.md` | — |
| 10 | Итерации + Аудит | Оркестратор + Auditor | Metrics snapshot, retrospective. **Auditor report:** что улучшить, основные проблемы, delegation quality, все проблемы. Артефакт: `docs/retrospectives/<date>-<slug>.md` | — |

## Старшие агенты (сопровождают весь цикл)

| Агент | Роль | Может создавать sub-агентов | Инструменты |
|-------|------|---------------------------|-------------|
| **System Analyst** | Возвращает к целям, проверяет соответствие, задаёт вопросы если что-то меняет картину | Да | file, search, web |
| **Researcher** | Ищет информацию, решает проблемы, структурирует знания | Да | search, web, file |
| **Architect** | Лазит в education graph, memory, claw graph — ищет что поможет команде | Да | file, search, web, browser |
| **Auditor** 🆕 | Контролирует качество делегирования: полный ли контекст, правильные ли toolsets, не потеряны ли требования. Ищет Tester autonomy violations. Молчит до Phase 10. | Нет | file, search, session_search |

## Новые роли (v2.0)

### Tester (#8, Phase 8.5)

| Свойство | Значение |
|----------|---------|
| **Мандат** | Автономное приёмочное тестирование. НИКОГДА не говорит «проверь сам». |
| **3 источника** | Requirements doc, System Analysis doc, user acceptance criteria |
| **Traceability matrix** | Каждый тест → ID требования |
| **Инструменты** | `terminal` (curl/adb/ping), `browser`, `read_file` (логи/конфиги), `search_files` |
| **НЕ использует** | `clarify` — тестирует сам, не делегирует пользователю |
| **NFR** | `time curl` (скорость), `ab`/`wrk` (нагрузка), TLS-проверки (безопасность) |
| **Артефакт** | `docs/tests/<slug>.md` — таблица с результатами |
| **Эскалация** | Failures → System Analyst (#2): fix (→ Phase 6) или accept deviation |

### Orchestrator — Managerial Oversight (усиление v2.0)

6 кросс-фазных проверок на каждом quality gate:
1. **Requirement propagation** — требование из Phase 1 дошло до Tester?
2. **Root cause resolution** — починили причину или симптом?
3. **Goal tree completion** — каждый sub-goal реализован и протестирован?
4. **Context completeness** — все требования переданы в context агенту?
5. **Agent accountability** — агент реально сделал работу или сказал «done» без артефакта?
6. **Tester autonomy** — Tester не просил пользователя тестировать?

### Auditor — Delegation Quality (усиление v2.0)

Новые критерии:
- **Delegation quality** — правильный ли context? Правильные toolsets?
- **Requirement propagation** — требование выжило все фазы?
- **Agent accountability** — агент сказал «done» без артефакта?
- **Tester autonomy violations** — Tester попросил пользователя тестировать?

Новая секция в отчёте: **Delegation Quality** — таблица проблем делегирования.

## Файлы персон

```
~/.hermes/agents/
├── general.md              🧠  основной агент (10 фаз, full lifecycle)
├── build.md                🔨  полная копия general
├── plan.md                 🎼  оркестратор + менеджер
├── requirements-agent.md   📋  сборщик требований
├── system-analyst.md       🔍  системный аналитик
├── researcher.md           🔬  исследователь
├── architect-agent.md      🏗️  архитектор
├── techlead-agent.md       👷  техлид
├── developer-agent.md      ⚡  разработчик
├── security-agent.md       🛡️  безопасник
├── tester-agent.md         🧪  тестировщик (NEW)
├── deployment-agent.md     🚀  деплой
```
