---
name: android-hermes-gui
description: "Develop, debug, and deploy the Hermes Android GUI app — voice chat, personas, agents, ADB reverse, and voice proxy."
version: 1.0.0
platforms: [linux, android]
metadata:
  hermes:
    tags: [android, gui, voice, kotlin, compose, adb]
---

# Hermes Android GUI

The Hermes Android app is a Kotlin/Jetpack Compose app that connects to the Hermes API server for text chat, voice interaction, agent switching, and persona selection. It lives at `/home/user/dev/Opencode/`.

## Project Layout

```
/home/user/dev/Opencode/
├── app/
│   ├── build.gradle.kts              # Dependencies (Compose, Hilt, Room, ExoPlayer, OkHttp)
│   └── src/main/java/com/hermes/gui/
│       ├── data/
│       │   ├── local/               # Room DB, DAOs, entities
│       │   ├── remote/              # HermesApi (Retrofit), SseClient, HealthCheckManager, VoiceRepository
│       │   │   └── dto/             # ChatRequest, VoiceDtos, etc.
│       │   ├── repository/          # ChatRepository, DialogRepository, SettingsRepository, VoiceRepository
│       │   ├── settings/            # SettingsDataStore (EncryptedSharedPreferences + regular SharedPreferences)
│       │   └── remote/interceptor/  # AuthInterceptor (URL rewrite + Bearer token)
│       ├── di/                      # AppModule (Hilt DI)
│       ├── domain/model/            # Message, Conversation, Toolset, AgentPreset
│       ├── ui/
│       │   ├── chat/               # ChatScreen, ChatViewModel, ChatUiState, ChatInputBar
│       │   │   └── components/      # MessageBubble, ModelSelector, PersonaSelector, AgentSelector,
│       │   │                           VoiceInputButton, VoiceStatusBar, WaveformIndicator
│       │   ├── dialogs/            # DialogListScreen, DialogListViewModel
│       │   ├── navigation/         # NavGraph (Scaffold + TopAppBar + BottomToolbar + NavHost)
│       │   ├── settings/           # SettingsScreen, SettingsViewModel, ApiSettingsSection
│       │   └── theme/              # Material 3 theme
│       └── util/                   # Constants (personas, agents, models, prompts)
├── voice_proxy.py                  # Python HTTP proxy: STT + TTS endpoints (port 8647)
└── voice_proxy_watchdog.sh         # Auto-restart wrapper
```

## Build & Deploy

```bash
cd /home/user/dev/Opencode
./gradlew assembleDebug                     # Build APK

# ADB is at /home/user/Android/Sdk/platform-tools/adb (QEMU wrapper for ARM64)
export ADB=/home/user/Android/Sdk/platform-tools/adb
$ADB install -r app/build/outputs/apk/debug/app-debug.apk
$ADB shell am start -n com.hermes.gui.debug/com.hermes.gui.MainActivity
```

## Voice Chat Architecture

The voice chat uses a **voice proxy** (Python HTTP server on port 8647) that wraps Hermes STT/TTS tools as simple HTTP endpoints.

### Voice Proxy (`voice_proxy.py`)

- **Port:** 8647
- **Endpoints:**
  - `GET /health` — status check
  - `POST /stt` — accepts raw audio bytes, returns `{"transcript": "..."}`
  - `POST /tts` — accepts `{"text": "..."}`, returns OGG/Opus audio binary
- **Uses:** Hermes `tools/transcription_tools.py` (faster-whisper) and `tools/tts_tool.py` (Piper)
- **Run:** `/home/user/.hermes/hermes-agent/venv/bin/python3 /home/user/dev/Opencode/voice_proxy.py`
- **Watchdog:** `bash /home/user/dev/Opencode/voice_proxy_watchdog.sh` auto-restarts every 15s

### Connection flow

```
Phone → localhost:8643 → ADB reverse → socat:8643 → OpenCode API:8646 (chat)
Phone → localhost:8647 → ADB reverse → voice_proxy:8647 → Hermes STT/TTS tools
```

**ADB reverse setup (CRITICAL — решать локально, не уходить во внешние туннели):**
```bash
$ADB reverse tcp:8643 tcp:8643   # Chat (socat → OpenCode API :8646)
$ADB reverse tcp:8647 tcp:8647   # Voice (proxy)
```

