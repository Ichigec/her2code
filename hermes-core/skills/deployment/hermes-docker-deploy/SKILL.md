---
name: hermes-docker-deploy
description: "Локальный Docker деплой Hermes с mount-директорией. Офлайн, внутренняя сеть, без интернета."
category: deployment
triggers:
  - "docker deploy hermes"
  - "запусти hermes в докере с mount"
  - "офлайн hermes докер"
  - "внутренняя сеть hermes"
  - "hermes без интернета"
  - "docker run volume hermes"
  - "разверни hermes локально"
---

# Hermes Docker Deploy — локальное развёртывание с mount

> Для работы с Docker контейнером Hermes, где данные сохраняются на хосте через mount volume.

## Архитектура (3 слоя)

GUI **не подключается к gateway напрямую**. Три слоя:

```
Electron GUI ──WebSocket──► Dashboard (:9123) ──► Gateway (:18649)
  ↑                              ↑                    ↑
  читает connection.json         отдельный процесс    api_server platform
  mode: local | remote           даёт /api/ws +       даёт /health +
                                 /api/status          /v1/chat/completions
```

**⚠️ Порт :9123 — BY DESIGN, не "исправляйте" на :9122!** Основной Hermes
автоматически перезапускает свой dashboard на :9122. Portable использует :9123,
чтобы жить параллельно без конфликтов. Та же логика для gateway: :18649 вместо
:18648 (основной Hermes).

- **Gateway** (`api_server`): REST API — `/health`, `/v1/chat/completions`. НЕ имеет `/api/ws` или `/api/status`.
- **Dashboard**: веб-сервер — `/api/status`, `/api/ws` (WebSocket для чата), `/api/sessions`. GUI подключается именно сюда.
- **GUI** (Electron): в `mode: "local"` сам spawn'ит dashboard+gateway; в `mode: "remote"` подключается к уже запущенному dashboard.

```
Хост                                    Docker контейнер
┌─────────────────┐                    ┌──────────────────────┐
│  ~/.hermes-docker/  ──volume mount──►  /opt/data            │
│  ├── config.yaml  │                  │  ├── config.yaml     │
│  ├── .env         │                  │  ├── .env            │
│  ├── state.db     │                  │  ├── state.db        │
│  ├── logs/        │                  │  ├── logs/           │
│  └── sessions/    │                  │  └── sessions/       │
└─────────────────┘                    └──────────────────────┘
```

## Минимальный запуск (одной командой)

```bash
docker run -d --name hermes-gateway --restart unless-stopped --network host \
  -v ~/.hermes-docker:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  -e API_SERVER_ENABLED=true \
  -e API_SERVER_PORT=18649 \
  -e HERMES_DISABLE_MESSAGING=1 \
  -e GATEWAY_ALLOW_ALL_USERS=true \
  hermes-agent gateway run
```

**Что делает:**
- `-v ~/.hermes-docker:/opt/data` — монтирует постоянную директорию
- `HERMES_UID=$(id -u)` — контейнер работает под текущим пользователем (иначе UID 10000 заблокирует host)
- `API_SERVER_ENABLED=true` — обязательно, иначе gateway не поднимет API server
- `API_SERVER_PORT=18649` — порт API (параллельно с основным Hermes на 8643)
- `HERMES_DISABLE_MESSAGING=1` — отключает Telegram и другие платформы
- `--network host` — контейнер использует сеть хоста (доступ к localhost)

**⚠️ PITFALL: `.env` переопределяет `-e API_SERVER_PORT`!** Если в `~/.hermes-docker/.env` уже есть `API_SERVER_PORT=8643`, то `-e API_SERVER_PORT=18649` из `docker run` будет проигнорирован — `.env` загружается python-dotenv ПОСЛЕ env vars. **Fix:** отредактировать `.env` напрямую (`sed -i 's/API_SERVER_PORT=8643/API_SERVER_PORT=18649/' ~/.hermes-docker/.env`) или использовать отдельный HERMES_HOME без `.env`. См. `api_server.py:706`: `raw_port = extra.get("port")` — extra (из config/.env) имеет приоритет над `os.getenv()`.

## Что нужно для запуска контейнера

### Обязательно

| Компонент | Команда | Пояснение |
|-----------|---------|-----------|
| **Docker** | `docker --version` | Любая современная версия (проверено 24+) |
| **Docker образ** | `docker images hermes-agent` | Собрать: `docker build -t hermes-agent /path/to/hermes-agent` |
| **Директория данных** | `mkdir -p ~/.hermes-docker` | Будет смонтирована в `/opt/data` |
| **config.yaml** | `cp template ~/.hermes-docker/` | Конфигурация Hermes (см. ниже) |
| **.env** | `openssl rand -hex 32` | API_SERVER_KEY (не ***, не плейсхолдер) |

### Опционально, но желательно

| Компонент | Команда | Пояснение |
|-----------|---------|-----------|
| **LLM API ключ** | `echo 'DEEPSEEK_API_KEY=...' >> .env` | Для облачных моделей |
| **tui_gateway** | см. ниже | Для WebSocket dashboard |
| **systemd unit** | `hermes gateway service install` | Автозапуск при загрузке |

## Simplified portable package (v1 pattern)

> See the **V1 Simplified Package Pattern** section below for the full description.
> The monolithic `start.sh` is deprecated for new deployments — use 3 small scripts instead.

## ⚠️ Monolithic start.sh failure mode (root cause of "ничего не происходит")

When `start.sh` is 760 lines with 10 modes (compose, full, minimal, gui, build,
stop, litellm, status, logs, help), the failure mode is silent:

1. User runs `./start.sh compose` → it calls `prepare_home()` internally
2. But `prepare_home()` references `$HERMES_HOME` which can resolve to
   `~/.hermes` (main Hermes) instead of `~/.hermes-portable` if env vars
   aren't properly exported
3. Gateway mounts the WRONG volume, reads main Hermes `.env` with
   `API_SERVER_PORT=8643`, health check on :18649 fails
4. Dashboard waits for `gateway: service_healthy` forever → nothing happens
5. User sees no error — just silence

**Diagnostic:** `docker inspect hermes-gateway --format '{{range .Mounts}}{{.Source}}{{println}}{{end}}'`
→ if `~/.hermes` instead of `~/.hermes-portable`, the volume is wrong.

**Fix:** Use the v1 simplified package (separate scripts), or ensure `prepare_home()`
exports `HERMES_HOME` BEFORE calling `docker compose up`. **Also see the
HERMES_HOME inheritance pitfall below** — even a correct script can fail when
launched from within a Hermes Agent session.

## Для работы с GUI (Dashboard + WebSocket)

Если нужен не только gateway, но и графический интерфейс:

```bash
# 1. Gateway (обязательно сначала)
docker run -d --name hermes-gateway --network host \
  -v ~/.hermes-portable:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  -e API_SERVER_ENABLED=true \
  -e API_SERVER_PORT=18649 \
  -e HERMES_DISABLE_MESSAGING=1 \
  hermes-agent gateway run

# 2. Dashboard — ⚠️ SEPARATE volume!
docker run -d --name hermes-dashboard --network host \
  -v ~/.hermes-portable-dash:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  -e HERMES_DASHBOARD_SESSION_TOKEN=sk-docker-b \
  -e PYTHONPATH=/opt/data \
  -e GATEWAY_HEALTH_URL=http://127.0.0.1:18649/health \
  hermes-agent dashboard --host 127.0.0.1 --port 9123 \
    --insecure --tui --no-open --skip-build
```

**⚠️ tui_gateway:** Если WebSocket не работает (95% зависание GUI), скопировать модуль:
```bash
tar -C ~/.hermes/hermes-agent -c tui_gateway/ | \
  docker exec -i hermes-dashboard tar -C /opt/data -x
```

### Токен dashboard

Извлечь из HTML:
```bash
curl -s http://127.0.0.1:9123/ | grep -oP '__HERMES_SESSION_TOKEN__=sk-[^"]*' | head -1
```

