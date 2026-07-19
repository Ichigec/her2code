# Native Gateway — полный контроль хоста (без Docker)

## Проблема Docker Gateway

Docker-контейнер `hermes-gateway` изолирован:
- Терминал `local` исполняется внутри контейнера, НЕ на хосте
- Агент видит только `/opt/data` (примонтированный `/home/user/.hermes-portable`)
- Нет доступа к `/home/user/`, `docker`, `systemctl`, GPU, etc.
- `localhost` внутри контейнера ≠ хост. Для доступа к LiteLLM — `172.17.0.1:4000`

Симптом: агент говорит «LiteLLM не установлен», хотя он работает на хосте. Команды `which litellm`, `ps aux | grep litellm` внутри контейнера не видят хост-процессы.

## Решение: Native Gateway

Hermes Gateway запускается прямо на хосте (не в Docker), с собственным `HERMES_HOME`.

```
Phone → VPS:8643 (SSH tunnel) → Native Gateway:8643 → LiteLLM:4000 → cloud models
```

**Преимущества:**
- Терминал `local` = хост, полный доступ к файлам, Docker, GPU, процессам
- Нет socat моста (Gateway слушает прямо на 8643)
- Меньше latency (на 1 hop меньше)
- Проще диагностика (логи прямо на хосте)

## Конфигурация

### Структура директории

```bash
mkdir -p /home/user/.hermes-native-gateway/.hermes
```

### config.yaml (`/home/user/.hermes-native-gateway/config.yaml`)

```yaml
_config_version: 28

model:
  provider: custom:litellm
  default: deepseek-chat
  context_length: 131072

custom_providers:
  - name: litellm
    base_url: http://localhost:4000/v1          # НЕ 172.17.0.1 — хост!
    api_mode: chat_completions
    key_env: LITELLM_API_KEY
    models:
      deepseek-chat: { context_length: 65536 }
      deepseek-reasoner: { context_length: 65536 }
      deepseek-v4-flash: { context_length: 65536 }
      deepseek-v4-pro: { context_length: 65536 }
      glm-5.2: { context_length: 131072 }
      gpt-4.1: { context_length: 1047576 }
      gpt-4.1-mini: { context_length: 1047576 }

agent:
  max_turns: 900
  gateway_timeout: 1800
  api_max_retries: 3
  tool_use_enforcement: auto
  task_completion_guidance: true
  environment_probe: true
  reasoning_effort: xhigh
  disabled_toolsets: []

toolsets:
  - hermes-cli

terminal:
  backend: local           # ХОСТ-терминал!
  cwd: /home/user         # Домашняя директория пользователя
  timeout: 18000
  persistent_shell: true

platforms:
  api_server:
    port: 8643             # Прямо на 8643 — без socat!
    host: 0.0.0.0
    enabled: true

approvals:
  mode: 'off'
  timeout: 60

skill_router:
  enabled: true
```

### .env (`/home/user/.hermes-native-gateway/.env`)

```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=eb7324f34fd41a7959a3f1647f1fa1100f81deac2aac1ecac747ef12aae7a966
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8643
LITELLM_API_KEY=*** GLM_API_KEY=<glm_key>
```

## Запуск

```bash
HERMES_HOME=/home/user/.hermes-native-gateway \
LITELLM_API_KEY=*** GLM_API_KEY=*** /home/user/.hermes/hermes-agent/venv/bin/hermes gateway run
```

**ПРИМЕЧАНИЕ:** Использовать венв из `/home/user/.hermes/hermes-agent/venv/bin/hermes` (НЕ `/opt/hermes/.venv/bin/hermes` — это Docker-путь, не существует на хосте).

## Skills для Native Gateway

Нативный Gateway использует skills из венва. Для совместимости с пользовательскими скиллами:

```bash
ln -sf /home/user/.hermes/hermes-agent/skills /home/user/.hermes-native-gateway/skills
ln -sf /home/user/.hermes/skills /home/user/.hermes-native-gateway/.hermes/skills
```

## Переключение между Docker и Native

| Аспект | Docker Gateway | Native Gateway |
|--------|---------------|----------------|
| Порт | 18649 (Docker) | 8643 (прямой) |
| Мост | socat 8643→18649 | не нужен |
| Терминал | внутри контейнера | хост |
| Доступ к хосту | ограничен `/opt/data` | полный |
| LiteLLM URL | `172.17.0.1:4000` | `localhost:4000` |
| HERMES_HOME | `/opt/data` | `/home/user/.hermes-native-gateway` |
| Вердикт агента | «litellm не установлен» | видит litellm |

## Остановка Docker → запуск Native

```bash
# 1. Остановить Docker Gateway
docker stop hermes-gateway

# 2. Убить socat мост (больше не нужен)
kill $(pgrep -f "socat.*8643") 2>/dev/null

# 3. Запустить Native Gateway
HERMES_HOME=/home/user/.hermes-native-gateway \
LITELLM_API_KEY=*** /home/user/.hermes/hermes-agent/venv/bin/hermes gateway run &

# 4. Проверить
curl http://localhost:8643/health
# → {"status":"ok","platform":"hermes-agent"}
```

## Возврат к Docker

```bash
# 1. Убить нативный Gateway
kill $(pgrep -f "hermes gateway") 2>/dev/null

# 2. Запустить Docker
docker start hermes-gateway

# 3. Поднять socat мост
socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:18649 &

# 4. Проверить
curl http://localhost:8643/health
```