Reverse слетает при переподключении USB — перезапускать.

### Тестирование сотовой связи САМОСТОЯТЕЛЬНО

Агент должен тестировать сам, не перекладывать на пользователя. Телефон на сотовой сети (WiFi выключен), ADB по USB:

```bash
# Проверить сеть телефона (rmnet_data* = сотовая)
$ADB shell "ip addr show wlan0"    # NO-CARRIER = WiFi выключен

# Тест API с телефона на сотовой сети
$ADB shell "/system/bin/curl -s -m 5 http://localhost:8643/health"
# → {"status":"ok","platform":"opencode+","agent_count":10}
```

### Питфол: НЕ уходить в «туннельный шторм»

Пользователь хочет локальные решения. Не перебирать cloudflared → serveo → ngrok → bore → localhost.run когда ADB reverse решает задачу (при USB-подключении).

**Для сотовой связи БЕЗ USB-кабеля** нужен интернет-туннель. **Основное решение — свой VPS с SSH reverse tunnel.** Подробный обзор всех протестированных решений: [cellular-tunneling.md](references/cellular-tunneling.md).

| Туннель | Стабильность | HTTPS с телефона | Примечание |
|---------|-------------|-------------------|------------|
| **Свой VPS (SSH)** | ⭐⭐⭐⭐⭐ | ✅ HTTP | СВОЙ СЕРВЕР. URL не меняется. Пинг <1ms. |
| **localhost.run** (SSH) | ⭐⭐⭐⭐⭐ | ✅ Да | Запасной. URL привязан к SSH-ключу. |
| serveo.net (SSH) | ⭐⭐ | ❌ Нет (TLS fail) | Меняет URL при реконнекте → 502 |
| cloudflared HTTP2 | ⭐ | ❌ Нет (TLS fail) | Умирает через минуты. ISP блокирует QUIC, HTTP2 тоже нестабилен |

- **Свой VPS — приоритет №1.** Не уходить в перебор облачных сервисов когда есть VPS.
- cloudflared free tunnels: QUIC-сессия обрывается (`timeout: no recent network activity`). Даже `--protocol http2` умирает в течение минут на Jetson GB10. НЕ тратить время на отладку cloudflared — переключиться на VPS/SSH.
- serveo.net: URL меняется при каждом переподключении SSH → приложение получает 502 на старый URL. Watchdog НЕ решает проблему — URL вшит в APK.
- localhost.run: SSH-туннель (TCP), URL держится привязанным к SSH-ключу. HTTPS работает с телефона. Запасной вариант если VPS недоступен.
- Tailscale без sudo: только userspace-networking (SOCKS5), входящие НЕ работают (нет TUN-интерфейса)
- ISP блокирует входящие на residential IP — порт-форвардинг на роутере не поможет

### Voice chat UI flow

1. **Tap 🎙️** → enters voice mode (`isVoiceActive = true`)
2. Auto-cycle: `🎙️ Слушаю...` (8s AAC record) → `🧠 Думаю...` (STT + LLM) → `🔊 Отвечаю...` (TTS + ExoPlayer) → auto-restart
3. **Tap 🎙️ again** → exits voice mode
4. `VoiceStatusBar` shows current state
5. `VoiceInputButton` changes color: gray (off), primary (active), red (recording), tertiary (playing)

### Key files for voice

| File | Role |
|------|------|
| `VoiceInputButton.kt` | Mic button (tap toggle, color state, pulse animation) |
| `VoiceStatusBar.kt` | Status strip: "Слушаю...", "Думаю...", "Отвечаю..." |
| `ChatViewModel.kt` | `toggleVoice()`, `startListeningCycle()`, `synthesizeAndPlay()` |
| `VoiceRepository.kt` | AAC recording (MediaRecorder), STT/TTS via OkHttp, ExoPlayer playback |
| `voice_proxy.py` | STT `/stt` + TTS `/tts` HTTP bridge |

## Pitfalls

### OpenCode API leaks protocol events into SSE content

OpenCode API `/v1/chat/completions` может возвращать внутренние протокольные события (`step_start`, `sessionID`, `part`) как часть текстового контента ответа. Они приходят посимвольно через SSE `data:` строки, образуя полные JSON-объекты.