Или задать свой при запуске: `-e HERMES_DASHBOARD_SESSION_TOKEN=sk-docker-b`

## V1 Simplified Package Pattern (2026-07-08)

The original monolithic `start.sh` (760 lines, 36KB, 10+ modes) is TOO COMPLEX for portable
deployments. It embeds prepare_home(), docker run, docker compose, GUI launch, status, stop,
build, litellm, superqwen, 3models — all in one file. Bugs hide in the complexity, and the
silent failure mode ("ничего не происходит") is nearly impossible to debug.

**The v1 pattern splits into 3 small scripts (~150 lines each):**

```
hermes_portable_v1/              ~1.9 GB (self-contained)
├── start-backend.sh             ← prepare_home() + docker compose up + health wait
├── launch.sh                    ← connection.json + GUI binary launch
├── stop.sh                      ← docker rm + GUI kill
├── docker/
│   ├── docker-compose.yml       ← 2 services (gateway + dashboard)
│   └── hermes-agent-arm64.tar.gz ← Docker image bundled (1.6 GB)
├── config/
│   └── config.docker.yaml       ← Provider/model config
└── gui/                         ← Pre-built Electron binary (ARM64, 345 MB)
    └── Hermes
```

**Why this works better:**
1. Each script does ONE thing (SRP). Bugs are isolated.
2. `start-backend.sh` starts with `unset HERMES_HOME DASH_HOME` — prevents env var inheritance from parent Hermes (see HERMES_HOME pitfall below).
3. `start-backend.sh` auto-loads the Docker image from tarball on first run (`docker load --input docker/hermes-agent-arm64.tar.gz`).
4. Creates BOTH .env files: gateway with `API_SERVER_*`, dashboard WITHOUT.
5. `launch.sh` generates connection.json from scratch every time — no stale configs.
6. No "mode" selection — backend and GUI are independent.
7. `HERMES_UID=$(id -u)` is baked in — no UID mismatch.
8. **Nothing is downloaded** — image, GUI binary, configs all bundled.

**Dashboard cold start:** s6-overlay init takes 2-3 minutes on ARM64. Wait loop
is 60 iterations × 3 sec = 180 sec. Do NOT shorten this — the dashboard WILL
time out on first boot.

**Usage:**
```bash
./start-backend.sh    # First time: loads image, creates .env, starts containers (~3 min)
./launch.sh           # Opens Electron GUI window
./stop.sh             # Stops everything
# Subsequent: ./start-backend.sh && ./launch.sh
```

**Templates**: `templates/start-backend.sh` and `templates/launch.sh` — copy-paste-ready.

## Подключение GUI к Docker backend

**⚠️ For launching/fixing the GUI itself, see the `hermes-gui-launch` skill** —
it covers connection.json troubleshooting, stale process/scope cleanup, boot
failure diagnosis, and a full recovery script (`scripts/gui-recover.sh`).

Key points (full details in `hermes-gui-launch`):
- `url` MUST be the **dashboard port** (:9123), NOT the gateway port (:18649).
  Gateway has no `/api/status` endpoint → boot fails with `404`.
- `token.value` MUST be the **DASH_TOKEN** (`sk-docker-b`), NOT the gateway's
  `API_SERVER_KEY`. Wrong token → `401: Unauthorized` on every API call.
- **ARM64 (Jetson):** launch with `--disable-gpu --disable-software-rasterizer --no-sandbox`
  or Electron crashes with `FATAL: GPU process isn't usable. Goodbye` (error_code=1002).

В `~/.config/Hermes/connection.json`:
```json
{
  "mode": "remote",
  "remote": {
    "url": "http://127.0.0.1:9123",
    "token": {"value": "sk-docker-b"},
    "authMode": "token"
  },
  "profiles": {}
}
```

**ВАЖНО:** 
- Не плоская структура: `{"mode":"remote","remote":{...}}`, не `{"mode":"remote","url":...}`
- Токен — объект: `"token": {"value": "***"}`, не строка
- Перезапустить GUI после изменения

## Работа без интернета

### Когда можно без интернета:

1. **Docker образ уже загружен** — `docker save` / `docker load`
2. **Локальная LLM модель** — GGUF файл через llama.cpp
3. **Все сервисы локальны** — Neo4j, LiteLLM на локальных моделях

### Когда интернет нужен:

1. **Первый docker pull** — без него нет образа
2. **Облачные LLM** — DeepSeek, OpenAI, OpenRouter
3. **Skills Hub** — установка скиллов
4. **pip/npm install** — установка зависимостей

## Предзагрузка образов для офлайна:

```bash
# На машине с интернетом:
docker pull hermes-agent:latest
docker pull neo4j:5-community
docker save hermes-agent:latest | gzip > hermes-agent.tar.gz

# На офлайн-машине:
docker load < hermes-agent.tar.gz
```

## Полный офлайн-пакет (portable deployment)

Для переноса на машину без интернета нужно 3 компонента:

| Компонент | Размер | Как получить |
|-----------|--------|-------------|
| Docker образ | ~1.6G (compressed) | `docker save hermes-agent:latest \| gzip > docker/hermes-agent-arm64.tar.gz` |
| Pre-built GUI | ~345M | `cp -a ~/.hermes/hermes-agent/apps/desktop/release/linux-<arch>-unpacked gui/` |
| Scripts + configs | ~12M | `rsync -a ~/dev/hermes_portable/ target/` |

### Portable v1 — полностью автономный пакет

**Локация:** `/media/pavel/One Touch/hermes_portable_v1/` (~1.9 GB)

```
hermes_portable_v1/
├── start-backend.sh       Запуск Docker (compose V1/V2 auto-detect, autoload tarball)
├── launch.sh              Запуск GUI (ARM64 GPU flags, connection.json auto-write)
├── stop.sh                Остановка
├── docker/
│   ├── docker-compose.yml
│   └── hermes-agent-arm64.tar.gz   ← Образ в комплекте (1.6G)
├── config/
│   └── config.docker.yaml
└── gui/                   ← Electron binary (ARM64, 345M)
    └── Hermes
```

**Ничего не скачивается.** Единственное требование — установленный Docker.

`start-backend.sh` автоматически:
1. Загружает образ из tarball при первом запуске (`docker load --input`)
2. Определяет compose V1/V2 (`docker compose` vs `docker-compose`)
3. Создаёт `~/.hermes-portable/` и `~/.hermes-portable-dash/`
4. Форсит `HERMES_HOME` (не наследует от родителя — `unset` в начале)
5. Генерирует API ключ
6. Ждёт gateway (до 2 мин) и dashboard (до 3 мин)

**⚠️ При первом запуске ждать 5+ минут** — s6-overlay chown -R на 4.65GB ARM64
образе занимает продолжительное время (см. раздел про chown выше).

**На новой машине нужны только:** Docker (из deb/rpm), llama.cpp (собранный), GGUF модель.

## Работа на удалённом сервере (внутренняя сеть)

```bash
# На сервере (без GUI, без интернета):
docker run -d --name hermes-gateway --network host \
  -v ~/.hermes-docker:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  -e API_SERVER_ENABLED=true \
  -e API_SERVER_PORT=18649 \
  -e HERMES_DISABLE_MESSAGING=1 \
  hermes-agent gateway run

# Dashboard на сервере:
docker run -d --name hermes-dashboard --network host \
  -v ~/.hermes-dash-data:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  -e PYTHONPATH=/opt/data \
  -e GATEWAY_HEALTH_URL=http://127.0.0.1:18649/health \
  hermes-agent dashboard --host 0.0.0.0 --port 9123 \
    --insecure --tui --no-open --skip-build

# На клиенте (ноутбук с GUI):
# connection.json:
# { "mode": "remote",
#   "remote": {
#     "url": "http://<СЕРВЕР_IP>:9123",
#     "token": {"value": "sk-docker-b"},
#     "authMode": "token"
#   }, "profiles": {} }
```

