---
name: hermes-android-gui
description: "Develop, build, deploy, and debug the Hermes Android companion app — voice chat, agent/persona management, multi-URL connectivity, ADB workflows."
version: 1.0.0
author: Pavel + Hermes Agent
license: MIT
platforms: [linux, android]
metadata:
  hermes:
    tags: [android, voice, kotlin, compose, adb, audio, hermes-gui]
    related_skills: [hermes-agent, opencode]
---

# Hermes Android GUI

Android-приложение (Kotlin + Jetpack Compose) для общения с Hermes Agent. Поддерживает текстовый чат (SSE), голосовой чат (STT → LLM → TTS, toggle-цикл), 15 персон, 10 agent presets, multi-URL с авто-fallback.

**Проект:** `/home/user/dev/Opencode/`

## ДВА РАЗНЫХ КОНЦЕПТА: Agent Presets vs Personas

**Agent presets** (из `~/.hermes/hermes-agent/agent/agents.py`) — это инструменты/возможности:
general, build, plan, review, safe, explore, scout, deep-explore, claw, composter.
Меняют system prompt + доступные tools + permission policy + reasoning effort.
**НИКОГДА не удалять, не заменять, не выдумывать новые.** Только из agents.py.

**⚠️ Реальные серверные пресеты (8):** general, build, plan, explore, scout, deep-explore, claw,
composter. `review` и `safe` — есть только в Constants.AGENTS приложения (отсутствуют
в `_BUILTIN_AGENTS` серверного `agents.py`).

**Механизм смены пресета (реализован 2026-06-29):**

1. **Кнопка 🤖 в BottomToolbar** — показывает эмодзи + имя активного пресета (🤖 General, 🔨 Build, 🧠 Plan...)
2. Тап → открывается диалог `AgentSelector` (список из 10 пресетов из `Constants.AGENTS`)
3. При выборе:
   - Локально сохраняется `selectedAgent` в SharedPreferences
   - **Сервер активируется** через `POST /v1/agents/activate {"id": "<agent_id>"}`
   - **Следующее сообщение** уходит с полем `agent_id` в `ChatRequest` → сервер вызывает `apply_agent()`:
     меняет toolsets, reasoning, model, system_prompt, permissions — **полноценно**

4. **Хардкод-промпты из `Constants.AGENT_PROMPTS` больше НЕ используются** — `ChatViewModel` не
   вставляет однострочные промпты «You are the Build agent...». Вся логика на сервере.

**Файлы, участвующие в агенте:**
| Файл | Роль |
|------|------|
| `NavGraph.kt` | Кнопка 🤖 в BottomToolbar + диалог AgentSelector |
| `AgentSelector.kt` | UI диалога выбора (уже существовал) |
| `ChatRequest.kt` | Поле `agentId: String?` — передаётся в API |
| `ChatRepository.kt` | Методы `getAgents()`, `activateAgent()` |
| `HermesApi.kt` | Эндпоинты `GET /v1/agents`, `POST /v1/agents/activate` |
| `AgentDto.kt` | DTO для ответов API агентов |
| `ChatViewModel.kt` | Метод `activateAgent()`; **убраны** хардкод-промпты |

**Серверные API эндпоинты (в `api_server.py`):**
- `GET /v1/agents` — список пресетов (34 агента: built-in + disk)
- `POST /v1/agents/activate {"id":"<agent_id>"}` — активация с персистентностью по `session_key`
- `agent_id` в `POST /v1/chat/completions` — применение `apply_agent()` при создании агента

## Model Selector — кнопка в TopAppBar (2026-07-14)

Кнопка выбора модели — FilterChip в `actions` топ-бара, слева от шестерёнки настроек.

**Файлы:**
| Файл | Роль |
|------|------|
| `NavGraph.kt` | FilterChip в TopAppBar `actions` + `showModelSelector` state + диалог ModelSelector |
| `ModelSelector.kt` | AlertDialog со списком моделей из `Constants.MODELS` |
| `Constants.kt` | Список `MODELS` — 8 моделей с эмодзи |
| `SettingsDataStore.kt` | `DEFAULT_MODEL = "deepseek-chat"`, `selectedModel` в SharedPreferences |
| `SettingsViewModel.kt` | `updateSelectedModel()` + `toggleBackend()` меняет модель |
| `ChatViewModel.kt` | `ensureConversation()` исправляет модель если не соответствует backend |

**UI:**
- FilterChip показывает имя активной модели: `⚡ DeepSeek Chat`, `✨ GLM 5.2`, etc.
- Тап → AlertDialog со списком всех моделей
- Выбор → `settingsViewModel.updateSelectedModel(id)` → сохраняется в SharedPreferences
- Следующее сообщение уходит с новой моделью

**Доступные модели (Constants.MODELS):**
```
🤖 Hermes Agent (авто)   — hermes-agent
⚡ DeepSeek Chat          — deepseek-chat
🧠 DeepSeek Reasoner (R1) — deepseek-reasoner
💨 DeepSeek V4 Flash      — deepseek-v4-flash
🔧 DeepSeek V4 Pro        — deepseek-v4-pro
✨ GLM 5.2                — glm-5.2
🔵 GPT 4.1                — gpt-4.1
🔷 GPT 4.1 Mini           — gpt-4.1-mini
```