**❗ КРИТИЧЕСКИЙ ПИТФОЛ: `filterProtocolJson` может сделать ответ ПУСТЫМ.** OpenCode-агент иногда генерирует ТОЛЬКО протокольный JSON без текста (особенно на втором запросе или при ошибке). Фильтр вырезает всё → `responseText.isEmpty()` → сообщение не сохраняется → пользователь видит пустоту. **Всегда проверять длину после фильтрации.** Если отфильтрованный текст пуст — сохранить fallback: `"Агент не ответил. Попробуйте ещё раз."`

**Правильный подход — НЕ фильтровать в SseClient, фильтровать в ChatViewModel с fallback:**

```kotlin
// В Done-обработчике ChatViewModel:
val rawText = collectedContent.toString()
val displayText = if (rawText.isNotBlank() &&
    rawText.trimStart().startsWith("{\"type\":\"step_start\"") &&
    !rawText.contains("\"content\":")) {
    "Агент не ответил. Попробуйте ещё раз."
} else {
    rawText
}
finalizeMessage(conversationId, displayText)
```

**❗ НЕ использовать буферный state machine в SseClient.** При посимвольном стриминге buffer никогда не сбрасывается корректно если модель генерирует только JSON → весь ответ теряется → responseText length=1.

**Альтернативный подход — `filterProtocolJson()` (устарел, не рекомендуется):**

```kotlin
/** Strip OpenCode protocol JSON blobs from response text */
private fun filterProtocolJson(text: String): String {
    val sb = StringBuilder()
    var i = 0
    while (i < text.length) {
        if (text[i] == '{') {
            var depth = 1; var j = i + 1
            while (j < text.length && depth > 0) {
                when (text[j]) { '{' -> depth++; '}' -> depth-- }; j++
            }
            if (depth == 0) {
                val json = text.substring(i, j)
                if (json.contains("\"type\":\"step_start\"") ||
                    json.contains("\"sessionID\":\"ses_")) { i = j; continue } // skip
            }
        }
        sb.append(text[i]); i++
    }
    return sb.toString()
}
```

Применять в двух местах:
```kotlin
// При стриминге — фильтровать для UI
collectedContent.append(event.text)
val displayText = filterProtocolJson(collectedContent.toString())
_uiState.update { it.copy(streamingContent = displayText) }

// При сохранении — фильтровать для БД
val content = filterProtocolJson(collectedContent.toString())
```

**Альтернативный подход — буферный state machine в SseClient:** (сложнее, для случаев когда фильтрация нужна на уровне SSE)

```kotlin
val protocolBuffer = StringBuilder()
var inProtocolEvent = false; var braceDepth = 0

for (ch in text) {
    if (!inProtocolEvent) {
        if (ch == '{') { /* start buffering */ }
        else { emit(SseEvent.Content(ch.toString())) }
    } else {
        protocolBuffer.append(ch); /* track braces */
        if (braceDepth == 0) {
            val json = protocolBuffer.toString(); inProtocolEvent = false
            if (!json.contains("\"type\":\"step_start\"") && ...) emit(SseEvent.Content(json))
        }
    }
}
```

### Honor/Huawei phones: Log.d() не виден в logcat

Honor API 36 использует `hilogd` параллельно с `logd`. Системное свойство `hilog.tag=I` подавляет ВСЕ `Log.d()` и `Log.v()` вызовы.

- **Использовать `Log.i()`, `Log.w()`, `Log.e()` вместо `Log.d()`.**
- `adb logcat -s Tag:D` покажет ПУСТО для debug-уровня.
- `adb logcat --pid=$(adb shell pidof com.hermes.gui.debug)` захватывает все логи приложения независимо от фильтра тегов.

### MessageBubble: долгое нажатие → копировать

`MessageBubble.kt` — добавить `combinedClickable` (ExperimentalFoundationApi) с `onLongClick`:

```kotlin
import android.content.ClipData
import android.content.ClipboardManager
import android.widget.Toast
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.ui.platform.LocalContext

Surface(
    modifier = Modifier
        .widthIn(max = 320.dp)
        .combinedClickable(
            onClick = { },
            onLongClick = {
                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                clipboard.setPrimaryClip(ClipData.newPlainText("message", message.content))
                Toast.makeText(context, "Скопировано", Toast.LENGTH_SHORT).show()
            }
        )
)
```

### Compose элементы не кликаются через `adb shell input tap`