**Проверка с клиента:**
```bash
curl http://<СЕРВЕР_IP>:9123/api/status  # Должен ответить 200
```

## Конфигурация для локальной модели (без интернета)

`~/.hermes-docker/config.yaml`:
```yaml
model:
  provider: custom:llama-local      # ⚠️ MUST include provider name suffix!
  default: llama-local
  context_length: 65536

custom_providers:
  - name: llama-local
    base_url: http://localhost:8092/v1   # ⚠️ :8092, not :8090
    api_key: sk-no-key-required
    models:                              # ⚠️ MUST be a DICT, not a list
      llama-local: {}
```

**⚠️ CRITICAL — `provider: custom` (bare, without name) causes "gateway needs setup"!**
Legacy `custom_providers` (list format) requires `provider: custom:<name>`. Bare `custom` →
Hermes returns `"No LLM provider configured. Run hermes model to select a provider"` on every
`/v1/chat/completions` call. See `hermes-custom-providers` skill → Pitfalls for the full root cause.

Запуск llama.cpp:
```bash
llama-server --model ~/models/deepseek.gguf --port 8092 --host 0.0.0.0 --gpu-layers 99
```

## Скрипты автоматизации

```bash
# Минимальный запуск (одна команда):
~/dev/hermes_portable/scripts/deploy-minimal.sh --port 18649

# Полный стек с локальной моделью:
~/dev/hermes_portable/scripts/deploy-full.sh --model ~/models/deepseek.gguf

# Portable compose (рекомендуется — через start.sh):
cd ~/dev/hermes_portable && ./start.sh compose

# ВНИМАНИЕ: никогда не запускай docker compose вручную!
# docker compose -f docker/docker-compose.yml up -d  ← НЕ ДЕЛАЙ ТАК
# start.sh compose запускает prepare_home() который создаёт .env
# с правильными портами. Без него volume монтирует ~/.hermes вместо ~/.hermes-portable.
```

## Проверка что всё работает

```bash
# Gateway health:
curl http://127.0.0.1:18649/health

# Dashboard status:
curl http://127.0.0.1:9123/api/status

# Чат через API:
curl -X POST http://127.0.0.1:18649/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(grep API_SERVER_KEY ~/.hermes-portable/.env | cut -d= -f2)" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"привет"}],"max_tokens":100}'
```

## ⚠️ Shared volume pitfalls (CRITICAL — TWO root causes)

When gateway and dashboard containers **share the same `/opt/data` volume**
(common when both mount `~/.hermes-docker:/opt/data`), TWO distinct failure
modes occur. Both require separate volumes as the fix.

### Root cause 1: s6-log lock crash-loop

The gateway enters a crash-loop on restart:

```
s6-log: fatal: unable to lock /opt/data/logs/gateways/default/lock: Resource busy
```

s6 catches the error and sends the process to `sleep infinity` — the gateway
container shows as `Up` but **never serves requests**. `curl :PORT/health` hangs.

**Root cause:** Both containers try to lock the same `logs/gateways/default/lock`
file on the shared volume.

**Partial fix:** `rm -rf ~/.hermes-docker/logs/gateways/` before each start.

### Root cause 2: `.env` bleed-through → api_server port conflict

Even after fixing the s6-log lock, the **dashboard** reads the gateway's `.env`
file (which lives in the shared volume) and finds `API_SERVER_ENABLED=true` +
`API_SERVER_PORT=18649`. The dashboard then tries to start its **own** api_server
on the same port as the gateway:

```
ERROR gateway.platforms.api_server: [Api_Server] Port 18649 already in use.
```

This loops forever in dashboard logs. The dashboard's `/api/status` responds
(bare web server), but it never connects to the gateway properly.

**Root cause:** Dashboard container reads `/opt/data/.env` (shared volume) which
contains gateway-specific `API_SERVER_*` settings.

**Fix:** Dashboard must have its **own** `.env` WITHOUT any `API_SERVER_*` vars.

### Fix: separate volumes (resolves BOTH root causes)

```bash
# Gateway volume — contains .env with API_SERVER_KEY, API_SERVER_PORT, etc.
docker run -d --name hermes-gateway ... \
  -v ~/.hermes-portable:/opt/data ...

# Dashboard volume — separate! .env here has NO api_server settings
docker run -d --name hermes-dashboard ... \
  -v ~/.hermes-portable-dash:/opt/data ...
```

**Dashboard `.env`** must contain ONLY dashboard-specific vars:
```bash
# ~/.hermes-portable-dash/.env
# ⚠️ NO API_SERVER_ENABLED, NO API_SERVER_PORT, NO API_SERVER_KEY!
HERMES_DASHBOARD_SESSION_TOKEN=sk-docker-b
```

If `prepare_home()` in your start script generates both `.env` files, make sure
the dashboard copy excludes `API_SERVER_*` keys entirely.

## ⚠️ HERMES_UID pitfall (CRITICAL)

The Docker image defaults to `HERMES_UID=10000`, which means all files in the
mounted volume are owned by UID 10000. The host user (typically UID 1000) **cannot
read or edit** config.yaml, .env, state.db, or logs without sudo.

**Symptom:**
```bash
$ stat ~/.hermes-docker/config.yaml
Uid: (10000/ UNKNOWN)  Gid: (10000/ UNKNOWN)
$ cat ~/.hermes-docker/config.yaml
cat: ...: Permission denied
```

**Fix:** Always pass `HERMES_UID` and `HERMES_GID` matching the host user:
```bash
docker run -d --name hermes-gateway \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  ...
```

The Docker image's `stage2-hook.sh` runs `usermod -u $HERMES_UID hermes` at
startup, so files created in the volume will be owned by the host user. If the
volume was previously created with UID 10000, you must either `chown -R` it or
delete it and let `prepare_home()` recreate it.

## ⚠️ API_SERVER_KEY propagation

The `API_SERVER_KEY` must be available to the gateway for authenticating
`/v1/chat/completions` requests. It can be set via:

1. **`.env` in the volume** (preferred for persistence):
   ```bash
   echo "API_SERVER_KEY=$(openssl rand -hex 32)" >> ~/.hermes-docker/.env
   ```

2. **`-e` flag in `docker run`** (for programmatic injection):
   ```bash
   # Read from .env on host, pass to container
   API_KEY=$(grep '^API_SERVER_KEY=' ~/.hermes-docker/.env | cut -d= -f2)
   docker run -e "API_SERVER_KEY=$API_KEY" ...
   ```

**Pitfall:** If neither `.env` nor `-e` provides the key, the gateway generates
a random one at startup — but you won't know what it is. You'd have to extract
it from inside the container:
```bash
docker exec hermes-gateway grep API_SERVER_KEY /opt/data/.env
```

**Test auth works:**
```bash
# Extract key and test chat
python3 -c "
import urllib.request, json
key = open('/dev/stdin').read().strip()  # pipe key in
req = urllib.request.Request(
    'http://127.0.0.1:18649/v1/chat/completions',
    json.dumps({'model':'qwen3.6-35b-heretic','messages':[{'role':'user','content':'Say OK'}],'max_tokens':20}).encode(),
    {'Content-Type':'application/json','Authorization':f'Bearer {key}'})
print(urllib.request.urlopen(req, timeout=120).read().decode()[:200])
" <<< "$API_KEY"
```

## LiteLLM Integration (multi-model routing)

When you need multiple models routed through a single proxy (e.g. for
Hermes + OpenCode+ sharing the same backend), add LiteLLM between
gateway and llama-server:

```
Hermes Gateway (:18649) → LiteLLM (:4000) → llama-server (:8092)
OpenCode+ (:4000 client) ─┘
```

### ARM64 image pitfall

On ARM64 (Jetson/DGX Spark), use `main-stable` tag — NOT versioned tags:
```bash
# ✅ arm64-native
docker pull ghcr.io/berriai/litellm-database:main-stable

# ❌ amd64-only → QEMU emulation → prisma-migrate SIGSEGV
docker pull ghcr.io/berriai/litellm-database:v1.83.7-stable
```

