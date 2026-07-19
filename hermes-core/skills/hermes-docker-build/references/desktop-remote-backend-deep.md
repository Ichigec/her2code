# Desktop GUI Remote Backend Analysis

> Source: `hermes-agent/apps/desktop/electron/main.cjs` (5762 строки)
> Дата: 2026-06-20

## Как Desktop находит бэкенд

`resolveRemoteBackend()` (строка 4004) проверяет три источника, в порядке приоритета:

1. **Per-profile override** (`connection.json` → `profiles.<name>`)
2. **Environment variables**: `HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN`
3. **Global settings** (`connection.json` → `mode: "remote"`)

```javascript
async function resolveRemoteBackend(profile) {
  const config = readDesktopConnectionConfig()
  
  // 1. Per-profile override
  const override = profileRemoteOverride(config, profile)
  if (override) return buildRemoteConnection(...)
  
  // 2. Env override — HERMES_DESKTOP_REMOTE_URL + TOKEN
  const rawEnvUrl = process.env.HERMES_DESKTOP_REMOTE_URL
  const rawEnvToken = process.env.HERMES_DESKTOP_REMOTE_TOKEN
  if (rawEnvUrl) return buildRemoteConnection(rawEnvUrl, 'token', rawEnvToken, 'env')
  
  // 3. Global remote from connection.json
  if (config.mode !== 'remote') return null
  return buildRemoteConnection(config.remote?.url, ...)
}
```

**ВАЖНО:** Desktop НЕ читает `HERMES_API_URL` или `HERMES_API_KEY`. Только `HERMES_DESKTOP_REMOTE_URL` и `HERMES_DESKTOP_REMOTE_TOKEN`.

## Токен: X-Hermes-Session-Token, НЕ Authorization: Bearer

`fetchJson()` (строка 2321) отправляет токен через заголовок:
```javascript
'X-Hermes-Session-Token': token
```

Это НЕ `Authorization: Bearer`. Gateway должен принимать этот заголовок (api_server.py делает).

## Health check: /health (после патча)

`waitForHermes()` (строка 2970) проверяет бэкенд через:
```javascript
await fetchJson(`${baseUrl}/health`, token)
```

Оригинально использовался `/api/status` — эндпоинт dashboard, которого нет у gateway.
Патч: `sed -i 's|/api/status|/health|g' electron/main.cjs`

## connection.json (persistent config)

```json
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:18648",
    "token": "sk-local",
    "authMode": "token"
  },
  "profiles": {}
}
```

Путь: `~/.config/Hermes/connection.json` (Electron `app.getPath('userData')`).
Если файл существует и `mode === 'remote'` — Desktop пропускает локальный бутстрап.

**ПРЕДУПРЕЖДЕНИЕ:** Этот файл ГЛОБАЛЬНЫЙ для всех запусков Desktop. Если переключить в remote,
основной локальный Hermes перестанет запускаться через Desktop GUI.
Для тестирования Docker — создать файл. Для возврата к основному — удалить.
