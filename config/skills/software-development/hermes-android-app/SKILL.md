---
name: hermes-android-app
description: "Develop, debug, and deploy the Hermes Android client app — Kotlin + Jetpack Compose, voice chat, multi-URL, personas."
version: 2.0.0
author: User
---

# Hermes Android App

Android-приложение для общения с Hermes Agent. Kotlin + Jetpack Compose + Hilt + Room + Retrofit + OkHttp.

**Расположение:** `/home/user/dev/Opencode/`
**Сборка:** `rm -rf app/build && ./gradlew assembleDebug --no-build-cache`
**APK:** `app/build/outputs/apk/debug/app-debug.apk`

## Финальная архитектура (июнь 2026)

### Стек
```
Телефон (Android API 36)              Сервер (Jetson ARM64)
├── STT: SpeechRecognizer (Google)    
├── TTS: TextToSpeech (Google TTS)    
│                                     ├── Hermes Gateway API :8643
│                                     │   ├─ Qwen 35B (локально)
│                                     │   ├─ DeepSeek V4 Pro (облако)
│                                     │   ├─ Инструменты (terminal, file, web...)
│                                     │   ├─ Память (persistent)
│                                     │   └─ Навыки (skills)
│                                     ├── VPS SSH tunnel :8643→:8643
│                                     └── Voice Proxy :8647 (опционально)
```

**Default URL:** `http://<YOUR_VPS_IP>:8643` (VPS → SSH → Hermes Gateway API).
**Default модель:** `qwen3.6-35b-heretic` (локальная, 0.4-0.7s).
**Backend toggle:** 🔄 H/OC+ переключает `backendMode` + `selectedModel`.

### Ключевые файлы

| Файл | За что отвечает |
|------|----------------|
| `ChatViewModel.kt` | Голосовой цикл, SSE streaming, вызов TTS |
| `VoiceRepository.kt` | STT через SpeechRecognizer, TTS через TextToSpeech |
| `NavGraph.kt` | BottomToolbar, PersonaSelector, AgentSelector, ModelSelector, TTS toggle |
| `Constants.kt` | 15 персон, 10 агентов, модели, DEFAULT_API_URL=localhost:8643 |
| `SettingsDataStore.kt` | primaryUrl, fallbackUrl, selectedPersona, selectedAgent |
| `ChatInputBar.kt` | Поле ввода + кнопка микрофона |
| `VoiceInputButton.kt` | Кнопка 🎙️: тап для вкл/выкл, цвета по состоянию |
| `ChatUiState.kt` | isRecording, isVoiceActive, isPlaying, ttsEnabled |
| `voice_proxy.py` | HTTP-обёртка STT/TTS Hermes (порт 8647, частично deprecated) |

### BottomToolbar

```
[Hermes/OC+] 🔊 🎭 📜
│            │   │   └─ История диалогов
│            │   └───── Персоны (Шекспир, Нуар, Пират...)
│            └───────── TTS toggle (🔊/🔇)
└────────────────────── Переключатель бэкенда (кликабельный FilledTonalButton)
                        H → Qwen 35B чат | OC+ → OpenCode+ агенты
```

Упрощено: отдельные кнопки «Агент» и «Модель» убраны. Переключатель H/OC+ сам меняет модель:
```kotlin
fun toggleBackend() {
    val next = if (current == "hermes") "opencode" else "hermes"
    viewModelScope.launch {
        settingsRepository.updateBackendMode(next)
        val model = if (next == "hermes") "qwen3.6-35b-heretic" else "hermes-agent"
        settingsRepository.updateSelectedModel(model)
    }
}
```

## Голосовой чат

### Проверенная архитектура

**STT**: Android `SpeechRecognizer` (Google) — быстро, бесплатно, высокое качество.
```kotlin
speechRecognizer?.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
})
```

**TTS**: Android `TextToSpeech` (Google TTS) — единственный надёжный способ.
```kotlin
tts = TextToSpeech(context) { status -> ttsReady = (status == TextToSpeech.SUCCESS) }
tts?.language = Locale("ru")
tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tts_id")
```

### SSE retry при обрыве потока — КРИТИЧЕСКИ

Через туннели (особенно SSH/VPS) SSE-поток может обрываться с `unexpected end of stream`. Особенно на КАЖДОМ ВТОРОМ сообщении — OkHttp переиспользует соединение, а сервер уже закрыл его (`Connection: close`).

