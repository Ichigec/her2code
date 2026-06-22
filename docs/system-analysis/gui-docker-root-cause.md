# System Analysis: GUI + Docker — Root Cause Investigation

> **Date:** 2026-06-21
> **PID:** SANITIZED_PID
> **Agent:** #2 System Analyst
> **Scope:** her2code Docker+GUI integration

---

## SMART-Цель

**S**pecific: Обеспечить 100% работоспособность Desktop GUI при подключении к Docker-контейнеру Hermes (загрузка до 100%, WebSocket-соединение установлено, чат функционирует).

**M**easurable: GUI загружается до 100% (не 24% или 95%), WebSocket /api/ws открывается за <5s, прокси не падает в течение 24h uptime, Telegram не блокирует запуск gateway.

**A**chievable: Все проблемы имеют конкретные технические причины с известными фиксами.

**R**elevant: Критично для использования Docker как production-среды Hermes с GUI-доступом.

**T**ime-bound: Фиксы реализуемы в течение 1-2 спринтов.

---

## Проблема 1: GUI зависает на 24%

### Наблюдение
Desktop GUI при подключении к Docker показывает прогресс 24% с сообщением "Connecting to remote Hermes backend" и не продвигается дальше.

### 5 Whys

**Why 1:** Почему GUI зависает на 24%?
- Потому что HTTP health check (GET /health) к Docker-гейтвею не возвращает успешный ответ в течение 45-секундного таймаута waitForHermes().

**Why 2:** Почему /health не отвечает?
- Потому что Desktop GUI шлёт запрос на http://localhost:18648/health, но реальный трафик может идти через прокси (status-proxy.py), который форвардит на неправильный порт.

**Why 3:** Почему прокси форвардит на неправильный порт?
- Потому что status-proxy.py (v1) hardcoded GATEWAY_URL=http://localhost:8648 (дефолтный порт gateway на хосте), а Docker слушает API_SERVER_PORT=18648.

**Why 4:** Почему в коде захардкожен порт 8648?
- Потому что прокси создавался как временный workaround для локального (не-Docker) gateway, и значение порта не было параметризовано под Docker-окружение.

**Why 5:** Почему это не было обнаружено при тестировании?
- Потому что тестирование Docker+GUI интеграции не было автоматизировано, а ручное тестирование проводилось в условиях где порты совпадали или прокси не использовался.

### ROOT CAUSE
**Несовпадение портов между прокси (8648) и Docker API server (18648).**

### Evidence
- status-proxy.py строка 7: GATEWAY = os.environ.get('GATEWAY_URL', 'http://localhost:8648')
- docker-compose.yml строка 14: API_SERVER_PORT=18648
- /tmp/proxy.log: циклические 404 ошибки на /api/logs?file=gui
- proxy2.py: ИСПРАВЛЕНО на GATEWAY_URL=http://localhost:18648

---

## Проблема 2: GUI зависает на 95%

### Наблюдение
Desktop GUI проходит health check (24% -> 94%), но зависает на ~95%. Чат не открывается, WebSocket-соединение не устанавливается.

### 5 Whys

**Why 1:** Почему GUI зависает на 95%?
- Потому что Renderer (Electron) не может открыть WebSocket-соединение к /api/ws на Docker-гейтвее.

**Why 2:** Почему /api/ws недоступен?
- Потому что endpoint /api/ws реализован ТОЛЬКО в Dashboard (hermes_cli/web_server.py, строка 8735: @app.websocket("/api/ws")), а Docker-контейнер запускает только gateway run (без dashboard).

**Why 3:** Почему Docker не запускает dashboard?
- Потому что docker-compose.yml (her2code) содержит только сервис hermes с командой gateway run. Dashboard — отдельный сервис в hermes-agent/docker-compose.yml, но не включён в her2code/docker-compose.yml.

**Why 4:** Почему API server не предоставляет /api/ws?
- Потому что API server (api_server.py) — это OpenAI-compatible REST API. Архитектурно WebSocket /api/ws принадлежит Dashboard, а не API server.

**Why 5:** Почему Desktop GUI не может работать без /api/ws?
- Потому что архитектура Desktop GUI (main.cjs) требует ДВА шага: (1) HTTP /health для верификации бэкенда, (2) WebSocket /api/ws для chat surface. Это фундаментальное требование.

### ROOT CAUSE
**Docker-контейнер запускает только gateway run (API server), но Desktop GUI требует Dashboard с WebSocket /api/ws.**

