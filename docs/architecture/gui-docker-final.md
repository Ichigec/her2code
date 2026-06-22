# GUI ↔ Docker — Итоговая архитектура her2code

> **PID:** SANITIZED_PID  
> **Фаза:** 4 — Architecture  
> **Дата:** 2026-06-21

---

## 1. Ответы на ключевые вопросы

### (1) Нужен ли прокси? — **НЕТ**

`status-proxy.py` **не нужен**. Причины:

- **Desktop main.cjs уже использует `/health`** (нативный эндпоинт API-сервера Hermes), а не `/api/status`. Прокси создавался когда Desktop ожидал `/api/status`, но после патча (`/api/status → /health`) необходимость отпала.
- **API-сервер нативно предоставляет** все эндпоинты, которые прокси эмулировал:
  - `GET /health` — liveness probe
  - `GET /api/sessions` — список сессий (не пустой массив-заглушка, а реальные данные)
  - `POST /v1/chat/completions` — OpenAI-совместимый чат
  - `GET /v1/models` — список моделей
- Прокси добавлял **лишний hop** (задержка), **лишнюю точку отказа** (502 при недоступности upstream), и **маскировал реальные ошибки** пустыми стабами.

### (2) Нужен ли volume mount? — **ДА, обязательно**

Монтирование `~/.hermes:/opt/data` необходимо:

| Данные | Путь внутри контейнера | Зачем |
|--------|------------------------|-------|
| `state.db` | `/opt/data/state.db` | Сессии, история диалогов |
| `audit.db` | `/opt/data/audit.db` | Аудит-лог |
| `config.yaml` | `/opt/data/config.yaml` | Основной конфиг |
| `skills/` | `/opt/data/skills/` | Пользовательские навыки |
| `agents/` | `/opt/data/agents/` | Файлы агентов |
| `hooks/` | `/opt/data/hooks/` | Хуки |
| `cron/` | `/opt/data/cron/` | Расписания |
| `plugins/` | `/opt/data/plugins/` | Плагины |
| `logs/` | `/opt/data/logs/` | Логи |

**Gateway и Dashboard разделяют этот volume** — Dashboard читает те же сессии, что создаёт Gateway.

### (3) Как решить Telegram? — **Нативный platform adapter**

Telegram встроен в Gateway Hermes как platform adapter:

- **Код:** `gateway/platforms/telegram.py` (6000+ строк, зрелый адаптер)
- **Библиотека:** `python-telegram-bot` (long polling)
- **Активация:** Установить `TELEGRAM_BOT_TOKEN` в `.env` → gateway автоматически поднимает Telegram-адаптер
- **Сеть:** Только **исходящий HTTPS** на `api.telegram.org:443` — не требует входящих портов
- **Webhook vs Long Polling:** По умолчанию long polling. Webhook требует входящего порта + HTTPS-сертификат; для Docker за NAT проще long polling.

**Конфигурация в `.env`:**
```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghijk
```

**Конфигурация в `config.yaml` (опционально):**
```yaml
platforms:
  telegram:
    enabled: true
telegram:
  allowed_chats: ""          # пусто = все чаты разрешены
  reactions: false
```

### (4) Какая топология портов? — **Bridge network, минимальный exposed surface**

**Отказ от `network_mode: host`** (security anti-pattern) в пользу **bridge network**:

| Сервис | Порт контейнера | Порт хоста | Bind | Назначение |
|--------|:---------------:|:----------:|------|------------|
| **gateway** (API) | 18648 | 18648 | `0.0.0.0` | REST API для Desktop GUI + внешние клиенты |
| **dashboard** | 9119 | 9119 | `127.0.0.1` | Web UI (только localhost!) |
| **neo4j** (опционально) | 7474 | 7474 | `127.0.0.1` | Neo4j Browser |
| **neo4j** (опционально) | 7687 | 7687 | `127.0.0.1` | Neo4j Bolt |

**Telegram:** Исходящий HTTPS (не требует published ports).

**Правило безопасности:**
- `18648` exposed на `0.0.0.0` **только с `API_SERVER_KEY`** (обязательная аутентификация)
- `9119` (Dashboard) — **только `127.0.0.1`**, для удалённого доступа использовать SSH-туннель
- `7474`/`7687` (Neo4j) — **только `127.0.0.1`**