**Решение: `retryOnConnectionFailure` + retry loop в `ChatRepository.streamMessage()`:**

```kotlin
// AppModule.kt — OkHttp сам переоткроет соединение
OkHttpClient.Builder()
    .retryOnConnectionFailure(true)  // ← ключевое
    .connectTimeout(30, TimeUnit.SECONDS)
    .readTimeout(120, TimeUnit.SECONDS)
    .build()
```

```kotlin
// ChatRepository.kt — retry при обрыве SSE
fun streamMessage(...): Flow<SseEvent> = flow {
    var attempt = 0
    val maxRetries = 2
    while (attempt <= maxRetries) {
        if (attempt > 0) delay((1000L * attempt).coerceAtMost(3000L))
        val call = api.chatCompletionStream(request)
        var streamBroken = false
        try {
            val response = withContext(Dispatchers.IO) { call.execute() }
            if (response.isSuccessful) {
                sseClient.parseStream(body).flowOn(Dispatchers.IO).collect { event ->
                    if (event is SseEvent.Error) {
                        val msg = event.message ?: ""
                        if (msg.contains("unexpected end") || msg.contains("stream error")) {
                            streamBroken = true  // retry
                        } else { emit(event) }
                    } else { emit(event) }
                }
                if (streamBroken) { attempt++; continue }
                return@flow  // success
            }
        } catch (e: Exception) { attempt++ }
    }
}
```

**В ChatViewModel при обрыве SSE — сохранить частичный ответ:**
```kotlin
is SseEvent.Error -> {
    val partialText = collectedContent.toString()
    if (partialText.isNotBlank()) finalizeMessage(conversationId)  // не терять частичный ответ
    _uiState.update { it.copy(isStreaming = false, error = event.message) }
}
```

`finalizeMessage()` вызывает `collectedContent.clear()`. Текст для TTS нужно сохранять ДО вызова:

```kotlin
is SseEvent.Done -> {
    val responseText = collectedContent.toString()  // ← сохранить до clear()
    finalizeMessage(conversationId)
    if (autoRestartVoice && responseText.isNotBlank()) {
        viewModelScope.launch { synthesizeAndPlay(responseText) }
    }
}
```

Без этого `synthesizeAndPlay` получает пустую строку и молча выходит.

### Голосовой цикл

1. Тап 🎙️ → `toggleVoice()` → `startVoiceMode()` → `startListeningCycle()`
2. `listenAndTranscribe()` → SpeechRecognizer → `onResults` → текст
3. `sendMessage(transcript)` → SSE → LLM ответ
4. SSE `Done` → сохранить текст → `finalizeMessage()` → `synthesizeAndPlay()`
5. TTS `onDone` → `isPlaying = false` → `delay(300)` → `startListeningCycle()`
6. Повторный тап 🎙️ → `stopVoiceMode()`

### TTS toggle (🔊/🔇)

- `ChatUiState.ttsEnabled` (default=true)
- `toggleTts()` — при выключении вызывает `tts.stop()` для мгновенной остановки
- `synthesizeAndPlay` проверяет `ttsEnabled` до запуска

### Что НЕ работает (испытано и провалено)

- **ExoPlayer**: не даёт звук, `STATE_ENDED` не срабатывает
- **AudioTrack**: `write()` блокируется навсегда
- **MediaPlayer** с OGG: файл читается, звука нет
- **faster-whisper GPU**: CUDA есть, но ctranslate2 не видит устройства на aarch64
- **LocalAI whisper backend**: падает при загрузке модели

## Voice Proxy (опционально)

`voice_proxy.py` на порту 8647. Сейчас почти не нужен (STT/TTS на телефоне), но оставлен как fallback.

```bash
# Запуск
/home/user/.hermes/hermes-agent/venv/bin/python3 /home/user/dev/Opencode/voice_proxy.py

# Эндпоинты
POST /stt  — бинарный аудио → {"transcript": "..."}
POST /tts  — {"text": "..."} → WAV PCM
GET /health
```

Прокси падает при выходе shell. Нужен watchdog:
```bash
while true; do
  curl -s --max-time 2 http://localhost:8647/health >/dev/null 2>&1 || \
    /home/user/.hermes/hermes-agent/venv/bin/python3 /home/user/dev/Opencode/voice_proxy.py &
  sleep 15
done
```

## ADB reverse — ОСНОВНОЙ способ подключения

