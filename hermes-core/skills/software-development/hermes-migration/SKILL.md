---
name: hermes-migration
description: "Перенос Hermes Agent между машинами, дисками и носителями — бэкап, миграция, клонирование, ARM64↔x86_64."
version: 1.0.0
author: Hermes Agent + Pavel
license: MIT
metadata:
  hermes:
    tags: [migration, backup, transfer, portable, arm64, x86_64, disk, machine]
    related_skills: [hermes-distribution-packaging, session-maintenance, hermes-database-maintenance]
---

# Hermes Migration — перенос между носителями

Перенос ЛИЧНОГО Hermes (со всеми данными, сессиями, ключами) между
машинами, дисками и архитектурами. Это НЕ про создание публичного
дистрибутива — для этого используй `hermes-distribution-packaging`.

## Когда использовать

- «Купил новый компьютер, хочу перенести Hermes»
- «Переношу Hermes на внешний SSD»
- «Делаю полный бэкап перед экспериментом»
- «Клонирую Hermes на вторую машину»
- «Как обновить Hermes с сохранением всех данных?»
- «Что именно копировать чтобы не сломать?»
- «Нужно пересобрать под x86_64 с ARM64»

## Принципиальное отличие от distribution-скиллов

| | Distribution/Packaging | Migration |
|---|---|---|
| **Цель** | Отдать другому | Перенести себе |
| **Секреты (.env, ключи)** | ❌ Исключить, санитизировать | ✅ Сохранить |
| **state.db (сессии)** | ❌ Исключить | ✅ Сохранить |
| **memory/ (память)** | ❌ Исключить | ✅ Сохранить |
| **config.yaml** | → template с CHANGEME | ✅ Как есть |
| **Размер пакета** | ~40 MB | ~450 MB — 97 GB |

## Четыре уровня данных

```
┌─ 🔴 IDENTITY (без этого — другой агент) ─────────────────────┐
│ .env           25K   ключи API (DeepSeek, Kimi, Telegram...) │
│ config.yaml     12K   модель, провайдеры, порты              │
│ persona.md      2.6K  характер, стиль общения                │
│ profiles/       19M   профили с настройками                  │
└──────────────────────────────────────────────────────────────┘
┌─ 🟡 KNOWLEDGE (без этого — потеря памяти) ────────────────────┐
│ state.db       335M   ВСЕ сессии (session_search)            │
│ memories/       12K   MEMORY.md + USER.md                    │
│ auditor_memory.md 1.3K cross-cycle patterns                  │
│ sessions/        3M   JSON-дампы сессий                      │
└──────────────────────────────────────────────────────────────┘
┌─ 🟢 TOOLS (без этого — потеря наработок) ────────────────────┐
│ agents/         1.2M  38 agent-файлов                        │
│ skills/         17M   133 скилла                             │
│ hooks/         100K   8 хуков                                │
│ scripts/       452K   30 скриптов                            │
│ gates/         536K   quality gates                          │
│ plugins/        45M   MCP (claw-neo4j и др.)                 │
│ cron/          196K   cron-задачи + output                   │
│ AGENTS.md       15K   проектные конвенции                    │
└──────────────────────────────────────────────────────────────┘
┌─ ⬜ REBUILDABLE (не копировать — переустановить) ─────────────┐
│ hermes-agent/  8.1G  исходники + venv → pip install         │
│ lsp/           105M   LSP-серверы → hermes lsp install       │
│ bin/            95M   бинарники LSP                          │
└──────────────────────────────────────────────────────────────┘
┌─ ⬜ JUNK (не копировать — мусор) ─────────────────────────────┐
│ state.db.bak.* 821M   старые бэкапы БД                      │
│ logs/           39M   логи                                   │
│ cache/          1.9M  кэш                                    │
│ backups/         48K  бэкапы конфигов                        │
│ sandboxes/        8K  временные песочницы                    │
│ home/            1G   циклическая копия ~/.hermes            │
└──────────────────────────────────────────────────────────────┘
```

### Три сценария

| | Бэкап (та же машина) | Новая машина | Внешний диск (exFAT) |
|---|---|---|---|
| **Пути** | Те же | Другие | Те же |
| **Архитектура** | Та же | Может отличаться | Та же |
| **sed путей** | ❌ | ✅ | ❌ |
| **Метод копирования** | `tar czf` | `tar czf` + `sed` | `tar czf` (ОБЯЗАТЕЛЬНО!) |

## Процедура: 4 шага

### Шаг 1: Остановить Hermes

```bash
hermes gateway stop 2>/dev/null || true
pkill -f "hermes gateway" 2>/dev/null || true
# Закрыть десктопное приложение если запущено
# Проверить: ps aux | grep -i hermes
```