**Питфол:** `toggleBackend()` в SettingsViewModel хардкодит модель при переключении H↔OC+. При смене дефолтной модели — обновить ВСЕ хардкоды: `SettingsViewModel.toggleBackend()`, `ChatViewModel.ensureConversation()`, `SettingsDataStore.DEFAULT_MODEL`, `Constants.DEFAULT_MODEL`.

**Питфол:** `pm clear` обязателен при смене `DEFAULT_MODEL` — старое значение из SharedPreferences перекрывает новый дефолт.

## Personas (15 штук из `~/.hermes/config.yaml` → `personalities:`) — это стиль/тон:
стандартный, технический, краткий, креативный, нуар, шекспир, пират, neko-chan...
Выбираются отдельной кнопкой в BottomToolbar. Меняют ТОЛЬКО system prompt (стиль ответа).
Не влияют на доступные инструменты.

**Правило:** никогда не путать. Agent presets ≠ personas.

**Подробный анализ разрыва** приложение↔сервер: `references/agent-preset-switching.md` — полная архитектура смены пресетов на всех поверхностях (Desktop, TUI, CLI, Gateway, REST API, Android), код `apply_agent()`, таблица серверных пресетов, варианты исправления для Android. Пользователь явно исправлял:
«это прикольно, но мне нужны agent presets которые берут skills, траектории и системные промпты».

## Быстрый старт

**Порядок: бэкенд → bridge → build → install → verify**

```bash
# 0. Бэкенд жив? (Docker Gateway на 18649)
curl -s http://localhost:18649/health

# 1. Мост 8643→18649 (если порты отличаются)
socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:18649 &  # background!

# 2. SSH туннель VPS (для сотовой связи)
ssh -R 0.0.0.0:8643:localhost:8643 root@<YOUR_VPS_IP> "while true; do sleep 30; done" &  # background!

# 3. Health с телефона
adb shell "/system/bin/curl -s http://<YOUR_VPS_IP>:8643/health"

# 4. Clean build (без кеша — важно!)
cd /home/user/dev/Opencode
rm -rf app/build && ./gradlew assembleDebug --no-build-cache

# 5. Установка + разрешения + запуск
ADB=/home/user/Android/Sdk/platform-tools/adb
$ADB install -r app/build/outputs/apk/debug/app-debug.apk
$ADB shell pm grant com.hermes.gui.debug android.permission.RECORD_AUDIO
$ADB shell pm grant com.hermes.gui.debug android.permission.POST_NOTIFICATIONS
$ADB shell am start -n com.hermes.gui.debug/com.hermes.gui.MainActivity

# 6. Если менялся DEFAULT_API_KEY — ОБЯЗАТЕЛЬНО pm clear ДО install
# $ADB shell pm clear com.hermes.gui.debug

# 7. Verify: должен быть 200 OK
$ADB logcat --pid=$($ADB shell pidof com.hermes.gui.debug) -d | grep -E "200 OK|401|Connection reset"
```

## Архитектура (актуальная)

```
Android App (телефон)
├── Chat (SSE) ─────────────► Hermes API (localhost:8643 → ADB reverse → PC:8642)
├── Voice STT ──────────────► Android SpeechRecognizer (Google, on-device, fast)
├── Voice TTS ──────────────► Android TextToSpeech (Google TTS, on-device, neural)
├── Personas (15) ──────────► system prompt (стиль)
├── Agent Presets (10) ─────► 🤖 кнопка в BottomToolbar → POST /v1/agents/activate → apply_agent()
└── HealthCheckManager ─────► авто-fallback WiFi↔мобильная сеть (multi-URL)
```

**STT/TTS — ТОЛЬКО on-device.** Server-side whisper и Piper TTS через прокси НЕ использовать:
- faster-whisper на Jetson ARM64: 4 сек задержка, модель medium
- Piper/ExoPlayer/MediaPlayer/AudioTrack: ВСЕ провалились на Honor API 36
- Android SpeechRecognizer + TextToSpeech — единственный надёжный путь

## ADB reverse — ОСНОВНОЙ способ подключения (локальный, без туннелей)

```bash
ADB=/home/user/Android/Sdk/platform-tools/adb
$ADB reverse tcp:8643 tcp:8643   # Chat: phone:8643 → socat:8643 → OpenCode API :8646
$ADB reverse tcp:8647 tcp:8647   # Voice proxy (опционально)
$ADB reverse tcp:8089 tcp:8089   # OpenAI relay (опционально)
```

Phone использует `http://localhost:8643` → ADB пробрасывает на ПК.
ADB reverse сбрасывается при переподключении USB — перезапускать.

### Тестирование сотовой связи САМОСТОЯТЕЛЬНО

Телефон на сотовой сети (WiFi OFF), ADB по USB. Агент тестирует сам — НЕ перекладывать на пользователя:

```bash
# Проверить что телефон на сотовой (rmnet_data* = cellular)
$ADB shell "ip addr show wlan0 | grep -q NO-CARRIER && echo CELLULAR || echo WIFI"

# Тест API
$ADB shell "/system/bin/curl -s -m 5 http://localhost:8643/health"
# → {"status":"ok","platform":"opencode+","agent_count":10}
```

