# Desktop GUI → Docker: Final Architecture

> Результат глубокого анализа 2026-06-19. Как Desktop GUI подключается к Docker-бэкенду.

## Схема

```
Desktop GUI (Electron)              Docker (hermes-test)
┌──────────────────────┐            ┌──────────────────────┐
│ main.cjs:4017         │            │ proxy (status-proxy) │
│ resolveRemoteBackend()│  HTTP GET  │ :18648               │
│ ├── env vars?         │───────────→│  /api/status → 200   │
│ │   REMOTE_URL/TOKEN  │            │  /* → hermes:8648    │
│ ├── connection.json?  │            └──────┬───────────────┘
│ │   mode:"remote"     │                   │
│ └── per-profile?      │            ┌──────▼───────────────┐
│                       │            │ hermes gateway :8648 │
│ waitForHermes()       │            │  /health ✅           │
│ → /health             │            │  /api/status ❌       │
│                       │            │  /v1/models ✅        │
│ fetchJson()           │            └──────────────────────┘
│ → X-Hermes-Session-   │
│   Token: sk-local     │
└──────────────────────┘
```

## Ключевые точки

1. **Env vars**: Desktop читает `HERMES_DESKTOP_REMOTE_URL` и `HERMES_DESKTOP_REMOTE_TOKEN` (main.cjs:4017-4027). НЕ `HERMES_API_URL`.

2. **connection.json**: `~/.config/Hermes/connection.json` — раз проставлен `mode: "remote"`, Desktop всегда подключается к Docker без env vars.

3. **Токен**: Desktop шлёт `X-Hermes-Session-Token` (НЕ `Authorization: Bearer`). Gateway принимает оба.

4. **Эндпоинт `/api/status`**: Desktop (рендерер) вызывает `/api/status`, но gateway (api_server) его не обслуживает. Решение: `status-proxy.py` проксирует 18648, перехватывает `/api/status`, остальное форвардит на `hermes:8648`.

5. **Эндпоинт `/health`**: `waitForHermes()` и `probeRemoteAuthMode()` в main.cjs вызывают `/health` напрямую (без прокси).

6. **Dashboard не нужен**: в Docker-режиме Desktop сам служит GUI. Dashboard в docker-compose конфликтует за s6-log lock на общем вольюме `~/.hermes`.

## connection.json (persistent)

```json
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:18648",
    "token": "***",
    "authMode": "token"
  },
  "profiles": {}
}
```

## docker-compose.yml (финальный)

```yaml
services:
  hermes:
    build: ./hermes-agent
    image: hermes-agent
    container_name: hermes-test
    restart: unless-stopped
    volumes:
      - ~/.hermes:/opt/data
      - ./docker-entrypoint.sh:/docker-entrypoint.sh:ro
    environment:
      - HERMES_UID=1000
      - HERMES_GID=1000
      - API_SERVER_HOST=0.0.0.0
      - API_SERVER_PORT=8648
      - "API_SERVER_KEY=***"
      - GATEWAY_ALLOW_ALL_USERS=true
    entrypoint: ["/bin/sh", "/docker-entrypoint.sh"]
    command: ["gateway", "run"]

  proxy:
    image: python:3.12-alpine
    container_name: hermes-proxy
    restart: unless-stopped
    ports:
      - "18648:18648"
    volumes:
      - ./status-proxy.py:/status-proxy.py:ro
    environment:
      - GATEWAY_URL=http://hermes:8648
    command: ["python3", "/status-proxy.py"]
```

## status-proxy.py

Минимальный HTTP-прокси на Python stdlib (http.server + urllib):
- `GET /api/status` → `{"status":"ok","auth_required":false}`
- Всё остальное → форвард на `GATEWAY_URL` с теми же заголовками
