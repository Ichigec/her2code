# Dual Backend Architecture: LiteLLM + OpenCode+

**Дата:** 2026-06-13
**Контекст:** Оба режима (H и OC+) изначально стучались в один OpenCode+ API. Ответы содержали протокольные события `step_start` вместо чистого текста.

## Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│                         Android App                               │
│  BottomToolbar: [🔄 H] [🔊] [🎭] [🤖] [📜] [🧠]                  │
│       │                                                           │
│       ├── H  → AuthInterceptor → litellmUrl + litellmKey          │
│       │         http://<YOUR_VPS_IP>:8644/v1                       │
│       │         Authorization: Bearer sk-local                     │
│       │         Модели: 44 (GPT-4o, DeepSeek, Qwen, Gemma...)     │
│       │         Ответ: чистый текст (без step_start)               │
│       │                                                           │
│       └── OC+ → AuthInterceptor → primaryUrl + apiKey             │
│                 http://<YOUR_VPS_IP>:8643/v1                       │
│                 Authorization: Bearer <YOUR_API_SERVER_KEY>                  │
│                 Агенты: 10 (general, build, plan...)               │
│                 Ответ: может содержать step_start                  │
└──────────────────────────────────────────────────────────────────┘
```

## Сетевая инфраструктура

```
Jetson:
  socat :8643 → OpenCode+ API (:8646)
  socat :8644 → LiteLLM (:4000, Docker)

VPS (<YOUR_VPS_IP>):
  sshd-session :8643 → SSH reverse → Jetson:8643
  sshd-session :8644 → SSH reverse → Jetson:8644

Телефон (сотовая связь):
  http://<YOUR_VPS_IP>:8643 → OpenCode+
  http://<YOUR_VPS_IP>:8644 → LiteLLM
```

## Ключевые файлы

| Файл | Изменение |
|------|-----------|
| `SettingsDataStore.kt` | Добавлены `litellmUrl`, `litellmKey`, `backendMode` |
| `AuthInterceptor.kt` | Выбор URL/ключа по `backendMode` вместо `healthCheckManager.getCurrentUrl()` |
| `SettingsViewModel.kt` | `toggleBackend()` — переключение H ↔ OC+ |
| `NavGraph.kt` | BottomToolbar: кликабельная кнопка с Sync icon + подпись H/OC+ |
| `tunnel_keeper.sh` | Проброс ОБОИХ портов (8643, 8644) |

## AppSettings (итоговая структура)

```kotlin
data class AppSettings(
    val primaryUrl: String = "http://<YOUR_VPS_IP>:8643",
    val litellmUrl: String = "http://<YOUR_VPS_IP>:8644/v1",
    val fallbackUrl: String = "",
    val apiKey: String = "tfpq7h9s...",
    val litellmKey: String = "sk-local",
    val backendMode: String = "hermes",
    // ... selectedModel, selectedPersona, selectedAgent, etc.
)
```

## tunnel_keeper.sh (два порта)

```bash
#!/bin/bash
VPS="root@<YOUR_VPS_IP>"
PORTS="8643 8644"

while true; do
    for PORT in $PORTS; do
        if ! ssh -o ConnectTimeout=5 $VPS \
            "curl -s --max-time 3 http://127.0.0.1:$PORT/health | grep -q ok" 2>/dev/null; then
            for pid in $(pgrep -f "ssh.*-R.*0.0.0.0:$PORT"); do kill "$pid" 2>/dev/null; done
            ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
                -o TCPKeepAlive=yes -o ExitOnForwardFailure=yes -fN \
                -R "0.0.0.0:$PORT:localhost:$PORT" $VPS
            sleep 2
        fi
    done
    sleep 15
done
```

## Итог

- **H режим:** LiteLLM → 44 модели → чистый LLM-текст → надёжно
- **OC+ режим:** OpenCode+ → 10 агентов → с инструментами → возможен step_start
- **step_start больше не проблема в H режиме** — LiteLLM возвращает только чистый текст