Verify: `docker image inspect <tag> --format '{{.Architecture}}'` must show `arm64`.

### LiteLLM config

`~/.hermes-docker/litellm/config.yaml`:
```yaml
model_list:
  - model_name: heretic        # what clients request
    litellm_params:
      model: openai/heretic
      api_base: http://host.docker.internal:8092/v1   # ← :8092, not :8090
      api_key: sk-no-auth-required
```

**⚠️ `LLAMA_CPP_API_BASE` must point to :8092** (not the default :8090).
If `.env` doesn't override it, LiteLLM returns 500 Connection error.

**⚠️ `docker restart litellm` does NOT re-read `.env`!** Env vars are baked
at container creation. Use `docker compose up -d --force-recreate litellm` to
apply env changes. Verify: `docker exec litellm printenv VAR_NAME`.

### Docker networking

LiteLLM in Docker needs `host.docker.internal` to reach llama-server on host:
```yaml
# docker-compose.yml or docker run:
extra_hosts:
  - "host.docker.internal:host-gateway"
# OR use --network host (simpler, no bridge needed)
```

### `--network host` bypasses UFW entirely (CRITICAL for multi-model)

When the gateway container uses `--network host`, it shares the host's network
namespace and can reach ANY localhost port directly — including ports that UFW
blocks for Docker bridge-network containers. This is critical for multi-model
deployments with multiple llama-server instances on :8101/:8102/:8103:

```
Gateway (--network host) ──→ :8101 (nex)     ✅ direct
                           ──→ :8102 (qwen)    ✅ direct
                           ──→ :8103 (world)   ✅ direct

LiteLLM (bridge network)  ──→ :8101           ❌ UFW TIMEOUT
                           ──→ :8102           ❌ UFW TIMEOUT
                           ──→ :8103           ❌ UFW TIMEOUT
```

**Decision:** For multi-model direct deployments, prefer `--network host`
(no UFW injection needed). For LiteLLM proxy mode, either use `--network host`
on LiteLLM too, or inject UFW rules (see `local-model-serving` skill →
Docker→Host connectivity).

## 3-Model APEX deployment (direct, no LiteLLM)

For 3 simultaneous APEX models (Nex + Qwen + AgentWorld), configure 3 separate
`custom_providers` — one per model/port. No LiteLLM needed when gateway uses
`--network host`:

```yaml
# config.docker.3models.yaml
model:
  provider: custom:qwen          # default provider
  default: qwen3.6-35b
  context_length: 262144

custom_providers:
  - name: nex
    base_url: http://localhost:8101/v1
    api_mode: chat_completions
    api_key: sk-no-auth-required
    models:
      nex-n2-mini:
        context_length: 262144

  - name: qwen
    base_url: http://localhost:8102/v1
    api_mode: chat_completions
    api_key: sk-no-auth-required
    models:
      qwen3.6-35b:
        context_length: 262144

  - name: world
    base_url: http://localhost:8103/v1
    api_mode: chat_completions
    api_key: sk-no-auth-required
    models:
      agentworld:
        context_length: 262144
```

Full template: `templates/config.3models.yaml`. The `start.sh full --3models`
flag in `~/dev/hermes_portable` switches to this config automatically.

## Single-model APEX deployment (SuperQwen only)

For a single-model deployment (SuperQwen on :8103, frees ~55G GPU RAM vs 3-model),
use `start.sh full --superqwen` or the offline `deploy-offline-superqwen.sh`:

```yaml
# config.docker.superqwen.yaml
model:
  provider: custom:world
  default: agentworld
  context_length: 262144

custom_providers:
  - name: world
    base_url: http://localhost:8103/v1
    api_mode: chat_completions
    api_key: sk-no-auth-required
    models:
      agentworld:
        context_length: 262144
```

The `start.sh full --superqwen` flag switches to this config automatically.
Full template: `~/dev/hermes_portable/config/config.docker.superqwen.yaml`.

## Single-model deployment (SuperQwen APEX only)

For running just one model (saves ~55G GPU RAM vs 3-model, faster cold start),
use `--superqwen`:

```bash
cd ~/dev/hermes_portable
REAL_HOME=$HOME bash ./start.sh full --superqwen
```

This launches only SuperQwen (agentworld) on :8103, with a single-provider
config. Config template: `templates/config.superqwen.yaml`.

The config is identical to the 3-model version but with a single
`custom_providers` entry pointing to :8103:

```yaml
model:
  provider: custom:world
  default: agentworld
  context_length: 262144

custom_providers:
  - name: world
    base_url: http://localhost:8103/v1
    api_mode: chat_completions
    api_key: sk-no-key-required
    models:
      agentworld:
        context_length: 262144
```

**To switch between 1-model and 3-model:** stop containers, re-run start.sh
with the desired flag. The config is overwritten each time.

**Verify all 3 models via gateway:**
```bash
API_KEY=$(grep '^API_SERVER_KEY=' ~/.hermes-portable/.env | cut -d= -f2)
for m in nex-n2-mini qwen3.6-35b agentworld; do
  curl -sf http://127.0.0.1:18649/v1/chat/completions \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK\"}],\"max_tokens\":10}" \
    | python3 -c "import sys,json; print(f'  ✅ $m:', json.load(sys.stdin)['choices'][0]['message']['content'][:30])"
done
```

## ⚠️ Host Hermes port conflicts (parallel deployment)

When running Docker Hermes alongside the host Hermes daemon, the host daemon
**auto-restarts its dashboard process** on :9122. If the Docker dashboard tries
to bind :9122, it enters a crash-loop:

```
ERROR: [Errno 98] error while attempting to bind on address ('127.0.0.1', 9122): address already in use
```

**Port allocation for parallel deployment:**

| Service | Main (host) | Portable (Docker) |
|---------|:-----------:|:-----------------:|
| Gateway | :18648 | :18649 |
| Dashboard | :9121, :9122 (auto-restart) | :9123 |

**Fix:** Use :9123 for Docker dashboard. Never :9122 — the host daemon will
re-grab it within seconds of being killed.

**⚠️ CRITICAL: Port offsets are BY DESIGN — do not "unify" them!** When auditing
a portable distribution, you will find `PORT_DASH=9123` in start.sh but possibly
`:9122` in docker-compose.yml defaults or `.env`. The temptation is to "fix" by
aligning everything to one value. **Do NOT align to :9122** — that port collides
with the host daemon's auto-restart. The canonical portable value is **:9123**.
Align ALL files (start.sh comments, start.sh defaults, docker/.env, .env.example,
docker-compose.yml healthcheck) to :9123. User correction (2026-07-08): "не надо
правильных — там специально такие, чтобы не конфликтовать с текущим hermes."
**Lesson: understand WHY values differ before "fixing" them — they may be
intentional design choices, not bugs.**

## ⚠️ `docker compose` vs `./start.sh compose` — volume mount root cause (CRITICAL)

**ВСЕГДА запускай через `./start.sh compose`** или v1 `start-backend.sh`, никогда — через `docker compose` напрямую.

When you manually run `docker compose -f docker/docker-compose.yml --env-file
docker/.env up -d`, the `HERMES_HOME` variable in `docker/.env` may resolve to
`~/.hermes` — the **main Hermes home directory** — because Docker daemon
expands `~` differently than the shell.

**Symptom:** Gateway starts but health check fails on :18649. Inside the
container, the API server is on :8643 (the main Hermes port) because it read
the main Hermes `.env` from the wrongly-mounted volume. Dashboard never starts
because it waits for `gateway: service_healthy` and the gateway is unhealthy.

**Diagnostic:** Check the actual volume mount inside the container:
```bash
docker inspect hermes-gateway --format '{{range .Mounts}}{{.Source}} → {{.Destination}}{{println}}{{end}}'
# If Source is ~/.hermes (not ~/.hermes-portable) → WRONG volume
docker exec hermes-gateway grep API_SERVER_PORT /opt/data/.env
# If port is 8643 → reading main Hermes .env, not portable
```