**Телефон и ПК в разных подсетях** (телефон: 10.4.x.x сотовая / ПК: 192.168.0.x WiFi).
ADB reverse решает это БЕЗ внешних туннелей — трафик идёт по USB-кабелю.

### Настройка

```bash
ADB=/home/user/Android/Sdk/platform-tools/adb

# Проверить текущие реверсы
$ADB reverse --list

# Пробросить порт (телефон:8643 → ПК:8643)
$ADB reverse tcp:8643 tcp:8643

# Если phone на другой подсети — reverse ВСЁ РАВНО работает (через USB)
```

**Default URL в приложении:** `http://localhost:8643` (работает через ADB reverse).

### Тестирование сотовой связи САМОСТОЯТЕЛЬНО

Телефон подключён по USB (ADB), но интернет-трафик идёт через сотовую сеть (WiFi выключен). Агент может тестировать доступность API с телефона сам — **не перекладывать на пользователя**:

```bash
# Проверить на какой сети телефон
$ADB shell "ip route | head -3"        # rmnet_data* = сотовая, wlan0 = WiFi
$ADB shell "ip addr show wlan0"        # NO-CARRIER = WiFi выключен

# Тестировать API с телефона
$ADB shell "/system/bin/curl -s -m 5 http://localhost:8643/health"
# → {"status":"ok","platform":"opencode+","agent_count":10}
```

Reverse слетает при переподключении USB — всегда перезапускать перед тестом.

### Интернет-доступ (без USB) — VPS SSH reverse tunnel (ОСНОВНОЙ)

Для сотовой связи без USB-кабеля: собственный VPS (<YOUR_VPS_IP>, Debian, sing-box VPN на :443 — НЕ ТРОГАТЬ).

**Архитектура:**
```
📱 Телефон (сотовая) → http://<YOUR_VPS_IP>:8643 → 🖥️ VPS → SSH reverse → 💻 Jetson
```

**Настройка на VPS (одноразово):**
```bash
# GatewayPorts yes в /etc/ssh/sshd_config (чтобы порт слушал 0.0.0.0)
sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config
systemctl reload sshd

# Keepalive чтобы туннель не рвался
echo 'ClientAliveInterval 15' >> /etc/ssh/sshd_config
echo 'ClientAliveCountMax 4' >> /etc/ssh/sshd_config
systemctl reload sshd
```

**Поднятие туннеля с Jetson:**
```bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
    -o ServerAliveCountMax=3 -o TCPKeepAlive=yes \
    -o ExitOnForwardFailure=yes \
    -R 0.0.0.0:8643:localhost:8643 \
    root@<YOUR_VPS_IP> "while true; do sleep 30; done"
```

**Watchdog:** `/home/user/vps_watchdog.sh` — авто-перезапуск туннеля при падении.
**Default URL:** `http://<YOUR_VPS_IP>:8643` (не меняется — свой сервер).

**Преимущества перед внешними сервисами:**
- 🚀 Скорость: пинг <1ms (свой сервер рядом)
- 🔒 Надёжность: SSH/TCP, не умирает как cloudflared/serveo
- ♾️ URL не меняется никогда
- VPN (sing-box) не затрагивается

### ИЗБЕГАТЬ «туннельного шторма»

**НЕ перебирать** cloudflared → ngrok → bore → localhost.run → ... когда есть рабочий вариант.
- cloudflared free tunnels падают: QUIC-сессия обрывается (`timeout: no recent network activity`)
- Tailscale без sudo: только userspace-networking (SOCKS5 исходящие), входящие НЕ работают (нет TUN-интерфейса)

## Gradle pitfalls

Кеш Gradle часто отдаёт старый APK. После изменений кода всегда:
```bash
rm -rf app/build && ./gradlew assembleDebug --no-build-cache
```

## Питфол: «туннельный шторм»

Пользователь хочет локальные решения. Если телефон на USB — ADB reverse решает ВСЁ.
**НЕ перебирать** cloudflared → serveo → ngrok → bore → localhost.run → ... когда ADB reverse работает.
cloudflared free tunnel умирает (QUIC timeout), Tailscale без sudo — входящие не работают.

**Приоритет решений для сотовой связи:**
1. VPS SSH reverse tunnel (свой сервер) — лучший вариант: стабильно, быстро, URL не меняется
2. localhost.run — надёжнее serveo, но медленный (AWS Virginia)
3. serveo.net — меняет URL при реконнекте → 502
4. cloudflared — QUIC блокируется ISP, HTTP2 нестабилен (умирает за минуты)

