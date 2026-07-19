---
name: hermes-docker-build
description: Build and run Hermes Agent from sanitized her2code/ in Docker. Tested on Jetson ARM64.
category: deployment
triggers:
  - "собери hermes docker"
  - "docker compose build hermes"
  - "запусти hermes в докере"
  - "hermes docker build"
  - "запусти hermes gui docker"
  - "открой hermes gui"
  - "desktop gui docker"
  - "сборка hermes docker"
  - "hermes gui docker сборка"
  - "открой hermes gui"
---

> После сборки: GUI (Dashboard) на `http://localhost:19119`, API на `http://localhost:18648/health`.
> Первый запуск: `sleep 240` обязателен — chown `.venv` внутри контейнера (~4-5 мин на Jetson ARM64). Повторные: мгновенно.

# Hermes Docker Build — Working Recipe

> Проверено 2026-06-19 на Jetson ARM64 (NVIDIA GB10, Ubuntu, Docker 28).

## АРХИТЕКТУРНОЕ ПРАВИЛО: ИЗОЛЯЦИЯ `~/.hermes/`

Два экземпляра Hermes (хост + Docker) **НЕ МОГУТ использовать одну `~/.hermes/` директорию**:

| Ресурс | Конфликт |
|--------|----------|
| `config.yaml` | гонка записи, YAML corruption при модификации entrypoint'ом |
| `state.db` | SQLite блокировки |
| `logs/` | файловые блокировки s6-log |
| `skills/` | дубликаты синхронизации |

**Решение:** отдельная `~/.hermes-docker/` для контейнера:

```bash
mkdir -p ~/.hermes-docker
cp config/config.yaml.example ~/.hermes-docker/config.yaml
# .env ТОЛЬКО с плейсхолдерами:
echo 'DEEPSEEK_API_KEY=***' > ~/.hermes-docker/.env
```

В docker-compose: `~/.hermes-docker:/opt/data` (не `~/.hermes`).

`her2code/hermes-agent/Dockerfile` — апстримный Dockerfile Hermes Agent с закешированным SHA базового образа.

**⚠️ КРИТИЧЕСКИ: НЕ удалять `ui-tui/`, `web/`, `apps/desktop/` при санитизации.** 
Эти директории — часть монорепо Hermes. Без них ломается:
- Docker-сборка (Dockerfile копирует их в образ)
- Desktop GUI (зависит от корневого `npm ci`)
- npm workspace resolution (root `package.json` ссылается на них)
- `npm run build` (assert-root-install, stage-native-deps, vite resolve)

**Размер не важен — функциональность важнее.** node_modules внутри них удалять (ставятся через npm ci), но исходники ОБЯЗАТЕЛЬНО сохранять.

Удалять ТОЛЬКО `node_modules/`, `venv/`, `__pycache__/`, `tests/`, `website/` внутри них.

Если уже удалили — скопировать обратно из оригинала:
```bash
cp -r /path/to/original/hermes-agent/ui-tui her2code/hermes-agent/
cp -r /path/to/original/hermes-agent/web her2code/hermes-agent/
rm -rf her2code/hermes-agent/ui-tui/node_modules
rm -rf her2code/hermes-agent/web/node_modules
```

## Шаги

### 1. Починить SHA базового образа

```bash
cd her2code
docker pull ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie
SHA=$(docker inspect ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie --format='{{index .RepoDigests 0}}')
sed -i "1s|FROM .*|FROM $SHA AS uv_source|" hermes-agent/Dockerfile
```

### 2. Убедиться что ui-tui/, web/, apps/desktop/ на месте

```bash
ls hermes-agent/ui-tui/package.json && echo "✅ ui-tui"
ls hermes-agent/web/package.json && echo "✅ web"
ls hermes-agent/apps/desktop/package.json && echo "✅ desktop"
```

Если нет — скопировать из оригинальной установки Hermes (без node_modules).

### 3. docker-compose.yml + docker-entrypoint.sh

```yaml
services:
  hermes:
    build: ./hermes-agent
    image: hermes-agent
    container_name: hermes-test
    restart: unless-stopped
    ports:
      - "18648:8648"
    volumes:
      - ~/.hermes:/opt/data          # НЕ :ro — нужна запись!
      - ./docker-entrypoint.sh:/docker-entrypoint.sh:ro
    environment:
      - HERMES_UID=1000
      - HERMES_GID=1000
      - API_SERVER_HOST=0.0.0.0
      - API_SERVER_PORT=8648
      - "API_SERVER_KEY=sk-local"    # КАВЫЧКИ обязательны — *** без кавычек ломает YAML!
      - GATEWAY_ALLOW_ALL_USERS=true
    entrypoint: ["/bin/sh", "/docker-entrypoint.sh"]
    command: ["gateway", "run"]

  dashboard:
    image: hermes-agent
    container_name: hermes-test-dash
    restart: unless-stopped
    ports:
      - "19119:9119"
    depends_on:
      - hermes
    volumes:
      - ~/.hermes:/opt/data
    environment:
      - HERMES_UID=1000
      - HERMES_GID=1000
    command: ["dashboard", "--host", "0.0.0.0", "--no-open"]
```

### 4a. docker-entrypoint.sh — вырезать Telegram (блокирован в РФ)

**Рабочая версия на sed (не требует pyyaml):**

```bash
#!/bin/sh
CONFIG=/opt/data/config.yaml
while [ ! -f "$CONFIG" ]; do sleep 1; done  # ждать монтирования
sed -i '/^[[:space:]]*telegram:/,/^[[:space:]]*[a-z]/{ /^[[:space:]]*telegram:/d; /^[[:space:]]*[a-z]/!d; }; /^  telegram:/d' "$CONFIG" 2>/dev/null || true
exec /init /opt/hermes/docker/main-wrapper.sh "$@"
```

**Почему sed, не Python:** pyyaml не гарантирован в образе до активации venv. sed — всегда есть в Debian.

**Почему:** Основной `~/.hermes/config.yaml` содержит Telegram. В России `api.telegram.org` заблокирован — gateway висит на реконнектах, API-сервер не стартует. Entrypoint вырезает `telegram` из `gateway.platforms` перед запуском.

### 5. Desktop GUI — Правильный способ (Dashboard, не прокси)

GUI из her2code НЕ собрать через `npm ci`: `tsc` (TypeScript) отсутствует, Electron (~80 MB)
блокируется в РФ, `assert-root-install.cjs` требует `vite/package.json` в корневых `node_modules/`.

**Решение (2026-06-21, проверено):** Pre-built binary с хоста + ОТДЕЛЬНЫЙ Docker-контейнер с **dashboard**.
Прокси-подход (status-proxy.py) **НЕ НУЖЕН** — dashboard сам отдаёт `/api/status` и WebSocket.

#### 5a. Dashboard контейнер — ОБЯЗАТЕЛЬНЫЕ флаги из официальной документации

Согласно https://hermes-agent.nousresearch.com/docs/user-guide/desktop и статьям сообщества,
dashboard ДОЛЖЕН запускаться с флагами `--tui` (включает WebSocket для чата) и `--insecure`
(разрешает simple token auth для remote desktop client):

```bash
docker run -d --name hermes-dashboard --network host \
  --volumes-from hermes-test \
  -e HERMES_UID=1000 -e HERMES_GID=1000 \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  hermes-agent dashboard --host 127.0.0.1 --port 9119 \
    --insecure --tui --no-open --skip-build
```

**⚠️ КРИТИЧЕСКИ: `tui_gateway/` ОТСУТСТВУЕТ в Docker-образе!**

Без него WebSocket (`/api/ws`) возвращает `ModuleNotFoundError: No module named 'tui_gateway'` в логах.
Это **единственная причина** зависания GUI на 95% при использовании dashboard.

**Просто `docker cp` в `/opt/hermes/tui_gateway/` НЕДОСТАТОЧНО** — файлы на диске, но не на Python path.
Нужно ДВА шага:

```bash
# Шаг 1: скопировать на persistent volume (переживает перезапуски контейнера)
tar -C ~/.hermes/hermes-agent -c tui_gateway/ | \
  docker exec -i hermes-dashboard tar -C /opt/data -x

# Шаг 2: добавить PYTHONPATH в docker run
#   -e PYTHONPATH=/opt/data
```

**Почему `/opt/data` а не `/opt/hermes`:** `/opt/data` — persistent Docker volume (`--volumes-from hermes-test`),
переживает перезапуски контейнера. `/opt/hermes` — внутри контейнера, теряется при пересоздании.

**FastAPI HTTP middleware НЕ применяется к WebSocket-роутам.** WebSocket auth проверяется через
`_ws_auth_ok()` по `?token=` query-параметру. REST auth идёт через `X-Hermes-Session-Token` header
(первичный) или `Authorization: Bearer` (legacy). Поэтому WebSocket работает без `Authorization` header.

**Полная команда запуска dashboard (с persistent tui_gateway):**

```bash
docker run -d --name hermes-dashboard --network host \
  --volumes-from hermes-test \
  -e HERMES_UID=1000 -e HERMES_GID=1000 \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  -e PYTHONPATH=/opt/data \
  hermes-agent dashboard --host 127.0.0.1 --port 9119 \
    --insecure --tui --no-open --skip-build
```

После этого WebSocket даёт `HTTP 101 Switching Protocols`.

**Флаги:**
| Флаг | Зачем |
|------|-------|
| `--tui` | Включает `/api/ws` WebSocket для чата (иначе GUI не может отправлять сообщения) |
| `--insecure` | Simple token auth для remote desktop client (иначе `/api/sessions`, `/api/agents` → 401) |
| `--no-open` | Не открывать браузер (в Docker нет браузера) |
| `--skip-build` | Пропустить сборку фронтенда (уже собран в образе) |