**Fix:** Always launch via `./start.sh compose`. The script runs `prepare_home()`
which: (1) creates `~/.hermes-portable/.env` with correct `API_SERVER_PORT=18649`,
(2) creates `~/.hermes-portable-dash/.env` WITHOUT api_server settings,
(3) sources gateway `.env` into the shell environment,
(4) exports all vars before calling `docker compose up`.
The manual `docker compose` approach skips all four steps.

**Never manually `docker compose up` for a portable deployment.**

## ⚠️ `docker compose --env-file` not supported on older Docker (CRITICAL)

Some Docker versions (e.g. Docker 24.x without compose v2 plugin, or Kali/RPi
Docker packages) do NOT support the `--env-file` flag for `docker compose`:

```
unknown flag: --env-file
Usage:  docker [OPTIONS] COMMAND [ARG...]
```

**Fix:** Do NOT use `--env-file`. Instead, `export` all variables in the
shell before calling `docker compose up -d`. Docker Compose v2 automatically
reads exported environment variables for `${VAR}` interpolation in the
compose file. A `.env` file next to the compose file also works.

```bash
# ✅ Correct — export then compose
export HERMES_HOME="$REAL_HOME/.hermes-portable"
export DASH_HOME="$REAL_HOME/.hermes-portable-dash"
export PORT_GW=18649 PORT_DASH=9123
export HERMES_IMAGE=hermes-agent
export HERMES_UID=$(id -u) HERMES_GID=$(id -g)
cd "$SCRIPT_DIR/docker"
docker compose up -d

# ❌ Wrong — --env-file not universally supported
docker compose --env-file /dev/null up -d
```

## ⚠️ HERMES_HOME inherited from parent Hermes process (CRITICAL)

When a deploy script runs **inside a Hermes Agent session**, the parent
process exports `HERMES_HOME=~/.hermes` (the main Hermes home). If the
deploy script uses `HERMES_HOME="${HERMES_HOME:-...}"`, the default never
fires because the variable is already set — and the container mounts the
**main Hermes volume** instead of the portable one.

**Symptom:** `Data: /home/user/.hermes` printed at startup instead of
`/home/user/.hermes-portable`. Gateway reads main Hermes `.env` with
`API_SERVER_PORT=8643` → health check on :18649 fails forever.

**Fix:** `unset HERMES_HOME DASH_HOME` at the top of the script, BEFORE
assigning them:

```bash
unset HERMES_HOME DASH_HOME || true
export HERMES_HOME="$REAL_HOME/.hermes-portable"
export DASH_HOME="$REAL_HOME/.hermes-portable-dash"
```

## ⚠️ s6-overlay first boot takes 5+ minutes on ARM64

The Docker image uses s6-overlay for process supervision. On ARM64
(Jetson/DGX Spark), the **first boot** (fresh volume, no cache) can take
**5 minutes or more** before the dashboard Python process starts. The
gateway health check passes in ~2 minutes, but dashboard waits for
gateway `service_healthy` condition, then does its own s6 init.

**Implication:** Deploy scripts must wait at least **5 minutes** for
dashboard, not 2-3. Use `for i in $(seq 1 100); do ... sleep 3; done`
(300 seconds) minimum. Subsequent restarts are faster (~60-90 seconds)
because the volume cache exists.

## ⚠️ read_file display redaction (NOT file corruption — CORRECTED 2026-07-10)

> **CORRECTION:** This section previously claimed `write_file`/`patch` "censor"
> token-like strings to `***` in the written file. This was **WRONG**. Code
> analysis proves `write_file`/`patch` do NOT apply redaction on write. Files
> on disk contain real content. The `***` appears only in `read_file` OUTPUT
> via `redact_sensitive_text(content, code_file=True)` at `file_tools.py:823`.
> The Hermes redaction layer (`agent/redact.py`) masks secrets in display/log
> output only — it never modifies file content on write.

**What actually happens:**
1. `write_file(path="config.sh", content="TOKEN=sk-docker-b")` → file on disk has `sk-docker-b`
2. `read_file("config.sh")` → output shows `TOKEN=***` (display redaction)
3. Agent sees `***`, wrongly concludes file is corrupted

**Note:** `write_file`/`patch` do NOT corrupt token strings — files on disk get real content.
The `***` appears only in `read_file` output. However, using `terminal` heredoc avoids the
display-redaction confusion entirely and is still recommended for exFAT (avoids LINE MERGE).

```bash
# Preferred for exFAT files (avoids line merge + no redaction confusion)
cat > "$FILE" << 'RAWEOF'
DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-docker-b}"
RAWEOF

# write_file also works (file on disk has real token) but read_file will show ***
# Use terminal('cat <file>') to verify actual content
```

**Diagnostic:** If a script fails with `invalid substitution` on a line
containing a token, check the raw bytes:
```bash
sed -n '21p' script.sh | od -c | head -3
```
If you see `* * *` instead of the variable name, this is **display redaction** by `read_file`, NOT file corruption. The file on disk has the real value.

### ⚠️ HERMES_HOME inheritance from parent Hermes daemon (DEEPEST root cause)

Even when using `start-backend.sh`, the script can fail with the SAME symptom
(wrong volume mount) if it's launched **from within a running Hermes Agent
session**. The parent Hermes daemon exports `HERMES_HOME=~/.hermes` into the
environment, and the child script inherits it:

```bash
# Inside Hermes Agent terminal:
$ echo $HERMES_HOME
/home/user/.hermes    ← this leaks into child scripts!

$ ./start-backend.sh
# HERMES_HOME="${HERMES_HOME:-...}" → inherits ~/.hermes → WRONG volume!
```

The `:-` default operator only fires when the variable is **empty**, not when
it's **set to the wrong value**. This is the most insidious failure mode: the
script LOOKS correct (`HERMES_HOME="${HERMES_HOME:-$REAL_HOME/.hermes-portable}"`)
but the `:-` fallback never triggers because `HERMES_HOME` is already set by
the parent.

**Fix — `unset` before setting:**
```bash
# At the TOP of start-backend.sh, before any HERMES_HOME usage:
unset HERMES_HOME DASH_HOME || true
export HERMES_HOME="$REAL_HOME/.hermes-portable"
export DASH_HOME="$REAL_HOME/.hermes-portable-dash"
```

**This is why v1 `start-backend.sh` starts with `unset HERMES_HOME DASH_HOME`.**
Without it, scripts launched from a Hermes terminal will always mount the wrong
volume. User correction (2026-07-08): the original `start-backend.sh` printed
`Data: /home/user/.hermes` instead of `/home/user/.hermes-portable`.

**Diagnostic — check what the script actually sees:**
```bash
# Add this debug line to the top of any portable script:
echo "DEBUG: HERMES_HOME=$HERMES_HOME REAL_HOME=$REAL_HOME"
# If HERMES_HOME != $REAL_HOME/.hermes-portable → inherited from parent
```

## ⚠️ Dashboard volume config sync (CRITICAL — stale config = "Connection error")

When the gateway and dashboard containers use **separate volumes** (the recommended
fix for the s6-log lock problem above), each volume has its OWN `config.yaml`:
the gateway reads `~/.hermes-portable/config.yaml`, the dashboard reads
`~/.hermes-portable-dash/config.yaml`.

**Symptom:** Chat in GUI fails with "API call failed after 3 retries: Connection
error", but `curl http://127.0.0.1:18649/v1/chat/completions` (gateway directly)
works fine. The dashboard web UI loads (HTML serves), but model calls fail.

**Root cause:** The dashboard container's internal gateway reads its OWN volume's
`config.yaml`. If that config is stale (e.g., points to a dead port `:8092`, or
has old model names like `qwen3.6-35b-heretic` instead of `qwen3.6-35b`), the
dashboard's gateway tries to reach the wrong endpoint and fails after 3 retries.

