# Hermes — Offline / Internal Network Deployment Guide

> Дата: 2026-07-07
> Контекст: развёртывание Hermes Agent в изолированной сети без доступа к интернету

## Когда возможна работа без интернета

| Компонент | Без интернета | Зависимости |
|-----------|---------------|-------------|
| **Docker-образ Hermes** | ✅ Если образ загружен заранее | Нужен `docker pull` или `docker load` с архивом |
| **Локальная LLM (llama.cpp)** | ✅ Полностью локально | GGUF файл на диске |
| **LiteLLM (прокси)** | ✅ Если модели локальные | Предварительный docker pull |
| **Neo4j** | ✅ Полностью локально | Предварительный docker pull |
| **Phoenix (трассировка)** | ✅ Полностью локально | Предварительный docker pull |
| **Cloud LLM (DeepSeek, OpenAI)** | ❌ Нужен интернет | API-вызовы к внешним серверам |
| **Skills Hub** | ❌ Нужен интернет | GitHub raw-загрузки |
| **GitHub / npm / pip** | ❌ Нужен интернет | Установка зависимостей |

## Режимы развёртывания

### Режим A: Полностью локальный (без интернета)

```
Hermes gateway ──► Local llama.cpp (:8090)
                                   │
                              GGUF model файл (.gguf)
```

**Требования:**
1. Docker образ `hermes-agent` предварительно загружен (см. ниже)
2. LLM модель в формате GGUF на диске
3. Никаких API-ключей не нужно
4. Hermes настроен на `custom_providers` с локальной llama.cpp

**Настройка config.yaml для локальной модели:**

```yaml
model:
  provider: custom
  default: llama-local

providers:
  custom_providers:
    - name: llama-local
      base_url: http://localhost:8090/v1
      api_key: sk-no-key-required
      models:
        - llama-local

model:
  default: llama-local
  provider: custom
  context_length: 65536
```

### Режим Б: Mixed (локальные + облачные модели)

```
Hermes gateway ──► LiteLLM (:4000) ──► GGUF / DeepSeek / OpenAI
                         │
                    config.yaml с роутингом
```

**Требования:**
- Интернет только для облачных провайдеров
- Локальные модели работают без интернета
- LiteLLM маршрутизирует запросы

### Режим В: Cloud-only (требует интернет)

```
Hermes gateway ──► DeepSeek / OpenAI / OpenRouter
```

**Стандартный режим.** Только интернет + API-ключ.

## Подготовка к офлайн-развёртыванию

### Шаг 1: Загрузить Docker образы заранее (на машине с интернетом)

```bash
# Список образов для полного стека
IMAGES=(
  "hermes-agent:latest"                          # собранный образ
  "ghcr.io/berriai/litellm:latest"               # LiteLLM прокси
  "neo4j:5-community"                            # Knowledge Graph
  "localai/localai:latest-nvidia-l4t-arm64-cuda-13"  # LocalAI (ARM64)
  "langgenius/dify-api:1.13.3"                   # Dify
)

for img in "${IMAGES[@]}"; do
  docker pull "$img"
  # Сохранить в tar для переноса
  docker save "$img" | gzip > "${img//\//_}.tar.gz"
done

# На машине без интернета:
for tar in *.tar.gz; do
  docker load < "$tar"
done
```

### Шаг 2: Загрузить GGUF модель

```bash
# С машины с интернетом
wget https://huggingface.co/bartowski/DeepSeek-V4-Flash-GGUF/resolve/main/deepseek-v4-flash-q4_k_m.gguf

# Перенести на офлайн-машину (USB/SCP/NFS)
scp deepseek-v4-flash-q4_k_m.gguf user@offline-server:~/models/
```

### Шаг 3: Предзагрузить Python/npm зависимости (опционально)

```bash
# Если собирать образ на офлайн-машине — нужны кеши:
# pip кеш:
pip download -r requirements.txt -d ./pip-cache
# npm кеш:
npm pack --pack-destination ./npm-packages
```

## Запуск в изолированной сети (internal network)

### Сценарий: сервер во внутренней сети, GUI на той же машине

