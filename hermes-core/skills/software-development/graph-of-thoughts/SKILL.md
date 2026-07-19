---
name: graph-of-thoughts
description: "Построение графа размышлений (GoT) после уточнения неоднозначного запроса — декомпозиция, ветвление, синтез."
version: 1.0.0
author: Hermes Agent
tags: [reasoning, clarification, structured-thinking, got]
related_skills: [intent-validation, plan, requirements-analysis]
---

# Graph of Thoughts (GoT)

## Overview

Когда запрос пользователя неоднозначен, агент ДОЛЖЕН сначала уточнить через `clarify()`, а затем — в зависимости от ответа — построить граф размышлений (Graph of Thoughts) для систематического исследования задачи.

## Gate: Clarify → Branch → GoT

### Шаг 1: Обнаружение неоднозначности

Сканируй запрос пользователя на наличие multiple interpretations:

- **Омонимы:** «Mattermost» = сервер или десктоп-клиент?
- **Глаголы действия:** «установи» = Docker, бинарник, snap, из исходников?
- **Область:** «почини» = код, конфиг, данные, процесс?
- **Платформа:** «настрой» = Linux, Docker, Android, VPS?

Если найдено ≥2 интерпретаций → вызывай `clarify()` с вариантами. **Никогда не выбирай молча.**

### Шаг 2: Построение GoT

После получения ответа от пользователя:

```
ROOT: Задача пользователя (конкретная, уточнённая)
├── Branch A: Основной путь (выбор пользователя)
│   ├── Node A1: Что известно? (данные, контекст)
│   ├── Node A2: Что нужно? (инструменты, доступ)
│   ├── Node A3: Шаги (план действий)
│   └── Node A4: Верификация (как проверить успех)
├── Branch B: Альтернативный путь (отвергнутая интерпретация)
│   └── Node B1: Кратко: почему этот путь не выбран
└── Branch C: Краевые случаи / риски
    └── Node C1: Что может пойти не так?
```

### Шаг 2.5: Верификация утверждений (ОБЯЗАТЕЛЬНО)

**Прежде чем строить план (Node A3), проверь ключевые утверждения из Node A1.**

Утверждения из context-compact summaries, memory, и предыдущих сессий — это **гипотезы, не факты**. Особенно опасны утверждения вида «X не работает», «Y сломано», «Z требует исправления» — они могли быть уже исправлены или никогда не были правдой.

**Обязательные действия после Node A1:**
1. Выпиши 2-3 ключевых утверждения, на которых строится анализ
2. Для каждого утверждения — прочитай актуальный код через `read_file` или `search_files`
3. Если утверждение не подтвердилось кодом — ветка A ложная, перестрой анализ

**Пример провала:** Агент поверил summary «`switchAgentPreset` делает bail-out без сессии» и построил 4-фазный план исправления. `read_file` показал бы что код УЖЕ исправлен — весь план был впустую.

### Шаг 3: Исполнение

**Правило 3-шагового лимита:** Максимум 3 шага планирования (Node A1→A2→A3) перед обязательным переходом к execution. После 3 шагов — либо выполни первый actionable шаг, либо явно сообщи пользователю почему не можешь. Не спрашивай «начинаем?» — начинай.

Для ВЕТКИ A (выбранный путь):
1. Собери данные (Node A1) — `web_search`, `search_files`, `read_file`
2. **Верифицируй ключевые утверждения кодом (Шаг 2.5)** — `read_file` реальных файлов
3. Проверь доступ (Node A2) — `terminal` для проверки
4. Выполни шаги (Node A3)
5. Проверь результат (Node A4)

Для ВЕТКИ B — один короткий абзац почему не подходит.

Для ВЕТКИ C — список рисков (1-3 пункта).

### Шаг 4: Синтез

Заверши работу сводкой по графу:

```
## Graph of Thoughts: [задача]

ROOT: [уточнённая задача]
├── ✓ Branch A: [выбранный путь] — [результат]
├── ✗ Branch B: [отвергнутый путь] — [причина отклонения]
└── ⚠ Branch C: [риски] — [митигация]
```

## Пример

**Пользователь:** «установи mattermost»
**Агент:** `clarify(«Mattermost-сервер (self-hosted) или десктоп-приложение?», [«Сервер», «Десктоп-клиент», «Всё вместе»])`
**Пользователь:** «Десктоп-клиент»

