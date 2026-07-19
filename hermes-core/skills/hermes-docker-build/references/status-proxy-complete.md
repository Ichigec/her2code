# Status Proxy — Complete Working Version (2026-06-21)

Рабочий прокси для подключения Desktop GUI к Docker Hermes.
Решает зависания на 24% и 95%, ошибку "something broke in the interface".

## Ключевые инсайты

1. **GUI ждёт `/api/status`** (24% зависание) — Docker имеет только `/health`
2. **GUI ждёт `/api/logs`, `/api/profiles`, `/api/sessions`, `/api/agents`** (95% зависание) — Docker возвращает 404
3. **GUI крашится на 502** ошибках ("something broke in the interface") — прокси должен возвращать 200 с `{}` для неизвестных эндпоинтов
4. **GUI использует WebSocket** (`/api/ws?token=***`) — HTTP прокси не может обработать, но GUI продолжает работу без него
5. **CORS заголовки** нужны для запросов из Electron

## Полный список стабов

```
/api/status         → {"status":"ok","auth_required":false}
/api/sessions       → []
/api/agents         → []
/api/skills         → []
/api/cron           → []
/api/config         → {}
/api/memory         → []
/api/models         → []
/api/personalities  → []
/api/profiles       → {"profiles":[],"active":"default"}
/api/profiles/active → {"profile":"default"}
/api/hooks          → []
/api/logs           → ""  (пустая строка, не JSON)
```

## Рабочий код

См. `scripts/status-proxy.py` — полная версия с:
- Стабами для всех endpoint'ов
- CORS заголовками
- Проксированием `/v1/*` на Docker
- Возвратом `200 {}` вместо `502` для неизвестных путей
- Логгированием в `/tmp/proxy.log` (опционально)

## Как запускать

```bash
# Прокси на :18649 → Docker на :18648
GATEWAY_URL=http://localhost:18648 PROXY_PORT=18649 \
  python3 status-proxy.py &

# GUI подключается к прокси
env HERMES_DESKTOP_REMOTE_URL=http://localhost:18649 \
    HERMES_DESKTOP_REMOTE_TOKEN=*** \
    ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" \
    /path/to/Hermes --user-data-dir=/tmp/hermes-gui-docker
```

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| Прокси умирает при `docker compose down` | Перезапускать прокси после каждого рестарта Docker |
| `***` в token — буквальные звёздочки | Использовать реальный `API_SERVER_KEY` (из `.env` или `docker-compose.yml`) |
| GUI не читает `connection.json` из `--user-data-dir` | GUI всегда читает `~/.config/Hermes/connection.json`. Использовать `HERMES_DESKTOP_REMOTE_URL` env var вместо `connection.json` |
| GPU crash при запуске из фона | GUI требует `$DISPLAY`. Только из интерактивного терминала |