**Питфол:** ADB reverse может показываться как "UsbFfs" вместо "tcp" — перезапустить reverse при сомнениях.

### Детектирование системных диалогов (permission prompts)

Системные диалоги Android (запросы разрешений — микрофон, файлы) блокируют UI и НЕ видны в `adb logcat`. Детектировать через `uiautomator dump`:

```bash
ADB=/home/user/Android/Sdk/platform-tools/adb
$ADB shell "uiautomator dump /sdcard/ui.xml 2>&1 && cat /sdcard/ui.xml" \
  | python3 -c "import sys,re; texts=re.findall(r'text=\"([^\"]+)\"',sys.stdin.read()); [print(t) for t in texts if t.strip()]"
```

Пример вывода: `«Разрешить приложению Hermes GUI записывать аудио?»` → понятно что блокирует.

### Bypass permission диалогов через ADB

Вместо ручного нажатия пользователем — грант разрешений через ADB:

```bash
$ADB shell pm grant com.hermes.gui.debug android.permission.RECORD_AUDIO
$ADB shell pm grant com.hermes.gui.debug android.permission.READ_EXTERNAL_STORAGE
$ADB shell pm grant com.hermes.gui.debug android.permission.WRITE_EXTERNAL_STORAGE
```

После `pm grant` диалог НЕ появляется — экономит время при отладке.

## Голосовой прокси (DEPRECATED для STT/TTS)

Proxy на порту 8647 (`voice_proxy.py`) больше НЕ используется для основных STT/TTS.
Оставлен только как fallback. Android SpeechRecognizer + TextToSpeech — основной путь.

Причина: faster-whisper на Jetson ARM64 медленный (4 сек), Piper/ExoPlayer/AudioTrack
не работают на Honor API 36. On-device Google STT/TTS — мгновенно и надёжно.

## Голос: Android TextToSpeech — единственный надёжный способ

ExoPlayer, MediaPlayer и AudioTrack ВСЕ провалились на устройстве Павла (Honor API 36). Использовать ТОЛЬКО Android TextToSpeech:

```kotlin
val tts = TextToSpeech(context) { status ->
    if (status == TextToSpeech.SUCCESS) { /* ready */ }
}
tts.setLanguage(Locale("ru"))
tts.setSpeechRate(0.9f)
tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
    override fun onDone(id: String?) { /* playback complete */ }
    override fun onError(id: String?) { /* retry */ }
})
tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tts_id")
```

**Питфол:** `com.google.android.tts` может быть заморожен — проверять `adb logcat | grep freezing.*tts`.
**Питфол:** НЕ использовать Thread.sleep для ожидания инициализации TTS — использовать suspendCancellableCoroutine.

## Голосовой цикл в ChatViewModel (toggle-режим, авто-цикл)

Пользователь жмёт 🎙️ → voice mode ON:
1. `startListening()` — Android SpeechRecognizer, on-device, мгновенно
2. `onResults` → `sendMessage(text)` — отправка в Hermes API (SSE streaming)
3. SSE Done → **сохранить `responseText` ДО `finalizeMessage()`** (critical bug!)
4. `synthesizeAndPlay(responseText)` — Android TTS.speak(), on-device
5. После playback → авто-рестарт `startListening()` (цикл)
🎙️ Tap again → voice mode OFF, TTS.stop()

**Статус-бар фазы (обязательно):**
- "🎙️ Слушаю..." (красный) — активное распознавание
- "🧠 Думаю..." (фиолетовый) — LLM обрабатывает
- "🔊 Отвечаю..." (синий) — TTS озвучка

**Кнопка 🔊/🔇 в BottomToolbar:** останавливает TTS мгновенно (tts.stop()),
меняет иконку. Пользователь различает «голосовые сообщения» (запись — плохо)
и «голосовой чат» (toggle → авто-цикл — хорошо).

## Сборка: баги и решения

| Проблема | Решение |
|----------|---------|
| AAPT2 не запускается (ARM64) | QEMU wrapper: `/home/user/Android/Sdk/platform-tools/adb` |
| Gradle кеш отдаёт старый код | `rm -rf app/build && ./gradlew assembleDebug --no-build-cache` |
| KSP падает с NonExistentClass | Файл повреждён — перезаписать полностью через write_file |
| 39 tasks up-to-date, но код старый | `--no-build-cache` + `rm -rf app/build` |
| APK не устанавливается (подпись) | Использовать debug-сборку: `assembleDebug` |
| `adb: device unauthorized` | На телефоне: отозвать разрешения отладки, переподключить USB |

## Hermes Gateway API — два режима: Docker vs Native

**Native Gateway (рекомендуется для управления ПК):** прямой запуск на хосте, порт 8643, полный доступ
к файлам/Docker/GPU. Подробнее: `references/native-gateway-setup.md` — конфиг, запуск, миграция.

**Docker Gateway (изоляция):** контейнер `hermes-gateway` на порту 18649, socat мост 8643→18649.
Агент работает внутри контейнера → НЕ видит хост-файлы и процессы.

Выбор: нужен контроль ПК с телефона → Native. Нужна изоляция/портабельность → Docker.

## Docker Gateway — детали

### Docker Gateway — архитектура подключения