**Проверка dashboard перед запуском GUI (7 endpoint'ов):**

| Endpoint | Ожидаемый ответ |
|----------|----------------|
| `/api/status` | `{"version":"0.16.0",...,"gateway_running":true}` |
| `/api/sessions` | `{"sessions":[...]}` |
| `/api/logs?file=gui&lines=12` | `{"file":"gui","lines":[...]}` |
| `/api/config` | `{...}` |
| `/api/ws?token=...` | `HTTP 101 Switching Protocols` |
| `/health` | HTML страница (не JSON — это нормально для dashboard) |
| `/api/agents` | 404 (не блокирует GUI) |

**Прокси-подход (status-proxy.py) — УСТАРЕЛ.** Был нужен когда dashboard не использовался и GUI стучался напрямую в gateway (порт 18648). Gateway имеет только `/health`, без `/api/status` и `/api/ws`. При использовании dashboard прокси НЕ НУЖЕН.

```bash
# Запустить прокси
GATEWAY_URL=http://localhost:18648 PROXY_PORT=18649 \
  python3 her2code/status-proxy.py &

# Проверить
curl http://localhost:18649/api/status
# → {"status":"ok","auth_required":false}
```

#### 5b. Запуск GUI из pre-built бинарника (изолированно от хостового GUI)

```bash
BIN=~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes
DATA=/tmp/hermes-gui-docker
rm -rf "$DATA"  # чистый старт

# Подключение к DASHBOARD (порт 9119) — НЕ к gateway (18648) и НЕ к прокси (18649)
# Единый рабочий способ (2026-06-22): env vars + --user-data-dir
env HERMES_DESKTOP_REMOTE_URL=http://localhost:9119 \
    HERMES_DESKTOP_REMOTE_TOKEN=*** \
    ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" \
    "$BIN" --user-data-dir="$DATA"
```

**⚠️ `--user-data-dir` НЕ влияет на `connection.json`:**
GUI всегда читает `connection.json` из `~/.config/Hermes/` (или per-profile override),
НЕ из `--user-data-dir`. Для изоляции от хостового GUI использовать env vars
`HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN` (они имеют приоритет над `connection.json`).
`--user-data-dir` изолирует кэш/сессии/настройки, но НЕ точку подключения.

**Готовый скрипт:** `scripts/launch-docker-gui.sh` — одна команда для запуска Docker GUI.

#### 5c. `npm ci` network failure workaround

Если очень нужно собрать GUI из исходников (а не из pre-built binary):

```bash
# Скопировать node_modules с хоста (1.6 GB)
cp -rn ~/.hermes/hermes-agent/node_modules/. her2code/hermes-agent/node_modules/
# Скопировать typescript в apps/desktop
cp -r ~/.hermes/hermes-agent/apps/desktop/node_modules/typescript \
     her2code/hermes-agent/apps/desktop/node_modules/
# Запустить (tsc и vite уже на месте, electron всё равно не скачается в РФ)
cd her2code/hermes-agent/apps/desktop && npm start
```

**Pitfall:** Без `electron` бинарника `npm start` всё равно упадёт на `electron .`.

Docker не умеет GUI. `desktop.sh` — собирает на хосте и подключается к контейнеру.

**Ключевой инсайт:** Desktop — часть монорепо. Нужен **полный `npm ci` из корня `hermes-agent/`**, не `npm install --prefix .` в apps/desktop/. Только корневой `npm ci` поднимает `react`, `react-dom`, `node-pty` в корневой `node_modules/` — именно оттуда их импортирует Vite (`../../node_modules/react`).

**Рабочий desktop.sh:**
```bash
#!/bin/bash
set -e
ROOT="$(dirname "$0")/hermes-agent"

curl -s http://localhost:18648/health > /dev/null 2>&1 || {
  echo "❌ Docker не отвечает. Запусти: docker compose up -d && sleep 120"
  exit 1
}

cd "$ROOT"
export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
export GITHUB_SHA="sanitized-release"

[ ! -d "node_modules/react" ] && npm ci 2>&1 | tail -3

# Electron sandbox fix
SANDBOX="node_modules/electron/dist/chrome-sandbox"
[ -f "$SANDBOX" ] && [ "$(stat -c %U "$SANDBOX")" != "root" ] && \
  sudo chown root:root "$SANDBOX" && sudo chmod 4755 "$SANDBOX" || \
  export ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox"

export HERMES_API_URL=http://localhost:18648
# ВАЖНО: НЕ HERMES_API_URL. Desktop читает именно HERMES_DESKTOP_REMOTE_URL.
# См. apps/desktop/electron/main.cjs:4017 — resolveRemoteBackend()
export HERMES_DESKTOP_REMOTE_URL=http://localhost:18648
export HERMES_DESKTOP_REMOTE_TOKEN=*** cd apps/desktop && npm start
```

### 6. Собрать и запустить

```bash
cp .env.example .env
nano .env   # добавить OPENROUTER_API_KEY=*** или DEEPSEEK_API_KEY=*** НЕ плейсхолдер!
# Сгенерировать API_SERVER_KEY: openssl rand -hex 32 → вставить в .env
docker compose build hermes --no-cache     # ~5-8 минут первый раз
docker compose up -d
# Ждать ~240s на ARM64 при первом запуске, ~60s на x86_64, ~10s при повторных:
for i in $(seq 1 150); do curl -sf localhost:18648/health && break; sleep 2; done
curl http://localhost:18648/health
# → {"status": "ok", "platform": "hermes-agent"}

# GUI (Desktop Electron — на хосте, подключается к Docker):
# ./start.sh desktop
```

## Desktop GUI — полный рабочий рецепт

Сборка + запуск Electron Desktop GUI, подключение к Docker-контейнеру на порту 18648.

### Ключевой инсайт: не удалять `ui-tui/` и `web/`

При санитизации **сохранить исходники** `ui-tui/`, `web/`, `apps/desktop/` — они нужны для сборки монорепо.
Удалять только `node_modules/` внутри них (переустанавливаются через `npm ci`).

### desktop.sh (рабочая версия)

См. `scripts/desktop.sh` — полный скрипт. Логика:
1. Проверить что Docker отвечает (`curl health`)
2. Первый запуск: `npm ci` из корня `hermes-agent/`
3. Исправить песочницу Electron: `sudo chown root:root chrome-sandbox && chmod 4755` ИЛИ fallback `--no-sandbox`
4. `export HERMES_API_URL=http://localhost:18648 HERMES_API_KEY=***`
5. `cd apps/desktop && npm start`

### Electron pitfalls

| Проблема | Причина | Fix |
|----------|--------|-----|
| `SIGTRAP: chrome-sandbox not root:root 4755` | Скопированный `node_modules` — владелец пользователь, не root | `sudo chown root:root node_modules/electron/dist/chrome-sandbox && sudo chmod 4755` ИЛИ `--no-sandbox` (менее безопасно) |
| `npm start` только после `npm ci` из корня | Монорепо: `npm start` → `npm run build` → `assert-root-install.cjs` проверяет корневой `node_modules/` | `cd hermes-agent && npm ci` перед первым запуском |
| `npm run build` ≠ бинарник | `build` собирает только фронтенд (Vite → dist/). Electron-бинарник — `electron-builder` (`npm run dist`). Для dev — `npm start` (Vite + Electron) | Использовать `npm start` для запуска |
| Electron download fails (РФ) | GitHub заблокирован | `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/` |
| `npm ci` из корня конфликтует с заглушками | Имена заглушек должны быть уникальны | `hermes-tui-stub`, `hermes-ink-stub`, `hermes-web-stub` |

## Скрипты быстрого разворачивания  

Скрипты в `~/dev/hermes_portable/scripts/`:

### `deploy-full.sh` — ПОЛНЫЙ СТЕК (+ локальная модель)

```bash
# Полный стек + локальная модель GGUF
~/dev/hermes_portable/scripts/deploy-full.sh --model ~/models/deepseek.gguf

# Полный стек без модели (только Docker + Hermes + Dashboard + GUI токен)
~/dev/hermes_portable/scripts/deploy-full.sh
```

Запускает: Docker-инфраструктура → llama.cpp (если --model) → Hermes gateway → Dashboard → вывод токена

### `deploy-minimal.sh` — МИНИМАЛЬНЫЙ (docker run с volume)

```bash
# Минимальный gateway: docker run -v ~/.hermes-docker:/opt/data -e API_SERVER_PORT=18648
~/dev/hermes_portable/scripts/deploy-minimal.sh --port 18648

# С указанием директории данных
~/dev/hermes_portable/scripts/deploy-minimal.sh --hermes-home ~/hermes-data --port 18649
```

Запускает: подготовка ~/.hermes-docker/ → docker run одного контейнера → health check

## Связанные файлы

- `scripts/docker-entrypoint.sh` — вырезает Telegram из конфига (sed, без Python)
- `scripts/build-gui.sh` — **NEW (2026-07-07):** Сборка GUI из локальных файлов (офлайн/онлайн). `--dir`, `--dist`, `--arch x64`, `--skip-install`.
- `scripts/desktop.sh` — сборка Desktop GUI + запуск с подключением к Docker
- `scripts/launch-docker-gui.sh` — **NEW (2026-06-22):** запуск Docker GUI одной командой (env vars, изоляция через --user-data-dir)
- `references/connection-json-remote-format.md` — **NEW (2026-06-22):** правильный формат connection.json для remote-подключения
- `references/pii-second-pass.md` — уроки второго прогона PII-санитизации
- `references/desktop-remote-backend.md` — анализ исходного кода: как Desktop находит remote бэкенд
- `references/desktop-api-status-workaround.md` — `/api/status` → `/health` патч для Docker
- `references/working-llama-config.md` — рабочий конфиг с локальной llama.cpp моделью
- `references/desktop-gui-proxy.md` — прокси со стабами для устранения зависаний GUI
- `references/no-volume-discovery.md` — открытие: дефолтный конфиг образа чище, чем монтированный
- `references/desktop-remote-backend.md` — анализ исходного кода: как Desktop находит remote бэкенд
- `references/local-llama-integration.md` — **NEW (2026-06-21):** Подключение Docker Hermes к локальной llama.cpp (custom_providers YAML list, context_length override, network_mode: host для доступа к host localhost).
- `references/gui-95-hang-debug.md` — **NEW (2026-06-22):** Root cause анализа 95% зависания GUI: неправильный формат connection.json (плоская структура + токен-строка вместо объекта). Пошаговый рецепт диагностики: логи Electron, REST API, WebSocket. Поток токена в main.cjs.
- `references/tui-gateway-module-fix.md` — **NEW (2026-06-22):** Корневая причина 95% зависания GUI — `ModuleNotFoundError: No module named 'tui_gateway'`. Просто `docker cp` недостаточно, нужен `PYTHONPATH=/opt/data`.
- `references/dashboard-auth-mechanics.md` — **NEW (2026-06-22):** Как работает auth в dashboard: REST (`X-Hermes-Session-Token` + `Authorization: Bearer`), WebSocket (`?token=` query param), FastAPI middleware vs WebSocket handler, 401 pitfall, отладочные curl-команды.
- `references/gui-docker-testing-workflow.md` — **NEW (2026-07-07):** Полный workflow тестирования GUI с Docker-окружением: connection.json switch, dashboard launch flags, pitfalls.
- `references/gateway-connection-settings.md` — **NEW (2026-07-07):** Quick reference: Backend A/B settings (URLs, ports, keys, tokens), connection.json formats, one-liner switch commands, Dashboard B startup with `--insecure`, verification commands.
- `references/dashboard-token-extraction.md` — **NEW (2026-07-07):** Как извлечь session token dashboard'а из HTML или задать свой при запуске.
- `references/offline-internal-deployment.md` — **(2026-07-07):** Развёртывание Hermes в изолированной сети без интернета. Режимы: офлайн (локальные GGUF), mixed, cloud-only. Предзагрузка Docker образов. Работа на сервере во внутренней сети. **UPDATED (2026-07-08):** Self-contained USB drive package pattern (~25G), FAT/exFAT symlink pitfall (`cp -rL` not `cp -a`), `deploy-offline-superqwen.sh` single-command launcher.
- `references/gui-build-pipeline.md` — **NEW (2026-07-07):** Детальный pipeline сборки GUI: архитектурные зависимости (node-pty, Electron), офлайн-перенос через tar, смена архитектуры, полная карта npm scripts, validateBundle() проверки, структура результатов.
- `scripts/start.sh` — **единая точка входа (2026-07-07):** два варианта (compose + full docker-run), команды: compose, full, minimal, gui, build, stop, status, logs. Дизайн: `references/unified-start-sh-design.md`.
- `references/unified-start-sh-design.md` — **NEW (2026-07-07):** Design document for unified start.sh — two variants, key decisions ($HOME detection, shared dashboard function, port overrides), replaced scripts, verified endpoints.
- `references/litellm-portable-deployment.md` — **NEW (2026-07-07):** LiteLLM proxy в portable: два режима (direct/proxied), arm64 image pitfall, config.docker.litellm.yaml, docker-compose.litellm.yml, start_litellm() function.
- `references/offline-portable-package.md` — **NEW (2026-07-08):** Complete offline deployment package pattern. Docker image save/load, GUI binary, GGUF model, llama-server. USB/exFAT symlink pitfalls, auto-architecture detection.
- `references/x64-cross-compilation.md` — **NEW (2026-07-08):** Cross-compiling llama-server for x64 from ARM64 host. `llama_ui_asset` build error fix, stale CMakeCache, xxd.cmake restore, Docker buildx QEMU failure, shared lib copying.

## Cross-architecture Docker build (ARM64 → x64 via QEMU buildx)

When you need to build an x64 Docker image from an ARM64 host (or vice versa),
use `docker buildx` with `--platform`. However, **QEMU cannot run Node.js** —
any `npm install`, `npm run build`, or `npx playwright` step will SIGSEGV.

### Pattern: skip Node.js steps for cross-builds

```bash
# 1. Copy Dockerfile and patch out all npm/node steps
cp Dockerfile Dockerfile.x64
# Replace npm-related RUN steps with no-ops:
sed -i '/^RUN npm install/,/npm cache clean/c\RUN true # npm skipped — QEMU SIGSEGV on x64 cross-build' Dockerfile.x64
sed -i '/^RUN cd web && npm run build/c\RUN true # web+ui-tui build skipped — QEMU SIGSEGV' Dockerfile.x64
# Fix chown that references node_modules (won't exist):
sed -i 's| /opt/hermes/node_modules||g' Dockerfile.x64

# 2. Fix apt signature issues in QEMU cross-build
sed -i 's/apt-get update/apt-get update --allow-insecure-repositories || apt-get update/' Dockerfile.x64
sed -i 's/apt-get install -y --no-install-recommends/apt-get install -y --allow-unauthenticated --no-install-recommends/' Dockerfile.x64

# 3. Build
docker buildx create --name x64builder --use 2>/dev/null || docker buildx use x64builder
docker buildx build --platform linux/amd64 -t hermes-agent:x64 -f Dockerfile.x64 --load .

# 4. Save for offline transfer
docker save hermes-agent:x64 | gzip > hermes-agent-x64.tar.gz
```

**Result:** x64 image without web UI assets (gateway+dashboard+API work, but
dashboard serves no bundled frontend). On x64 machine, run `npm run build` at
runtime to generate web assets, or use GUI Electron separately.

**QEMU SIGSEGV is not fixable** — it's a QEMU limitation with V8/Node.js JIT
on emulated x86-64. The only alternatives are: build natively on an x64 machine,
or use a CI/CD pipeline with native x64 runners.

## exFAT / FAT32 transfer limitations

External USB drives formatted as exFAT/FAT32 do NOT support:
- **Symlinks** → `cp -a` fails with "Operation not permitted". Use `cp -rL`
  (dereference symlinks) instead.
- **File permissions** → SUID bit on `chrome-sandbox` is lost. Always launch
  GUI with `--no-sandbox` when running from exFAT.
- **Hardlinks** → Docker layer deduplication doesn't work, images are larger.

```bash
# WRONG (symlinks fail on exFAT):
cp -a /home/user/dev/llama.cpp/build "/media/pavel/One Touch/hermes_portable/llama.cpp/"

# RIGHT (dereference all symlinks):
cp -rL /home/user/dev/llama.cpp/build "/media/pavel/One Touch/hermes_portable/llama.cpp/"
```

## Portable path resolution pattern

When deploying from a USB drive or portable directory, scripts must check the
portable directory FIRST, then fall back to standard home paths:

```bash
# GUI binary: check USB first, then standard install
for cand in \
  "$PORTABLE_DIR/gui/linux-${arch}-unpacked/Hermes" \
  "$REAL_HOME/.hermes/hermes-agent/apps/desktop/release/linux-${arch}-unpacked/Hermes"; do
  [ -f "$cand" ] && bin="$cand" && break
done

# Model file: check USB models/ first
local model="$PORTABLE_DIR/models/SuperQwen-APEX-I-Quality-v3.gguf"
[ -f "$model" ] || model="${REAL_HOME}/models/SuperQwen-APEX-I-Quality-v3.gguf"

# llama-server: check USB build first
local llama_bin="$PORTABLE_DIR/llama.cpp/build/bin/llama-server"
[ -f "$llama_bin" ] || llama_bin="${REAL_HOME}/dev/llama.cpp/build/bin/llama-server"
```

## Сравнение с другими AI coding agents

См. `references/comparative-research.md` — полный анализ Docker-подходов Open Interpreter, OpenHands, Ollama, vLLM, Aider, Continue.dev, Cursor.

| Агент | Docker | Изоляция | Healthcheck | Multi-arch | GUI |
|-------|:------:|----------|:-----------:|:----------:|:---:|
| **Open Interpreter** | Опционально | Контейнер на сессию | ❌ | ❌ | ❌ |
| **OpenHands** | ✅ | volumes на инстанс | ✅ `depends_on` | ✅ CI/CD | Web |
| **Ollama** | ✅ | `OLLAMA_HOME` | ❌ | ✅ | Web |
| **vLLM** | ✅ | Порт на инстанс | ✅ `HEALTHCHECK` | ✅ `buildx` | ❌ |
| **Aider** | ❌ | venv/pipx | ❌ | ❌ | ❌ |
| **Continue** | ❌ | subprocess (VS Code) | Встроенный | ❌ | ✅ |
| **Hermes (мы)** | ✅ | `HERMES_HOME` | ⚠️ `sleep` | ❌ | ✅ |

**Что нам не хватает:** `HEALTHCHECK` (vLLM), `depends_on: service_healthy` (OpenHands), CI/CD (OpenHands/Ollama). Именно их отсутствие создало 90% проблем.

## Сборка GUI из локальных файлов (офлайн/онлайн) — build-gui.sh

Одна команда для пересборки Desktop GUI на любой машине. Работает без интернета если `node_modules/` уже скопирован.

### Быстрый старт

```bash
# Только unpacked-директория (быстро, ~2 мин на ARM64)
~/.hermes/skills/deployment/hermes-docker-build/scripts/build-gui.sh

# Полный дистрибутив (AppImage/deb/rpm, ~5 мин)
~/.hermes/skills/deployment/hermes-docker-build/scripts/build-gui.sh --dist

# Пропустить проверку npm ci (node_modules уже на месте)
~/.hermes/skills/deployment/hermes-docker-build/scripts/build-gui.sh --skip-install

# Кросс-архитектура (нужен Docker x64)
~/.hermes/skills/deployment/hermes-docker-build/scripts/build-gui.sh --arch x64
```

### Что нужно на новой машине

| Компонент | Зачем | Где взять |
|-----------|-------|-----------|
| **Node.js >= 22** | Сборка | `apt install nodejs` или nvm |
| **python3, make, g++** | Компиляция node-pty | `apt install python3 make g++` |
| **node_modules/ (1.6 GB)** | Все JS-зависимости | Скопировать с донора: `cp -a hermes-agent/node_modules /target/` |
| **~/.cache/electron/ (115 MB)** | Electron binary offline | Скопировать: `cp -a ~/.cache/electron /target/~/.cache/` |
| **GITHUB_SHA env var** | write-build-stamp.cjs | Скрипт задаёт `GITHUB_SHA=local-build` автоматически |

### Pipeline сборки (что происходит внутри)

```
npm run build:
  1. assert-root-install.cjs  → проверяет ../../node_modules/vite/package.json
  2. write-build-stamp.cjs    → apps/desktop/build/install-stamp.json (git SHA)
  3. stage-native-deps.cjs    → копирует node-pty .node в build/native-deps/
  4. tsc -b                   → TypeScript type-check (500+ файлов)
  5. vite build               → frontend bundle в dist/ (22 MB JS)

electron-builder --dir:
  6. Упаковка в release/linux-<arch>-unpacked/Hermes (195 MB бинарник)
```

### Архитектурные зависимости

| Файл | Архитектура | Что делать при смене arch |
|------|-------------|--------------------------|
| `node-pty/build/Release/pty.node` | linux-arm64 (81 KB) | `npm rebuild node-pty` (нужны python3 make g++) |
| `node_modules/electron/dist/electron` | linux-arm64 (195 MB) | Удалить + `npx electron install` (скачает нужную arch) |
| `~/.cache/electron/electron-v40.9.3-linux-arm64.zip` | linux-arm64 (115 MB) | Для x64: скачать `electron-v40.9.3-linux-x64.zip` |

### Офлайн-перенос на новую машину (та же архитектура ARM64)

```bash
# На доноре: упаковать всё необходимое
cd ~/.hermes/hermes-agent
tar czf /tmp/hermes-gui-deps.tar.gz \
  node_modules/ \
  apps/desktop/package.json \
  apps/desktop/package-lock.json \
  apps/desktop/electron/ \
  apps/desktop/src/ \
  apps/desktop/scripts/ \
  apps/desktop/assets/ \
  apps/desktop/tsconfig.json \
  apps/desktop/vite.config.ts \
  ui-tui/ \
  web/ \
  package.json \
  package-lock.json

# Electron cache отдельно
tar czf /tmp/hermes-electron-cache.tar.gz -C ~/.cache electron/

# На новой машине:
mkdir -p ~/hermes-agent && cd ~/hermes-agent
tar xzf /tmp/hermes-gui-deps.tar.gz
mkdir -p ~/.cache && tar xzf /tmp/hermes-electron-cache.tar.gz -C ~/.cache
apt install -y python3 make g++  # для node-pty если нужно пересобрать

# Сборка:
~/.hermes/skills/deployment/hermes-docker-build/scripts/build-gui.sh --skip-install
```

### Запуск после сборки

```bash
# Прямой запуск бинарника:
~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes --no-sandbox &

# Через hermes CLI:
hermes gui --skip-build

# Через hermes CLI с принудительной пересборкой:
hermes gui --force-build
```

## Cross-architecture Docker builds (ARM64 → x64 via QEMU)

Building x64 Docker images from an ARM64 host (Jetson) via `docker buildx --platform linux/amd64`:

**QEMU SIGSEGV on Node.js**: Node.js/npm/Vite all crash under QEMU x86_64 emulation with `x86_64-binfmt-P: QEMU internal SIGSEGV`. This makes it impossible to run `npm install`, `npm run build`, or any Node.js command during Docker build.

**Workaround — skip all npm steps in Dockerfile for x64:**
```dockerfile
# Replace npm steps with no-ops for cross-build
RUN true # npm+playwright skipped — QEMU SIGSEGV on x64 cross-build
RUN true # web+ui-tui build skipped — QEMU SIGSEGV
# Also remove node_modules from chown (it won't exist)
# chown -R hermes:hermes /opt/hermes/.venv /opt/hermes/ui-tui /opt/hermes/gateway
```

**Result**: x64 Docker image works for gateway (Python-only), but has no web UI dashboard and no node_modules. Dashboard will start but serve blank page.

**Alternative — build on target x64 machine directly:**
```bash
# On x64 machine with Docker:
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
docker build -t hermes-agent .
```

**node-pty arch mismatch**: When copying node_modules from ARM64 Docker image to x64 build, `node-pty/build/Release/pty.node` is ARM64 ELF. Must rebuild on target:
```bash
cd hermes-agent && npm rebuild node-pty
```

## V2 Dual-Arch Pre-Built Binary Pattern (2026-07-09) — FINAL SOLUTION

**The definitive approach for portable offline deployment.** Ship BOTH
pre-built Electron binaries. Target machine needs ZERO build tools.

### What changed from V1 → V2

| Aspect | V1 (failed) | V2 (working) |
|--------|-------------|--------------|
| x64 GUI binary | Not shipped — tried building on-site (needs Node.js 22, fails with Node 24) | Pre-built on Jetson via `electron-builder --dir --x64` |
| node-pty | ARM64 native, crashes on x64 | Cross-compiled: `CC=x86_64-linux-gnu-gcc CXX=x86_64-linux-gnu-g++ npx node-gyp rebuild --target_arch=x64` |
| Docker x64 image | QEMU build — npm SIGSEGV, no node_modules | Same limitation (permanent), but documented — GUI works without web UI |
| Scripts | Monolithic start.sh (890 lines, accumulated bugs) | Clean separate scripts: start-backend.sh, launch.sh, chat.sh, stop.sh |
| Target requirements | Node.js 22, npm, python3, make, g++ | Docker ONLY. No Node.js, no npm, no build tools. |

### Build x64 binary on ARM64 Jetson

```bash
cd ~/.hermes/hermes-agent/apps/desktop

# 1. Cross-compile node-pty for x64
cd node_modules/node-pty
CC=x86_64-linux-gnu-gcc CXX=x86_64-linux-gnu-g++ npx node-gyp rebuild --target_arch=x64
cd ../..

# 2. Build x64 GUI binary
ELECTRON_SKIP_BINARY_DOWNLOAD=1 npx electron-builder --dir --x64
# → release/linux-x64-unpacked/Hermes (ELF 64-bit, x86-64, 339M)

# 3. Verify architecture
file release/linux-x64-unpacked/Hermes
```

### Ship both binaries

```bash
# ARM64 binary (native build)
cp -r release/linux-arm64-unpacked "/media/pavel/One Touch/hermes_portable_v2/gui-arm64/"

# x64 binary (cross-built)
cp -r release/linux-x64-unpacked "/media/pavel/One Touch/hermes_portable_v2/gui-x64/"
```

### exFAT corruption lesson (CORRECTED — 2026-07-10)

**exFAT LINE MERGE = silent corruption.** The ONLY confirmed failure mode:
1. **exFAT merges adjacent lines**: Two lines → one line. `bash -n` PASSES (syntax valid, semantics broken).

> **CORRECTION (2026-07-10):** Previous version of this skill claimed `write_file`
> "censors token-like strings to `***`". This was **WRONG**. Code analysis of
> `agent/redact.py` + `tools/file_tools.py` proves `write_file`/`patch` do NOT
> apply redaction on WRITE — files on disk contain real content. The `***` was
> **display-time redaction** by `read_file` (line 823:
> `result.content = redact_sensitive_text(result.content, code_file=True)`).
> See `agent/redact.py:_mask_token()` — `sk-docker-b` (12 chars < 18-char floor)
> → fully masked to `***`.

```bash
# EXPECTED (2 lines):
DASH_TOKEN="${HE...name -m)"

# ON DISK (1 line — exFAT merged 2 lines; *** in read_file = display redaction):
DASH_TOKEN=*** "$(uname -m)"
```

Result with `set -u`: `HOST_ARCH` unbound → **SILENT EXIT**. User sees empty
output after `./launch.sh`. No error, no traceback. Just dead.

**PREVENTION — ALWAYS write scripts to exFAT via terminal, not write_file:**
```bash
# CORRECT — terminal heredoc to /tmp, then cp
cat > /tmp/script.sh << 'RAWEOF'
#!/usr/bin/env bash
DASH_TOKEN="${HE...RAWEOF
bash -n /tmp/script.sh && head -20 /tmp/script.sh | cat -n
cp /tmp/script.sh "/media/pavel/One Touch/hermes_portable_v2/script.sh"
sync

# WRONG — exFAT merges adjacent lines silently (write_file itself is safe;
# the *** you see in read_file output is display-time redaction, NOT file corruption)
# write_file(path="/media/.../script.sh", content="DASH_TOKEN=...")  # Line merge risk
```

**VERIFICATION after writing to exFAT:**
```bash
bash -n script.sh                    # syntax check (DOES NOT catch line merges!)
head -20 script.sh | cat -n          # visual inspection (DOES catch line merges)
sync                                # exFAT caches writes
```

## Offline portable deployment packaging

### When NOT to rebuild (reuse from prior portable build)

Before running `docker buildx` or `electron-builder`, check if a prior portable
build on the same USB drive already has compatible assets:

```bash
# Compare versions
hermes --version
ls -la "/media/pavel/One Touch/hermes_portable_v2/docker/"  # prior build

# If Hermes version matches, copy directly (saves 2-3 hours):
cp -r "/media/pavel/One Touch/hermes_portable_v2/docker/"* "v3/docker/"
cp -r "/media/pavel/One Touch/hermes_portable_v2/gui-arm64" "v3/"
cp -r "/media/pavel/One Touch/hermes_portable_v2/gui-x64" "v3/"
```

Only rebuild when Hermes version changed or codebase has significant new commits.
See `hermes-distribution-packaging` skill → "Reuse from prior portable build".

### What to include

| Component | ARM64 source | x64 source | Size |
|-----------|-------------|------------|------|
| Docker image | `docker save hermes-agent:latest \| gzip > arm64.tar.gz` | QEMU build (limited) or build on x64 | 1.6G / 810M |
| GUI binary | `release/linux-arm64-unpacked/Hermes` | Build on x64 with `npm run pack` | 687M |
| GGUF model | `~/models/SuperQwen-*.gguf` | Same file (arch-independent) | 22G |
| llama-server | `build/bin/llama-server` (ARM64) | Cross-compile with `x86_64-linux-gnu-gcc` | 7M / 18M |
| node_modules | `tar -czf` from Docker image | Must build on x64 with `npm ci` | 109M |

**Deploy script structure** (`deploy-offline-superqwen.sh`): auto-detect arch → load Docker image from tar → start llama-server → start gateway → start dashboard → write connection.json → launch GUI.

**exFAT USB pitfalls**: see `hermes-gui-launch` skill → "Writing scripts to exFAT USB drives".

### Что нужно

| Компонент | Откуда | Размер |
|-----------|--------|--------|
| `hermes-agent/` (исходники) | git clone или копия | ~50 MB (без node_modules/venv) |
| `node_modules/` | `npm ci` или копия с донора той же arch | 1.6 GB |
| `~/.cache/electron/` | Копия с донора или скачивание | 115 MB |
| Node.js >= 22 | nvm / apt | — |
| python3, make, g++ | apt | для компиляции node-pty на Linux |

### Шаги

```bash
# 1. Получить исходники
git clone https://github.com/NousResearch/hermes-agent.git ~/hermes-agent
cd ~/hermes-agent

# 2. Установить зависимости (онлайн — npm ci, офлайн — копия node_modules/)
npm ci                              # онлайн
# ИЛИ для офлайн: cp -a /donor/node_modules ./

# 3. Собрать GUI
~/.hermes/skills/hermes-docker-build/scripts/build-gui.sh --dir

# 4. Запустить
hermes gui --skip-build
# ИЛИ напрямую:
~/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes --no-sandbox
```

### Офлайн-перенос (та же архитектура)

```bash
# На доноре: упаковать
cd ~/hermes-agent
tar czf /tmp/hermes-gui-deps.tar.gz \
  node_modules/ apps/desktop/ ui-tui/ web/ package.json package-lock.json
tar czf /tmp/hermes-electron-cache.tar.gz -C ~/.cache electron/

# На новой машине:
tar xzf hermes-gui-deps.tar.gz
mkdir -p ~/.cache && tar xzf hermes-electron-cache.tar.gz -C ~/.cache
apt install -y python3 make g++
build-gui.sh --skip-install --dir
```

## Восстановление GUI (rollback)

Если новая сборка сломалась — восстановить из backup:

```bash
# 1. Остановить GUI
kill $(pgrep -f 'Hermes --no-sandbox')

# 2. Восстановить из backup
BACKUP=~/dev/codemes/gui-backup-v1   # путь к backup
DESKTOP=~/.hermes/hermes-agent/apps/desktop

rm -rf $DESKTOP/release/linux-arm64-unpacked
rm -rf $DESKTOP/dist
cp -r $BACKUP/electron-app $DESKTOP/release/linux-arm64-unpacked
cp -r $BACKUP/dist $DESKTOP/dist

# 3. Восстановить connection.json
echo '{"mode": "local"}' > ~/.config/Hermes/connection.json

# 4. Запустить
hermes gui --skip-build
```

### Создание backup перед пересборкой

```bash
BACKUP=~/dev/codemes/gui-backup-v1
DESKTOP=~/.hermes/hermes-agent/apps/desktop
mkdir -p $BACKUP
cp -a $DESKTOP/release/linux-arm64-unpacked $BACKUP/electron-app
cp -a $DESKTOP/dist $BACKUP/dist
# Метаданные
cat > $BACKUP/BACKUP_METADATA.json << EOF
{
  "backup_created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source": "$DESKTOP",
  "hermes_version": "$(hermes --version 2>/dev/null | head -1)",
  "commit": "$(cd ~/.hermes/hermes-agent && git rev-parse HEAD 2>/dev/null)",
  "arch": "$(uname -m)",
  "gateway_port": 8643,
  "dashboard_port": 9120
}
EOF
```

## Тесты и упаковка

### Тип-check и lint (быстрые, без сборки)

```bash
cd ~/.hermes/hermes-agent/apps/desktop

# TypeScript type-check (~30s на ARM64)
npm run type-check

# ESLint
npm run lint

# UI тесты (vitest, 63 spec-файла)
npm run test:ui

# Electron platform тесты (8 test-файлов, node --test)
npm run test:desktop:platforms
```

### Полные desktop тесты (с упаковкой)

```bash
cd ~/.hermes/hermes-agent/apps/desktop

# Собрать packaged app и запустить с существующим Hermes
npm run test:desktop:existing

# Собрать packaged app и запустить с temp userData + HERMES_HOME (чистый старт)
npm run test:desktop:fresh

# Быстрый реран (без пересборки если packaged app уже есть)
HERMES_DESKTOP_SKIP_BUILD=1 npm run test:desktop:fresh

# Всё сразу: сборка + валидация bundle + вывод артефактов
npm run test:desktop:all
```

**Что проверяет `validateBundle()`:**
- ✅ Бинарник Hermes существует
- ✅ install-stamp.json с валидным commit + branch
- ✅ node-pty native deps (.node бинарник) в resources/native-deps/
- ✅ Renderer payload (dist/index.html) в unpacked или asar
- ✅ Нет stale factory-payload (thin-installer регрессия)

### Упаковка дистрибутива

```bash
cd ~/.hermes/hermes-agent/apps/desktop

# Unpacked-директория (быстро, для тестов)
npm run pack                         # = npm run build + electron-builder --dir

# Linux: AppImage + deb + rpm
npm run dist:linux

# macOS: dmg + zip
npm run dist:mac

# Windows: msi + nsis
npm run dist:win

# Все платформы (без указания target — дефолтные для текущей ОС)
npm run dist
```

### Результат сборки

```
apps/desktop/
├── dist/                          ← Frontend bundle (vite, 22 MB JS)
├── build/
│   ├── install-stamp.json         ← git commit + branch + timestamp
│   └── native-deps/
│       └── node-pty/
│           └── build/Release/pty.node   ← Native бинарник (81 KB)
└── release/
    ├── linux-arm64-unpacked/      ← Готовый бинарник Hermes (335 MB)
    │   ├── Hermes                 ← Electron app (195 MB)
    │   ├── chrome-sandbox         ← SUID wrapper
    │   ├── icudtl.dat             ← ICU data (10 MB)
    │   └── ...
    ├── Hermes-0.15.1-linux-arm64.AppImage  ← (при --dist)
    ├── Hermes-0.15.1-linux-arm64.deb       ← (при --dist)
    └── Hermes-0.15.1-linux-arm64.rpm       ← (при --dist)
```

## Diff: hermes_portable vs скилл

| Категория | hermes_portable/scripts/ | skill scripts/ | Статус |
|-----------|-------------------------|----------------|--------|
| **Deploy orchestration** | deploy.sh, deploy-full.sh, deploy-minimal.sh, deploy-offline.sh, deploy-verify.sh | — | только в portable |
| **GUI build/launch** | build-gui.sh *(NEW)* | build-gui.sh, desktop.sh, launch-docker-gui.sh | синхронизировано |
| **Docker helpers** | — | docker-entrypoint.sh, docker-quick-start.sh, quick-start.sh, status-proxy.py, test-dashboard.py | только в скилле |
| **Infra scripts** | check-hardware.sh, setup-firewall.sh, setup-cron.sh, skills-migrate.sh, env-var-resolver.py, litellm-config-generator.py, knowledge-graph-rebuild.py, migrate-state.py, path-rewrite.py, state-export.sh, state-import.sh | — | только в portable |

**GAP закрыт:** `build-gui.sh` скопирован в `hermes_portable/scripts/`. Теперь portable-пакет может собирать GUI.

## start.sh — единая точка входа (два варианта)

**Файл:** `scripts/start.sh` (копия: `~/dev/hermes_portable/start.sh`)

Единый скрипт с двумя вариантами разворачивания:

| Команда | Вариант | Описание |
|---------|---------|----------|
| `./start.sh compose` | A | docker-compose: gateway + dashboard в одном compose |
| `./start.sh full` | B | docker run: полный стек (gateway + dashboard + опц. llama.cpp) |
| `./start.sh full --litellm` | B | Полный стек + LiteLLM proxy (:4000 → :8092) |
| `./start.sh full --3models` | B | 3 APEX models (Nex+Qwen+World on :8101/:8102/:8103) |
| `./start.sh full --3models` | B | Полный стек + LiteLLM (multi-model routing) |
| `./start.sh full --superqwen` | B | 1 модель: SuperQwen APEX only (:8103) |
| `./start.sh minimal` | B | docker run: только gateway, без dashboard |
| `./start.sh litellm` | — | Запуск LiteLLM proxy (arm64-native, :4000 → host :8092) |
| `./start.sh gui` | — | Запуск Desktop GUI (подключается к работающему dashboard) |
| `./start.sh build` | — | Сборка Docker образа из `~/.hermes/hermes-agent/` |
| `./start.sh stop` | — | Остановка всех контейнеров (включая litellm) |
| `./start.sh status` | — | Статус gateway, dashboard, litellm, llama-server, контейнеров |
| `./start.sh logs [svc]` | — | Логи: gateway, dashboard, neo4j, litellm |

### Variant A (compose) — простое разворачивание

```bash
./start.sh compose
# → docker compose -f docker/docker-compose.yml up -d
# → gateway на :18648, dashboard на :9121
# → healthcheck с start_period: 180s
# → dashboard зависит от gateway (condition: service_healthy)
```

### Variant B (full) — полный стек

```bash
# Полный стек без локальной модели:
./start.sh full

# С локальной GGUF моделью:
./start.sh full --model ~/models/deepseek.gguf --gpu-layers 80

# Полный стек + LiteLLM proxy (multi-model routing через :4000):
./start.sh full --litellm

# Минимальный (только gateway):
./start.sh minimal
```

### LiteLLM Proxy — два режима маршрутизации LLM

Gateway может ходить к llama-server напрямую или через LiteLLM. Выбор определяется конфигом:

```
РЕЖИМ DIRECT (по умолчанию):
  Gateway (:18648) ──→ localhost:8092 (llama-server)
  config.docker.yaml (custom_providers → base_url: localhost:8092)

РЕЖИМ PROXIED (--litellm):
  Gateway (:18648) ──→ :4000 (LiteLLM) ──→ :8092 (llama-server)
                                       └──→ cloud APIs (DeepSeek, OpenAI, ...)
  config.docker.litellm.yaml (providers → base_url: localhost:4000)
```

| Конфиг | Маршрут | Когда использовать |
|--------|---------|-------------------|
| `config/config.docker.yaml` | Direct → :8092 | Offline, одна модель |
| `config/config.docker.litellm.yaml` | Proxied → :4000 | Multi-model, cloud fallback |

Переключить: `cp config/config.docker.litellm.yaml config/config.docker.yaml` (или `start.sh full --litellm` делает это автоматически).

### Single-model deployment (--superqwen)

For running just ONE model (SuperQwen APEX on :8103), use `start.sh full --superqwen`.
This launches a single llama-server instance (~22G VRAM vs ~77G for 3 models), and
switches to `config.docker.superqwen.yaml` — a single `custom_providers` entry pointing
to `:8103`. Useful when GPU memory is limited or only one model is needed.

The `start_llama_superqwen()` function in start.sh handles model detection, launch,
and health check. Override the model path with `MODEL_FILE=/path/to/model.gguf`.

### 3-Model direct deployment (no LiteLLM needed)

For 3 simultaneous models (Nex/Qwen/AgentWorld on :8101/:8102/:8103), use `start.sh full --3models` which switches to `config.docker.3models.yaml` — 3 `custom_providers` entries, one per port. This works WITHOUT LiteLLM because gateway on `--network host` reaches all ports directly, bypassing UFW. **Full config + verification:** see `hermes-docker-deploy` skill → "3-Model APEX deployment" and "`--network host` bypasses UFW".

### Single-model SuperQwen deployment (--superqwen)

For running only SuperQwen APEX (agentworld on :8103, ~22G GPU RAM instead of 77G for 3 models):

```bash
cd ~/dev/hermes_portable
REAL_HOME=$HOME bash ./start.sh full --superqwen
```

Config: `config/config.docker.superqwen.yaml` — single `custom:world` provider → :8103, model `agentworld`. Saves ~55G GPU RAM vs 3-model mode.

**Single-model alternative:** `start.sh full --superqwen` launches only SuperQwen (agentworld) on :8103 — saves ~55G GPU RAM (22G vs 77G for 3 models). Config: `hermes-docker-deploy` skill → `templates/config.superqwen.yaml`.

**LiteLLM образ (ARM64):** `ghcr.io/berriai/litellm-database:main-stable` (arm64-native). НЕ `v1.83.7-stable` — amd64-only → QEMU SIGSEGV на prisma-migrate. См. `references/litellm-portable-deployment.md`.

### Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PORT_GW` | 18648 | Порт Gateway API |
| `PORT_DASH` | 9121 | Порт Dashboard |
| `HERMES_HOME` | ~/.hermes-docker | Директория данных |
| `DASH_TOKEN` | hermes-docker-token | Dashboard session token |
| `HERMES_IMAGE` | hermes-agent | Docker image name |

### `start.sh gui` — всегда remote mode

`start.sh gui` **всегда** пишет `connection.json` в remote mode перед запуском.
Backup/restore НЕ делается — пользователь хочет простоту. Для возврата на локальный Hermes:

```bash
echo '{"mode":"local"}' > ~/.config/Hermes/connection.json
```

**⚠️ BUG (discovered 2026-07-07):** `start.sh gui` writes `PORT_GW` (gateway,
:18649) into `connection.json` instead of `PORT_DASH` (dashboard, :9123).
Desktop's `waitForHermes()` polls `/api/status` — gateway returns 404, dashboard
returns 200. This causes boot failure: `Hermes backend did not become ready: 404`.

**Workaround:** manually write connection.json with PORT_DASH before launching:
```bash
cat > ~/.config/Hermes/connection.json <<EOF
{"mode":"remote","remote":{"url":"http://localhost:9123","token":{"value":"$DASH_TOKEN"},"authMode":"token"},"profiles":{}}
EOF
```

**⚠️ ARM64 Jetson:** `start.sh gui` does NOT add `--disable-gpu` flags. Without
them, Electron crashes with `FATAL: GPU process isn't usable. Goodbye`. Either
patch start.sh to add the flags or launch the binary directly.

Env vars `HERMES_DESKTOP_REMOTE_URL`/`HERMES_DESKTOP_REMOTE_TOKEN` **НЕ работают** (проверено 2026-06-22 и 2026-07-07) — GUI игнорирует их и читает `connection.json`. Только запись правильного JSON в `~/.config/Hermes/connection.json` переключает GUI в remote.

### Pitfalls в start.sh

| Pitfall | Fix |
|---------|-----|
| `uname -m` → `aarch64`, electron-builder → `arm64` | Мапить: `aarch64\|arm64 → arm64`, `x86_64\|amd64 → x64` |
| Hermes переопределяет `$HOME` → `/home/user/.hermes/home` | Использовать `getent passwd "$(id -u)" \| cut -d: -f6` для реального home |
| `|| { ... fi }` — bash syntax error | Использовать `if ! ...; then ... fi` |
| `--user-data-dir` НЕ влияет на `connection.json` | GUI всегда читает `~/.config/Hermes/connection.json` |

### Старые скрипты (deprecated, заменены start.sh)

- `scripts/quick-start.sh` — заменён на `start.sh compose`
- `scripts/docker-quick-start.sh` — заменён на `start.sh build && start.sh compose`
- `scripts/status-proxy.py` — **obsolete** (dashboard предоставляет `/api/status`)
- `scripts/deploy-full.sh` — заменён на `start.sh full`
- `scripts/deploy-minimal.sh` — заменён на `start.sh minimal`

## Ключевые инсайты (всё в одном месте)

1. **Два Hermes НЕ делят `~/.hermes/`** — нужна `~/.hermes-docker/`
2. **`network_mode: host`** — единственный рабочий режим для gateway
3. **`HERMES_DISABLE_MESSAGING=1` — ❌ ПЕРЕМЕННАЯ-ПРИЗРАК. НЕ СУЩЕСТВУЕТ в коде Hermes (0 упоминаний). Не использовать.**
4. **Desktop читает `HERMES_DESKTOP_REMOTE_URL`**, не `HERMES_API_URL`
5. **Desktop ждёт `/api/status`**, gateway имеет `/health`
6. **Dashboard НУЖЕН для GUI** — даёт WebSocket (`/api/ws`) и `/api/status`, без которых GUI не работает. Запускать ОТДЕЛЬНЫМ контейнером с `--volumes-from hermes-test` и `-e PYTHONPATH=/opt/data`. **ОБЯЗАТЕЛЬНЫЕ флаги:** `--tui` (WebSocket для чата), `--insecure` (token auth для remote desktop, без него `/api/sessions`, `/api/agents` → 401), `--skip-build`, `--no-open`. Токен `HERMES_DASHBOARD_SESSION_TOKEN=sk-local` обязателен при `--insecure`.
7. **`tui_gateway/` ОТСУТСТВУЕТ в Docker-образе — КОРНЕВАЯ ПРИЧИНА 95% ЗАВИСАНИЯ.** Просто `docker cp` НЕДОСТАТОЧНО — файлы копируются на диск, но Python не может импортировать (`ModuleNotFoundError`). **Fix:** (1) `tar -C ~/.hermes/hermes-agent -c tui_gateway/ | docker exec -i hermes-dashboard tar -C /opt/data -x` (persistent volume), (2) `-e PYTHONPATH=/opt/data` в `docker run`. См. `references/tui-gateway-module-fix.md`.
8. **FastAPI HTTP middleware НЕ применяется к WebSocket** — WebSocket auth проверяется через `_ws_auth_ok()` по `?token=` query-параметру. REST auth — через `auth_middleware`, которая проверяет ДВА заголовка: `X-Hermes-Session-Token` (основной, шлёт Electron main process) И `Authorization: Bearer` (legacy, для обратной совместимости). При `--insecure` оба работают. Поэтому GUI может использовать `X-Hermes-Session-Token` без `Authorization` header.
8. **`HERMES_DASHBOARD_SESSION_TOKEN`** — ОБЯЗАТЕЛЕН при `--insecure`. Без него `/api/sessions`, `/api/agents` → 401.
9. **Прокси (status-proxy.py) НЕ НУЖЕН при использовании dashboard** — dashboard сам отдаёт `/api/status` и WebSocket. Прокси был workaround'ом когда корневая причина (ModuleNotFoundError для tui_gateway) ещё не была найдена. Теперь, с `PYTHONPATH=/opt/data`, прокси полностью obsolete.
10. **`GITHUB_SHA` вне условных блоков** — иначе повторные запуски ломаются
9. **`chown .venv` — ~4-5 минут на ARM64 при ПЕРВОМ запуске** (с новым HERMES_UID). Повторные запуски — мгновенно: stage2 hook проверяет `venv_owner == actual_hermes_uid` перед chown. Без `HERMES_UID`/`HERMES_GID` chown пропускается полностью.
10. **ТЕСТИРОВАТЬ ВСЕ ENDPOINT'Ы ПЕРЕД тем как просить пользователя запустить GUI** — curl health, sessions, WebSocket, models. Только после 100% прохождения — давать команду.
11. **НЕ пушить на GitHub без полного smoke-теста** — docker compose up → health → models → chat → down
12. **НИКОГДА не вставлять реальные ключи** в файлы дистрибутива — только `.env.example` с плейсхолдерами
13. **`--user-data-dir` НЕ влияет на `connection.json`** — GUI всегда читает `~/.config/Hermes/connection.json`. Для изоляции использовать ТОЛЬКО env vars `HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN`.

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| **`HERMES_DISABLE_MESSAGING=1` — GHOST VARIABLE** | Обнаружено 2026-06-21: переменная имеет 0 упоминаний во всём коде Hermes. Не существует. Telegram не блокируется этой переменной. Использовать `docker-entrypoint.sh` (sed) для удаления Telegram из config.yaml, или не задавать `TELEGRAM_BOT_TOKEN`. |
| **custom_providers as dict** → "must be a YAML list" error | Use `- name: llama` list format, NOT `llama:` dict key |
| **Model context < 64K rejected** by Hermes | Set `model.context_length: 65536` in config |
| **Telegram hardcoded in gateway** — config removal insufficient | Telegram platform imported in gateway code; `HERMES_DISABLE_MESSAGING=1` doesn't stop platform init. Solution: tolerate Telegram connection timeouts (gateway eventually starts API server) |
| **GUI 95% hang (КОРНЕВАЯ ПРИЧИНА)** | `docker cp` копирует `tui_gateway/` но Python не может импортировать → `ModuleNotFoundError: No module named 'tui_gateway'` → WebSocket 500 → GUI висит на 95%. **Fix:** (1) скопировать `tui_gateway/` на persistent volume `/opt/data/`, (2) добавить `-e PYTHONPATH=/opt/data` в `docker run`. См. `references/tui-gateway-module-fix.md`. |
| **GUI 24% hang** — missing `/api/status` | Proxy stub `{"status":"ok","auth_required":false}` |
| **`docker compose restart` doesn't reload volumes** | Use full `down` + `up` to pick up config changes |
| **Config overwritten on boot** — Hermes stage2 seeds default if format differs | Write config BEFORE `docker compose up`, verify after container starts |
| **GPU crash launching GUI from background** | GUI requires `$DISPLAY` — launch from terminal with display access, not via agent background tools. **On ARM64 Jetson: ADDITIONALLY requires `--disable-gpu --disable-software-rasterizer --no-sandbox`** — Chromium GPU sandbox crashes with `error_code=1002 → FATAL: GPU process isn't usable. Goodbye`. See `hermes-gui-launch` skill for full details. |
| **Cross-compile Docker x64 from ARM64 (QEMU)** | **QEMU SIGSEGV on Node.js:** `npm install`, `npm run build`, `playwright install` all crash with `x86_64-binfmt-P: QEMU internal SIGSEGV`. apt-get works (needs `--allow-unauthenticated`), pip works, but Node.js does not. **Fix:** skip ALL npm steps in Dockerfile (`RUN true` instead), build natively on x64, or accept no web UI in x64 image. See `hermes-docker-deploy` skill → "Docker platform mismatch" + `references/offline-usb-packaging.md`. |
| **exFAT breaks bash heredocs** | USB drives formatted as exFAT corrupt `cat <<EOF` — lines merge, EOF eaten. **Fix:** use `printf` for all file generation on exFAT. Also: exFAT strips symlinks → use `cp -rL`. See `hermes-docker-deploy` skill → "exFAT pitfalls". |
| **start.sh gui BUG (FIXED 2026-07-08)** | Was writing PORT_GW instead of PORT_DASH into connection.json + wrong token (API_SERVER_KEY instead of DASH_TOKEN) + missing `--disable-gpu` flags. **Fixed** — now writes PORT_DASH + DASH_TOKEN + all 3 GPU flags. |
|---------|-----|
| `:ro` (read-only) монтирование | Hermes пишет `gateway.pid`, `.backup` — нужна запись |
| chown висит на `.venv` | Первый запуск: ждать **4-5 минут** на Jetson ARM64 (`.venv` внутри контейнера, не на volume). Повторные запуски: мгновенно (stage2 hook пропускает chown если `venv_owner == actual_hermes_uid`). Проверять: `for i in $(seq 1 150); do curl -sf localhost:9119/api/status && break; sleep 2; done`. **Ускорение:** `env -u HERMES_UID -u HERMES_GID docker run ...` пропускает UID remap и chown (но может дать permission denied на `/opt/data`). После первого успешного chown — повторные запуски мгновенные. |
| Telegram вешает gateway (РФ) | **Вариант А:** `HERMES_DISABLE_MESSAGING=1` (одна переменная, все платформы). **Вариант Б:** `docker-entrypoint.sh` вырезает telegram из config.yaml. **Вариант А проще и надёжнее** |
| `***` без кавычек в YAML | YAML парсит `***` как alias anchor — всегда `"API_SERVER_KEY=***"`. **В одном поле на строку.** Наблюдался баг: `- "API_SERVER_KEY=***      - GATEWAY_ALLOW_ALL_USERS=true` — всё на одной строке, `GATEWAY_ALLOW_ALL_USERS` не выставлялась. |
| Порт 8648 занят основным Hermes | С `network_mode: host` — использовать `API_SERVER_PORT=18648`. Без host-сети — `ports: "18648:8648"` |
| `sk-proj-...Cr8A` в `.env` | Убедиться что санитизирован |
| SHA образа недоступен | `docker pull` + `sed` (шаг 1) |
| MCP-серверы падают (node, searchbox) | Не критично для API — варнинги, не fatal |
| `GATEWAY_ALLOW_ALL_USERS` warning | Добавить `GATEWAY_ALLOW_ALL_USERS=true` в environment |
| **Desktop: npm workspace конфликт** | Имена заглушек должны быть уникальны: `hermes-tui-stub`, `hermes-ink-stub`, `hermes-web-stub`. Не `stub` во всех трёх |
| **Desktop: assert-root-install** | Требует `node_modules/vite/package.json` в корне `hermes-agent/`. Создать заглушку |
| **Desktop: write-build-stamp** | Требует git SHA. Установить `GITHUB_SHA=sanitized-release` ДО блока `if [ ! -d "node_modules/react" ]` (вне условного блока, иначе при повторных запусках не выставляется) |
| **Desktop: Electron не качается (РФ)** | `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/` |
| **Desktop: env vars не работают → GUI подключается к локальной среде** | Наблюдалось 2026-06-22: несмотря на `HERMES_DESKTOP_REMOTE_URL/TOKEN`, GUI подключался к локальному Hermes. **Решение:** временно переключить `connection.json` в remote mode (с правильным форматом токена — `{"value": "sk-local"}`), запустить GUI, восстановить `local` mode. Или использовать скрипт `scripts/launch-docker-gui.sh` который читает токен из `/tmp/dashboard_token`. |
| **Desktop: висит на 24%** | Desktop ждёт `/api/status`, Docker gateway имеет только `/health`. Решение: `status-proxy.py` на порту 18649. См. `scripts/status-proxy.py`. GUI → прокси :18649 → Docker :18648. |
| **Desktop: висит на 95%** | GUI загружает `/api/sessions`, `/api/agents`, `/api/skills` — Docker возвращает 404. Стабы в прокси: все возвращают `[]` или `{}`. |
| **Desktop: 95% + "Connect a model provider"** | Нет модели. Нужен API-ключ или локальная модель через `custom_providers`. См. `references/local-llama-integration.md`. |
| **`custom_providers` — YAML LIST** | Должен быть list с `- name:`, не dict. См. `references/local-llama-integration.md`. |
| **`context_length` < 65536** | Hermes требует 64K минимум. Ставить `model.context_length: 65536`. |
| **Config перезаписывается** | Hermes при старте перезаписывает config.yaml. После `docker compose up` проверить и восстановить custom_providers. |
| **Прокси умирает при рестарте Docker** | После `docker compose down && up` перезапустить прокси вручную. |
| **`--user-data-dir` НЕ влияет на `connection.json`** | GUI всегда читает `connection.json` из `~/.config/Hermes/` (или per-profile override), НЕ из `--user-data-dir`. Для изоляции от хостового GUI использовать ТОЛЬКО env vars `HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN` (они имеют приоритет над `connection.json`). `--user-data-dir` изолирует кэш/сессии/настройки, но НЕ точку подключения. |
| **Hermes переопределяет `$HOME`** | Внутри Hermes agent context `$HOME` = `/home/user/.hermes/home`, а НЕ `/home/user`. Скрипты deploy (start.sh и др.) должны использовать `getent passwd "$(id -u)" \| cut -d: -f6` для определения реального домашнего каталога. |
| **`uname -m` ≠ electron-builder arch** | `uname -m` → `aarch64`, но electron-builder создаёт `linux-arm64-unpacked/`. Скрипты должны мапить: `aarch64\|arm64 → arm64`, `x86_64\|amd64 → x64`. |
| **connection.json: PLAIN STRING TOKEN → 401** | `decryptDesktopSecret()` ожидает объект `{value: "sk-local"}`, а не строку `"sk-local"`. Токен-строка → `typeof secret !== 'object'` → возвращает `""` → 401 Unauthorized на ВСЕ REST-запросы. Формат: `"token": {"value": "sk-local"}`. |
| **connection.json: FLAT STRUCTURE → undefined URL** | `readDesktopConnectionConfig()` читает `parsed.remote.url`, не `parsed.url`. Правильная структура: `{"mode":"remote","remote":{"url":"...","token":{...},"authMode":"token"},"profiles":{}}`. Flat structure → `config.remote = {}` → undefined URL. |
| **Desktop: GPU crash из фонового процесса** | `GPU process isn't usable. Goodbye.` — Electron требует дисплей (`$DISPLAY`). Фоновые процессы (`terminal(background=true)`) не имеют доступа к GPU. GUI можно запустить ТОЛЬКО из интерактивного терминала. Для тестов — дать пользователю команду, не пытаться запустить самим из фона. |
| **ТЕСТИРОВАТЬ ПЕРЕД ЗАПУСКОМ** | Pavel: **НИКОГДА не говори «работает» без визуального подтверждения от пользователя.** Curl-тесты endpoint'ов (200/101) — необходимое, но НЕ достаточное условие. GUI может висеть на 95% даже когда все curl-тесты проходят. Причины: (1) connection.json формат — flat structure/plain-string token дают 401 только через GUI auth path (decryptDesktopSecret), curl с Authorization: Bearer этого не ловит; (2) GPU crash в фоновых процессах; (3) GUI boot stateful — каждый следующий шаг зависит от предыдущего. **Проверять всё через curl СНАЧАЛА, потом давать команду пользователю и ЖДАТЬ подтверждения.** |
| **HERMES_UID/GID leak из родительского shell** | Если в родительском shell экспортированы `HERMES_UID=1000` и `HERMES_GID=1000`, они ПРОСАЧИВАЮТСЯ в `docker run` даже без явных `-e`. Результат: медленный chown на первом старте. Чтобы запустить БЕЗ chown: `env -u HERMES_UID -u HERMES_GID docker run ...`. Для production — оставить `-e HERMES_UID=1000` (chown один раз, потом мгновенно). См. `references/hermes-uid-leakage.md`. |
| **Dashboard нужен для GUI** | GUI требует WebSocket (`/api/ws`) и `/api/status` — их даёт dashboard, не gateway. Запускать dashboard отдельным контейнером: `docker run -d --name hermes-dashboard --network host --volumes-from hermes-test hermes-agent dashboard --host 127.0.0.1 --port 9119 --no-open`. |
| **GUI+Docker WebSocket работает (2026-06-22 проверено)** | WebSocket (`/api/ws?token=...`) даёт `HTTP 101` при правильном `PYTHONPATH=/opt/data`. FastAPI HTTP middleware НЕ применяется к WebSocket-роутам — auth проверяется через `_ws_auth_ok()` по `?token=` query-параметру, не через `Authorization` header. `X-Hermes-Session-Token` header работает для REST API (проверено: `/api/sessions`, `/api/config/defaults` → 200). Единственная причина зависания на 95% — `ModuleNotFoundError: No module named 'tui_gateway'`. |
| **Dashboard restart loop** | Dashboard и Gateway конфликтуют за `s6-log` lock на общем `~/.hermes` вольюме при использовании docker-compose. Решение: dashboard отдельным `docker run` с `--volumes-from`, не в compose. |
| **s6-log lock даже с --volumes-from (2026-06-22)** | Даже с `--volumes-from` оба контейнера делят ОДИН volume и s6-log конфликтует. **Решение:** dashboard должен иметь СВОЙ отдельный data-каталог (`-v /tmp/dash-data:/opt/data`), не делить volume с gateway. tui_gateway монтировать ОТДЕЛЬНЫМ bind mount: `-v /tmp/dash-data/tui_gateway:/opt/hermes/tui_gateway`. |
| **GUI: 401 Unauthorized при правильном токене** | GUI шлёт `X-Hermes-Session-Token` (правильный заголовок, проверенный curl), но получает 401. Возможные причины: (1) `connection.json` per-profile overrides перекрывают env vars — проверить `cat ~/.config/Hermes/connection.json`; (2) `decryptDesktopSecret()` падает на строковом токене, возвращает `""` → 401. Решение: правильный формат `{"value": "sk-local"}` в объекте токена; (3) race condition в `startHermes()` кеширует `connectionPromise` до полного разрешения env vars. **Debug:** проверить `docker logs hermes-dashboard | grep -i "ws\|auth\|Unauthorized"`. **Env vars не работали у Pavel 2026-06-22** — GUI подключался к локальному Hermes несмотря на `HERMES_DESKTOP_REMOTE_URL/TOKEN`. Работает ТОЛЬКО через `connection.json` в remote mode с правильным форматом токена. После теста — восстановить `local` mode. |
| **GATEWAY_HEALTH_URL для кросс-контейнерного обнаружения** | Dashboard не видит gateway через PID-файлы (разные data dirs). Нужна env var `GATEWAY_HEALTH_URL=http://localhost:18648/health`. Тогда dashboard пробует HTTP health endpoint и показывает `gateway_running: true`. Без неё: `gateway_running: false, gateway_state: null`. |
| **s6-overlay container_environment и --env-file** | `docker run -e` может ненадёжно передавать env vars в s6 `container_environment`. Надёжнее: `--env-file /tmp/dashboard.env`. Проверить: `docker exec <ctr> cat /run/s6/container_environment/GATEWAY_HEALTH_URL`. |
| **170s chown при каждом запуске** | На Jetson ARM64 chown `.venv` занимает ~170s при КАЖДОМ создании контейнера. После chown dashboard отвечает на :9119. Ждать: `for i in $(seq 1 90); do curl -sf localhost:9119/api/status && break; sleep 2; done`. |
| **Dashboard стартует свой gateway (main-hermes)** | `hermes-agent` образ включает оба сервиса: `main-hermes` (gateway) и `dashboard`. При `--network host` dashboard контейнер запускает СОБСТВЕННЫЙ gateway на порту 18648, который конфликтует с основным gateway контейнером. Не смертельно — один из них займёт порт. Для чистоты: либо выключить `main-hermes` в dashboard контейнере, либо использовать отдельный порт для каждого gateway. |
| **connection.json: ПРАВИЛЬНЫЙ ФОРМАТ (2026-06-22)** | ~/.config/Hermes/connection.json ДОЛЖЕН иметь вложенную структуру: `{"mode":"remote","remote":{"url":"http://localhost:9119","token":{"value":"sk-local"},"authMode":"token"},"profiles":{}}`. Две фатальные ошибки: (1) плоская структура (url на верхнем уровне) → config.remote = {} → undefined URL; (2) токен-строка вместо объекта → decryptDesktopSecret() возвращает "" → 401 на всех REST API. **Подробно:** `references/connection-json-remote-format.md`. |
| **connection.json: deprecated flat format** | Старый формат (был причиной 95% зависания): `{"mode":"remote","url":"http://...","token":"sk-local","authMode":"token"}` — НЕ РАБОТАЕТ. Использовать новый формат с вложенным `remote` объектом выше. |
| **YAML: `***` без кавычек ломает парсинг** | YAML интерпретирует `***` как alias. Всегда: `- "API_SERVER_KEY=***"` с кавычками |
| **Desktop: connection.json > env vars** | Приоритет: 1) per-profile override, 2) `HERMES_DESKTOP_REMOTE_URL/TOKEN`, 3) `connection.json`. Проще всего — `connection.json` раз и навсегда |
| **docker-entrypoint.sh ломает config.yaml** | sed-патч для Telegram портит структуру YAML. **Решение: `HERMES_DISABLE_MESSAGING=1` вместо entrypoint**. Или использовать Python-скрипт с pyyaml (но venv может быть не готов на этапе entrypoint) |
| **Bridge-сеть: proxy не видит hermes:8648** | С `network_mode: bridge` нужен proxy для `/api/status`. Но proxy не может достучаться до hermes-контейнера пока gateway не стартовал (chown). **Решение: `network_mode: host` + `API_SERVER_PORT=18648`** — проще и надёжнее |
| **docker-entrypoint.sh permission** | `chmod +x docker-entrypoint.sh` перед `docker compose up` |
| `docker compose` orphan warnings | `docker compose down --remove-orphans` перед `up` |
| **ДВА Hermes = конфликт `~/.hermes/`** | Создать `~/.hermes-docker/` с отдельным config.yaml и .env. Не использовать общий `~/.hermes/` |
| **Docker образ по умолчанию использует OpenRouter** | Встроенный config.yaml в Docker-образе: `model.default: anthropic/claude-opus-4.6`, `provider: auto` → `openrouter`. Нужен `OPENROUTER_API_KEY` в `.env`, а не только `DEEPSEEK_API_KEY`. Без ключа — HTTP 401 `Missing Authentication header`. |
| **`API_SERVER_KEY=***` отвергается** | Hermes явно проверяет на плейсхолдеры: `Refusing to start: API_SERVER_KEY is set to a placeholder value`. **Всегда генерировать настоящий ключ:** `openssl rand -hex 32`. |
| **Docker НЕ монтировать `~/.hermes-docker/` для дистрибуции** | Дефолтный конфиг образа чище — без Telegram, MCP, сломанных путей `/home/user/`. Монтирование нужно только для персистентности (скиллы, cron, state.db). Для первого запуска — без volume. |
| **Neo4j Community cannot STOP DATABASE for dump (2026-07-06)** | `cypher-shell "STOP DATABASE neo4j"` → `Unsupported administration command` on Community edition. `neo4j-admin database dump` → "database is in use". **Workaround:** (1) `docker stop neo4j`, (2) `docker run --rm -v <volume>:/data -v <dumps>:/dumps neo4j:5-community neo4j-admin database dump neo4j --to-path=/dumps --overwrite-destination`, (3) `docker start neo4j`. Must `chmod 777` dumps dir first (container user is `neo4j` UID 7474). |
| **`~` в docker-compose не раскрывается в sandbox** | `HERMES_HOME=/home/user/.hermes/home` → `~` → `/home/user/.hermes/home/` а не `/home/user/`. Использовать абсолютные пути: `/home/user/.hermes-docker:/opt/data`. |
| **Плейсхолдеры API ключей в `.env` = 401** | Даже если ключ передан через env var, Hermes проверяет его на валидность при вызове LLM. `<YOUR_KEY>`, `***`, `CHANGEME` → 401 от провайдера. |
| **`custom_providers` должен быть YAML LIST, не dict** | `custom_providers: {llama: {base_url: ...}}` → ошибка `[ERROR] custom_providers is a dict — it must be a YAML list`. Правильно: `custom_providers:\n  - name: llama\n    base_url: ...`. См. `references/local-llama-integration.md`. |
| **`context_length` < 65536 → ValueError** | Hermes требует минимум 64K контекста. Даже если модель имеет 32K — поставить `model.context_length: 65536` в config.yaml. Hermes обрежет по факту. |
| **`CUSTOM_PROVIDER_*` env vars НЕ создают провайдера** | Недостаточно установить `CUSTOM_PROVIDER_BASE_URL` + `CUSTOM_PROVIDER_NAME` + `CUSTOM_PROVIDER_API_KEY` в docker-compose environment. Нужен полноценный `custom_providers` блок в config.yaml (и volume mount для него). |
| **`docker compose restart` не перечитывает volume config** | `restart` перезапускает процесс контейнера без пересоздания. Изменения в монтированном config.yaml не подхватываются. Нужен полный `docker compose down && up`. |
| **`HERMES_DISABLE_MESSAGING=1` не глушит Telegram полностью** | Даже с этой переменной gateway ВСЁ РАВНО пытается подключиться к `api.telegram.org` (видно в логах: `WARNING gateway.platforms.telegram_network`). Это не блокирует API server, но создаёт шум. Для чистого запуска — удалить `telegram` из `config.yaml` через Python-скрипт ДО первого старта. |
| **НИКОГДА не вставлять реальные ключи в `.env` дистрибутива** | `.env` с реальными ключами НЕ должен быть в репозитории. Только `.env.example` с плейсхолдерами. `.gitignore` обязан исключать `.env`. Пользователь сам создаёт `.env` из `.env.example`. Pavel отвергает любые попытки вставить ключи — дистрибутив должен быть key-free. |
| **НЕ пушить на GitHub без полного тестирования** | Минимальный smoke-test перед push: (1) `docker compose up -d`, (2) дождаться health, (3) `curl /v1/models` с ключом, (4) `curl /v1/chat/completions`, (5) `docker compose down`. Только после успешного прохождения всех 5 шагов — push. |
| **`/health` есть, `/api/status` — нет** | Docker-образ Hermes имеет только `/health` эндпоинт. Desktop GUI ждёт `/api/status`. Без патча `main.cjs` или `connection.json` Desktop не подключится. `status-proxy.py` — мёртвый код (symptom treatment), должен быть удалён. |
| **`.env` переопределяет command-line env vars** | `API_SERVER_PORT=18648` в команде не сработает если в `.env` уже есть `API_SERVER_PORT=8643` — `.env` загружается через python-dotenv ПОСЛЕ command-line. Решение: использовать отдельный HERMES_HOME с нужным `.env`, или установить `HERMES_DASHBOARD_SESSION_TOKEN` и `API_SERVER_PORT` в `.env`, а не в `-e`. |
| **`--skip-build` fails after GUI rebuild** | После `build-gui.sh` пересборки, `hermes dashboard --skip-build` падает: "no web dist found at .../resources/app.asar/dist". **Fix:** `npm run build -w web` сначала, или убрать `--skip-build` (dashboard сам соберёт web dist, ~30s). |
| **Dashboard B без `--insecure` → 401 на REST** | `/api/sessions` возвращает `{"detail":"Unauthorized"}` даже с правильным `X-Hermes-Session-Token`. `--insecure` обязателен для remote desktop token auth. Также нужно `HERMES_DASHBOARD_SESSION_TOKEN=*** env var. |
| **GUI открывается в local mode вместо Docker** | `connection.json` стоит `{"mode":"local"}` — GUI spawn'ит свой dashboard+gateway. **ДО запуска GUI** переключить в remote: `echo '{"mode":"remote","remote":{"url":"http://127.0.0.1:9121","token":{"value":"sk-docker-b"},"authMode":"token"},"profiles":{}}' > ~/.config/Hermes/connection.json`. См. `references/gui-docker-testing-workflow.md`. |
| **`--skip-build` fails after GUI rebuild** | После `build-gui.sh` web dist path меняется → `--skip-build` не находит `app.asar/dist`. Fix: убрать `--skip-build` или заранее `npm run build -w web`. |
| **Dashboard B `--tui` and `--insecure` flags** | `--tui` включает `/api/ws` WebSocket для чата. `--insecure` включает token auth для REST API из external clients. Без `--tui` — GUI не может отправлять сообщения. Без `--insecure` — `/api/sessions` → 401. |
| **Извлекать токен ПОЛНОСТЬЮ, не обрезая** | При извлечении `__HERMES_SESSION_TOKEN__` из HTML показывать полное значение, не `chvbgr...IC-s`. Обрезанный токен нельзя вставить в connection.json. См. `references/dashboard-token-extraction.md`. |

## Минимальный docker-compose.yml (host-сеть, без volume, ключи из .env)

```yaml
services:
  hermes:
    build: ./hermes-agent
    image: hermes-agent
    container_name: hermes-test
    restart: unless-stopped
    network_mode: host
    # Образ自带 чистый конфиг — volume только для персистентности
    # volumes:
    #   - /home/user/.hermes-docker:/opt/data
    environment:
      - HERMES_UID=${HERMES_UID:-1000}
      - HERMES_GID=${HERMES_GID:-1000}
      - API_SERVER_HOST=0.0.0.0
      - API_SERVER_PORT=${API_SERVER_PORT:-18648}
      - API_SERVER_KEY          # из .env (сгенерировать: openssl rand -hex 32)
      - GATEWAY_ALLOW_ALL_USERS=true
      - HERMES_DISABLE_MESSAGING=1
      # LLM-ключи — передаются из .env
      - OPENROUTER_API_KEY
      - DEEPSEEK_API_KEY
      - OPENAI_API_KEY
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:18648/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 120s
    command:
      - gateway
      - run