Jetpack Compose не обрабатывает синтетические `input tap` события. Для отправки сообщений в приложении через ADB использовать прямой HTTP-запрос к API (через туннель или ADB reverse), а не симуляцию UI.

```bash
# Правильно: тестировать API напрямую
$ADB shell "/system/bin/curl -s http://<YOUR_VPS_IP>:8643/health"
# Неправильно: пытаться кликать Compose-кнопки
$ADB shell "input tap 1154 2234"  # не сработает
```

### Audio playback fails (no sound, hangs on "Отвечаю...")
- **ExoPlayer, MediaPlayer, and AudioTrack ALL fail for WAV/OGG playback on User's Honor API 36 device.** Do NOT use any of them for TTS.
- **Use Android TextToSpeech.speak() — единственный надёжный способ.**
- `TextToSpeech(context) { status -> ... }` + `setLanguage(Locale("ru"))` + `speak(text, QUEUE_FLUSH, null, id)`
- Избегать Thread.sleep в init — использовать suspendCancellableCoroutine для ожидания колбэка onInit.
- Питфол: `com.google.android.tts` может быть заморожен менеджером активности — проверить через `adb logcat | grep freezing.*tts`

### Audio recording fails
- Prefer **AAC/MP4** over Opus/OGG for broader device compatibility.
- `MediaRecorder.OutputFormat.MPEG_4` + `MediaRecorder.AudioEncoder.AAC`
- File extension: `.m4a`

### Voice proxy dies silently
- Background Python processes may exit after shell termination.
- Run with watchdog script that health-checks every 15s.
- Direct venv path: `/home/user/.hermes/hermes-agent/venv/bin/python3`

### SSE Retry при обрыве потока

SSE через туннели может обрываться. Паттерн retry в ChatRepository.streamMessage():
- До 2 попыток при "unexpected end of stream"
- Задержка между попытками: 1s, затем 2s
- OkHttp: retryOnConnectionFailure(true) в AppModule.kt
- ChatViewModel: при SseEvent.Error сохранять частичный ответ через finalizeMessage()

### Connection reuse (каждое второе сообщение — unexpected end of stream)

Сервер шлёт `Connection: close` после SSE-потока. OkHttp может переиспользовать закрытое соединение из пула → второе сообщение падает.

**Исправление в AppModule.kt:**
```kotlin
return OkHttpClient.Builder()
    .retryOnConnectionFailure(true)   // ← ДОБАВИТЬ
    .connectTimeout(30, TimeUnit.SECONDS)
    ...
```

**❗ Питфол: НЕ использовать `connectionPool(0)`.** Это ломает даже ПЕРВЫЙ запрос — OkHttp закрывает SSE-соединение до завершения стрима. `connectionPool(ConnectionPool(0, 1, MILLISECONDS))` отключает keep-alive и мгновенно разрывает соединение → `unexpected end of stream` на каждом запросе.

**Единственное правильное решение:** `retryOnConnectionFailure(true)` + retry логика в ChatRepository (до 2 попыток при SSE-обрыве). Пул соединений оставить как есть (по умолчанию 5 idle, 5 минут keep-alive).
### Connection error — диагностика

- **DEFAULT_API_URL должен совпадать с активным туннелем.** Свой VPS: `http://<vps-ip>:8643`. Без VPS: localhost.run (`https://<id>.lhr.life`).
- HealthCheckManager: 30s интервал, 3 фейла → fallback, 2 успеха → primary.
- Honor API 36 HTTPS: работает с localhost.run, НЕ работает с serveo/cloudflared (TLS fail).

### TTS returns "unexpected keyword argument 'provider'"
- Hermes `text_to_speech_tool()` does NOT accept a `provider` parameter.
- Use the configured provider from `config.yaml` (usually Piper via local AI).

### KSP build errors after editing Kotlin files
- If `error.NonExistentClass` appears, a `.kt` file is corrupted (partial write).
- Re-read and rewrite the entire file — patches can truncate.

## BottomToolbar Layout (v3 — с оркестратором)

Агенты и модели убраны в кнопку `Hermes ▾` / `OpenCode+ ▾`. Добавлен постоянный тумблер `🔄` оркестратора.