**Diagnostic recipe (run in order):**
```bash
# 1. Check connection.json — what endpoint is the GUI targeting?
cat ~/.config/Hermes/connection.json

# 2. Test gateway directly (bypasses dashboard entirely):
API_KEY=$(grep '^API_SERVER_KEY=' ~/.hermes-portable/.env | cut -d= -f2)
curl -sf http://127.0.0.1:18649/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.6-35b","messages":[{"role":"user","content":"Say OK"}],"max_tokens":10}'

# 3. Check which config the dashboard is actually using:
docker exec hermes-dashboard cat /opt/data/config.yaml | grep -E 'model:|base_url:|provider:'

# 4. Compare with gateway's config:
docker exec hermes-gateway cat /opt/data/config.yaml | grep -E 'model:|base_url:|provider:'

# 5. Check dashboard logs for the exact endpoint it's trying:
docker logs hermes-dashboard --tail 20 2>&1 | grep -E 'Endpoint:|Error:'
```

**Fix:** Sync the dashboard volume's config with the gateway's:
```bash
cp ~/.hermes-portable/config.yaml ~/.hermes-portable-dash/config.yaml
docker restart hermes-dashboard
```

**`connection.json` endpoint choice:**
- `mode: "local"` → Electron spawns its OWN gateway using HOST `~/.hermes/config.yaml`.
  If the host config is stale (wrong model names, dead ports), chat fails. Only
  use this mode when there's no Docker/remote backend running.
- `mode: "remote"` → `remote.url` can point to EITHER the dashboard port (:9123)
  or the gateway port (:18649). Pointing to the gateway directly works for REST
  API calls but may miss WebSocket features. Pointing to the dashboard requires
  the dashboard's volume config to be correct (see above).

## ⚠️ s6-overlay chown — 5+ минут на ARM64 (CRITICAL)

Каждый контейнер Hermes при старте выполняет `stage2-hook.sh` → `chown -R
hermes:hermes /opt/hermes/.venv /opt/hermes/ui-tui /opt/hermes/gateway
/opt/hermes/node_modules`. На ARM64 с образом 4.65GB это занимает **5+ минут**.

**Симптомы во время chown:**
- Контейнер показывает `Up X minutes (health: starting)` или `unhealthy`
- Логи застряли на `[stage2] Fixing ownership of build trees`
- Порты ещё не слушаются (`ss -tlnp | grep 9123` пусто)
- `docker stats` показывает активный Block I/O (400-600MB read)

**Это НЕ зависание — chown активно работает.** Проверить:
```bash
docker top hermes-gateway 2>&1 | grep chown
# Если процесс есть — просто ждите, он завершится
```

**Диагностика: не путать с реальным зависанием:**
```bash
# Прогрессирует ли chown? (Block I/O должен расти)
docker stats --no-stream hermes-gateway --format "{{.BlockIO}} {{.CPUPerc}}"
# Подождать 30 сек и повторить — I/O должен вырасти

# Если Block I/O не меняется 2+ минуты — реальное зависание (перезапустить)
```

**Таймауты для скриптов:** gateway health check нужен `start_period: 120s`
(минимум). Dashboard — `start_period: 300s` на первом запуске. В скриптах
wait-loop должен быть **не менее 5 минут** (150 итераций × 2 сек).

## ⚠️ `docker compose` V1 vs V2 — auto-detect (CRITICAL)

Не все машины имеют Docker Compose V2 plugin. Старые установки (Debian, Ubuntu
20.04) используют V1 standalone (`docker-compose` через дефис).

**Ошибка V1 при вызове V2 синтаксиса:**
```
unknown shorthand flag: 'd' in -d
```

Docker парсит `up -d` как флаг базовой команды `docker`, а не compose.

**Fix — auto-detect в скриптах:**
```bash
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)        # V2 plugin
elif command -v docker-compose &>/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)        # V1 standalone
else
    echo "ERROR: docker compose not found. Install:"
    echo "  sudo apt install docker-compose-plugin  # V2"
    echo "  sudo apt install docker-compose         # V1"
    exit 1
fi
"${COMPOSE_CMD[@]}" up -d
```

**Также:** флаг `--env-file` может отсутствовать в старых версиях. НЕ
использовать `docker compose --env-file /dev/null up -d` — просто экспортируйте
переменные в окружение перед вызовом compose.

## ⚠️ HERMES_HOME inheritance (CRITICAL при запуске из Hermes Agent)

Когда `start-backend.sh` запускается **изнутри Hermes Agent** (как терминальная
команда), родительский процесс Hermes уже экспортировал `HERMES_HOME` в
окружение. Скрипт наследует это значение (`~/.hermes` — основной Hermes home),
и контейнер монтирует **неправильный volume**.

**Симптом:**
```
Data: /home/user/.hermes       ← НЕПРАВИЛЬНО (должно быть .hermes-portable)
```

Gateway читает основной Hermes `.env` с `API_SERVER_PORT=8643`, health check
фейлится на `:18649`, dashboard никогда не запускается.

**Fix — force override в начале скрипта:**
```bash
unset HERMES_HOME DASH_HOME || true
REAL_HOME="${REAL_HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
export HERMES_HOME="$REAL_HOME/.hermes-portable"
export DASH_HOME="$REAL_HOME/.hermes-portable-dash"
```

Никогда не используйте `HERMES_HOME="${HERMES_HOME:-...}"` — fallback не
сработает, т.к. переменная уже установлена родителем.

## ⚠️ GUI hang + recovery (полный алгоритм восстановления)

GUI может зависнуть во время ответа (особенно с reasoning моделями) и не
запускаться после закрытия. Причины и fixes:

### 1. Electron сбрасывает connection.json при закрытии

При каждом закрытии GUI Electron пишет `{"mode":"local"}` в connection.json.
Следующий запуск пытается spawn'ить локальный backend вместо подключения к Docker.

**Fix — перезаписывать connection.json перед каждым запуском:**
```bash
REAL_HOME=$(getent passwd "$(id -u)" | cut -d: -f6)
cat > "$REAL_HOME/.config/Hermes/connection.json" << 'EOF'
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:9123",
    "token": {"value": "sk-docker-b"},
    "authMode": "token"
  },
  "profiles": {}
}
EOF
```

### 2. SingletonLock и stale systemd scopes

Electron оставляет lock-файлы и systemd scope units после падения. Без очистки
новый процесс не стартует (окно не появляется, процесс молча умирает).

**Fix — полная очистка перед запуском:**
```bash
# Singleton locks
rm -f ~/.config/Hermes/SingletonLock ~/.config/Hermes/SingletonCookie ~/.config/Hermes/SingletonSocket

# Stale systemd scopes (могут блокировать cgroups)
for s in $(systemctl --user list-units --all 'app-org.chromium.Chromium-*.scope' --no-legend 2>/dev/null | awk '{print $1}'); do
    systemctl --user stop "$s" 2>/dev/null
done

# Stale GUI processes
pgrep -f "linux-.*-unpacked/Hermes" | xargs kill 2>/dev/null
```

### 3. Полный launch-скрипт (надёжный)

```bash
#!/usr/bin/env bash
REAL_HOME=$(getent passwd "$(id -u)" | cut -d: -f6)
BIN="$REAL_HOME/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes"
PORT_DASH="${PORT_DASH:-9123}"
DASH_TOKEN="${HE...# 1. Check backend
curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1 || { echo "Backend not running"; exit 1; }

# 2. Kill old GUI
pkill -f "linux-.*-unpacked/Hermes" 2>/dev/null; sleep 2

# 3. Clean locks
rm -f "$REAL_HOME"/.config/Hermes/Singleton* 2>/dev/null
for s in $(systemctl --user list-units --all 'app-org.chromium.Chromium-*.scope' --no-legend 2>/dev/null | awk '{print $1}'); do
    systemctl --user stop "$s" 2>/dev/null
done

# 4. Write connection.json
mkdir -p "$REAL_HOME/.config/Hermes"
cat > "$REAL_HOME/.config/Hermes/connection.json" << JSONEOF
{"mode":"remote","remote":{"url":"http://localhost:${PORT_DASH}","token":{"value":"${DASH_TOKEN}"},"authMode":"token"},"profiles":{}}
JSONEOF

# 5. Launch with ARM64 GPU flags (MANDATORY)
exec "$BIN" --disable-gpu --disable-software-rasterizer --no-sandbox
```