## Honor / Huawei logcat pitfall

На телефонах Honor/Huawei работает `hilogd` ПОВЕРХ `logd`. Системное свойство `hilog.tag=I` подавляет ВСЕ `Log.d()` и `Log.v()` вызовы.

**Следствие:** `adb logcat -s TAG:D` показывает ПУСТО даже когда debug-логи пишутся.
`adb logcat -s TAG:I` или `TAG:W` работает, но `TAG:D` и `TAG:V` — нет.

**Решение:** использовать `adb logcat --pid=$(adb shell pidof com.hermes.gui.debug)` для захвата ВСЕХ логов процесса (включая системные), и фильтровать через grep на стороне ПК.

## Тестирование сотовой связи — САМ агент проверяет

Агент ДОЛЖЕН сам протестировать API с телефона через ADB до объявления успеха. Телефон на сотовой сети (WiFi выключен) — `adb shell curl` идёт через cellular.

```bash
# Проверить на какой сети телефон
adb shell "ip route | head -3"           # rmnet_data* = сотовая
adb shell "ip addr show wlan0"           # NO-CARRIER = WiFi выключен

# Проверить API с телефона (сотовая связь)
adb shell "/system/bin/curl -s -m 10 http://<YOUR_VPS_IP>:8643/health"
# → {"status":"ok"} = работает

# Проверить латентность
adb shell "/system/bin/curl -s -o /dev/null -w 'total: %{time_total}s' -m 10 http://<YOUR_VPS_IP>:8643/health"
```

**НИКОГДА не писать «User, проверь сам»** пока агент не протестировал через `adb shell curl`.

## Backend toggle: H ↔ OC+ (кликабельный индикатор)

Индикатор сети (зелёный/красный) — **кликабельная кнопка** 🔄, переключает `backendMode` между "hermes" и "opencode". Не просто визуальный индикатор.

### Добавление backendMode в систему настроек:

1. `AppSettings` → поле `backendMode: String = "hermes"`
2. `SettingsDataStore.loadSettings()` → `regularPrefs.getString("backend_mode", "hermes")`
3. `SettingsDataStore.updateBackendMode(mode)` → запись + `emitUpdate()`
4. `SettingsRepository.updateBackendMode(mode)` → делегат
5. `SettingsViewModel.toggleBackend()` → `val next = if (current == "hermes") "opencode" else "hermes"`

### BottomToolbar:

```kotlin
// Было: Box с CircleShape (просто индикатор)
Box(Modifier.size(10.dp).clip(CircleShape).background(color, CircleShape))

// Стало: FilledIconButton с Sync + подпись H/OC+
FilledIconButton(onClick = onToggleBackend, ...) {
    Icon(Icons.Default.Sync, tint = connectionColor)
}
Text(if (backendMode == "hermes") "H" else "OC+", color = connectionColor)
```

## Один диалог на бэкенд

При старте приложение не создаёт новый диалог каждый раз. `ensureConversation()` ищет последний диалог нужного бэкенда:

```kotlin
private suspend fun ensureConversation() {
    val settings = settingsRepository.settingsFlow.first()
    val backendMode = if (settings.backendMode == "opencode") "OPENCODE_PLUS" else "HERMES"
    val existingConv = dialogRepository.getConversationsByMode(backendMode)
        .firstOrNull()
        ?.maxByOrNull { it.updatedAt }
    val id = if (existingConv != null) existingConv.id
    else dialogRepository.createConversation(backendMode = backendMode).id
    _uiState.update { it.copy(currentConversationId = id) }
}
```

## Архивные диалоги — навигация

При клике на диалог в DialogListScreen → `chat/{conversationId}`. ChatScreen должен загрузить сообщения:

```kotlin
// ChatScreen.kt
LaunchedEffect(conversationId) {
    if (conversationId != null) viewModel.loadConversation(conversationId)
}

// ChatViewModel.kt
fun loadConversation(conversationId: String) {
    if (_uiState.value.currentConversationId == conversationId) return
    _uiState.update { it.copy(currentConversationId = conversationId) }
    viewModelScope.launch {
        dialogRepository.getMessages(conversationId).collect { messages ->
            _uiState.update { it.copy(messages = messages) }
        }
    }
}
```

