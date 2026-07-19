# PII Sanitization: Token Replacement Pitfall

> Урок второго прогона PII-аудита (2026-06-19).

## Проблема

При санитизации все API-ключи заменяются на `***` (плейсхолдер). Но некоторые файлы используют `***` как РЕАЛЬНЫЙ токен для локального подключения (non-production):

- `connection.json` → Desktop GUI читает `token: "***"` и шлёт его как `X-Hermes-Session-Token: ***`
- `desktop.sh` → `export HERMES_DESKTOP_REMOTE_TOKEN=***`
- `docker-compose.yml` → `API_SERVER_KEY=***`

Gateway ожидает `API_SERVER_KEY` из `.env`. Если `.env` содержит `API_SERVER_KEY=***`, а `connection.json` содержит `***` — Desktop получает 401. Если `.env` содержит `API_SERVER_KEY=***`, а `connection.json` содержит `***` — тоже 401.

## Решение

Для локальной разработки/тестирования использовать `sk-local`:

```json
{"token": "***"}
```

```bash
API_SERVER_KEY=*** ```

```yaml
- "API_SERVER_KEY=***"
```

## Категории замен

| Оригинал | Замена для публикации | Замена для local dev |
|----------|----------------------|---------------------|
| `sk-proj-...Cr8A` | `<YOUR_OPENAI_KEY>` | Реальный ключ в `.env` |
| `sk-local` | `sk-local` (оставить) | `sk-local` |
| `***` (плейсхолдер) | `***` | `sk-local` |

## Что попало под замену (и было исправлено)

1. `config/.env.docker` — `API_SERVER_KEY=***` → `API_SERVER_KEY=***`
2. `connection.json` — `"token": "***"` → `"token": "***"`
3. `desktop.sh` — `TOKEN=***` → `TOKEN=***`
4. `docker-compose.yml` — `API_SERVER_KEY=***` → `API_SERVER_KEY=***`