```
[Hermes ▾]  [🔊]  [🔄]  [🎭]  [📜]
    │          │      │      │      └─ История диалогов
    │          │      │      └──────── Персона (15 стилей)
    │          │      └─────────────── Оркестратор (/agent plan)
    │          └────────────────────── TTS вкл/выкл
    └───────────────────────────────── H/OC+ переключатель (И модель)
```

**🔄 Кнопка оркестратора** — переключает `fullCycleEnabled`. Когда включена, каждое сообщение пользователя получает префикс `/agent plan ` (кроме сообщений, уже начинающихся с `/`). Состояние сохраняется в SharedPreferences и переживает перезапуск.

- **🟢 Синяя (on):** `/agent plan` добавляется в каждое сообщение. Полный оркестрационный цикл.
- **⚪ Серая (off):** обычный режим без префикса.

**Файлы для добавления нового persistent toggle (паттерн):**

| Файл | Изменение |
|------|-----------|
| `ChatUiState.kt` | + поле `fullCycleEnabled` |
| `ChatViewModel.kt` | `sendMessage()` — префикс; `toggleFullCycle()`; `ensureConversation()` — загрузка из настроек |
| `SettingsDataStore.kt` | + поле в `AppSettings`, + `loadSettings`, + `updateFullCycleEnabled()` |
| `SettingsRepository.kt` | + метод-делегат |
| `NavGraph.kt` | Параметры в `BottomToolbar`; кнопка `FilledIconButton` с `Icons.Default.Refresh` |

**Код `sendMessage` с префиксом:**
```kotlin
val finalText = if (_uiState.value.fullCycleEnabled && !trimmed.startsWith("/")) {
    "/agent plan $trimmed"
} else trimmed
```

## Настройки

- `primaryUrl` — Default `http://<YOUR_VPS_IP>:8643` (VPS — основной способ, сотовая связь)
- `fallbackUrl` — Резервный URL: `http://localhost:8643` (ADB reverse при USB)
- Опционально: `http://<YOUR_LOCAL_IP>:8643` (Wi-Fi, когда телефон в той же сети)
- `backendMode` — `"hermes"` (чат-модели через LiteLLM) или `"opencode"` (агенты с инструментами)
- Модель по умолчанию: `openai/qwen3.6-35b-heretic` (локальная на Jetson, без rate limit)

## Архитектура (текущая — Hermes Gateway API напрямую)

Hermes Gateway API слушает порт 8643 напрямую (настоящий Hermes Agent с инструментами, памятью, MCP). Unified proxy убран.

```
📱 → http://<YOUR_VPS_IP>:8643 → VPS → SSH reverse tunnel → Jetson:8643 → Hermes Gateway API
                                                                              ├─ инструменты (terminal, file, browser)
                                                                              ├─ память (MEMORY.md, state.db)
                                                                              ├─ навыки (skills/)
                                                                              └─ модели (qwen3.6-35b-heretic через LiteLLM custom provider)
```

**Hermes Gateway API — нативный режим:**
```bash
# Конфигурация порта — ВАЖНО: ключ platforms.api_server.port
hermes config set platforms.api_server.port 8643
hermes config set api_server.port 8643
hermes gateway run --replace
```
Gateway даёт настоящий Hermes-агент (инструменты, память, навыки) через OpenAI-совместимый API.

**Проверка:**
```bash
curl http://localhost:8643/health     # → {"status":"ok","platform":"hermes-agent"}
curl http://localhost:8643/v1/toolsets  # → terminal, file, browser, memory...
```

**Питфол: Hermes gateway PID file переживает kill -9.** После принудительного убийства gateway процесс удалён, но PID file остаётся → следующий `hermes gateway run` отказывается стартовать с «Gateway already running». Использовать `hermes gateway run --replace` или `rm -f /tmp/hermes-gateway.pid`.

**Питфол: НЕ запускать отдельный socat.** Раньше схема была 8643→socat→8647→proxy. Socat умирал, pkill убивал терминал. Теперь unified_proxy слушает 8643 напрямую — одно звено вместо трёх.

**Питфол: SharedPreferences сохраняют старые значения.** Изменение дефолтов в `AppSettings` не перезаписывает сохранённые на телефоне значения. Сброс: `adb shell pm clear com.hermes.gui.debug`. Или авто-коррекция в `ensureConversation()`:
```kotlin
if (settings.backendMode == "hermes" && settings.selectedModel == "hermes-agent") {
    settingsRepository.updateSelectedModel("qwen3.6-35b-heretic")
}
```