## Copy-to-clipboard (долгое нажатие)

```kotlin
// MessageBubble.kt — поверх Surface добавить combinedClickable
Surface(
    modifier = Modifier.combinedClickable(
        onClick = { },
        onLongClick = {
            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            clipboard.setPrimaryClip(ClipData.newPlainText("message", message.content))
            Toast.makeText(context, "Скопировано", Toast.LENGTH_SHORT).show()
        }
    )
)
```

## VPS SSH tunnel — tunnel_keeper.sh (НАДЁЖНЫЙ подход)

Bash watchdog надёжнее Python-аналогов (paramiko не форвардит, subprocess убивает сам себя):

```bash
#!/bin/bash
while true; do
    if ! ssh -o ConnectTimeout=5 root@<YOUR_VPS_IP> "curl -s --max-time 3 http://127.0.0.1:8643/health | grep -q ok"; then
        # Kill stale tunnels
        for pid in $(pgrep -f "ssh.*-R.*8643.*64.188"); do kill "$pid" 2>/dev/null; done
        # Clean VPS stale sessions
        ssh -o ConnectTimeout=5 root@<YOUR_VPS_IP> \
            "ss -tlnp | grep 8643 | grep -oP 'pid=\K\d+' | xargs -r kill" 2>/dev/null
        # Start fresh
        ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
            -o ServerAliveCountMax=3 -o TCPKeepAlive=yes \
            -o ExitOnForwardFailure=yes -fN \
            -R 0.0.0.0:8643:localhost:8643 root@<YOUR_VPS_IP>
    fi
    sleep 15
done
```

Запуск: `chmod +x tunnel_keeper.sh && exec ./tunnel_keeper.sh` (background).

**НИКОГДА не использовать** `pkill -f "ssh.*-R.*8643"` из foreground shell — убивает сам shell!

## OpenCode `step_start` — СЕРВЕРНАЯ проблема (не фиксить клиентски)

Модель OpenCode+ генерирует протокольные события `step_start` как текст ответа.
Фильтрация на клиенте **бесполезна**: character-by-character buffer, regex-фильтр, `filterProtocolJson` —
все варианты вырезают ВЕСЬ контент (responseText length=1), потому что модель выдаёт ТОЛЬКО протокол без текста.

**Что НЕ работает (испытано и провалено):**
- Character-by-character buffer в SseClient с braceDepth — застревает в режиме буфера
- `filterProtocolJson()` в ChatViewModel — вырезает весь ответ → 1 символ остаётся
- Проверка `delta.content` на `"type":"step_start"` — не помогает при посимвольном стриминге

**Решение:** не фильтровать. Показывать как есть или показывать «Агент не ответил» если ответ = только step_start без текста:
```kotlin
val displayText = if (responseText.startsWith("{\"type\":\"step_start\"") &&
    !responseText.contains("\"content\":"))
    "Агент не ответил. Попробуйте ещё раз."
else responseText
```

**Настоящее решение:** раздельные бэкенды (см. ниже).

## Hermes Gateway API — ОСНОВНОЙ бэкенд

**Hermes Gateway API** на порту 8643 — это НАСТОЯЩИЙ Hermes-агент с инструментами, памятью и навыками.
Заменяет все предыдущие костыли (unified proxy, LiteLLM, OpenCode+).

```bash
# Запуск
hermes gateway run

# Проверка
curl http://localhost:8643/health
# → {"status":"ok"}
```

**Конфигурация в `~/.hermes/config.yaml`:**
```yaml
api_server:
  host: 0.0.0.0
  port: 8643

custom_providers:
- api_key: sk-local
  base_url: http://localhost:4000/v1
  model: qwen3.6-35b-heretic
  name: Local (localhost:4000)

model:
  default: deepseek-v4-pro
  provider: deepseek
```

**ВАЖНО: порт API сервера в `platforms.api_server.port`.** `hermes config set platforms.api_server.port 8648`. Команда `api_server.port` (без `platforms.`) меняет не тот ключ. Gateway читает из `platforms.api_server.port`.

**Модели:**
- `qwen3.6-35b-heretic` — локальная Qwen 35B через LiteLLM (0.4-0.7s, без rate limit)
- `deepseek-v4-pro` — DeepSeek API (требует DEEPSEEK_API_KEY в .env, может быть rate-limited)

