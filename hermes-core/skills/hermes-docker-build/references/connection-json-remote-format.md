# connection.json: Правильный формат для Remote-подключения

## Проблема (обнаружено 2026-06-22)

GUI зависал на 95% из-за двух ошибок в формате `connection.json`:

### Ошибка 1: Плоская структура
```json
{"mode":"remote","url":"http://localhost:9119","token":"sk-local","authMode":"token"}
```
`readDesktopConnectionConfig()` читает `parsed.remote.url`, а не `parsed.url`.  
При плоской структуре `config.remote = {}` → undefined URL.

### Ошибка 2: Токен-строка вместо объекта
```json
"token": "sk-local"
```
`decryptDesktopSecret()` ожидает `typeof secret === 'object'`.  
Токен-строка → возвращает `""` → 401 Unauthorized на ВСЕ REST-запросы.

## Правильный формат

```json
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:9119",
    "token": {"value": "sk-local"},
    "authMode": "token"
  },
  "profiles": {}
}
```

## Код Electron

`electron/main.cjs:3756` — `readDesktopConnectionConfig()`:
```js
const remote = parsed.remote && typeof parsed.remote === 'object' ? parsed.remote : {}
```

`electron/main.cjs:3702` — `decryptDesktopSecret()`:
```js
function decryptDesktopSecret(secret) {
  if (!secret || typeof secret !== 'object') { return '' }  // ← строка даёт ''
  const value = String(secret.value || '')
  if (!value) { return '' }
  if (secret.encoding === 'safeStorage') {
    return safeStorage.decryptString(Buffer.from(value, 'base64'))
  }
  return value  // ← без encoding возвращает value как есть
}
```

## Env vars: НЕ РАБОТАЮТ (доказано дважды)

`HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN` якобы имеют приоритет
над `connection.json` (см. `electron/main.cjs:4004 resolveRemoteBackend`, шаг 2 "Env override").

**На практике НЕ работают** — проверено 2026-06-22 и 2026-07-07. GUI игнорирует env vars
и читает `connection.json`. Если `connection.json` имеет `mode=local`, GUI запускает
свой локальный gateway независимо от env vars.

**Единственный надёжный способ:** записать правильный JSON в `~/.config/Hermes/connection.json`.
`start.sh gui` делает это автоматически перед запуском.