**Питфол: `nohup` для background процессов.** `terminal(background=true)` процессы умирают без уведомления. Запускать через `nohup command > /tmp/log.log 2>&1 &`. Watchdog должен тоже использовать `nohup`.

## Один диалог на бэкенд

`ensureConversation()` переиспользует последний диалог для текущего backendMode:

```kotlin
val existingConv = dialogRepository.getConversationsByMode(backendMode)
    .firstOrNull()
    ?.maxByOrNull { it.updatedAt }
val id = existingConv?.id ?: dialogRepository.createConversation(backendMode = backendMode).id
```

Переключение H↔OC+ создаёт/переиспользует **разные** диалоги. В списке диалогов фильтрация по `backendMode`.

## Модели для H и OC+ режимов

- **H (Hermes/чат):** `qwen3.6-35b-heretic` (по умолчанию, локальная), `deepseek-chat`, `deepseek-reasoner`, `gpt-4o`, `gpt-4o-mini`, `gemma-4-26b`, `qwen3.5-122b`... (44+ моделей через Hermes Gateway API → LiteLLM custom provider)
- **OC+ (OpenCode+ агенты):** `hermes-agent` (по умолчанию), `general`, `build`, `plan`, `review`, `safe`, `explore`, `scout`, `deep-explore`, `claw`, `composter` (10 агентов)
- Переключение бэкенда **автоматически меняет модель**: H → `qwen3.6-35b-heretic`, OC+ → `hermes-agent`.
- **Имя модели:** Для Hermes Gateway API используется `qwen3.6-35b-heretic` (без префикса `openai/`). Hermes Gateway сам матчит модель с custom provider в `config.yaml`.
- **Питфол: модель `hermes-agent` не существует в LiteLLM.** Если отправить `hermes-agent` в LiteLLM → 400 Bad Request. Используется только в OC+ режиме.

## Cellular Tunneling (без USB-кабеля)

Когда телефон не подключён по USB, нужен интернет-туннель. **Лучший вариант — свой VPS с SSH reverse tunnel.** Бесплатные туннели (cloudflared, serveo, localhost.run) — запасной план.

### Setup VPS SSH Reverse Tunnel (ОСНОВНОЙ)

Используется VPS `<YOUR_VPS_IP>` (Debian, sing-box VPN на :443 не трогать).

**На VPS (одноразово):**
```bash
# GatewayPorts — разрешить проброс на внешний интерфейс
sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config
# Keepalive — не рвать неактивные туннели
echo 'ClientAliveInterval 15' >> /etc/ssh/sshd_config
echo 'ClientAliveCountMax 4' >> /etc/ssh/sshd_config
systemctl reload sshd
```

**На Jetson — скопировать ключ и запустить туннель:**
```bash
ssh-copy-id root@<YOUR_VPS_IP>   # одноразово

# Туннель с keepalive
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
    -o ServerAliveCountMax=3 -o TCPKeepAlive=yes \
    -o ExitOnForwardFailure=yes \
    -R 0.0.0.0:8643:localhost:8643 \
    root@<YOUR_VPS_IP> "while true; do sleep 30; done"
```

**Watchdog (авто-перезапуск):** `/home/user/vps_watchdog.sh`

**❗ Питфол: Python tunnel_keeper vs Bash.** Python-обёртки (`subprocess.Popen`) глючат — subprocess умирает вместе с родительским shell, pkill убивает сам скрипт. **Использовать bash-цикл с `exec`:**

```bash
#!/bin/bash
# /home/user/tunnel_keeper.sh — надёжный авто-перезапуск
while true; do
    if ! ssh -o ConnectTimeout=5 root@VPS "curl -s --max-time 3 http://127.0.0.1:8643/health | grep -q ok"; then
        # Убить старые туннели локально
        for pid in $(pgrep -f "ssh.*-R.*8643"); do kill "$pid" 2>/dev/null; done
        # Убить orphaned сессии на VPS (КРИТИЧНО — без этого порт занят мёртвым пробросом)
        ssh root@VPS "ss -tlnp | grep 8643 | grep -oP 'pid=\d+' | cut -d= -f2 | xargs -r kill"
        sleep 1
        ssh -fN -o ServerAliveInterval=5 -o TCPKeepAlive=yes \
            -R 0.0.0.0:8643:localhost:8643 root@VPS
    fi
    sleep 15
done
```

