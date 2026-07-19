# Desktop Remote Backend: /api/status vs /health

## Проблема

Desktop GUI при подключении к remote backend вызывает `GET /api/status` (см. `main.cjs:2976` — `waitForHermes`).
Docker-контейнер с `hermes gateway run` имеет только `/health`, но не `/api/status`.
Desktop висит на 24% ("Connecting to remote Hermes backend") и падает по таймауту.

## Решение

Заменить все вхождения `/api/status` на `/health` в `apps/desktop/electron/main.cjs`:

```bash
sed -i 's|/api/status|/health|g' apps/desktop/electron/main.cjs
```

И создать `~/.config/Hermes/connection.json`:

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

## Почему так

`/api/status` — эндпоинт Dashboard-бэкенда (`hermes dashboard`). Возвращает `auth_required: true/false`.
Docker-контейнер запускает `hermes gateway run` — у него `/api/status` нет, есть `/health`.

Альтернативные подходы (не реализованы):
1. Запустить `hermes dashboard` в Docker вместо `gateway run` — ломает API-сервер
2. socat/nginx sidecar для прокси `/api/status` → `/health`
3. Добавить `/api/status` в gateway код (требует правки Python)

Выбран подход с патчем main.cjs — минимально инвазивный.

## Связанные находки

- `HERMES_DESKTOP_REMOTE_URL` — env var, которую Desktop РЕАЛЬНО читает (не `HERMES_API_URL`)
- `HERMES_DESKTOP_REMOTE_TOKEN` — токен для remote backend
- `connection.json` хранится в `app.getPath('userData')` → `~/.config/Hermes/` на Linux
- `readDesktopConnectionConfig()` в `main.cjs:3756`
- `resolveRemoteBackend()` в `main.cjs:4004` — проверяет env vars ДО config file
