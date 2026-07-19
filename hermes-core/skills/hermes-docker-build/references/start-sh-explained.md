# Hermes Docker Quick Start

Стартовый скрипт для `her2code/`. Одна команда = всё.

```bash
./start.sh          # Docker (API на :18648)
./start.sh desktop  # Docker + Desktop GUI
```

Скрипт сам делает:
1. `git init` в hermes-agent/ (нужен для сборки desktop)
2. `docker compose up -d` если контейнер не запущен
3. Ждёт до 3 минут инициализации (точки прогресса)
4. `health`-check
5. Если `desktop` — запускает Electron GUI с env vars

Переменные окружения автоматически:
- `GITHUB_SHA=sanitized-release`
- `HERMES_DESKTOP_REMOTE_URL=http://localhost:18648`
- `HERMES_DESKTOP_REMOTE_TOKEN=***`
- `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`

Не требуется:
- ❌ Ручной `git init`
- ❌ Ручной `docker compose`
- ❌ Ручной `sleep 180`
- ❌ Ручные `export HERMES_DESKTOP_REMOTE_*`
- ❌ Ручной `cd apps/desktop`
