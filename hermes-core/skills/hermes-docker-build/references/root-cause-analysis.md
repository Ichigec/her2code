# Root Cause Analysis: Hermes Docker + Desktop GUI

## Ключевой инсайт: `~/.hermes/` НЕЛЬЗЯ делить

Два экземпляра Hermes (хостовый + Docker) с общим `~/.hermes/` — архитектурно невозможны:

| Ресурс | Конфликт |
|--------|----------|
| `config.yaml` | гонка записи, corruption при модификации |
| `state.db` | SQLite блокировки (WAL mode, single-writer) |
| `logs/` | s6-log файловые блокировки |
| `skills/` | дубликаты синхронизации |

**Решение:** отдельная `~/.hermes-docker/` с чистым конфигом и `.env` с плейсхолдерами.

## Dashboard + Gateway в одном compose — гонка логов

Dashboard и Gateway оба используют s6-log для записи в `logs/gateways/default/`. При общем вольюме — `fatal: unable to lock .../lock: Resource busy`. Dashboard уходит в restart loop.

**Решение:** НЕ включать dashboard в docker-compose. Только gateway.

## Desktop GUI — remote mode

Desktop читает remote-бэкенд в порядке приоритета:
1. Per-profile override (настройки в GUI)
2. `HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN` (env vars)
3. `~/.config/Hermes/connection.json` (persistent config)

Токен передаётся в заголовке `X-Hermes-Session-Token` (НЕ `Authorization: Bearer`).

## `/api/status` vs `/health`

Gateway (`hermes gateway run`) имеет `/health`, но НЕ `/api/status`.
Desktop ждёт `/api/status` на этапе загрузки (24% прогресс-бара).

**Решение:** патч `main.cjs`: `s|/api/status|/health|g`. Но фронтенд (JS-бандл) тоже вызывает `/api/status` — это остаётся проблемой без dashboard-сервиса.

## Почему всё так сложно

Docker-образ Hermes спроектирован для **запуска как основной инстанс**, не параллельно с хостовым. Для GitHub-публикации это нормально — пользователь клонит и запускает ОДИН Hermes в Docker.

Упрощённый запуск: `./start.sh` (одна команда для всего).
