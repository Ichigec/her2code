---
name: android-hermes-app
description: Develop and maintain the Android Hermes companion app — Kotlin/Jetpack Compose, Gradle builds on ARM64, architecture patterns, voice features, and deployment to phone.
version: 1.1.0
---

# Android Hermes Companion App

Develop and maintain the Android Hermes GUI companion app — Kotlin + Jetpack Compose + Hilt + Room + Retrofit + OkHttp.

**Project location:** `/home/user/dev/Opencode/`

## Quick Reference

```bash
# Build — ALWAYS clean to avoid Gradle cache producing stale APKs
cd /home/user/dev/Opencode && rm -rf app/build && ./gradlew assembleDebug --no-build-cache

# ADB (ARM64 host — uses QEMU wrapper)
ADB=/home/user/Android/Sdk/platform-tools/adb

# Install + launch
$ADB install -r app/build/outputs/apk/debug/app-debug.apk
$ADB shell am start -n com.hermes.gui.debug/com.hermes.gui.MainActivity

# Logs
$ADB logcat -s HermesGUI:D AndroidRuntime:E

# Clear app data (after schema changes)
$ADB shell pm clear com.hermes.gui.debug
```

## Architecture (MVVM + Clean Architecture)

```
ui/
├── navigation/NavGraph.kt      — TopAppBar + BottomToolbar + NavHost + global dialogs
├── chat/
│   ├── ChatScreen.kt           — Chat UI with LazyColumn + ChatInputBar
│   ├── ChatViewModel.kt        — Streaming, voice, buildApiMessages
│   ├── ChatUiState.kt          — UI state data class
│   └── components/
│       ├── ChatInputBar.kt     — Text field + VoiceInputButton + send
│       ├── PersonaSelector.kt  — 15 persona dropdown
│       ├── AgentSelector.kt    — 10 agent presets dropdown
│       ├── ModelSelector.kt    — Model picker dialog
│       ├── VoiceInputButton.kt — Toggle-based voice chat microphone (tap on/off, color-coded states)\n│       ├── VoiceStatusBar.kt    — Voice state indicator (🎙️ Слушаю... / 🧠 Думаю... / 🔊 Отвечаю...)\n│       └── WaveformIndicator.kt — Recording animation
├── dialogs/                    — Dialog list screen
└── settings/                   — Settings screen

data/
├── remote/
│   ├── HermesApi.kt            — Retrofit interface (chat, toolsets, STT, TTS)
│   ├── SseClient.kt            — SSE stream parser (must run on Dispatchers.IO!)
│   ├── AuthInterceptor.kt      — URL rewriting + auth header
│   └── HealthCheckManager.kt   — Periodic /health ping, auto-failover
├── repository/
│   ├── ChatRepository.kt       — streamMessage (Call.execute in IO), transcribe, synthesize
│   ├── SettingsRepository.kt   — CRUD for all settings
│   └── VoiceRepository.kt      — MediaRecorder recording + playback
├── settings/
│   └── SettingsDataStore.kt    — EncryptedSharedPreferences + regular SharedPreferences
└── local/                      — Room DB

di/AppModule.kt                 — Hilt: OkHttpClient, Retrofit, VoiceRepository, HealthCheckManager
util/Constants.kt               — DEFAULT_API_URL, PERSONAS, AGENTS, AGENT_PROMPTS, PERSONA_PROMPTS, MODELS
```

## Key Patterns & Pitfalls

### DEFAULT_API_URL — THE #1 PITFALL
`Constants.kt` has `DEFAULT_API_URL` which seeds the `primaryUrl` in `AppSettings`. When this is wrong, every request fails silently. 

**Two scenarios, two correct defaults:**

| Scenario | DEFAULT_API_URL | How it works |
|----------|----------------|-------------|
| Same WiFi | `http://<YOUR_LOCAL_IP>:8643` | socat on 8643 → Hermes on 8642 |
| USB / ADB | `http://localhost:8643` | `adb reverse tcp:8643 tcp:8642` |

The phone and PC may be on **different subnets** (e.g., phone on 10.4.x.x via USB tethering, PC on 192.168.0.x). In that case, Wi-Fi IP won't work — use `localhost:8643` with `adb reverse`. Check with `$ADB logcat -s HealthCheckManager:*` — if you see `failed to connect to /<YOUR_LOCAL_IP>`, the phone is on a different network.

**After `pm clear` or fresh install, settings revert to this default.** If the user reports "connection error", check DEFAULT_API_URL FIRST, then check the phone's IP via `$ADB shell ip addr` and verify network reachability.