### Evidence
- api_server.py: 40+ роутов, ни одного websocket или /api/ws
- web_server.py строка 8735: @app.websocket("/api/ws") — единственное место с WebSocket
- main.cjs строка 4459: advanceBootProgress('backend.remote', ..., 24) -> HTTP health check
- main.cjs строка 4464: progress: 94 -> после HTTP, renderer ещё должен открыть WS
- docker-compose.yml (her2code): только сервис hermes, dashboard отсутствует

---

## Проблема 3: Прокси умирает

### Наблюдение
status-proxy.py периодически перестаёт отвечать, требует перезапуска. В логах — циклические ошибки 404 и 403.

### 5 Whys

**Why 1:** Почему прокси умирает?
- Потому что это однопоточный http.server.HTTPServer (Python stdlib), который блокируется на медленных/зависших upstream запросах.

**Why 2:** Почему upstream запросы зависают?
- Потому что: (а) порт форвардинга неверный (8648 вместо 18648) -> connection refused -> повторные попытки; (б) таймаут 30-120с для медленных endpoint'ов; (в) один медленный запрос блокирует все остальные.

**Why 3:** Почему используется однопоточный сервер?
- Потому что прокси проектировался как быстрый workaround для разработки, а не production-grade решение.

**Why 4:** Почему не используется aiohttp (уже установлен в gateway)?
- Потому что прокси — отдельный Python-скрипт вне Docker-контейнера. Он не имеет доступа к зависимостям gateway.

**Why 5:** Почему прокси не встроен в Docker-образ как часть gateway?
- Потому что архитектурное решение «прокси как внешний адаптер» было принято для быстрого прототипирования без пересборки Docker-образа.

### ROOT CAUSE
**Однопоточная архитектура прокси + неверный порт форвардинга + отсутствие мониторинга и авторестарта.**

### Evidence
- status-proxy.py строка 73: HTTPServer(('0.0.0.0', PROXY_PORT), Proxy).serve_forever() — однопоточный
- /tmp/proxy.log: циклические ERR: HTTP Error 404: Not Found (порт 8648)
- proxy3.py: улучшенная версия с CORS, но всё ещё однопоточная

---

## Проблема 4: Telegram блокирует запуск

### Наблюдение
Docker-контейнер пытается инициализировать Telegram-адаптер, что приводит к ошибкам подключения и потенциально блокирует старт gateway.

### 5 Whys

**Why 1:** Почему Telegram пытается запуститься в Docker?
- Потому что docker-entrypoint.sh пытается удалить Telegram из config.yaml через sed, но эта операция ненадёжна.

**Why 2:** Почему sed-подход ненадёжен?
- Потому что: (а) sed удаляет строки от telegram: до следующего ключа — сложный regex чувствительный к форматированию YAML; (б) 2>/dev/null || true скрывает ошибки; (в) если config.yaml не найден за 30 секунд, entrypoint продолжает БЕЗ удаления Telegram.

**Why 3:** Почему Telegram в config.yaml внутри Docker-образа?
- Потому что config.yaml копируется из config/config.yaml.example который содержит все платформы включая Telegram.

**Why 4:** Почему HERMES_DISABLE_MESSAGING=1 не решает проблему?
- Потому что HERMES_DISABLE_MESSAGING — "ghost variable": установлена в docker-compose.yml (строка 17), но НЕ ИСПОЛЬЗУЕТСЯ в коде hermes-agent (0 упоминаний).

**Why 5:** Почему переменная была добавлена но не реализована?
- Потому что это был интент отключить messaging платформы, но реализация не была завершена — вместо кода положились на entrypoint sed-workaround.

### ROOT CAUSE
**HERMES_DISABLE_MESSAGING — ghost variable. Отсутствие нативной поддержки отключения платформ.**

### Evidence
- HERMES_DISABLE_MESSAGING: 0 вхождений в коде hermes-agent (только в docker-compose.yml)
- docker-entrypoint.sh строка 19-22: sed с 2>/dev/null || true
- gateway/run.py строка 4567-4614: цикл инициализации всех enabled платформ



## Дерево целей (Goal Tree)