```
Phone → VPS:8643 (SSH reverse tunnel) → Jetson:8643 (socat) → Docker:18649 (Gateway)
                                                                ↓
                                                    custom:litellm → 172.17.0.1:4000 (LiteLLM)
                                                                    ↓
                                                    deepseek-chat, glm-5.2, gpt-4.1, etc.
```

- **Gateway порт:** 18649 (из `.env`: `API_SERVER_PORT=18649`)
- **socat мост:** 8643→18649 (для совместимости с SSH туннелем)
- **LiteLLM:** Docker контейнер `litellm` на :4000, конфиг `/home/user/dev/llama/litellm-config.yaml`
- **Docker→host сеть:** контейнер обращается к хосту через `172.17.0.1` (НЕ `localhost`!)

### API ключ Gateway

Ключ берётся из `.env` файла, НЕ из config.yaml:
```bash
docker exec hermes-gateway env | grep API_SERVER_KEY
# API_SERVER_KEY=eb7324...a966
```

Этот ключ должен совпадать с `DEFAULT_API_KEY` в `SettingsDataStore.kt`. Если ключ меняется — обновить в коде И сделать `adb shell pm clear` (SharedPreferences кеширует старый).

### Docker Gateway → LiteLLM (модельный роутинг)

Когда локальные llama-servers (8101-8103) не запущены, Gateway должен указывать на LiteLLM:

```yaml
# /home/user/.hermes-portable/config.yaml
model:
  provider: custom:litellm
  default: deepseek-chat
  context_length: 131072

custom_providers:
  - name: litellm
    base_url: http://172.17.0.1:4000/v1    # Docker → host через bridge gateway
    api_mode: chat_completions
    key_env: LITELLM_API_KEY               # из .env: LITELLM_API_KEY=***
    models:
      deepseek-chat: { context_length: 65536 }
      deepseek-reasoner: { context_length: 65536 }
      glm-5.2: { context_length: 131072 }
      gpt-4.1: { context_length: 1047576 }
```

**Питфол:** `localhost:8092` внутри Docker = контейнер, НЕ хост. Использовать `172.17.0.1:4000` для LiteLLM на хосте.
**Питфол:** После изменения config.yaml — `docker restart hermes-gateway`. После изменения litellm-config.yaml — `docker restart litellm`.
**Питфол:** Пустой SSE-ответ (`responseText length=0`, `completion_tokens: 0`) = Gateway не может достучаться до model backend. Проверить `docker logs hermes-gateway --tail 50` на `APIConnectionError`.

### Запуск (Docker)

```bash
# Gateway уже в Docker — просто перезапустить при изменении конфига
docker restart hermes-gateway

# Проверить
curl http://localhost:18649/health
# → {"status": "ok", "platform": "hermes-agent"}

# socat мост 8643→18649 (для SSH туннеля)
socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:18649 &  # background=true!
```

**Питфол:** socat в foreground terminal нельзя запускать с `&` — использовать `terminal(background=true)`.
**Питфол:** Gateway логирует в `docker logs hermes-gateway`. Если api_server не запустился — смотреть там.

### Когда нет ответа: диагностика

```bash
# 1. Hermes Gateway жив?
curl http://localhost:18649/health

# 2. Gateway может достучаться до модели? (ПРОВЕРИТЬ docker logs!)
docker logs hermes-gateway --tail 50 | grep -i "error\|fail\|connection"
# → "APIConnectionError" = model backend недоступен (localhost:8092 мёртв?)

# 3. LiteLLM работает?
curl -s http://localhost:4000/v1/models -H "Authorization: Bearer *** | grep '"id"'

# 4. Тест чата через Gateway (с правильным ключом из .env)
GATEWAY_KEY=$(docker exec hermes-gateway env | grep API_SERVER_KEY | cut -d= -f2)
curl -X POST http://localhost:18649/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GATEWAY_KEY" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}],"stream":true}'

# 5. Инструменты доступны?
curl http://localhost:18649/v1/toolsets -H "Authorization: Bearer $GATEWAY_KEY"
```

### Hermes Gateway vs Unified Proxy — правило выбора

**Hermes Gateway API** — когда нужен НАСТОЯЩИЙ Hermes (инструменты, память, MCP). Порт 8643 или 8648, один процесс.

**Unified Proxy** — временный костыль когда нужно маршрутизировать между Hermes и OpenCode+. Держать ТОЛЬКО пока OC+ нужен. Убрать как только OC+ отключён.

**ПРИОРИТЕТ: свой VPS с SSH reverse tunnel.** Самый быстрый, надёжный и стабильный способ.
Не требует сторонних сервисов, URL постоянный.

```bash
# На VPS (<YOUR_VPS_IP>): включить GatewayPorts в /etc/ssh/sshd_config
sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config
systemctl reload sshd

# Копировать SSH ключ для безпарольного доступа
ssh-copy-id root@<YOUR_VPS_IP>

# Туннель: VPS:8643 → Jetson:8643 (запускать на Jetson)
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
    -R 0.0.0.0:8643:localhost:8643 root@<YOUR_VPS_IP> \
    "while true; do sleep 30; done"
```

**URL приложения:** `http://<YOUR_VPS_IP>:8643` — НЕ меняется никогда.