## exFAT pitfalls (USB drive deployment)

When deploying scripts to an **exFAT-formatted USB drive** (common for
cross-platform transfer), two issues occur:

### 1. Bash heredocs break silently

`cat > file <<EOF ... EOF` produces corrupted files on exFAT — lines merge,
EOF markers get eaten, content after the heredoc is swallowed. Scripts pass
`bash -n` syntax check but fail at runtime.

**Fix:** Replace ALL heredocs with `printf`:
```bash
# WRONG (exFAT breaks this):
cat > "$DASH_HOME/.env" <<EOF
HERMES_DASHBOARD_SESSION_TOKEN=$DASH_TOKEN
EOF

# RIGHT:
printf 'HERMES_DASHBOARD_SESSION_TOKEN=%s\n' "$DASH_TOKEN" > "$DASH_HOME/.env"
```

### 2. Symlinks stripped during copy

`cp -a` or `cp -r` fails on symlinks ("Operation not supported"). Docker
builds and llama.cpp binaries have symlinks (libllama.so → libllama.so.0).

**Fix:** Use `cp -rL` (dereference) to copy file content instead of links:
```bash
cp -rL /home/user/dev/llama.cpp/build /target/llama.cpp/build
```

### 3. No executable permission retention

exFAT has no POSIX permissions. `chmod +x` is silently ignored — ALL files
appear executable. To ensure scripts run: `bash script.sh` instead of
`./script.sh`.

## Docker platform mismatch (arm64 image on amd64 host)

Running an ARM64 Docker image on an x64/amd64 host produces:
```
The requested image's platform (linux/arm64) does not match
the detected host platform (linux/amd64/v3) and no specific platform was requested
```

Container fails to start (exit immediately).

**Fix:** Add `platform:` to docker-compose.yml AND use arch-specific image tags:
```yaml
services:
  hermes:
    image: ${HERMES_IMAGE:-hermes-agent}
    platform: ${DOCKER_PLATFORM:-linux/amd64}  # ← CRITICAL
```

**Architecture auto-detection for deploy scripts:**
```bash
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64) export DOCKER_PLATFORM="linux/arm64"; TARBALL="hermes-agent-arm64.tar.gz" ;;
  x86_64|amd64)  export DOCKER_PLATFORM="linux/amd64"; TARBALL="hermes-agent-x64.tar.gz" ;;
esac
```

