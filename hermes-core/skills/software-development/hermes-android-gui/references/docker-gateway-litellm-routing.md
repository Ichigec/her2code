# Docker Gateway → LiteLLM Model Routing

## Проблема

Gateway в Docker контейнере настроен на `localhost:8092` (локальный llama-server),
но llama-server не запущен. Результат: SSE-ответ приходит пустым
(`responseText length=0`, `completion_tokens: 0`), приложение показывает пустой ответ.

## Симптомы

1. `adb logcat` показывает: `ChatVM: Done: responseText length=0`
2. `curl` через Gateway возвращает: `{"delta":{},"finish_reason":"stop"},"usage":{"completion_tokens":0}`
3. `docker logs hermes-gateway` показывает: `APIConnectionError: Connection error.`
   с `base_url=http://localhost:8092/v1`

## Решение: перенаправить Gateway на LiteLLM

LiteLLM (Docker контейнер `litellm` на :4000) маршрутизирует на cloud-модели
(DeepSeek, GLM, GPT) и локальные llama-servers (8101-8103).

### 1. Обновить config.yaml

Файл: `/home/user/.hermes-portable/config.yaml` (bind-mount → `/opt/data/config.yaml`)

```yaml
model:
  provider: custom:litellm
  default: deepseek-chat
  context_length: 131072

custom_providers:
  - name: litellm
    base_url: http://172.17.0.1:4000/v1    # Docker → host через bridge gateway
    api_mode: chat_completions
    key_env: LITELLM_API_KEY               # из .env: LITELLM_API_KEY=***    models:
      deepseek-chat: { context_length: 65536 }
      deepseek-reasoner: { context_length: 65536 }
      deepseek-v4-flash: { context_length: 65536 }
      deepseek-v4-pro: { context_length: 65536 }
      glm-5.2: { context_length: 131072 }
      gpt-4.1: { context_length: 1047576 }
      gpt-4.1-mini: { context_length: 1047576 }
```

### 2. Добавить GLM в LiteLLM конфиг

Файл: `/home/user/dev/llama/litellm-config.yaml`

```yaml
  - model_name: "glm-5.2"
    litellm_params:
      model: "openai/glm-5.2"
      api_base: "https://api.z.ai/api/coding/paas/v4"
      api_key: "<GLM_API_KEY>"   # из env: GLM_API_KEY (z.ai / ZhipuAI)
```

GLM API key находится в env процесса Hermes (не в .env файле):
```bash
# Найти через process tree
cat /proc/$(pgrep -f "hermes" | head -1)/environ | tr '\0' '\n' | grep GLM_API_KEY
```

### 3. Перезапустить контейнеры

```bash
docker restart litellm        # подхватить новый litellm-config.yaml
docker restart hermes-gateway  # подхватить новый config.yaml
```

### 4. Проверить

```bash
# LiteLLM видит GLM
curl -s http://localhost:4000/v1/models -H "Authorization: Bearer *** | grep glm

# Gateway → LiteLLM → DeepSeek (streaming)
GATEWAY_KEY=$(docker exec hermes-gateway env | grep API_SERVER_KEY | cut -d= -f2)
curl -X POST http://localhost:18649/v1/chat/completions \
  -H "Authorization: Bearer *** \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}],"stream":true}'
# → data: {"delta":{"content":"Hey there"}}...

# Gateway → LiteLLM → GLM
curl -X POST http://localhost:18649/v1/chat/completions \
  -H "Authorization: Bearer *** \
  -d '{"model":"glm-5.2","messages":[{"role":"user","content":"hi"}],"stream":true}'
```

## Docker networking

- `localhost` внутри Docker = контейнер, НЕ хост
- Доступ к хосту из контейнера: `172.17.0.1` (Docker bridge gateway)
- Проверка: `docker exec hermes-gateway curl -s http://172.17.0.1:4000/health`
- `host.docker.internal` может НЕ работать на Linux (только Docker Desktop)

## .env файлы

### Gateway (.env → /opt/data/.env)
```
API_SERVER_ENABLED=true
API_SERVER_KEY=eb7324...a966     # ← этот ключ использует приложение
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=18649
LLAMA_CPP_API_KEY=***           # legacy, не используется с LiteLLM
LITELLM_API_KEY=***             # ← ключ для LiteLLM
```

### LiteLLM (Docker container, config mounted)
- Конфиг: `/home/user/dev/llama/litellm-config.yaml` → `/app/config.yaml`
- Master key: `sk-local` (в `general_settings.master_key`)
- БД: `postgresql://litellm:***@litellm-db:5432/litellm`

## socat мост

Gateway на :18649, SSH туннель на :8643. socat соединяет:
```bash
socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:18649 &
```

Запускать в background (terminal background=true), НЕ nohup.
