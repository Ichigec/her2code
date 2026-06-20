---
name: hermes-android-gui
description: "Develop, build, deploy, and debug the Hermes Android companion app — voice chat, agent/persona management, multi-URL connectivity, ADB workflows."
version: 1.0.0
author: User + Hermes Agent
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

**Agent presets** (10 штук из `~/.hermes/hermes-agent/agent/agents.py`) — это инструменты/возможности:
general, build, plan, review, safe, explore, scout, deep-explore, claw, composter.
Выбираются в BottomToolbar кнопкой 🤖. Меняют system prompt + доступные tools.
**НИКОГДА не удалять, не заменять, не выдумывать новые.** Только из agents.py.

**Personas** (15 штук из `~/.hermes/config.yaml` → `personalities:`) — это стиль/тон:
стандартный, технический, краткий, креативный, нуар, шекспир, пират, neko-chan...
Выбираются отдельной кнопкой в BottomToolbar. Меняют ТОЛЬКО system prompt (стиль ответа).
Не влияют на доступные инструменты.

**Правило:** никогда не путать. Agent presets ≠ personas. Пользователь явно исправлял:
«это прикольно, но мне нужны agent presets которые берут skills, траектории и системные промпты».

## Быстрый старт

```bash
cd /home/user/dev/Opencode
# Полная чистая сборка (без кеша — важно!)
rm -rf app/build && ./gradlew assembleDebug --no-build-cache

# Установка на телефон
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.hermes.gui.debug/com.hermes.gui.MainActivity
```

## Архитектура (актуальная)

```
Android App (телефон)
├── Chat (SSE) ─────────────► Hermes API (localhost:8643 → ADB reverse → PC:8642)
├── Voice STT ──────────────► Android SpeechRecognizer (Google, on-device, fast)
├── Voice TTS ──────────────► Android TextToSpeech (Google TTS, on-device, neural)
├── Personas (15) ──────────► system prompt (стиль)
├── Agent Presets (10) ─────► system prompt + tools (из agent/agents.py)
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

## Hermes Gateway API — настоящий Hermes Agent

Hermes Gateway (`hermes gateway run`) запускает OpenAI-совместимый API сервер. Это **настоящий** Hermes — с инструментами (terminal, file, web, browser), памятью, навыками, MCP-серверами. **Предпочитать unified proxy.** Unified proxy — временный костыль для маршрутизации; конечная цель: Hermes Gateway API напрямую.

### Конфигурация порта

Два разных ключа в `config.yaml`, оба нужно установить:
```bash
hermes config set api_server.port 8648
hermes config set platforms.api_server.port 8648
```

**Питфол:** `api_server.port` ≠ `platforms.api_server.port`. Gateway читает `platforms.api_server.port`. Менять ОБА.

### Запуск

```bash
# Убить старый gateway (PID может висеть даже после kill -9 — проверить ps aux)
kill $(pgrep -f "hermes gateway") 2>/dev/null
sleep 2
# Запустить
/home/user/.hermes/hermes-agent/venv/bin/hermes gateway run

# Проверить
curl http://localhost:8648/health
# → {"status":"ok","platform":"hermes-agent"}
```

**Питфол:** `hermes gateway run` НЕ запускается если порт занят. Ошибка в логе: «Port 8643 already in use. Set a different port in config.yaml: platforms.api_server.port». Причина: watchdog перезапустил unified_proxy на этом же порту. Решение: убить ВСЕ процессы на порту (`fuser -k PORT/tcp`), убить watchdog, потом стартовать gateway.

**Питфол:** gateway логирует в `~/.hermes/logs/gateway.log`. Если api_server не запустился — смотреть там: `grep api_server ~/.hermes/logs/gateway.log`.

**Питфол:** `fuser -k PORT/tcp` — безопасный способ освободить порт (в отличие от pkill который убивает терминал).

### Когда нет ответа: диагностика

```bash
# 1. Hermes Gateway жив?
curl http://localhost:8648/health

# 2. Модель отвечает?
curl -X POST http://localhost:8648/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $HERMES_KEY" \
  -d '{"model":"qwen3.6-35b-heretic","messages":[{"role":"user","content":"Who are you"}],"stream":false}'