```

**Почему именно так:**
- `network_mode: host` — для доступа к localhost:8092 (llama.cpp) и другим host-сервисам
- Без volume — дефолтный конфиг образа чище (нет Telegram, сломанных путей)
- `18648` — свободный порт на хосте (8643 занят основным Hermes)
- `API_SERVER_KEY` — настоящий ключ (`openssl rand -hex 32`), не плейсхолдер. Hermes отвергает `***`
- Dashboard не в compose — запускать отдельным `docker run` с `--volumes-from` чтобы избежать конфликта s6-log
- `18648` — свободный порт на хосте (8643 занят основным Hermes)
- `API_SERVER_KEY` — ОБЯЗАТЕЛЬНО настоящий ключ, не плейсхолдер. Hermes отвергает `***`
| `docker-entrypoint.sh` permission | `chmod +x docker-entrypoint.sh` перед `docker compose up` |
| **`$HOME` override breaks bash deploy scripts** | Hermes redirects `$HOME` to `~/.hermes/home/`. Scripts like `start.sh` that use `$HOME/.hermes-docker` get wrong paths. **Fix:** `REAL_HOME=$(getent passwd "$(id -u)" | cut -d: -f6)` or use a distinctly-named env var like `HERMES_DOCKER_HOME`. See `hermes-scripting-patterns` skill for full pattern. |
| **Docker volume UID mismatch** | Container with `HERMES_UID=10000` creates files owned by UID 10000 on the host-mounted volume. Host user (UID 1000) gets "Отказано в доступе" on the data directory. **Fix:** (a) use `HERMES_UID=$(id -u)` to match host, (b) use `/tmp/` data dir for testing, (c) `sudo chown -R $(id -u):$(id -g) <dir>` to reclaim. |
| **QEMU SIGSEGV on npm during x64 cross-build** | QEMU cannot emulate Node.js V8 JIT — `npm install` inside `docker buildx --platform linux/amd64` crashes with `exit code: 139`. **Fix:** skip ALL npm steps in Dockerfile (`RUN true`), build image without web UI. See `references/x64-cross-compilation.md` → Pitfall 5B. |
| **Port conflict with local Hermes gateway** | Local Hermes gateway occupies :8643 (or :18648 if configured). Docker container on same port → "Port already in use" in gateway logs, API server fails to start. **Fix:** use `PORT_GW=18649 PORT_DASH=9122` (or any free ports). `start.sh` accepts these as env vars. |
| **s6-log lock when gateway+dashboard share volume** | Both containers mounting same `/opt/data` → `s6-log: fatal: unable to lock /opt/data/logs/gateways/default/lock: Resource busy`. **Fix:** (a) run dashboard with separate data dir (`-v /tmp/dash-data:/opt/data`), (b) or use `--volumes-from` for read-only access, (c) or accept the warning — dashboard still works despite log spam. **Preventive (start.sh):** `prepare_home()` now runs `rm -rf "$HERMES_HOME/logs/gateways"` before container start — eliminates stale locks from prior runs. |
| **x64 Docker image from ARM64 host** | QEMU SIGSEGV on npm/node inside buildx. Workaround: skip npm steps in Dockerfile (`RUN true # npm skipped`), accept missing web UI. Full x64 image requires native x64 build. node_modules ARE arch-independent JS — extract from ARM64 image for x64 GUI builds. |
| **exFAT USB drive: scripts break** | Heredocs corrupt, UTF-8 mangles, cp -a fails (ownership/symlinks). Fix: write to /tmp first, use printf (not heredoc), pure ASCII, cp -rL or tar. See `hermes-gui-launch` skill → "Writing scripts for exFAT". |
| **sudo breaks REAL_HOME detection** | `sudo ./launch.sh` → `REAL_HOME=/root` instead of `/home/user`. connection.json writes to wrong dir. Fix: add user to docker group (`usermod -aG docker`), run without sudo. |
| **`platform:` directive missing in compose** | ARM64 image on x64 host → "platform does not match". Fix: `platform: ${DOCKER_PLATFORM:-linux/amd64}` in docker-compose.yml. |
| **FAT/exFAT symlink failure on USB drives** | `cp -a` or `cp -r` fails with "cannot create symbolic link: Operation not permitted" when copying llama.cpp build to FAT32/exFAT USB drives. **Fix:** `cp -rL` (dereference symlinks). Size increases ~2.4x but binary works. See `references/offline-internal-deployment.md` → "Self-contained offline package". |
| **`provider: custom` (bare) in config.docker.yaml → "gateway needs setup"** | `config.docker.yaml` uses legacy `custom_providers` (list format). `model.provider` MUST be `custom:llama-local` (WITH suffix), not bare `custom`. Bare `custom` → gateway health returns OK but `/v1/chat/completions` → `"No LLM provider configured. Run hermes model"`. Dashboard shows `api_server: disconnected`. **Fix:** `sed -i 's/^  provider: custom$/  provider: custom:llama-local/' config.docker.yaml`. Same applies to `config.docker.litellm.yaml` → `provider: custom:litellm`. See `hermes-custom-providers` skill for the full format asymmetry explanation. |