**Питфол pkill:** `pkill -f` из foreground убивает свой же терминал. Использовать `kill` по PID из `pgrep`. В bash-цикле `pgrep -f` находит ТОЛЬКО ssh-процессы, не сам цикл.

**Питфол watchdog:** если не убивать старые SSH-процессы перед запуском нового, накапливаются множественные туннели (3+). Старые sshd-session на VPS становятся orphaned — порт слушается но проброс мёртв. Watchdog ДОЛЖЕН:
1. Проверить количество туннелей (`pgrep -cf "ssh.*8643.*64.188"`)
2. Если >1 — убить все кроме самого нового (`pgrep ... | tail -1`, остальных `kill`)
3. Если =0 — запустить один
4. **ДОПОЛНИТЕЛЬНО** — убить orphaned sshd-sessions на VPS: `ssh root@VPS "ss -tlnp | grep 8643 | grep -oP 'pid=\d+' | cut -d= -f2 | xargs -r kill"` перед запуском нового туннеля.
5. НЕ использовать `pkill -9` из foreground terminal — убивает сам терминал.
6. Host key может меняться при пересоздании VPS — удалить старую строку из `~/.ssh/known_hosts`.

Cron-джоб (`every 1m`) делает то же самое — проверяет и чинит.

**Архитектура:**
```
📱 Телефон (сотовая) → http://<YOUR_VPS_IP>:8643 → VPS → SSH → Jetson → socat:8643 → API:8646
```

**Преимущества VPS перед бесплатными туннелями:**
- URL не меняется никогда (`http://<YOUR_VPS_IP>:8643`)
- Пинг <1ms (свой сервер)
- SSH/TCP — не умирает как cloudflared QUIC
- Не требует пересборки APK при перезапуске туннеля
- **VPN на телефоне НЕ мешает** — трафик идёт phone→VPN→VPS:8643 (loopback через VPS). Проверено: sing-box VPN на телефоне (tun1) корректно пробрасывает запросы к VPS на loopback.

### Запасной: localhost.run (если VPS недоступен)

```bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
    -i ~/.ssh/id_ed25519 -R 80:localhost:8643 localhost.run \
    2>&1 | tee /tmp/lhr.log &
sleep 10
grep -oP '[a-z0-9]+\.lhr\.life' /tmp/lhr.log
# → https://<YOUR_TUNNEL_URL> (URL привязан к SSH-ключу)
```

### Зашивка URL в APK

```kotlin
// Constants.kt
const val DEFAULT_API_URL = "http://<YOUR_VPS_IP>:8643"  // VPS
// Или: "https://<YOUR_TUNNEL_URL>"               // localhost.run
// Или: "http://localhost:8643"                          // ADB reverse

// SettingsDataStore.kt (companion object)
const val DEFAULT_API_URL = "http://<YOUR_VPS_IP>:8643"
```

### Тестирование сотовой связи через туннель

```bash
# Телефон на сотовой (WiFi выключен), ADB по USB
$ADB shell "ip route"  # rmnet_data* = сотовая

# Тест туннеля (трафик curl идёт через сотовую сеть)
$ADB shell "/system/bin/curl -s -m 10 http://<YOUR_VPS_IP>:8643/health"
# → {"status":"ok","platform":"opencode+","agent_count":10}
```

**ВАЖНО: протестировать через `adb shell curl` ДО того как сказать пользователю «работает».**
Не говорить «проверь сам» — агент должен проверить сам.
- `apiKey` — Stored in EncryptedSharedPreferences
- `selectedPersona` — one of 15 personas (default: "default")
- `selectedAgent` — one of 10 agent presets (default: "general")
- Both persona and agent system prompts are sent together in API messages

## Key Dependencies

```kotlin
// build.gradle.kts
implementation("androidx.compose:compose-bom:2024.02.00")
implementation("com.google.dagger:hilt-android:2.50")
implementation("com.squareup.retrofit2:retrofit:2.9.0")
implementation("androidx.room:room-runtime:2.6.1")
implementation("androidx.media3:media3-exoplayer:1.3.0")  // for OGG playback
implementation("androidx.security:security-crypto:1.1.0-alpha06")  // EncryptedSharedPreferences
```