# 3. Инструменты доступны?
curl http://localhost:8648/v1/toolsets
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

**Модель по умолчанию для H:** `openai/qwen3.6-35b-heretic` (локальная, без rate-limit). `deepseek-chat` упирается в 429.

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

## Pitfalls

- **pkill в foreground = убивает терминал.** НИКОГДА не использовать `pkill -f` в foreground terminal. Использовать `fuser -k PORT/tcp` для освобождения портов, `kill PID` для конкретных процессов. При необходимости массового kill — background terminal или process API.
- **SharedPreferences кеширует старые значения.** После смены дефолтов в `AppSettings` старые сохранённые значения из SharedPreferences переопределяют новые дефолты. Использовать `adb shell pm clear com.hermes.gui.debug` для сброса. В коде: `ensureConversation()` должен проверять и исправлять неконсистентные настройки (модель не того бэкенда).
- **ТЕСТИРОВАТЬ САМОСТОЯТЕЛЬНО перед «готово».** НИКОГДА не говорить «работает» пока не проверено через `adb shell curl` с телефона. Пользователь явно требует: «почему ты не протестировал?», «важно протестировать самому». Тест с ПК (curl localhost) НЕ равен тесту с телефона.
- **Телефон на сотовой — тестировать через ADB.** WiFi OFF, cellular ON. `adb shell curl` идёт через сотовую сеть телефона. Это И ЕСТЬ самостоятельное тестирование сотовой связи.
- **НИКОГДА не выдумывать agent presets которых нет в `agent/agents.py`** — пользователь явно исправлял: «у меня в hermes нету таких агентов». Только 10 реальных: general, build, plan, review, safe, explore, scout, deep-explore, claw, composter.
- **Agent presets ≠ personas.** Presets = инструменты из agents.py (священные, не удалять). Personas = стиль из config.yaml (15 штук). Два разных селектора в BottomToolbar.
- **Не патчить промпты в клиенте когда проблема на сервере** — «не надо менять системный промпт. надо решать корневую проблему». Искать корень, не маскировать.
- **Один диалог на backend** — `ensureConversation()` должен переиспользовать последний диалог для текущего backendMode (getConversationsByMode), а не создавать новый при каждом запуске. Иначе плодятся пустые диалоги.
- **Архивные диалоги: loadConversation()** — при навигации на `chat/{convId}` ChatScreen должен вызывать `viewModel.loadConversation(convId)` через `LaunchedEffect(conversationId)`. Без этого диалоги из списка не открываются.
- **Gradle кеш на ARM64** — всегда `rm -rf app/build && --no-build-cache` при изменениях кода
- **ADB reverse сбрасывается** при переподключении USB — перезапускать
- **Python TCP proxy надёжнее socat** — socat умирает без watchdog
- **Перед выбором тунельного сервиса — СПРОСИТЬ про VPS.** Пользователь может иметь публичный сервер (<YOUR_VPS_IP>) и не упомянуть его сразу. VPS reverse SSH tunnel — быстрее, надёжнее и стабильнее любых бесплатных сервисов. 2026-06-13: агент потратил ~20 часов на перебор 7+ сервисов, а решение было в одном SSH-туннеле к своему VPS.
- **Shell escaping с API-ключами:** терминал обрезает API-ключи в inline Python. Для тестов с ключами писать скрипты в файлы (`/tmp/test_*.py`) и запускать их.

- `scripts/voice_proxy.py` — готовая копия голосового прокси
- `references/voice-architecture.md` — полная архитектура голосового пайплайна
- `references/audio-debug-log.md` — хронология отладки аудио и список питфолов
- `references/cellular-connectivity-saga.md` — хронология отладки сотовой связи
- `references/hermes-gateway-setup.md` — настройка Hermes Gateway API (порты, pitfalls, watchdog)
- `references/sse-retry-pattern.md` — паттерн retry для обрывов SSE-потока
- `references/protocol-event-filter.md` — фильтрация OpenCode protocol events из чата
- `references/unified-proxy.md` — архитектура unified proxy (один URL, умная маршрутизация)
- `references/python-tunnel-keeper.md` — надёжный Python watchdog для SSH-туннеля
- `references/message-copy-pattern.md` — долгое нажатие для копирования сообщений