```
GOAL: GUI + Docker работает стабильно
|
+-- SUB-GOAL 1: GUI загружается до 100%
|   +-- T1.1: Починить порт прокси (8648 -> 18648)
|   +-- T1.2: Обеспечить /api/ws на Docker-гейтвее
|   +-- T1.3: Интеграционный тест GUI<->Docker (health + ws)
|
+-- SUB-GOAL 2: Прокси не умирает
|   +-- T2.1: Заменить однопоточный http.server на aiohttp/nginx
|   +-- T2.2: Добавить health check + авторестарт прокси
|   +-- T2.3: Мониторинг (логи, алерты при падении)
|
+-- SUB-GOAL 3: Telegram не блокирует запуск
|   +-- T3.1: Имплементировать HERMES_DISABLE_MESSAGING в коде
|   +-- T3.2: Санитизировать config.yaml на этапе сборки образа
|   +-- T3.3: Добавить enabled: false для Telegram в Docker-конфиге
|
+-- SUB-GOAL 4: Архитектурная целостность
    +-- T4.1: Выровнять порты между хостом и Docker
    +-- T4.2: Документировать требуемые endpoint-ы для GUI
    +-- T4.3: CI-тест: docker compose up -> GUI health check -> WS connect
```

---


## Альтернативы решения

### Альтернатива A: «Минимальные фиксы» (Quick Wins)

**Описание:** Исправить только критические баги без архитектурных изменений.
- A1: status-proxy.py → использовать GATEWAY_URL=http://localhost:18648 (как в proxy2.py/proxy3.py)
- A2: docker-compose.yml → добавить сервис dashboard
- A3: docker-entrypoint.sh → заменить sed на Python-скрипт для удаления Telegram
- A4: start.sh → направлять GUI на прокси (18649) а не напрямую на Docker (18648)

**WSM-оценка:**

| Критерий | Вес | Оценка (1-5) | Взвешенно |
|----------|-----|-------------|-----------|
| Effectiveness (решает проблему) | 0.30 | 4 | 1.20 |
| Implementation Cost (время) | 0.25 | 5 | 1.25 |
| Risk (низкий=5) | 0.15 | 4 | 0.60 |
| Maintainability | 0.15 | 2 | 0.30 |
| Completeness (все сценарии) | 0.15 | 2 | 0.30 |
| **ИТОГО** | **1.00** | | **3.65** |

**Плюсы:** Быстро (1-2 дня), минимальный риск регрессий.
**Минусы:** Не решает архитектурные проблемы (прокси однопоточный, ghost variable остаётся).

---

### Альтернатива B: «Архитектурный рефакторинг» (Production-Grade)

**Описание:** Полный рефакторинг интеграции GUI↔Docker с устранением корневых причин.

- B1: Встроить прокси в Docker-образ как часть gateway (использовать aiohttp). API server получает все endpoint-ы (stubs не нужны).
- B2: Добавить /api/ws в API server (выделить WebSocket handler из dashboard в общий модуль, подключить в api_server.py).
- B3: Имплементировать HERMES_DISABLE_MESSAGING — чтение переменной в gateway/run.py, пропуск платформ при =1.
- B4: Санитизировать config.yaml на этапе сборки Docker-образа (Python-скрипт в Dockerfile).
- B5: Унифицировать порты: 18648 как единый порт API server + WebSocket (без прокси).
- B6: Добавить интеграционные тесты в CI (docker compose up → health → ws connect).

**WSM-оценка:**

| Критерий | Вес | Оценка (1-5) | Взвешенно |
|----------|-----|-------------|-----------|
| Effectiveness (решает проблему) | 0.30 | 5 | 1.50 |
| Implementation Cost (время) | 0.25 | 3 | 0.75 |
| Risk (низкий=5) | 0.15 | 3 | 0.45 |
| Maintainability | 0.15 | 5 | 0.75 |
| Completeness (все сценарии) | 0.15 | 5 | 0.75 |
| **ИТОГО** | **1.00** | | **4.20** |

**Плюсы:** Полное решение, устраняет корневые причины, production-grade, тестируемо.
**Минусы:** Требует 1-2 недели, больше риск регрессий, требует координации с upstream.

---

### Альтернатива C: «Docker как полный стек» (Dashboard-in-Docker)

**Описание:** Docker запускает и gateway, и dashboard в одном стеке. GUI подключается к dashboard.

- C1: docker-compose.yml → добавить сервис dashboard (из hermes-agent/docker-compose.yml).
- C2: GUI подключается к порту 9119 (dashboard) вместо 18648 (API server).
- C3: Прокси форвардит на оба порта (или убрать прокси, использовать dashboard напрямую).
- C4: Telegram отключается через переменные окружения платформы или entrypoint.

**WSM-оценка:**