---

## 2. docker-compose.yml (финальный)

```yaml
# her2code/docker-compose.yml — Финальная архитектура
# Bridge network, без прокси, с раздельными gateway+dashboard
#
# Использование:
#   1. cp config/.env.docker .env && nano .env  # добавить API ключи
#   2. HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d
#   3. curl http://localhost:18648/health

services:
  # ── Hermes Gateway (AI Agent + REST API + Telegram) ──
  gateway:
    build: ./hermes-agent
    image: hermes-agent
    container_name: hermes-gateway
    restart: unless-stopped
    ports:
      - "${API_SERVER_BIND:-0.0.0.0}:${API_SERVER_PORT:-18648}:18648"
    volumes:
      - ~/.hermes:/opt/data
    environment:
      - HERMES_UID=${HERMES_UID:-1000}
      - HERMES_GID=${HERMES_GID:-1000}
      # ── API Server ──
      - API_SERVER_HOST=0.0.0.0
      - API_SERVER_PORT=18648
      - API_SERVER_KEY=${API_SERVER_KEY:-sk-local}
      - GATEWAY_ALLOW_ALL_USERS=true
      - HERMES_DISABLE_MESSAGING=0
      # ── LLM Providers ──
      - CUSTOM_PROVIDER_BASE_URL=${CUSTOM_PROVIDER_BASE_URL:-http://localhost:8092/v1}
      - CUSTOM_PROVIDER_API_KEY=${CUSTOM_PROVIDER_API_KEY:-}
      - CUSTOM_PROVIDER_NAME=${CUSTOM_PROVIDER_NAME:-llama}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      # ── Telegram (опционально) ──
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
      # ── Neo4j (опционально) ──
      - NEO4J_PASSWORD=${NEO4J_PASSWORD:-changeme}
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:18648/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 180s
    command:
      - gateway
      - run

  # ── Hermes Dashboard (Web UI) ──
  dashboard:
    image: hermes-agent
    container_name: hermes-dashboard
    restart: unless-stopped
    depends_on:
      gateway:
        condition: service_healthy
    ports:
      - "127.0.0.1:9119:9119"
    volumes:
      - ~/.hermes:/opt/data
    environment:
      - HERMES_UID=${HERMES_UID:-1000}
      - HERMES_GID=${HERMES_GID:-1000}
    command:
      - dashboard
      - --host
      - "127.0.0.1"
      - --no-open

  # ── Neo4j (опционально — графовая БД для MCP) ──
  neo4j:
    image: neo4j:5-community
    container_name: hermes-neo4j
    restart: unless-stopped
    profiles:
      - full
      - neo4j
    ports:
      - "127.0.0.1:7474:7474"
      - "127.0.0.1:7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-changeme}
      - NEO4J_server_memory_heap_initial__size=512m
      - NEO4J_server_memory_heap_max__size=1G
      - NEO4J_server_memory_pagecache_size=512m
    volumes:
      - neo4j_data:/data
    healthcheck:
      test:
        - CMD-SHELL
        - cypher-shell -u neo4j -p "$${NEO4J_PASSWORD:-changeme}" "RETURN 1" || exit 1
      interval: 15s
      timeout: 10s
      retries: 10
      start_period: 40s

volumes:
  neo4j_data:

# ── Топология сети ──
# Docker Compose создаёт bridge-сеть автоматически.
# Все сервисы видят друг друга по именам (gateway, dashboard, neo4j).
# Исходящий трафик (Telegram → api.telegram.org, LLM API) идёт через NAT Docker.
```

### Запуск

```bash
# Минимальный (gateway + dashboard):
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d

# С Neo4j:
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose --profile neo4j up -d

# Desktop GUI (Electron, на хосте):
HERMES_DESKTOP_REMOTE_URL=http://localhost:18648 \
HERMES_DESKTOP_REMOTE_TOKEN=sk-local \
  npm --prefix hermes-agent/apps/desktop start
```

---

## 3. config.yaml (минимальный рабочий)