**GoT:**
```
ROOT: Установить Mattermost Desktop на Jetson (ARM64)
├── Branch A: Десктоп-клиент (выбран)
│   ├── A1: Ищем ARM64 AppImage на releases.mattermost.com
│   ├── A2: ~/Applications/, права +x
│   ├── A3: Скачать, переместить, chmod
│   └── A4: Запустить --no-sandbox, проверить pgrep
├── Branch B: Сервер (отвергнут)
│   └── B1: Пользователю нужен клиент, не инфраструктура
└── Branch C: Риски
    └── C1: AppImage может не открыть браузер для OAuth
```

## Пример: корневой анализ Hermes Desktop

Реальный пример построения GoT после `clarify()` для разбора проблемы в Hermes Desktop GUI — почему кнопки выбора агента требуют ручного Enter и не обновляют индикатор в чате:

→ `references/hermes-desktop-rca-example.md`

Full post-mortem сессии где агент провалился из-за доверия summary вместо кода:

→ `references/summary-trust-failure.md`

Пример GoT с корректной верификацией через первоисточники (kernel logs, state.db, filesystem) — диагностика OOM-killer крашей Hermes:

→ `references/oom-killer-rca-example.md`

## Правила

1. **Clarify BEFORE GoT.** Без уточнения граф строится на предположениях.
2. **Всегда 2+ ветки.** Даже если ответ пользователя однозначен, добавь Branch B (альтернатива) и Branch C (риски).
3. **Синтез в конце.** Не оставляй граф открытым — заверши сводкой.
4. **Используй clarify() с вариантами.** Не текстовый вопрос без структуры — используй `clarify()` tool.
5. **Код > summary.** Утверждения из context-compact/summary — гипотезы, не факты. Всегда проверяй ключевые утверждения через `read_file` актуального кода, прежде чем строить план исправления.
6. **3 шага → execute.** После 3 шагов планирования — либо выполни первый actionable шаг, либо явно объясни блокер. Не спрашивай разрешения начать.

## Pitfalls

- **Summary-as-truth trap:** Context-compact summaries могут содержать устаревшие или ложные утверждения о состоянии кода («X не работает», «Y сломано»). Агент строит план на основе этих утверждений, не проверив актуальный код. Результат: план исправления того, что уже исправлено. **Защита:** всегда проверяй утверждения из summary через `read_file` перед построением плана.
- **Clarify-mandate override trap:** Когда conversation history содержит мандат `clarify()` (MANDATORY, FIRST and ONLY), последующий context compact НЕ отменяет его. Мандат — системный гейт, context compact — handoff. **Защита:** если видишь мандат `clarify()` — выполни его, даже если потом пришёл context compact.
- **Analysis-paralysis trap:** Агент тратит всю сессию на GoT + анализ + план, но не выполняет ни одного действия. Заканчивает фразой «начинаем?». **Защита:** правило 3-шагового лимита — после 3 шагов планирования ОБЯЗАТЕЛЬНО переходи к execution.
- **Self-report trap:** Subagent summary ≠ verified fact. Если subagent утверждает «файл записан» или «код исправлен» — проверь сам через `read_file`, прежде чем строить на этом планы.
- **clarify-gate plugin blocks GoT execution (CRITICAL).** The `clarify-gate` plugin (`~/.hermes/plugins/clarify-gate/__init__.py`) stores ambiguity state in-memory (`_sessions` dict). On gateway restart, state is lost. If the user's message contains a word from `AMBIGUOUS_PRODUCTS` (e.g. "hermes"), the plugin re-triggers ambiguity detection and blocks ALL action tools — including `terminal`, `write_file`, `patch`, `execute_code`, `delegate_task`. Only read-only tools (`read_file`, `search_files`, `memory`, `skill_view`) remain accessible. This means GoT Step 3 (Execution) is completely blocked. **Symptom:** every tool call returns `⛔ AMBIGUITY NOT RESOLVED`. **Fix:** call `clarify()` to unblock (sets `state.clarified = True`), then proceed. For permanent fix, remove overly broad entries from `AMBIGUOUS_PRODUCTS` in the plugin file. **Applied 2026-07-03:** "hermes" removed from `AMBIGUOUS_PRODUCTS` — was triggering on every message containing "hermes" (i.e. all Hermes development work). Also: `observer-hook` plugin's `__init__.py` was renamed to `.disabled`, causing load failure on every gateway start — renamed back.