**Финальная архитектура:**
```
📱 → http://<YOUR_VPS_IP>:8643 → SSH tunnel → Hermes Gateway API :8643
                                               ├─ Инструменты (terminal, file, web...)
                                               ├─ Память (persistent, cross-session)
                                               ├─ Навыки (skills)
                                               ├─ Персоны (15: noir, shakespeare, catgirl...)
                                               └─ Модели (Qwen 35B / DeepSeek V4 Pro)
```

**НИКАКИХ unified proxy, LiteLLM-маршрутизации, OpenCode+ step_start.**
Hermes Gateway API сам делает ВСЁ. Один процесс, один порт.

### Watchdog для Hermes Gateway

```bash
while true; do
    if ! curl -s --max-time 3 http://localhost:8643/health | grep -q ok; then
        nohup hermes gateway run > /tmp/hermes_gateway.log 2>&1 &
    fi
    sleep 60
done
```

**КРИТИЧНО: фоновые процессы и watchdog'и конфликтуют.** При использовании `terminal(background=true)` нельзя запускать параллельные watchdog'и — один убьёт другой. Всегда убивать старые watchdog'и перед запуском нового.

**pkill в foreground убивает ТЕРМИНАЛ.** Использовать `kill PID` по конкретному PID или `fuser -k PORT/tcp`. НИКОГДА `pkill -f pattern` из foreground shell.

### AppSettings — минимальные

```kotlin
data class AppSettings(
    val primaryUrl: String = "http://<YOUR_VPS_IP>:8643",
    val apiKey: String = "...",
    val backendMode: String = "hermes",
    val selectedModel: String = "qwen3.6-35b-heretic",
    val selectedPersona: String = "default",
    val selectedAgent: String = "general",
)
```

### Почему не unified proxy / LiteLLM / OpenCode+

| Подход | Проблема | Почему провалился |
|--------|----------|-------------------|
| Unified proxy (Python) | 502 Bad Gateway, 401 Unauthorized | Фоновые процессы умирают, socat падает, pkill убивает терминал |
| LiteLLM напрямую | Чистый чат без агента | Нет инструментов, памяти, навыков — просто LLM |
| OpenCode+ API | step_start вместо текста | Модель генерирует протокол, не чат |
| Два порта + два туннеля | Туннели множатся, конфликтуют | SSH сессии на VPS блокируют порты |

**Hermes Gateway API — ЕДИНСТВЕННЫЙ правильный бэкенд.**

### Fallback: Hermes identity через system prompt (когда Gateway недоступен)

Если Hermes Gateway API не запущен, а используется Qwen/LiteLLM напрямую — модель не знает что она Hermes. Добавить system prompt:

```kotlin
// ChatViewModel.kt — buildApiMessages()
if (settings.backendMode == "hermes") {
    result.add(ChatMessage(role = "system", content = 
        "You are Hermes — an AI agent by Nous Research. " +
        "You run on Jetson ARM64 with NVIDIA GPU. " +
        "You have access to tools (terminal, file, web, browser). " +
        "Be concise, helpful, and proactive. " +
        "When asked who you are, say you are Hermes Agent running on User's Jetson."))
}
```

Без этого модель отвечает «I am Qwen» или «I am an AI assistant».

## ❌ connectionPool(0) — НЕ ДЕЛАТЬ

Попытка `connectionPool(0, 1, MILLISECONDS)` вызывает ошибки на КАЖДОМ сообщении. Не совместимо с SSE. Использовать только `retryOnConnectionFailure(true)` + retry loop.

## Deploy

```bash
cd /home/user/dev/Opencode
rm -rf app/build && ./gradlew assembleDebug --no-build-cache
$ADB install -r app/build/outputs/apk/debug/app-debug.apk
$ADB shell am start -n com.hermes.gui.debug/com.hermes.gui.MainActivity
```

## Reference files

- `references/hermes-gateway-api-setup.md` — Hermes Gateway API quick start (config, models, curl examples)
- `references/vps-tunnel-setup.md` — VPS SSH tunnel configuration (<YOUR_VPS_IP>)
- `references/vps-tunnel-keeper.md` — Надёжный bash watchdog для SSH reverse tunnel (с кодом)
- `references/sse-retry-pattern.md` — SSE retry loop for tunnel stability
- `references/voice-proxy-debug.md` — Voice proxy debugging history
- `references/unified-proxy-dead-end.md` — Почему unified proxy провалился (watchdog'и, pkill, socat, port conflicts)