**Watchdog:** НЕ использовать shell-скрипты с `pkill -f "ssh.*8643"` — паттерн убивает СВОЙ терминал если команда содержит `ssh.*8643`. Использовать Python `tunnel_keeper.py` (см. `scripts/tunnel_keeper.py`) или простой bash-луп `tunnel_keeper.sh` который проверяет здоровье через `curl` на VPS а не парсит процессы. Python-версия надёжнее: использует `subprocess.Popen` для старта ssh, `pkill` ТОЛЬКО по точному паттерну `ssh.*-R.*REMOTE_PORT.*VPS_HOST`.

**Важно:** чистить зомби-туннели на VPS при каждом реконнекте:
```bash
ssh root@<YOUR_VPS_IP> "ss -tlnp | grep 8643 | grep -oP 'pid=\K\d+' | xargs -r kill"
```

**Важно:** чистить зомби-туннели после перезапусков watchdog:
```bash
LATEST=$(pgrep -f "ssh.*-R.*8643" | tail -1)
for pid in $(pgrep -f "ssh.*-R.*8643"); do
    [ "$pid" != "$LATEST" ] && kill $pid
done
```
**Важно:** НЕ трогать существующие сервисы на VPS (sing-box VPN на :443, nginx и т.д.).

**Преимущества перед cloudflared/serveo/localhost.run:**
- 🚀 Пинг 0.3ms (свой сервер в датацентре)
- 🔒 SSH/TCP — не умирает как cloudflared (QUIC блокируется ISP, HTTP2 тоже падает)
- ♾️ URL постоянный — не меняется при перезапуске (в отличие от serveo/trycloudflare)
- 🏠 Никаких сторонних сервисов

**Альтернативы (НЕ использовать без крайней необходимости):**

| Сервис | Причина отказа |
|--------|---------------|
| cloudflared | QUIC блокируется ISP, HTTP2 умирает через минуты |
| serveo.net | URL меняется при реконнекте → 502 |
| localhost.run | Медленно (AWS Virginia, 1000ms+), URL меняется |
| pinggy.io | 60-минутный лимит без авторизации |

**NEVER test cellular by asking the user.** Test via ADB:
```bash
ADB=/home/user/Android/Sdk/platform-tools/adb
$ADB shell "/system/bin/curl -s -m 5 http://<YOUR_VPS_IP>:8643/health"
# Phone on cellular (rmnet_data*) — this IS testing cellular.

## OpenCode+: кнопка переключения в BottomToolbar

Кнопка 🔌 с подписью `H` или `OC+` в BottomToolbar — переключает режим бэкенда (hermes ↔ opencode).
Цвет кнопки = цвет индикатора соединения (зелёный/красный).
Нажатие → `settingsViewModel.toggleBackend()` → меняет `backendMode` в AppSettings.

Иконка: `Icons.Default.Sync`. Режим сохраняется в `regularPrefs["backend_mode"]`.

**2026-06-13: unified proxy.** Оба режима используют ОДИН URL (`http://<YOUR_VPS_IP>:8643`), маршрутизация по модели идёт на сервере (через `unified_proxy.py`). Переключатель меняет список моделей и агентов в UI, но не URL.

## Unified Proxy (один URL для всего)

Прокси (`/home/user/unified_proxy.py` на порту 8647) маршрутизирует по модели:
- **Chat models** (deepseek-chat, openai/qwen3.6-35b-heretic, gpt-4o...) → LiteLLM (127.0.0.1:4000)
- **Agent models** (hermes-agent, general, build, plan...) → OpenCode+ API (127.0.0.1:8646)

socat пробрасывает 8643 → 8647. Один SSH-туннель, один порт, умная маршрутизация.

**Запуск:**
```bash
python3 /home/user/unified_proxy.py 8647 &
socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:8647 &
```

**Питфол:** старые socat-циклы (while true; socat 8643→8646) могут перезапустить НЕПРАВИЛЬНЫЙ socat после pkill. Убивать и цикл тоже: `pkill -f "while true.*socat.*8643"`.

**Питфол:** LiteLLM требует ключ `sk-local` в заголовке `Authorization`. Прокси добавляет его для chat-моделей, для agent-моделей пробрасывает оригинальный ключ клиента.

**Модель по умолчанию для H:** `deepseek-chat` (через LiteLLM, cloud). Раньше была `qwen3.6-35b-heretic` (локальный llama-server), но локальные сервера часто не запущены. Cloud-модели (deepseek, GLM) стабильнее и доступны всегда.

## step_start / protocol events — как НЕ надо фильтровать

OpenCode+ API иногда возвращает `step_start` JSON в `delta.content` вместо текста. Это протокол агента.

**Что НЕ работает (испытано, приводит к багам):**
1. **SseClient buffer filter** (отслеживание `{...}` с brace depth) — застревает, блокирует ВЕСЬ вывод, ответ = 1 символ
2. **ChatViewModel filterProtocolJson** на accumulated content — удаляет весь ответ когда он = чистый протокол
3. **connectionPool(0)** — ломает SSE, каждый запрос падает с "unexpected end of stream"

**Что работает (текущее решение):**
В `SseEvent.Done` handler: если `responseText` начинается с `"type":"step_start"` и не содержит `"content":` → заменить на «Агент не ответил. Попробуйте ещё раз.»

