# Hermes Portable v4 — Глубокое описание проекта

**Версия:** Hermes Agent v0.16.0 (2026.6.5)  
**Сборка:** 2026-07-19  
**Автор:** Nous Research / адаптация Pavel  

---

## 1. Обзор

**Hermes Agent** — открытый фреймворк автономных AI-агентов от Nous Research. В отличие от классических
чат-ассистентов, Hermes Agent — это **среда исполнения** для LLM-моделей с полным доступом к файловой системе,
терминалу, Docker, веб-браузеру и внешним API. Модель (LLM) выступает в роли «мозга», а Hermes предоставляет:
инструменты (tools), плагины (plugins), навыки (skills), систему памяти, оркестрацию агентов и API-шлюз.

**Hermes Portable v4** — это самодостаточный дистрибутив, упакованный для переноса на USB-накопителе.
Не требует интернета для установки: Docker-образы, GUI-бинари, Python-пакеты — всё включено.
Достаточно Docker и любого Linux (ARM64 или x86_64).

### Ключевые возможности

- **33 AI-агента** — от сбора требований до деплоя и аудита
- **133 навыка (skills)** — процедурная память: накопленные workflow, приёмы, проверенные паттерны
- **9 хуков** — перехват событий жизненного цикла (старт/стоп сессии, pre/post tool call)
- **4 плагина** — MCP-серверы (Neo4j, OpenCode), роутинг, gating
- **Quality Gates** — обязательные проверки перед деплоем: SAST, PII-аудит, fitness-функции
- **Dual-arch:** ARM64 (Jetson, Raspberry Pi 5) + x86_64 (обычные ПК/серверы)
- **Санитизация:** нулевое содержание ключей API, IP-адресов и персональных данных

---

## 2. Архитектура

### 2.1. Системная топология

```
                         ┌─────────────────────────────────┐
  Пользователь           │         дистрибутив              │
  ───────────            │                                  │
      │                  │  docker/                         │
      ├── GUI ─────────► │    hermes-agent-arm64.tar.gz     │
      │   (Electron)     │    hermes-agent-x64.tar.gz       │
      │                  │                                  │
      └── CLI ─────────► │  gui-arm64/ + gui-x64/          │
          (curl)         │    Hermes (Electron binary)      │
                         │                                  │
                         │  hermes-core/                    │
                         │    agents/  skills/  hooks/      │
                         │    plugins/ scripts/ gates/      │
                         │    cron/    config.yaml.template │
                         └─────────────────────────────────┘
                                    │
                    docker load -i  │  cp -r hermes-core/
                                    ▼
┌───────────────────────────────────────────────────────────┐
│                    Хост-машина (Linux)                     │
│                                                           │
│  ~/.hermes-portable/          ~/.hermes-portable-dash/    │
│  ┌─────────────────┐         ┌──────────────────┐        │
│  │ Gateway (:18649)│◄────────│ Dashboard (:9123)│        │
│  │                 │  HTTP   │                  │        │
│  │ LLM API + Tools │         │ WebSocket + REST │        │
│  │ + Agents + Skills│        │ + GUI backend    │        │
│  └────────┬────────┘         └────────▲─────────┘        │
│           │                           │                   │
│           │  LLM API calls            │  WebSocket        │
│           ▼                           │                   │
│    ┌──────────────┐          ┌───────┴────────┐          │
│    │ LLM Provider │          │ Electron GUI   │          │
│    │ (OpenRouter/ │          │ (launch.sh)    │          │
│    │  DeepSeek/   │          └────────────────┘          │
│    │  Anthropic)  │                                      │
│    └──────────────┘                                      │
└───────────────────────────────────────────────────────────┘
```

### 2.2. Docker-контейнеры

| Компонент | Порт | Назначение |
|-----------|------|------------|
| **Gateway** | `:18649` | LLM API-сервер, исполнение тулов, оркестрация агентов |
| **Dashboard** | `:9123` | WebSocket-сервер для GUI, управление сессиями, мониторинг |

Оба контейнера используют один Docker-образ `hermes-agent:latest`, но **разные тома данных**:
- Gateway: `~/.hermes-portable/` → `/opt/data`
- Dashboard: `~/.hermes-portable-dash/` → `/opt/data`

### 2.3. Поток данных (один ход агента)

```
Пользователь → GUI (WebSocket) → Dashboard → Gateway (HTTP API)
                                                    │
                                          ┌─────────┴──────────┐
                                          │ Conversation Loop   │
                                          │  ┌───────────────┐  │
                                          │  │ LLM Call       │──► LLM Provider
                                          │  │ (system prompt │   (OpenRouter/
                                          │  │  + memory      │    DeepSeek/
                                          │  │  + skills      │    Anthropic)
                                          │  │  + tools)      │  │
                                          │  └───────┬───────┘  │
                                          │          │ ответ    │
                                          │          ▼          │
                                          │  ┌───────────────┐  │
                                          │  │ Tool Dispatch  │  │
                                          │  │ (terminal,     │  │
                                          │  │  file, web,    │  │
                                          │  │  browser, ...) │  │
                                          │  └───────┬───────┘  │
                                          │          │ результат│
                                          │          ▼          │
                                          │  ┌───────────────┐  │
                                          │  │ Hooks Fire     │  │
                                          │  │ (pre/post tool)│  │
                                          │  └───────────────┘  │
                                          └────────────────────┘
                                                    │
                                    Финальный ответ → Dashboard → GUI
```