| Критерий | Вес | Оценка (1-5) | Взвешенно |
|----------|-----|-------------|-----------|
| Effectiveness (решает проблему) | 0.30 | 4 | 1.20 |
| Implementation Cost (время) | 0.25 | 4 | 1.00 |
| Risk (низкий=5) | 0.15 | 4 | 0.60 |
| Maintainability | 0.15 | 4 | 0.60 |
| Completeness (все сценарии) | 0.15 | 3 | 0.45 |
| **ИТОГО** | **1.00** | | **3.85** |

**Плюсы:** Использует существующую архитектуру, dashboard уже поддерживает /api/ws.
**Минусы:** Два сервиса вместо одного, прокси всё ещё нужен, не решает ghost variable.

---

## WSM-выбор

**Победитель: Альтернатива B (Архитектурный рефакторинг)** с WSM 4.20.

**Рекомендация:** Реализовать Альтернативу B итеративно:
- **Sprint 1 (неделя 1):** Quick wins из Альтернативы A — восстановить базовую работоспособность.
- **Sprint 2 (неделя 2):** Архитектурные улучшения — /api/ws, HERMES_DISABLE_MESSAGING, CI тесты.



## Точная задача разработчику

### Sprint 1 — Критические фиксы

```
# T1: Исправить порт в status-proxy.py
# Файл: her2code/status-proxy.py, строка 7
# Было:  GATEWAY = os.environ.get('GATEWAY_URL', 'http://localhost:8648')
# Стало: GATEWAY = os.environ.get('GATEWAY_URL', 'http://localhost:18648')

# T2: Добавить dashboard сервис в docker-compose.yml
# Файл: her2code/docker-compose.yml
# Добавить сервис dashboard (см. hermes-agent/docker-compose.yml строки 63-76)

# T3: Исправить удаление Telegram в entrypoint
# Файл: her2code/docker-entrypoint.sh
# Заменить sed на надёжное удаление через Python (или использовать yq)
```

### Sprint 2 — Архитектурные улучшения

```
# T4: Добавить /api/ws handler в api_server.py
# Выделить WebSocket handler из hermes_cli/web_server.py в общий модуль
# Подключить в gateway/platforms/api_server.py

# T5: Имплементировать HERMES_DISABLE_MESSAGING
# Файл: gateway/run.py (функция start_gateway или GatewayRunner.__init__)
# Перед циклом инициализации платформ: проверять os.getenv("HERMES_DISABLE_MESSAGING")

# T6: Интеграционный тест
# CI: docker compose up → curl /health → ws connect → успех
```

### Верификация

```
# 1. Docker должен принимать /health
curl -sf http://localhost:18648/health

# 2. Docker должен принимать /api/ws (WebSocket upgrade)
# (проверить через wscat или скрипт)

# 3. GUI должен загружаться до 100%
HERMES_DESKTOP_REMOTE_URL=http://localhost:18648 npm --prefix apps/desktop start

# 4. Прокси должен форвардить без ошибок
tail -f /tmp/proxy.log  # не должно быть 404/502

# 5. Telegram НЕ должен пытаться запуститься
docker compose logs hermes | grep -i telegram  # должно быть пусто
```

---

## Приложение: Сводка корневых причин

| # | Проблема | Симптом | Корневая причина | Фикс |
|---|----------|---------|-----------------|------|
| 1 | GUI 24% | HTTP health check не проходит | Прокси форвардит на порт 8648 вместо 18648 | GATEWAY_URL=http://localhost:18648 |
| 2 | GUI 95% | WebSocket не устанавливается | /api/ws есть только в Dashboard, не в API server | Добавить /api/ws в API server ИЛИ запустить dashboard |
| 3 | Прокси умирает | Однопоточный сервер блокируется | http.server + неверный порт + нет мониторинга | aiohttp/nginx прокси, health check, авторестарт |
| 4 | Telegram блокирует | Gateway пытается запустить Telegram без токена | HERMES_DISABLE_MESSAGING — ghost variable | Имплементировать переменную + санитизация конфига |

---

**Verdict:** Все 4 проблемы имеют общую корневую тему — **разрыв между хост-окружением и Docker-окружением**. Порты, endpoint-ы, конфигурация платформ — всё предполагает хост-запуск и не адаптировано для Docker. Решение: систематическое выравнивание Docker-окружения с ожиданиями GUI и документирование контракта (требуемые порты, endpoint-ы, переменные окружения).