```kotlin
is SseEvent.Done -> {
    val responseText = collectedContent.toString()
    val displayText = if (responseText.isNotBlank() &&
        responseText.trimStart().startsWith("{\"type\":\"step_start\"") &&
        !responseText.contains("\"content\":")) {
        "Агент не ответил. Попробуйте ещё раз."
    } else { responseText }
    finalizeMessage(conversationId, displayText)
}
```

Это сохраняет нормальные ответы и заменяет чистый протокол на понятное сообщение.

## OkHttp: `retryOnConnectionFailure(true)` — CRITICAL

**Без этого флага** OkHttp переиспользует закрытые сервером соединения → «unexpected end of stream» на КАЖДОМ ВТОРОМ сообщении.

Паттерн: первое сообщение открывает новое соединение — работает. Сервер шлёт `Connection: close` после SSE-потока. Второе сообщение переиспользует тот же сокет → ошибка. Третье — опять работает (новое соединение).

**Исправление в `AppModule.kt`:**
```kotlin
OkHttpClient.Builder()
    .retryOnConnectionFailure(true)  // ← ВОТ ЭТО
    .connectTimeout(30, TimeUnit.SECONDS)
    .readTimeout(120, TimeUnit.SECONDS)
    .build()
```

**Связанное:** при `SseEvent.Error` с частичным контентом — вызывать `finalizeMessage()` чтобы сохранить накопленный текст + добавить retry на уровне ChatRepository (см. `references/sse-retry-pattern.md`):
```kotlin
is SseEvent.Error -> {
    val partialText = collectedContent.toString()
    if (partialText.isNotBlank()) {
        finalizeMessage(conversationId)
    }
    _uiState.update { it.copy(isStreaming = false, error = event.message) }
}
```

**connectionPool(0) — НЕ использовать.** `connectionPool(0, 1, MILLISECONDS)` делает ХУЖЕ: каждое соединение закрывается немедленно, SSE-потоки обрываются на первом же запросе. Правильное решение: `retryOnConnectionFailure(true)` + retry в ChatRepository при обрыве потока (см. `references/sse-retry-pattern.md`).

**OpenCode protocol events в чате:** API иногда возвращает `step_start`/`sessionID` JSON посимвольно в `delta.content`. Фильтровать через SseClient buffer (см. `references/protocol-event-filter.md`): буфер с отслеживанием скобок, строк и escape-символов. ChatViewModel-фильтр НЕ использовать — он удаляет весь контент когда ответ = чистый протокол.

## Honor/Huawei: Log.d() не работает — использовать Log.i()

Honor (Huawei) устройства используют `hilogd` параллельно с AOSP `logd`. Системное свойство `hilog.tag=I` подавляет ВСЕ `Log.d()` и `Log.v()` вызовы. Per-tag `setprop log.tag.*` не помогает — hilogd фильтрует первым.

**Правило для Андроид-кода:**
```kotlin
// ❌ НЕ использовать:
Log.d("ChatVM", "message")

// ✅ ИСПОЛЬЗОВАТЬ:
Log.i("ChatVM", "message")  // info level — доходит до logcat
```

**Чтение логов с Honor устройства:**
```bash
# По PID приложения (гарантированно захватывает все логи)
adb logcat --pid=$(adb shell pidof com.hermes.gui.debug)
# НЕ использовать: adb logcat -s ChatVM:D — покажет пустоту
```

## Docker Gateway: API key и порт (когда Gateway в Docker)

Когда Hermes Gateway работает в Docker-контейнере (`hermes-gateway`), конфигурация отличается от локальной:

- **HERMES_HOME** внутри контейнера = `/opt/data` (не `~/.hermes`)
- **API ключ** — в `/opt/data/.env` как `API_SERVER_KEY=<key>`, НЕ в config.yaml. config.yaml содержит комментарий: `# api_server settings come from .env`
- **Порт** — в `.env` как `API_SERVER_PORT=18649` (может отличаться от 8643)

### Найти ключ Gateway в Docker

```bash
docker exec hermes-gateway env | grep API_SERVER
# или
docker exec hermes-gateway cat /opt/data/.env | grep API_SERVER
```

### Синхронизация ключа с приложением

Ключ Gateway (`API_SERVER_KEY` из `.env`) ДОЛЖЕН совпадать с `DEFAULT_API_KEY` в `SettingsDataStore.kt`. Если не совпадает → `401 Unauthorized` в logcat.

**После изменения `DEFAULT_API_KEY` в коде ОБЯЗАТЕЛЬНО `pm clear`:**
```bash
adb shell pm clear com.hermes.gui.debug
```
Иначе зашифрованный SharedPreferences (`hermes_secure_prefs.xml`) отдаёт старый ключ, который переопределяет новый дефолт. Пересборка APK без `pm clear` НЕ помогает — SharedPreferences переживает переустановку.

### Мост портов (Gateway порт ≠ порт приложения)

Если Gateway слушает на 18649, а приложение/туннель ожидает 8643 — поднять socat мост:
```bash
socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:18649 &
```
Запускать в background terminal (долгоживущий процесс).

## Полный цикл деплоя: чеклист

Правильный порядок — **сначала бэкенд, потом приложение**:

