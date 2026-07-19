# Desktop GUI ↔ Docker: как Desktop находит remote бэкенд

> Ключевой инсайт: Desktop проверяет `HERMES_DESKTOP_REMOTE_URL`, НЕ `HERMES_API_URL`.

## Приоритет поиска бэкенда (main.cjs)

```javascript
// 1. Per-profile override (UI settings)
const override = profileRemoteOverride(config, profile)

// 2. Environment variables
const rawEnvUrl = process.env.HERMES_DESKTOP_REMOTE_URL    // ← ВОТ ЭТО
const rawEnvToken = process.env.HERMES_DESKTOP_REMOTE_TOKEN

// 3. connection.json (persistent config)
if (config.mode === 'remote') { ... }
```

## Формат connection.json

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

Путь: `~/.config/Hermes/connection.json` (Electron `userData`).

## Токен-хедер

Desktop отправляет токен в заголовке `X-Hermes-Session-Token`, НЕ `Authorization: Bearer`.

```javascript
// main.cjs:2339
headers: {
  'Content-Type': 'application/json',
  'X-Hermes-Session-Token': token
}
```

## Health check

`waitForHermes()` (main.cjs:2970) вызывает `fetchJson(${baseUrl}/api/status, token)`.
Docker-шлюз имеет `/health`, не `/api/status`. Патч:

```bash
sed -i 's|/api/status|/health|g' hermes-agent/apps/desktop/electron/main.cjs
```

## Зависание на 24%

24% = `advanceBootProgress('backend.remote', 'Connecting to remote Hermes backend...', 24)`.
Desktop ждёт ответа от `/api/status` (после патча — `/health`). Если шлюз ещё инициализируется — повторяет до 45 секунд, затем падает с «Desktop boot failed: Hermes backend did not become ready».

## Переменные, которые НЕ работают

- `HERMES_API_URL` — игнорируется resolveRemoteBackend()
- `HERMES_API_KEY` — игнорируется
- `HERMES_DESKTOP_NO_BOOTSTRAP` — не существует в коде
- `HERMES_DESKTOP_REMOTE_API` — не существует в коде