### Шаг 2: Упаковать

```bash
cd ~/.hermes

tar czf /tmp/hermes-migration.tar.gz \
  .env config.yaml persona.md \
  profiles/ memories/ state.db \
  agents/ skills/ hooks/ scripts/ gates/ plugins/ cron/ \
  AGENTS.md auditor_memory.md SOUL.md \
  skill-bundles/ schemas/ opencode_claw/ \
  observations/ reports/ plans/ pairing/ \
  2>/dev/null

echo "Размер: $(du -h /tmp/hermes-migration.tar.gz | cut -f1)"
```

**Что НЕ включать** (переустановится или мусор):
- `hermes-agent/` — исходники + venv → `pip install hermes-agent`
- `lsp/`, `bin/` — LSP-серверы → `hermes lsp install`
- `state.db.bak.*` — старые бэкапы БД (821 MB!)
- `logs/` — логи
- `cache/` — кэш моделей
- `backups/`, `sandboxes/` — временные файлы
- `home/` — циклическая копия (1 GB)
- `__pycache__/`, `*.pyc` — мусор Python

### Шаг 3: Перенести

```bash
# По сети
scp /tmp/hermes-migration.tar.gz user@new-machine:~/

# На внешний диск (любая ФС кроме exFAT)
cp /tmp/hermes-migration.tar.gz /mnt/backup/

# На exFAT диск — tar ОБЯЗАТЕЛЕН
# ❌ НИКОГДА: cp -r ~/.hermes /mnt/exfat/
# ✅ ВСЕГДА: tar czf /mnt/exfat/hermes.tar.gz -C ~/.hermes .
```

### Шаг 4: Развернуть

```bash
# На целевой машине
mkdir -p ~/.hermes
tar xzf hermes-migration.tar.gz -C ~/.hermes/

# Переустановить Hermes CLI
pip install hermes-agent

# Переустановить LSP
hermes lsp install

# ТОЛЬКО для новой машины — поправить пути
find ~/.hermes -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" -o -name "*.sh" \) \
  -exec sed -i 's|/home/OLDUSER/|/home/NEWUSER/|g' {} +

# Проверить что старых путей не осталось
grep -r '/home/OLDUSER/' ~/.hermes --include="*.yaml" --include="*.md" -l

# Запустить
hermes gateway run
```

## ⚠️ exFAT-ловушка (КРИТИЧНО)

При копировании на exFAT-диск (Seagate, WD, флешки) **НИКОГДА не использовать `cp -r`**.
exFAT не поддерживает POSIX symlinks — `cp -r` **раскрывает** их в полные копии файлов:

| Директория | Реальный размер | После `cp -r` на exFAT |
|---|---|---|
| `node_modules/` | 45 MB | 847 MB (19× раздутие!) |
| `llama.cpp/build/bin/` | 83 MB | 83 MB (мало symlinks) |

**Решение:** всегда `tar czf` на источнике → скопировать архив → `tar xzf` на цели.

## ARM64 ↔ x86_64: что пересобрать

При переносе на другую архитектуру ~80% артефактов переиспользуются:

```
✅ НЕ меняется:
  46/60 Python wheels (py3-none-any)
  3 GGUF модели (76 GB)
  Neo4j дамп
  Все конфиги/скиллы/агенты (текст)

🔄 НУЖНО пересобрать (или предсобрать на источнике):
  14/60 Python wheels (aarch64 → x86_64)     ~39 MB
  15 Docker образов (9 pull + 6 local)        ~15 GB
  llama-server binary (+ правка CUDA_ARCH)    ~50 MB
```

### ⚡ Предварительная сборка на ИСХОДНОЙ машине (рекомендуется)

**Открытие:** `docker buildx build --platform linux/amd64 --load` работает на
Jetson ARM64 через QEMU-эмуляцию. `pip download --platform manylinux2014_x86_64`
тоже работает. Это значит, что **ВСЕ x86_64-артефакты можно собрать на Jetson
(пока есть интернет) и перенести на целевую x86_64-машину без интернета.**