1. **Бэкенд жив?** `curl -s http://localhost:<gateway_port>/health`
2. **Мост/туннель?** socat если порты отличаются, SSH reverse туннель для VPS
3. **Health с телефона?** `adb shell "/system/bin/curl -s http://localhost:8643/health"` (или VPS URL)
4. **Ключ синхронизирован?** `DEFAULT_API_KEY` в SettingsDataStore.kt = `API_SERVER_KEY` в Docker .env
5. **THEN** clean build → install → pm clear (если ключ менялся) → grants → launch
6. **Verify:** `adb logcat | grep -E "200 OK|401|Connection reset"` — должен быть 200

## Pitfalls

- **pkill в foreground = убивает терминал.** НИКОГДА не использовать `pkill -f` в foreground terminal. Использовать `fuser -k PORT/tcp` для освобождения портов, `kill PID` для конкретных процессов. При необходимости массового kill — background terminal или process API.
- **SharedPreferences кеширует старые значения.** После смены дефолтов в `AppSettings` старые сохранённые значения из SharedPreferences переопределяют новые дефолты. Использовать `adb shell pm clear com.hermes.gui.debug` для сброса. В коде: `ensureConversation()` должен проверять и исправлять неконсистентные настройки (модель не того бэкенда).
- **ТЕСТИРОВАТЬ САМОСТОЯТЕЛЬНО перед «готово».** НИКОГДА не говорить «работает» пока не проверено через `adb shell curl` с телефона. Пользователь явно требует: «почему ты не протестировал?», «важно протестировать самому». Тест с ПК (curl localhost) НЕ равен тесту с телефона.
- **`pm clear` ОБЯЗАТЕЛЕН при смене DEFAULT_API_KEY.** Зашифрованный SharedPreferences (`hermes_secure_prefs.xml`) переживает переустановку APK. Без `pm clear` старый ключ перекрывает новый дефолт → 401 Unauthorized. Симптом в logcat: `Authorization: Bearer <старый_ключ>` + `<-- 401 Unauthorized`.
- **Проверять бэкенд ДО запуска приложения.** Запустить health check на порту приложения (8643) до `am start`. Если health fail — чинить бэкенд (socat/туннель/Gateway), потом запускать приложение. Иначе приложение стучится в закрытый порт → `Connection reset` в logcat.
- **Docker Gateway .env — источник правды для API_SERVER_KEY.** НЕ искать ключ в config.yaml (там только комментарий `# comes from .env`). Искать: `docker exec hermes-gateway env | grep API_SERVER`.
- **Телефон на сотовой — тестировать через ADB.** WiFi OFF, cellular ON. `adb shell curl` идёт через сотовую сеть телефона. Это И ЕСТЬ самостоятельное тестирование сотовой связи.
- **НИКОГДА не выдумывать agent presets которых нет в `agent/agents.py`** — пользователь явно исправлял: «у меня в hermes нету таких агентов». Реальные серверные пресеты (8): general, build, plan, explore, scout, deep-explore, claw, composter. `review` и `safe` — есть только в Constants.AGENTS приложения (отсутствуют в `_BUILTIN_AGENTS`).
- **Agent presets ≠ personas.** Presets = инструменты из agents.py (священные, не удалять). Personas = стиль из config.yaml (15 штук). Два разных селектора в BottomToolbar.
- **Не патчить промпты в клиенте когда проблема на сервере** — «не надо менять системный промпт. надо решать корневую проблему». Искать корень, не маскировать.
- **Один диалог на backend** — `ensureConversation()` должен переиспользовать последний диалог для текущего backendMode (getConversationsByMode), а не создавать новый при каждом запуске. Иначе плодятся пустые диалоги.
- **Архивные диалоги: loadConversation()** — при навигации на `chat/{convId}` ChatScreen должен вызывать `viewModel.loadConversation(convId)` через `LaunchedEffect(conversationId)`. Без этого диалоги из списка не открываются.
- **Gradle кеш на ARM64** — всегда `rm -rf app/build && --no-build-cache` при изменениях кода
**Питфол:** ADB reverse сбрасывается при переподключении USB — перезапускать. Перед любым тестом с телефона ВСЕГДА проверять: `adb reverse --list` (должно показывать tcp:8643 и tcp:8647), затем `adb shell "/system/bin/curl -s http://localhost:8643/health"`. Если health fail — `adb reverse` не восстановлен → перезапустить все 3 reverse-порта.
- **Python TCP proxy надёжнее socat** — socat умирает без watchdog
- **Перед выбором тунельного сервиса — СПРОСИТЬ про VPS.** Пользователь может иметь публичный сервер (<YOUR_VPS_IP>) и не упомянуть его сразу. VPS reverse SSH tunnel — быстрее, надёжнее и стабильнее любых бесплатных сервисов. 2026-06-13: агент потратил ~20 часов на перебор 7+ сервисов, а решение было в одном SSH-туннеле к своему VPS.
**Питфол:** Cloud API ключи в Docker env-переменных НЕ переживают перезапуск контейнера. Всегда добавлять ключ прямо в `litellm-config.yaml` через `api_key: "<key>"`. Симптом: после `docker restart litellm` модель возвращает 401, хотя до перезапуска работала. Проверить: `docker logs litellm --tail 20 | grep -i "auth\|401"`. Исправление: добавить `api_key` в `litellm_params` для каждой cloud-модели.
- **Локальная vLLM fallback.** Когда cloud ключи сдохли, `nvidia-smi` покажет запущенный vLLM (>80 GB GPU). Модель: `curl localhost:8000/v1/models`. Добавить как первый провайдер в `custom_providers`, сменить `model.default`. Diffusion LLM медленная (~50s/ответ), но работает 24/7.