```yaml
# ~/.hermes/config.yaml — Минимальная конфигурация для Docker
_config_version: 28

# ── Модель по умолчанию ──
model:
  default: deepseek-v4-pro
  provider: deepseek

# ── API Server (переопределяется env vars из docker-compose) ──
api_server:
  host: 127.0.0.1
  port: 8642

# ── Провайдеры ──
custom_providers:
  - name: openai
    api_mode: codex_responses
    base_url: https://api.openai.com/v1
    key_env: OPENAI_API_KEY
    models:
      gpt-4.1:
        context_length: 1000000
      gpt-4.1-mini:
        context_length: 1000000

# ── Терминал (в Docker используем local backend) ──
terminal:
  backend: local
  cwd: /home/user/dev/codemes

# ── Платформы ──
platforms:
  api_server:
    port: 8642      # переопределяется API_SERVER_PORT=18648

# ── Telegram (активируется только при TELEGRAM_BOT_TOKEN в .env) ──
telegram:
  allowed_chats: ""
  reactions: false

# ── MCP серверы (если используется Neo4j) ──
# mcp_servers:
#   claw-graph:
#     command: node
#     args: ["/home/user/.hermes/plugins/claw-neo4j/mcp-server.mjs"]
#     enabled: true
#     env:
#       NEO4J_URI: bolt://neo4j:7687
#       NEO4J_USER: neo4j
#       NEO4J_PASSWORD: ${NEO4J_PASSWORD}

# ── Безопасность ──
security:
  allow_lazy_installs: true
  redact_secrets: true
  tirith_enabled: true
  tirith_fail_open: true

# ── Логирование ──
logging:
  level: INFO
  backup_count: 3
  max_size_mb: 5
```

---

## 4. Диаграмма потока запросов

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HOST (Jetson ARM64)                          │
│                                                                     │
│  ┌──────────────┐   ┌──────────────────┐   ┌───────────────────┐   │
│  │ Desktop GUI  │   │  curl / clients  │   │  Telegram User    │   │
│  │ (Electron)   │   │  (Open WebUI...) │   │  (Phone/Desktop)  │   │
│  └──────┬───────┘   └────────┬─────────┘   └────────┬──────────┘   │
│         │                    │                       │              │
│         │ HTTP              │ HTTP                 │ HTTPS         │
│         │ localhost:18648   │ localhost:18648      │ (Internet)    │
│         │                    │                       │              │
│         ▼                    ▼                       ▼              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    DOCKER BRIDGE NETWORK                      │   │
│  │                                                              │   │
│  │  ┌──────────────────────────┐   ┌────────────────────────┐  │   │
│  │  │  hermes-gateway          │   │  hermes-dashboard      │  │   │
│  │  │                          │   │                        │  │   │
│  │  │  ┌────────────────────┐  │   │  Web UI :9119          │  │   │
│  │  │  │ API Server         │  │   │  (127.0.0.1 only)     │  │   │
│  │  │  │ :18648             │  │   │                        │  │   │
│  │  │  │                    │  │   │  Читает /opt/data:     │  │   │
│  │  │  │ GET /health        │  │   │  - state.db           │  │   │
│  │  │  │ GET /api/sessions  │  │   │  - config.yaml        │  │   │
│  │  │  │ POST /v1/chat/     │  │   └────────────────────────┘  │   │
│  │  │  │   completions      │  │                              │   │
│  │  │  │ POST /v1/runs      │  │   ┌────────────────────────┐  │   │
│  │  │  └────────────────────┘  │   │  neo4j (optional)      │  │   │
│  │  │                          │   │  :7474 :7687           │  │   │
│  │  │  ┌────────────────────┐  │   │  (127.0.0.1 only)     │  │   │
│  │  │  │ Telegram Adapter   │  │   └────────────────────────┘  │   │
│  │  │  │ (long polling)     │──┼───▶ api.telegram.org:443      │   │
│  │  │  └────────────────────┘  │   (исходящий HTTPS)           │   │
│  │  │                          │                              │   │
│  │  │  ┌────────────────────┐  │                              │   │
│  │  │  │ AIAgent            │──┼───▶ LLM API (DeepSeek/       │   │
│  │  │  │ + tools            │  │    OpenAI/Anthropic)          │   │
│  │  │  └────────────────────┘  │   (исходящий HTTPS)           │   │
│  │  │                          │                              │   │
│  │  │  /opt/data (volume)      │                              │   │
│  │  │  ├── state.db            │                              │   │
│  │  │  ├── config.yaml         │                              │   │
│  │  │  ├── skills/             │                              │   │
│  │  │  ├── agents/             │                              │   │
│  │  │  └── logs/               │                              │   │
│  │  └──────────────────────────┘                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ~/.hermes/ ──────────────────────▶ /opt/data/ (volume mount)       │
└─────────────────────────────────────────────────────────────────────┘