```bash
# Проверить что buildx поддерживает amd64:
docker buildx ls | grep -q linux/amd64 || apt install qemu-user-static

# 1. Python wheels для x86_64 (одна команда!)
pip download --platform manylinux2014_x86_64 --python-version 312 \
  --only-binary=:all: hermes-agent -d pip-packages-x86_64/

# 2. Docker pull-образы для amd64 (тянуть на ARM64!)
for img in neo4j:5-community arizephoenix/phoenix:latest postgres:16-alpine \
           python:3.12-slim python:3.12-alpine alpine:latest \
           ghcr.io/berriai/litellm-database:v1.83.7-stable \
           nvidia/cuda:13.0.0-devel-ubuntu24.04 nvidia/cuda:13.0.0-runtime-ubuntu24.04; do
  docker pull --platform linux/amd64 "$img"
  docker save "$img" -o "docker-images-amd64/$(echo $img | tr '/:' '-').tar"
done

# 3. Локальные Docker-образы для amd64 (6 шт, QEMU-эмуляция)
#    Фактический список из compose.agents-mesh.yml + compose.phoenix.yml:
for svc in agent-registry clawcode-adapter opencode-adapter \
           openhands-adapter skills-manager openai-stack-relay; do
  docker buildx build --platform linux/amd64 --load \
    -t "voice-assistant-${svc}:local" \
    -f "llm-stack/docker/${svc}/Dockerfile" .
done

# 4. llama-server для x86_64 (через Docker buildx + CUDA_ARCH override)
#    ⚠️ llamacpp Dockerfile хардкодит CUDA_ARCH=121 (Blackwell/Jetson).
#    Для x86_64 нужно переопределить под целевой GPU!
cat > /tmp/Dockerfile.llama-x86 << 'EOF'
FROM nvidia/cuda:13.0.0-devel-ubuntu24.04
RUN apt-get update && apt-get install -y git cmake build-essential
RUN git clone --depth 1 https://github.com/ggml-org/llama.cpp /src
# CUDA_ARCH: 90=Hopper, 89=Ada Lovelace, 80=Ampere, 89;90=multi
RUN cd /src && cmake -B build -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=89 && cmake --build build -j$(nproc) --target llama-server
EOF
docker buildx build --platform linux/amd64 --load \
  -t llama-x86-builder:latest -f /tmp/Dockerfile.llama-x86 .
  cp /src/build/bin/llama-server /out/
# Результат: /tmp/x86-out/llama-server — готовый бинарник под x86_64+CUDA
```

После этого все артефакты лежат локально — можно копировать на целевую
x86_64-машину и разворачивать **полностью офлайн**.

### Процедура пересборки на ЦЕЛЕВОЙ машине (если есть интернет)

```bash
# 1. Перекачать архитектурно-зависимые wheels
pip download --platform manylinux2014_x86_64 --python-version 312 \
  --only-binary=:all: hermes-agent -d pip-packages-x86/
# Заменить aarch64-whl на x86_64-версии

# 2. Пересобрать llama-server
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp && cmake -B build -DGGML_CUDA=ON
cmake --build build -j --target llama-server

# 3. Перетянуть Docker pull-образы
for img in neo4j:5-community arizephoenix/phoenix:latest \
           postgres:16-alpine python:3.12-slim alpine:latest; do
  docker pull --platform linux/amd64 "$img"
  docker save "$img" -o "docker-images/$(echo $img | tr '/:' '-').tar"
done

# 4. Пересобрать локальные Docker-образы
docker compose -f compose.agents-mesh.yml build
docker compose -f compose.phoenix.yml build
```

### Самый рисковый момент

6 локально собранных образов (`voice-assistant-*-adapter:local`,
`voice-assistant-agent-registry:local`, `voice-assistant-skills-manager:local`,
`voice-assistant-openai-stack-relay:local`). Их **не скачать** с Docker Hub —
только пересобрать из Dockerfile-ов. Если в Dockerfile зашит `--platform=linux/arm64`
или ARM64-специфичный base-образ, сборка упадёт на x86_64.

**⚠️ CUDA_ARCH pitfall:** llamacpp Dockerfile хардкодит `CUDA_ARCH=121` (sm_121 =
Blackwell, Jetson DGX Spark). Для x86_64 это **обязательно** изменить на compute
capability целевого GPU (90=Hopper, 89=Ada, 80=Ampere, или `89;90` для мульти-arch).
Без правки сборка завершится, но llama-server не сможет использовать GPU на целевой
машине.

**⚠️ Не путать с runtime-образами:** `voice-assistant-opencode:local`,
`voice-assistant-clawcode:local`, `openwebui-searchbox:local`, `openwebui-fsbox:local`,
`openwebui-shellbox:local` — это образы OpenWebUI/runtime, которые НЕ входят в
codewar дистрибутив. Проверяй фактический список по compose-файлам, а не по
`docker images` на dev-машине.

### Верификация плана перед представлением (КРИТИЧНО)

Перед тем как представлять план миграции, **проверь фактические артефакты на диске**.
В сессии 2026-07-06 план содержал 5 ошибок (перепутаны pull/local количества,
3 несуществующих образа, размер занижен в 3×, не упомянут CUDA_ARCH). См.
`references/arm64-x86-migration.md` → Шаг 6 для команд верификации.