### SSE Streaming — MUST use Dispatchers.IO
In `ChatRepository.streamMessage()`:
```kotlin
val call: Call<ResponseBody> = api.chatCompletionStream(request)
val response: Response<ResponseBody> = withContext(Dispatchers.IO) { call.execute() }
// ...
sseClient.parseStream(body).flowOn(Dispatchers.IO).collect { ... }
```
**Pitfall:** `@Streaming suspend fun` in Retrofit 2.9 closes the connection before SSE completes. Use `Call<ResponseBody>` + `call.execute()` in `Dispatchers.IO`.

**Pitfall:** `HttpLoggingInterceptor.Level.BODY` buffers the entire SSE stream. Use `Level.HEADERS`.

**Pitfall:** `NetworkOnMainThreadException` — SSE reading must be on `Dispatchers.IO`.

### Agent Presets vs Personas — SEPARATE CONCEPTS

### Voice Chat UX — Tap-toggle cycle, NOT push-to-talk

The user rejected push-to-talk. Use tap-to-toggle:
1. Tap 🎙️ → voice mode ON → SpeechRecognizer starts listening
2. `onEndOfSpeech` → auto-transcribes → sends to LLM → SSE streaming
3. `SseEvent.Done` → TextToSpeech.speak → `onDone` → auto-restart listening
4. Tap 🎙️ again → stop listening, voice mode OFF

**VoiceInputButton**: simple `FilledIconButton(onClick=...)` — NOT `detectTapGestures(onLongPress=...)`. Color-coded: Grey=off, Primary=on, Red=recording, Tertiary=playing.

**VoiceStatusBar**: compact `AnimatedVisibility` between message list and input bar with Russian labels:
- `🎙️ Слушаю...` (red) — recording
- `🧠 Думаю...` (tertiary) — transcribing/LLM
- `🔊 Отвечаю...` (primary) — playing TTS
**Do NOT merge them.** They are orthogonal:
- **Agent presets** (🤖 button): `general, build, plan, review, safe, explore, scout, deep-explore, claw, composter` — control TOOLS/CAPABILITIES via system prompt
- **Personas** (🎭 button): `default, technical, concise, creative, helpful, teacher, philosopher, noir, shakespeare, pirate, surfer, catgirl, kawaii, uwu, hype` — control STYLE/TONE via system prompt

Both are sent as `role: system` messages in `buildApiMessages()`. Agent prompt goes first, then persona, then custom system prompt.

**Pitfall:** When removing OC+/BackendMode during a refactor, AgentSelector was accidentally removed too because it shared the same code path. Always verify both selectors exist after removing OC+.

### HealthCheckManager — Auto-Failover Logic
- Health-checks `/health` every 30 seconds using a **separate OkHttpClient** (bypasses AuthInterceptor)
- 3 consecutive failures → switch to fallback URL, set `TAILSCALE` mode
- 2 consecutive successes on fallback → probe primary URL
- 2 consecutive successes on primary probe → switch back, set `WIFI` mode
- Both URLs failing → `OFFLINE`

The `AuthInterceptor` gets the active URL via `healthCheckManager.getCurrentUrl()`, NOT from `SettingsDataStore` directly.

### Voice — DO NOT USE (proven failures in this project)

| Approach | What failed | Symptom |
|----------|------------|---------|
| ExoPlayer + OGG | Plays silently on Honor/Huawei devices; `STATE_ENDED` never fires | "Отвечаю..." hangs forever |
| AudioTrack + WAV PCM | `track.write()` blocks before `play()`, or `Thread.sleep` hangs | Status stuck at "Отвечаю..." |
| Proxy faster-whisper (CPU) | 4+ seconds per request, model must reload each time | "Думаю..." takes >10 seconds |
| LocalAI whisper GPU | Backend crashes on Jetson ARM64 (`error reading from server: EOF`), GPU OOM | STT returns empty transcript |
| Proxy TTS → WAV → AudioTrack | Multi-step pipeline: OGG → ffmpeg → WAV → AudioTrack; fragile | Audio never plays |

### Voice — USE THIS (proven working)

**STT: `android.speech.SpeechRecognizer`**
- Fast, free, high quality (Google servers)
- Detects end of speech automatically via `onEndOfSpeech`
- Returns transcript in `onResults(results)` 
- No proxy, no file I/O, no server dependency

**TTS: `android.speech.tts.TextToSpeech`**
- Built into every Android device
- `speak(text, QUEUE_FLUSH, null, id)` — non-blocking
- `UtteranceProgressListener.onDone()` signals completion
- No proxy, no file I/O, no AudioTrack state machine

**Voice Chat Flow (simplified):**
```
🎙️ Tap mic → SpeechRecognizer.startListening()
   → onEndOfSpeech → onResults(transcript)
   → sendMessage(transcript) → SSE → LLM response  
   → TextToSpeech.speak(text) → onDone → auto-restart listening
```