```bash
# Всё на одной машине — работает как обычно
docker run -d --name hermes-gateway --network host \
  -v ~/.hermes-docker:/opt/data \
  -e API_SERVER_PORT=18648 \
  hermes-agent gateway run

# Dashboard для GUI
docker run -d --name hermes-dashboard --network host \
  -v ~/.hermes-dashboard-data:/opt/data \
  -v ~/.hermes/hermes-agent/tui_gateway:/opt/hermes/tui_gateway \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  -e PYTHONPATH=/opt/data \
  -e GATEWAY_HEALTH_URL=http://127.0.0.1:18648/health \
  hermes-agent dashboard --host 127.0. --port 9121 \
    --insecure --tui --no-open --skip-build
```

### Сценарий: сервер без GUI, клиент с GUI в другой подсети

```bash
# На сервере (без интернета, без GUI):
docker run -d --name hermes-gateway --network host \
  -v ~/.hermes-docker:/opt/data \
  -e API_SERVER_PORT=18648 \
  hermes-agent gateway run

# Dashboard на сервере (для WebSocket):
docker run -d --name hermes-dashboard --network host \
  -v ~/.hermes-dashboard-data:/opt/data \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  -e PYTHONPATH=/opt/data \
  -e GATEWAY_HEALTH_URL=http://127.0.0.1:18648/health \
  hermes-agent dashboard --host 0.0.0.0 --port 9121 \
    --insecure --tui --no-open --skip-build

# На клиенте (GUI на ноутбуке):
# connection.json:
# { "mode": "remote", "remote": {
#     "url": "http://<SERVER_IP>:9121",
#     "token": {"value": "***"},
#     "authMode": "token"
#   }, "profiles": {} }
```

### Важно для внутренней сети

| Аспект | Требование |
|--------|------------|
| **DNS** | Работает IP-адресация или используйте `/etc/hosts` |
| **Брандмауэр** | Открыть порт dashboard (9121) и gateway (18648) |
| **Host network** | `--network host` проще, bridge требует проброса портов |
| **--insecure** | Обязателен для remote-подключения (иначе 401) |
| **PYTHONPATH** | Обязателен для WebSocket (tui_gateway) |
| **API_SERVER_KEY** | Сгенерировать: `openssl rand -hex 32` |

## Быстрая команда — полный запуск в изолированной сети

```bash
# 1. Подготовить директорию
mkdir -p ~/.hermes-docker/logs ~/.hermes-docker/sessions

# 2. Запустить gateway
docker run -d --name hermes-offline-gateway --restart unless-stopped --network host \
  -v ~/.hermes-docker:/opt/data \
  -e API_SERVER_PORT=18648 \
  -e HERMES_DISABLE_MESSAGING=1 \
  -e GATEWAY_ALLOW_ALL_USERS=true \
  hermes-agent gateway run

# 3. Подождать
for i in $(seq 1 60); do curl -sf http://127.0.0.1:18648/health >/dev/null && break; sleep 2; done

# 4. Запустить dashboard
TOKEN="$(openssl rand -base64 32)"
docker run -d --name hermes-offline-dashboard --restart unless-stopped --network host \
  -v ~/.hermes-docker:/opt/data \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  -e PYTHONPATH=/opt/data \
  -e GATEWAY_HEALTH_URL=http://127.0.0.1:18648/health \
  hermes-agent dashboard --host 127.0.0.1 --port 9121 \
    --insecure --tui --no-open --skip-build

# 5. Получить токен (из HTML)
curl -s http://127.0.0.1:9121/ | grep -oP '__HERMES_SESSION_TOKEN__=*** echo "Dashboard token: $TOKEN"
```

## Когда интернет НУЖЕН (исключения)

| Ситуация | Почему | Workaround |
|----------|--------|------------|
| **Первый docker pull** | Образов нет на машине | `docker save` / `docker load` с архива |
| **Установка Hermes из pip/npm** | Зависимости из реестров | Предзагрузить кеш |
| **Облачные LLM** | API-вызовы к DeepSeek/OpenAI | Использовать локальную GGUF |
| **Skills Hub** | GitHub raw | Установить скиллы вручную из файлов |
| **MCP серверы** | npm install | Предзагрузить node_modules |
| **pip audit (SAST)** | База уязвимостей | `pip-audit --local` |