### Ограничения предварительной сборки

| Можно | Нельзя |
|-------|--------|
| ✅ Собрать amd64 Docker-образы | ❌ Запустить их (QEMU без GPU) |
| ✅ Скачать x86_64 Python wheels | ❌ Проверить CUDA-образы (`nvidia-smi`) |
| ✅ Скомпилировать llama-server под x86_64 | ❌ Проверить что llama-server грузит модели |
| — | ❌ Интеграционный тест всего стека |

**Вывод:** собрать можно всё. Проверить что работает — только на целевой машине
с GPU. Включи smoke-test скрипт в дистрибутив.

## Что НЕ восстанавливается автоматически

| Компонент | Почему | Что делать |
|-----------|--------|------------|
| **Модели GGUF** (76 GB) | Не в ~/.hermes | Скопировать отдельно или перекачать |
| **Docker-образы** (21 GB) | Не в ~/.hermes | `docker save` / `docker load` |
| **Neo4j данные графа** | Docker volume | `neo4j-admin database dump` → перенести дамп |
| **Android APK** | На телефоне | Пересобрать `./gradlew assembleDebug` |
| **VPS-туннель** | На VPS | Настроить заново `ssh -R` |
| **Cron-задачи ОС** | Вне Hermes | Перенастроить systemd/crontab |

## Docker-специфичные pitfalls после миграции

| Pitfall | Симптом | Фикс |
|---------|---------|------|
| **s6-log lock crash-loop** (2026-07-07) | После рестарта Docker gateway контейнер в `sleep infinity`, не обслуживает запросы. Лог: `s6-log: fatal: unable to lock /opt/data/logs/gateways/default/lock: Resource busy` | gateway и dashboard шарят `/opt/data` volume. Чистить `logs/gateways/` перед стартом: `rm -rf ~/.hermes-docker/logs/gateways/` |
| **`provider: custom` bare** (2026-07-07) | Dashboard пишет "gateway needs setup"; `/v1/chat/completions` возвращает `"No LLM provider configured"` | Legacy `custom_providers` требует `provider: custom:<name>` С суффиксом. Bare `custom` → Hermes не резолвит провайдер. См. `hermes-custom-providers` |
| **ARM64 LiteLLM image** (2026-07-07) | LiteLLM контейнер падает с SIGSEGV (prisma-migrate под QEMU) | `v1.83.7-stable` = amd64. Использовать `main-stable` (arm64-native). `docker image inspect <tag> --format '{{.Architecture}}'` |
| **`docker restart` НЕ обновляет env** (2026-07-07) | После правки `.env` и `docker restart` контейнер не видит новые переменные | env vars baked at creation. `docker compose up -d --force-recreate litellm` |

## Проверка после миграции

```bash
# 1. Hermes запускается
hermes --version

# 2. Память на месте
cat ~/.hermes/memories/MEMORY.md | head -3

# 3. Сессии доступны
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM messages;"

# 4. Ключи на месте (без вывода значений!)
grep -c 'API_KEY' ~/.hermes/.env

# 5. Старых путей не осталось (для новой машины)
grep -r '/home/OLDUSER/' ~/.hermes -l  # должно быть пусто

# 6. Docker: provider configured (не "gateway needs setup")
curl -s http://127.0.0.1:18648/v1/chat/completions \
  -H "Authorization: Bearer $API_SERVER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"test","messages":[{"role":"user","content":"say ok"}],"max_tokens":10}'
# Если "No LLM provider configured" → проверить provider: custom:<name> в config.yaml

# 7. Docker: s6-log lock cleaned
ls ~/.hermes-docker/logs/gateways/ 2>/dev/null && echo "WARN: lock dir exists, rm -rf it"
```

## Связанные скиллы

- `hermes-distribution-packaging` — создание публичного дистрибутива (НЕ для переноса личных данных)
- `session-maintenance` — очистка state.db, VACUUM
- `hermes-database-maintenance` — обслуживание БД
- `git-snapshot-workflow` — сохранение known-good state через git

## References

- `references/migration-matrix.md` — полная матрица: что копировать, что пересобирать, размеры, трудоёмкость
- `references/exfat-symlink-pitfall.md` — детальный разбор проблемы exFAT + symlinks
- `references/arm64-x86-migration.md` — ARM64↔x86_64: процедура пересборки (9 pull + 6 local Docker images), CUDA_ARCH pitfall, верификация плана
- `references/cross-arch-verification.md` — **NEW (2026-07-06):** Команды верификации плана миграции: wheel platform tags, Docker image architecture, binary ELF check, CUDA_ARCH audit, compose service names. Checklist для проверки плана перед представлением.