See `references/voice-pitfalls.md` for the full debugging history of failed voice approaches (ExoPlayer, AudioTrack, proxy whisper, LocalAI GPU).
**Hermes API server does NOT expose `/api/audio/*` REST endpoints** — they return 404. STT/TTS are internal tools (`tools/transcription_tools.py`, `tools/tts_tool.py`) accessible only to the agent loop, not via HTTP.

**Solution: `voice_proxy.py`** — a lightweight HTTP wrapper on port 8647 that calls Hermes internal tools and exposes them as simple endpoints:

```
POST /stt  — multipart audio file → {"transcript": "..."}
POST /tts  — JSON {"text": "..."} → audio/ogg binary
GET /health — {"status": "ok"}
```

**Script location:** `/home/user/dev/Opencode/voice_proxy.py` (committed to the project).
**Start:** `cd /home/user/dev/Opencode && python3 voice_proxy.py` (uses Hermes venv).
**ADB forward:** `$ADB reverse tcp:8647 tcp:8647`.

**Critical implementation details:**
- `text_to_speech_tool()` returns a **JSON string**, not a dict — must `json.loads()` before accessing fields
- TTS output is **OGG Opus** (not MP3) when using Piper/localai provider — detect MIME type from file extension
- STT accepts raw audio bytes (multipart or direct body), saves to temp file, calls `transcribe_audio()`
- The proxy imports from `tools.*` modules via `sys.path` pointing to `~/.hermes/hermes-agent/`

**Docker voice-assistant infrastructure (discovered, running on User's machine):**
- `voice-assistant-openai-stack-relay` on 127.0.0.1:8089 — LiteLLM-based OpenAI-compatible API with models listed (STT/TTS/LLM/agents), but audio endpoints 404
- `voice-assistant-opencode-adapter` on 8798-8799
- `voice-assistant-openhands-adapter` on 8791, 8797
- `voice-assistant-clawcode-adapter` on 8790, 8796
- `voice-assistant-agent-registry` on 8794
- `voice-assistant-skills-manager` on 8795
- Image: `kamilkrawiec/piper-openai-tts:latest` (1.06GB) — Piper TTS engine

See `references/voice-proxy-setup.md` for the full proxy script and setup details.

### Build on ARM64 — QEMU Wrapper
The host is ARM64 but Android SDK tools (AAPT2) are x86-64. A QEMU wrapper script at `/home/user/Android/Sdk/platform-tools/adb` bridges this. The real binary is `adb.real` in the same directory. Same pattern applies to other SDK tools.

### Testing Discipline
**Always test before claiming success.** After building and installing:
1. **Verify APK freshness:** `ls -la app/build/outputs/apk/debug/app-debug.apk` — must be seconds-old, not minutes-old
2. Check `$ADB logcat -s ChatVM:D VoiceRepo:D HermesGUI:D` — should show URL rewriting, recording, STT results
3. Verify no `AndroidRuntime:E` crashes
4. If "connection error" — check DEFAULT_API_URL in Constants.kt FIRST (it's been wrong before: 192.168.1.100 instead of <YOUR_LOCAL_IP>)
5. After `pm clear` — settings revert to defaults; URL and key are pre-filled from Constants
6. If HealthCheckManager shows `failed to connect to /<YOUR_LOCAL_IP>`, the phone is on a different subnet — check `$ADB shell ip addr | grep 'inet '` and set up `adb reverse`

### ADB Reverse Multi-Port Pattern
When phone is connected via USB, services on the PC become reachable through `localhost` on the phone via `adb reverse`:

```bash
ADB=/home/user/Android/Sdk/platform-tools/adb

# Hermes API (chat)
$ADB reverse tcp:8643 tcp:8642    # phone localhost:8643 → PC localhost:8642

# Voice proxy (STT/TTS)
$ADB reverse tcp:8647 tcp:8647    # phone localhost:8647 → PC localhost:8647

# Optional: OpenAI relay (more LLM models)
$ADB reverse tcp:8089 tcp:8089    # phone localhost:8089 → PC relay

# Verify
$ADB reverse --list
```

**Pitfall:** ADB reverse tunnels are lost on USB disconnect. Re-run on each reconnect. The app's `Fallback URL` field in settings can hold the Wi-Fi IP for when USB is disconnected.

## Settings Data Flow

```
SettingsScreen → SettingsViewModel → SettingsRepository → SettingsDataStore
                                                              ├── encryptedPrefs (apiKey)
                                                              └── regularPrefs (everything else)

AuthInterceptor reads: HealthCheckManager.getCurrentUrl() + SettingsDataStore.getSettings().apiKey
HealthCheckManager reads: SettingsDataStore.getSettings().primaryUrl / fallbackUrl
ChatViewModel reads: SettingsDataStore.settingsFlow (selectedAgent, selectedPersona, selectedModel)
```