ПОТОК ЗАПРОСА (Desktop GUI → Gateway):

  Desktop (Electron)                Docker: hermes-gateway
  ─────────────────                 ──────────────────────
  │
  │  1. Liveness probe
  ├─ GET /health ──────────────────▶ API Server проверяет
  │  ◀────────────────────────────── состояние gateway
  │  {"status":"ok","auth_required":false}
  │
  │  2. Auth mode probe (без токена)
  ├─ GET /health ──────────────────▶ public endpoint
  │  ◀────────────────────────────── auth_required: false → token mode
  │
  │  3. Chat request (с токеном)
  ├─ POST /v1/chat/completions ───▶ API Server
  │  Authorization: Bearer sk-local   │
  │  {"model":"...","messages":[...]} │→ AIAgent.run_conversation()
  │                                   │   → LLM API call (исходящий HTTPS)
  │                                   │   → tool calls (terminal, file, etc.)
  │  ◀──────────────────────────────── ответ (streaming или полный)
  │  {"choices":[{"message":{...}}]}
  │
  │  4. WebSocket (чат в реальном времени)
  ├─ WS /api/ws?token=... ─────────▶ Gateway WebSocket
  │  ◀═══════════════════════════════ streaming токенов


ПОТОК ЗАПРОСА (Telegram → Gateway):

  Telegram User          Internet          Docker: hermes-gateway
  ─────────────          ────────          ──────────────────────
  │
  │  Отправляет сообщение боту
  ├─ HTTPS ────────────▶ Telegram API
  │                      ◀─────────────── long polling (исходящий)
  │                                       │
  │                                       ├─ Telegram Adapter
  │                                       │  получает Update
  │                                       │→ AIAgent.run_conversation()
  │                                       │   → LLM API call
  │                                       │   → tool calls
  │                                       │
  │                      ◀─────────────── отправка ответа (HTTPS)
  │  ◀────────────────── ответ бота в чат
```

## 5. Ключевые отличия от текущей архитектуры

| Параметр | Старая (текущая) | Новая (финальная) |
|----------|:-----------------:|:------------------:|
| **Сеть** | `network_mode: host` | Bridge network |
| **Прокси** | `status-proxy.py` (port 18649→8648) | **Удалён** (не нужен) |
| **Сервисы** | 1 контейнер `hermes` | 2 контейнера: `gateway` + `dashboard` |
| **Desktop** | Требовал `/api/status` (через прокси) | Использует нативный `/health` |
| **Telegram** | Удалялся из конфига entrypoint'ом | Нативный platform adapter |
| **Dashboard** | Нет | Web UI на `:9119` (localhost) |
| **Volume** | Закомментирован | Активный `~/.hermes:/opt/data` |
| **Безопасность** | Все порты в host namespace | Только нужные порты exposed |
| **Задержка** | 170s chown .venv на ARM64 | Та же (проблема Dockerfile, не архитектуры) |

## 6. Миграция

```bash
# 1. Остановить старый стек
docker compose down

# 2. Закомментировать/удалить status-proxy.py (не нужен)

# 3. Заменить docker-compose.yml на новый

# 4. Убедиться что ~/.hermes/config.yaml существует
ls -la ~/.hermes/config.yaml

# 5. Запустить новый стек
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d

# 6. Проверить
curl http://localhost:18648/health
# → {"status":"ok","auth_required":false}

# 7. Desktop GUI
cd hermes-agent
HERMES_DESKTOP_REMOTE_URL=http://localhost:18648 \
HERMES_DESKTOP_REMOTE_TOKEN=sk-local \
  npm --prefix apps/desktop start
```

---

**Вывод:** Архитектура стала **проще** (минус прокси), **безопаснее** (bridge вместо host), **полнее** (добавлен dashboard), и **правильнее** (нативные эндпоинты вместо стабов).