---

## 3. Каталог агентов

Агенты делятся на **primary** (доступны как кнопки в GUI) и **subagent** (вызываются оркестраторами).

### 3.1. Оркестраторы (Plan → Execute → Verify)

| Агент | Роль |
|-------|------|
| **plan1** (GLM Orchestrator) | GLM-4.7-Flash как оркестратор, DeepSeek как исполнители. Полный цикл (требования → архитектура → разработка → тестирование → деплой) |
| **plan2** (Research Orchestra) | 5 агентов-исследователей параллельно, Pre-Flight Gate, Progressive Disclosure |
| **plan3** (Multi-Model Router) | 3 модели одновременно: Qwen3.6 (reasoning) + Nex (coding) + AgentWorld (simulation). Fugu/Fusion Pipeline |
| **plan4** (Single-Model Diffusion) | DiffusionGemma 26B-A4B — одна модель для всего цикла |
| **plan** | Оркестратор по умолчанию: Research Orchestra + Pre-Flight Gate |
| **aflow-orchestrator** | MCTS-поиск оптимального workflow. Запускает параллельные ветки, сравнивает результаты |
| **claw-orchestrator** | 5-фазный цикл обслуживания Claw-графа: discover → process → draft → review → close |
| **observer-orchestrator** | Координирует 4 наблюдателя: Auditor, Critic, Idea Generator, Knowledge Curator |

### 3.2. Аналитический конвейер

| Агент | Роль |
|-------|------|
| **requirements-agent** | Сбор требований: уточняющие вопросы, перезапуск цикла при неоднозначности |
| **requirements-interviewer** | Структурированное интервью: SPIN, 5 Whys, SMART, persona-based |
| **system-analyst** | Системный аналитик: возвращает команду к целям, проверяет соответствие требованиям на всех фазах |
| **researcher_old** | Глубокий анализ: итеративный поиск, создаёт sub-агентов для ускорения |
| **deep-plan-researcher** | Трёхфазный исследовательский пайплайн с гейтами, Claw-интеграцией, debate mode |
| **architect-agent** | Архитектор: проектирует топологию, границы модулей, протоколы, верифицирует с пользователем |
| **enterprise-architect** | Кросс-проектная валидация: проверяет архитектурные решения против всей системы |
| **project-architect** | Neo4j impact analysis: запросы CALLS/IMPORTS/CONTAINS для предсказания последствий изменений |
| **techlead-agent** | Техлид: StandardWork контракты, ownership matrix, import contracts, dependency audit |

### 3.3. Разработчики

| Агент | Стиль |
|-------|-------|
| **dev-creative** | Альтернативные архитектуры, нестандартные решения. Quality gates после каждого изменения |
| **dev-pragmatic** | Стандартные паттерны, промышленный стиль |
| **dev-skeptic** | Минимальные изменения, KISS extreme |
| **dev-maverick** | Ломает все правила, последнее средство. Даже здесь — quality gates |
| **developer-agent** | Упёртый разработчик: делает всё, чтобы код работал, может нарушать запреты ради результата |
| **build** (General) | Полный доступ: весь жизненный цикл, глубокие аналитические способности |
| **general** | Все инструменты: полный цикл с аналитикой |

### 3.4. Наблюдатели (Observer System)

| Агент | Функция |
|-------|---------|
| **auditor** | Проверяет качество процесса, полноту контекста, соответствие AGENTS.md |
| **critic** | Ищет over-engineering, лишнее, причины усложнения |
| **idea-generator** | Ловит неслышанные идеи, предлагает ADAS-мутации (автоматические улучшения) |
| **knowledge-curator** | Извлекает знания из артефактов, сохраняет в Neo4j knowledge graph |

### 3.5. Специалисты

| Агент | Зона ответственности |
|-------|---------------------|
| **security-agent** | SAST gate: bandit, gitleaks, pip-audit, semgrep. Ищет баги, дыры, утечки |
| **tester-agent** | Приёмочное и регрессионное тестирование. Проверяет требования → тесты |
| **deployment-agent** | Развёртывание: health-check, smoke-test, мониторинг |
| **devops-engineer** | Integration Gate: валидирует wiring модулей, проверяет imports/вызовы |
| **jidoka-evaluator** | Jidoka-оценщик: проверяет результат разработчика против StandardWork контрольного списка |

---

## 4. Санитизация и безопасность

Дистрибутив **не содержит**:

- **API-ключей** (все заменены на `<YOUR_..._KEY>` или `CHANGEME`)
- **Персональных путей** (`/home/username/` → `/home/user/`)
- **IP-адресов** (`<YOUR_VPS_IP>` → `<YOUR_VPS_IP>`)
- **Базы данных сессий** (`state.db` — 858 MB, исключена)
- **Файлов памяти** (`memories/` — исключены)
- **Observer-состояния** (`observer_state.db`, `observer_queue.jsonl` — исключены)
- **Секретных файлов** (`.sudo_pass`, `auth.json`, `.env` — исключены)

**1299 файлов** скопировано, **328** санитизированы (замены в тексте). Все API-ключи — через `.env`, который пользователь создаёт из `.env.example`.

---

## 5. Система Quality Gates

В дистрибутив включена система обязательных гейтов качества — 14 гейтов на 10 фаз
жизненного цикла разработки. Гейты реализованы в `hermes-core/gates/` (24 файла:
YAML-конфигурация, Python-движок, 10 gate-классов, git-хуки) и интеграционных
скриптах `hermes-core/scripts/`.

### 5.1. Принцип работы

Каждый гейт — это deny-by-default барьер (по модели OPA): фаза блокируется, пока
все проверки не пройдены. Проверки описаны декларативно в `gates/all_gates.yaml`.
Движок `quality_gate_runner.py` выполняет их и возвращает код:
- `0` — ALL_PASSED
- `1` — FAILED
- `2` — GATE_RUNNER_CRASHED
- `3` — GATE_RUNNER_TAMPERED

Pre-Flight Gate (`orchestrator_gate.py`) запускается перед Phase 6 (Implementation)
и проверяет контракты, порты, переменные окружения и доступность наблюдателей.
Хук `preflight-check.py` срабатывает на первом ходу сессии: Neo4j health,
свежесть памяти и навыков.

### 5.2. Каталог гейтов

| Фаза | Гейт | Ключевые проверки | Авто |
|------|------|-------------------|:----:|
| **0** Bootstrap | `bootstrap` | FS writable, ≥100 MB, AGENTS.md, venv, Python3, agent registry | ✅ |
| **1** Requirements | `requirements` | 6 BACCM-измерений, acceptance criteria verifiable, NFR measurable | — |
| **2** System Analysis | `system-analysis` | WSM-альтернативы, goal tree достижим, 5 Whys | — |
| **3** Research | `research` | Searchbox health, Neo4j health, ≥3 типа источников | ⚡ |
| **4** Architecture | `architecture` | Module contracts, port conflicts, cross-project validation | ⚡ |
| **5** Plan | `plan` | TDD tasks исполнимы, OWNERSHIP matrix, capability fabrication scan | ⚡ |
| **5.5** Pre-Flight | `preflight` | Все сервисы healthy, порты свободны, env vars, 4 observer'а живы | ✅ |
| **6** Implementation | `implementation` | Tools на разработчика, worktree isolation, codebase graph | — |
| **6a** Integration | `integration` | Нет orphan-модулей, integration tests green | — |
| **6.5** Verification | `verification` | Spec conformance, goal tree complete, root cause addressed | — |
| **7** Security | `security` | bandit, semgrep, gitleaks, pip-audit доступны | ✅ |
| **8** Deployment | `deployment` | Target reachable, permissions, Docker, ports free | — |
| **8.5** Acceptance | `acceptance` | Acceptance tests executable, traceability matrix | — |
| **9** Post-Deploy | `postdeploy` | Monitoring accessible, logs readable | — |
| **10** Iterate | `iterate` | 4 observer-отчёта, Neo4j для synthesis, AFlow comparison | — |

✅ = полностью автоматизирован  
⚡ = частично (есть автоматические + ручные проверки)  
— = шаблон (`check: "true"`), требует имплементации под проект

### 5.3. Текущее состояние

- **Автоматизировано:** ~40% проверок (bootstrap 6 шт., pre-flight 3 шт.,
  security tools 3 шт., частично ещё ~5 шт.)
- **Шаблоны:** ~60% проверок имеют `check: "true"` — каркас готов, требуется
  конкретизация под проект (пути, инструменты, порты)
- **Интеграция:** git-хуки (`pre-commit`, `pre-push`, `commit-msg`),
  хук `preflight-check.py` на старте сессии, вызов из оркестраторов
  (`orchestrator_gate.py` перед Phase 6)

Инфраструктура полная, каркас из 14 гейтов работает. Для production-использования
требуется замена шаблонных `"true"` на реальные проверки под конкретный проект.

---

## 6. Быстрый старт

```bash
# 1. Скопировать с USB
cp -r hermes_portable_v4 ~/ && cd ~/hermes_portable_v4

# 2. Запустить backend (авто-определит ARM64/x64)
./start-backend.sh

# 3. Настроить LLM-ключ
nano .env  # раскомментировать OPENROUTER_API_KEY=...

# 4. Запустить GUI
./launch.sh

# Статус: ./status.sh  |  Стоп: ./stop.sh  |  CLI: ./chat.sh
```

---

*Документ сгенерирован Hermes Agent, v0.16.0. Сборка дистрибутива: 2026-07-19.*
