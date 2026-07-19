# Desktop GUI from her2code — Workaround

**Date:** 2026-06-20  
**Session:** <SESSION_ID>

## Problem

`her2code/hermes-agent/apps/desktop/` содержит ИСХОДНИКИ Desktop GUI, но `npm start` 
не работает из коробки:

1. **`tsc: not found`** — TypeScript compiler не установлен в `apps/desktop/node_modules/.bin/`.
   `npm ci --workspace apps/desktop` должен установить, но...
2. **Network timeout** — Electron (~80 MB) не качается из-за блокировок РФ.
   Даже `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/` не всегда помогает.
3. **assert-root-install** — требует `node_modules/vite/package.json` в КОРНЕ `hermes-agent/`,
   а не только в `apps/desktop/node_modules/`. Нужен полный `npm ci` из корня.

## Solution: Connection.json + Pre-built Binary

На хосте Павла УЖЕ есть собранный Hermes Desktop GUI:
```
/home/user/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes
```

Чтобы подключить ЕГО к Docker-контейнеру (вместо хостового Hermes):

```bash
mkdir -p ~/.config/Hermes
cat > ~/.config/Hermes/connection.json << 'EOF'
{"mode":"remote","url":"http://localhost:18648","token":"<API_SERVER_KEY>","authMode":"token"}
EOF
```

Где `<API_SERVER_KEY>` — значение из `.env` (сгенерировано `openssl rand -hex 32`).

После этого запустить существующий бинарник:
```bash
/home/user/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes
```

## Why This Works

- `connection.json` имеет приоритет над `HERMES_DESKTOP_REMOTE_URL` env var
- Docker Hermes на порту 18648 НЕ конфликтует с хост-Hermes на 8648
- Не требует `npm ci`, `tsc`, Electron download, sandbox fix
- Один раз настроил — работает всегда

## For Distribution Users

В `her2code/README.md` или `DOCKER.md` нужно документировать, что Desktop GUI:
1. Требует Node.js 22+, npm, TypeScript
2. Может не собраться в РФ из-за блокировок
3. Альтернатива: Web Dashboard (`hermes dashboard`) или CLI (`hermes`)
4. Если есть доступ к другому Hermes — использовать `connection.json` как выше