## Cloud API key failures — silent empty responses

Когда API ключ cloud-модели истекает/блокируется, Gateway НЕ возвращает явную ошибку пользователю. Вместо этого SSE-поток приходит с `completion_tokens: 0` и пустым контентом. Симптомы в logcat:
- `SSE: [DONE] after 5 lines`
- `ChatVM: Done: responseText length=0`

**Причины и диагностика:**
```bash
# Проверить модели напрямую через LiteLLM:
for m in deepseek-chat deepseek-v4-flash glm-5.2 gpt-4.1-mini; do
  echo -n "$m: "
  curl -s -m 5 http://localhost:4000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer *** \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":false,\"max_tokens\":10}" 2>&1 | head -c 50
  echo
done
```

Типичные ошибки:
| Код | Модель | Причина | Решение |
|-----|--------|---------|---------|
| 401 | deepseek-* | Ключ заблокирован (governor) | Обновить DEEPSEEK_API_KEY |
| 429 | glm-5.2 | Rate limit (5-часовое окно) | Ждать сброса лимита |
| 500 | gpt-4.1 | OPENAI_API_KEY не задан | Добавить ключ |

**Fallback — локальная vLLM:**
Когда cloud модели недоступны, Gateway может использовать локальную vLLM:
```yaml
# config.yaml — добавить провайдер ПЕРЕД litellm:
model:
  provider: custom:vllm-local
  default: diffusiongemma-abliterated

custom_providers:
  - name: vllm-local
    base_url: http://localhost:8000/v1
    api_mode: chat_completions
    key_env: ''
    models:
      diffusiongemma-abliterated:
        context_length: 262144
  - name: litellm
    base_url: http://localhost:4000/v1
    ...
```
**Питфол:** Diffusion LLM (diffusiongemma-abliterated) — медленная: ~34s до первого токена, ~50s total. Это не баг, архитектурная особенность.

## systemd — Gateway + Tunnel автозапуск

Шаблоны сервисов: `templates/hermes-gateway.service` и `templates/hermes-tunnel.service`. Копировать в `~/.config/systemd/user/`, затем:
```bash
systemctl --user daemon-reload
systemctl --user enable hermes-gateway hermes-tunnel
systemctl --user start hermes-gateway hermes-tunnel
```

**Питфол:** `KillMode=process` и `Delegate=yes` необходимы для user-scoped systemd — без них Gateway падает с `status=216/GROUP` при каждом запуске. Симптом: `systemctl status` показывает `activating (auto-restart)` бесконечно.

**Питфол:** `setsid` безопаснее `nohup` для фонового запуска Gateway вне systemd — process group изолирована и не умирает при `kill` родительской сессии.

**Питфол:** Gateway может зависнуть в `deactivating (stop-sigterm)` при `systemctl restart` — не отвечает на SIGTERM. Решение: `systemctl --user kill hermes-gateway.service -s SIGKILL`, затем `systemctl --user start`. Симптом: `curl localhost:8643/health` = Connection refused, а `systemctl status` показывает `deactivating` десятки секунд.

- `references/silent-empty-response-diagnostic.md` — checklist: почему телефон молчит (401/429/туннель)
- `references/litellm-config-with-keys.yaml` — шаблон конфига LiteLLM с embedded ключами (НЕ env vars!)
- `scripts/voice_proxy.py` — готовая копия голосового прокси
- `references/docker-gateway-litellm-routing.md` — перенаправление Gateway на LiteLLM (Docker networking, GLM setup, .env файлы, socat мост)
- `references/native-gateway-setup.md` — Native Gateway: конфиг, запуск, миграция с Docker, полный доступ к хосту
- `references/agent-preset-switching.md` — полная архитектура: как каждая поверхность переключает agent presets, `apply_agent()`, разрыв REST API, варианты исправления
- `references/agent-api-endpoints.md` — имплементация API: добавленные эндпоинты `/v1/agents`, `/v1/agents/activate`, `agent_id` в chat completions, изменения в `api_server.py`, Android-клиент
- `references/voice-architecture.md` — полная архитектура голосового пайплайна
- `references/audio-debug-log.md` — хронология отладки аудио и список питфолов
- `references/cellular-connectivity-saga.md` — хронология отладки сотовой связи
- `references/hermes-gateway-setup.md` — настройка Hermes Gateway API (порты, pitfalls, watchdog)
- `references/sse-retry-pattern.md` — паттерн retry для обрывов SSE-потока
- `references/protocol-event-filter.md` — фильтрация OpenCode protocol events из чата
- `references/unified-proxy.md` — архитектура unified proxy (один URL, умная маршрутизация)
- `references/python-tunnel-keeper.md` — надёжный Python watchdog для SSH-туннеля
- `references/message-copy-pattern.md` — долгое нажатие для копирования сообщений