**Cross-compiling Docker images (QEMU limitation):** QEMU binfmt can run apt-get
and simple processes on x64 from ARM64, but **Node.js/npm SIGSEGV** inside QEMU
(`x86_64-binfmt-P: QEMU internal SIGSEGV`). Cannot cross-build Docker images
containing `npm install` or `npm run build`. Must build natively on the target
arch machine, or skip npm steps (gateway works, web UI doesn't).

## Полезные команды

```bash
# Логи контейнера:
docker logs hermes-gateway

# Остановка:
docker stop hermes-gateway hermes-dashboard

# Полное удаление (данные в ~/.hermes-docker сохранятся):
docker rm -f hermes-gateway hermes-dashboard

# Просмотр данных на хосте:
ls -la ~/.hermes-portable/state.db  # сессии
ls -la ~/.hermes-portable/logs/     # логи

# Проверить что chown завершён (ARM64):
docker top hermes-gateway 2>&1 | grep chown  # пусто = завершён

# Проверить volume mount:
docker inspect hermes-gateway --format '{{range .Mounts}}{{.Source}} → {{.Destination}}{{println}}{{end}}'
# Source должен быть ~/.hermes-portable, НЕ ~/.hermes
```

## Multi-architecture offline deployment

For deploying to machines without internet, package ALL architecture-specific
binaries + architecture-independent assets in one directory:

```
hermes_portable/
├── deploy-offline-superqwen.sh     ← auto-detects arch, loads correct Docker image
├── start.sh                        ← patched: portable path resolution + GPU flags
├── docker/
│   ├── hermes-agent-arm64.tar.gz   ← docker save | gzip (1.6G)
│   └── hermes-agent-x64.tar.gz     ← cross-built via buildx (810M, no web UI)
├── gui/
│   └── linux-arm64-unpacked/Hermes ← pre-built Electron (arch-specific)
├── llama.cpp/
│   ├── build/bin/llama-server      ← ARM64 native binary
│   └── x64/llama-server            ← x64 cross-compiled binary
├── models/
│   └── *.gguf                      ← arch-independent GGUF model
└── config/
    └── config.docker.*.yaml        ← arch-independent configs
```

**deploy-offline-superqwen.sh** auto-detects architecture and:
1. Loads the correct Docker image tar (arm64 or x64)
2. Finds the correct llama-server binary
3. Finds the correct GUI binary (if available for that arch)
4. Writes connection.json → dashboard port (not gateway!)
5. Launches GUI with `--disable-gpu --disable-software-rasterizer --no-sandbox` (ARM64)

**x64 limitation:** Cross-built x64 Docker image has NO web UI (QEMU can't
run npm). Gateway + API work, dashboard serves empty. Run `npm run build`
on the x64 target machine to generate web assets at runtime.

## Cross-architecture deployment (ARM64 ↔ x64)

**Problem:** Docker image built for ARM64 will NOT run on x64 host:
```
The requested image's platform (linux/arm64) does not match
the detected host platform (linux/amd64/v3)
```

**Fix:** Add `platform:` to docker-compose.yml:
```yaml
services:
  hermes:
    image: ${HERMES_IMAGE:-hermes-agent}
    platform: ${DOCKER_PLATFORM:-linux/amd64}
    ...
```

**Building x64 image from ARM64 host (QEMU cross-build):**
- QEMU cannot run Node.js/npm inside buildx → SIGSEGV on `npm install`
- Workaround: skip npm steps in Dockerfile (`RUN true # npm skipped`)
- The resulting image lacks node_modules and web UI assets
- Gateway + API still work; dashboard web UI will be blank
- For full x64 image: build natively on x64 machine (`docker build -t hermes-agent .`)

**Portable deployment on exFAT USB drives:**
- See `hermes-gui-launch` skill → "Writing scripts for exFAT / USB drives"
- Key: heredocs break, UTF-8 mangles, cp -a fails — use printf + ASCII + tar
- Write scripts to `/tmp` first, verify, then copy to USB

## Запуск второго бэкенда (parallel deployment)

Two patterns for running a second Hermes alongside the main one:

1. **Docker-based** (recommended for persistent parallel instance):
   Separate ports (:18649/:9122), separate volumes, shared LLM infra.
   See `references/parallel-docker-deployment.md` — full architecture, port map,
   volume layout, 8-point verification checklist, GUI switching commands.

2. **Host process** (for quick testing):
   Non-Docker local process with a different `HERMES_HOME`.
   See `references/multi-backend-testing.md` — separate HERMES_HOME, port fix
   in `.env`, dashboard launch, GUI remote mode, LLM verification on both.

## V2 Dual-Architecture Package (2026-07-09) — FINAL WORKING PATTERN

**STATUS: VERIFIED WORKING on x64 Kali (2026-07-09).** User confirmed GUI
launched successfully after fixing exFAT corruption in launch.sh.

Evolution of v1: pre-builds BOTH GUI binaries (ARM64 + x64) on the Jetson via
`electron-builder --dir --x64`. Target machine needs ZERO build tools — no
Node.js, no npm. Auto-arch detection in both `start-backend.sh` and `launch.sh`.

```
hermes_portable_v2/              3.0G total
├── start-backend.sh             # Auto-arch: loads correct Docker image
├── launch.sh                    # Auto-arch: selects gui-arm64/ or gui-x64/
├── chat.sh                      # CLI fallback (python3-based JSON parsing)
├── stop.sh
├── config/
│   └── config.docker.yaml
├── docker/
│   ├── hermes-agent-arm64.tar.gz   (1.6G — full image with web UI)
│   └── hermes-agent-x64.tar.gz     (810M — NO web UI, QEMU limitation)
├── gui-arm64/Hermes               (344M — pre-built ARM64 ELF)
└── gui-x64/Hermes                 (339M — pre-built x86-64 ELF)
```

**Usage on target machine (2 commands, no internet, no build tools):**
```bash
./start-backend.sh    # Auto-detects arch, loads Docker image, starts gateway+dashboard
./launch.sh           # Auto-selects GUI binary, writes connection.json, launches
```

**What V2 solved (vs V1):**
1. V1 only had ARM64 binary → x64 machines had to build (needs Node.js 22 + npm)
2. V2 ships BOTH binaries → x64 machines just run `./launch.sh`
3. V1 had QEMU cross-compiled Docker image (broken) → V2 uses it but documents limitation
4. V1 scripts accumulated multiple broken iterations → V2 is clean rewrite

**CRITICAL LESSON — exFAT line-merge corruption (2026-07-10, CORRECTED):**
`launch.sh` was written to exFAT USB. The exFAT filesystem **merged two adjacent
lines** into one: `DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-docker-b}" "$(uname -m)"`
(was 2 separate lines). Result: `HOST_ARCH` never set → `set -u` → silent exit.

> **CORRECTION:** Previous version claimed `write_file` "censored" the token to
> `***`. This was a **misdiagnosis** — the `***` was display-time redaction by
> `read_file` (`file_tools.py:823`, `agent/redact.py:_mask_token()`). The file
> on disk contained the real token. The ONLY corruption was LINE MERGE.

Result: `HOST_ARCH` never set → `set -u` → "unbound variable" → **SILENT EXIT**
(no error output, no traceback, just dead `$ ` prompt). User saw: `./launch.sh`
with no output, dropped back to shell.

**Fix:** Re-wrote via `terminal` heredoc to `/tmp/launch.sh`, verified with
`head -18` + `bash -n`, then `cp` to USB. **Lesson: NEVER use write_file for
scripts containing tokens on exFAT. Use terminal heredoc + cp. ALWAYS verify
with visual head inspection, not just bash -n.**

**x64 Docker limitation (permanent):** QEMU cannot run Node.js (SIGSEGV in V8
JIT). x64 image has gateway+API but NO web UI. Dashboard API still works for
Electron GUI connection — Electron renders its own UI from dist/ assets bundled
in the pre-built binary, not from dashboard web assets.

## Source Code Bind Mounts — persistent code sync (2026-07-11)

`docker cp` copies files into the container's writable layer — **lost on
recreate**. Bind mounts make local source code (`~/.hermes/hermes-agent/`)
instantly live in both containers, surviving `compose down`/`up`.

**What to mount:** 10 directories (agent/, hermes_cli/, tui_gateway/, tools/,
gateway/, cron/, plugins/, acp_adapter/, providers/, skills/) + 16 top-level
.py files. NOT: .venv/, node_modules/, ui-tui/ (image-specific compiled assets).

**Key decisions:**
- **Gateway data** = own volume (`~/.hermes-portable`) — separate state.db
- **Dashboard data** = `~/.hermes` (SHARED with local Hermes — same sessions)
- Bind mounts are **rw** (not :ro) — s6 chown hangs on read-only mounts
- YAML anchors DON'T work for volume arrays — duplicate the list per service

**Migration from `docker cp`:** requires container recreation (not restart).
Old containers from other compose projects need `docker stop` + `docker rm`
first to avoid name conflicts.

**Full guide:** `references/source-code-bind-mounts.md`
**Template:** `templates/docker-compose-local.yml` — complete working compose
with both services + full bind mount list.

## ⚠️ YAML anchors don't work for docker-compose volume arrays

```yaml
x-src: &src
  - /path:/mount    # ← array element
services:
  gateway:
    volumes:
      - *src         # ← ERROR: "must be a string"
```

Docker Compose rejects merge-key arrays in `volumes:`. Duplicate the volume
list explicitly per service. It's verbose but reliable.

## Связанные файлы

- `references/source-code-bind-mounts.md` — **(2026-07-11):** Source code bind
  mounts: persistent code sync, migration from `docker cp`, shared state.db
  pattern (dashboard ↔ local Hermes), verification checklist, daily workflow.
- `templates/docker-compose-local.yml` — **(2026-07-11):** Complete working
  docker-compose with gateway + dashboard, full source code bind mounts for
  both services, shared state.db on dashboard.
- `references/portable-v2-dual-arch-package.md` — **(2026-07-09):** V2 pattern: dual-arch pre-built binaries, auto-arch scripts, x64 QEMU limitation.
- `references/offline-usb-deployment.md` — **(2026-07-08):** exFAT scripting pitfalls (heredoc corruption, UTF-8 breakage, symlink failure, Docker volume mount failure), cross-arch Docker build via QEMU (Node.js SIGSEGV workaround), offline GUI build from Docker image, full package structure for USB deployment.
- `references/parallel-docker-deployment.md` — **NEW (2026-07-07):** Docker-based
  portable package with Docker tarball + pre-built GUI. Includes start-backend.sh,
  launch.sh, stop.sh, and cross-machine deployment instructions.
- `references/parallel-docker-deployment.md` — **(2026-07-07):** Docker-based
  `unset HERMES_HOME` fix, auto docker load from tarball, 3-min dashboard wait.
- `templates/launch.sh` — **(2026-07-08):** Simplified GUI launcher. Creates
  connection.json, launches Electron with ARM64 flags (--disable-gpu --no-sandbox).
- `references/self-contained-portable-package.md` — **(2026-07-08):** Self-contained
  package pattern (image + GUI bundled). Dashboard cold-start timing table.
  Tool corruption warning for write_file with token strings.
- `references/parallel-docker-deployment.md` — **(2026-07-07, updated 2026-07-08):**
  Docker-based parallel Hermes instance alongside main. Port allocation (:18649/:9123),
  separate volumes, shared llama-server/LiteLLM, 8-point verification, GUI switching.
- `references/multi-backend-testing.md` — **(2026-07-07):** Host-process parallel
  backend (non-Docker). `/tmp/hermes-backend2/` template, connection.json switching.
- `references/stale-dashboard-config-debug.md` — **(2026-07-07):** Debugging
  "API call failed after 3 retries: Connection error" — dashboard volume config
  goes stale independently of gateway volume. Full diagnostic recipe + 4-config
  location table.
- `references/multi-instance-topology-debug.md` — **(2026-07-10):** Debugging
  "unknown agent" / "model not in picker" when Electron connects to Docker but
  agents/ dir is missing from the dashboard volume. Code isolation: patches to
  `~/.hermes/hermes-agent/` are invisible to Docker (`/opt/hermes/` baked in
  image). Full topology map + fix steps.
- `references/config-drift-local-vs-docker.md` — **(2026-07-10):** Debugging
  "wrong model answering / no GPU load" — local config drifted from Docker
  (missing `custom_providers` + `extra_body`, default = cloud `deepseek-v4-pro`).
  Silent cloud fallback. Includes `patch` tool refusal workaround, full sync
  checklist (config, scripts, schemas, AGENTS.md, plans, reports), and
  `custom_providers` vs legacy `providers` format comparison.
- `references/offline-usb-packaging.md` — **(2026-07-08):** Full stack portable
  deployment to USB (exFAT). Architecture auto-detection, Docker platform
  mismatch, QEMU cross-compile limitations, heredoc-free script pattern for exFAT.