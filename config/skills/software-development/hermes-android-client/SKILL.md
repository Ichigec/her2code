---
name: hermes-android-client
description: Build and debug Android client apps (Kotlin/Jetpack Compose) that connect to Hermes Agent for chat, voice, and tool use. Covers voice pipeline (recording → STT → LLM → TTS → playback), ADB reverse networking, and Hermes API integration.
version: 1.0.0
author: User + Hermes
license: MIT
platforms: [linux, android]
---

# Hermes Android Client

Build Android applications (Kotlin + Jetpack Compose) that connect to a Hermes Agent instance running on a PC. Covers text chat with SSE streaming, voice-to-voice chat, multi-URL failover, and agent/persona selection.

**Trigger:** User asks to build, debug, or extend an Android app that communicates with Hermes.

## Quick Reference

- **Project:** `/home/user/dev/Opencode/`
- **Hermes API:** `http://localhost:8643` (via socat `8643→8642`) or `adb reverse tcp:8643 tcp:8642`
- **Voice proxy:** `/home/user/dev/Opencode/voice_proxy.py` on port 8647
- **ADB:** `/home/user/Android/Sdk/platform-tools/adb` (QEMU wrapper for ARM64)

## Architecture

```
Android App (Kotlin/Compose)          PC (Linux)
├── Chat (SSE streaming) ──► socat:8643 → Hermes API:8642
├── Voice STT ─────────────► voice_proxy:8647 → faster-whisper (local)
├── Voice TTS ─────────────► voice_proxy:8647 → Hermes TTS → ffmpeg → WAV
├── Agent presets ─────────► system prompt in messages[]
└── Personas ──────────────► system prompt in messages[]
```

## Voice Pipeline (Current — June 2026)

**PREFERRED: Android SpeechRecognizer + Android TextToSpeech.** After extensive testing of EVERY playback approach (ExoPlayer, AudioTrack, MediaPlayer, proxy-based TTS), only the built-in Android TTS works reliably on the user's Honor API 36 device. The proxy is no longer needed for STT or TTS — only for edge cases.

### STT: Android SpeechRecognizer

```kotlin
// Listen directly from mic — no recording, no proxy, no files
speechRecognizer.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
})
// Result arrives in onResults() callback — instant, free, Google quality
```

### TTS: Android TextToSpeech (Google TTS)

```kotlin
// Pre-init when voice mode starts
tts = TextToSpeech(context) { status ->
    if (status == TextToSpeech.SUCCESS) tts?.language = Locale("ru")
}

// Speak with completion tracking
tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
    override fun onDone(id: String?) { /* restart listening */ }
    override fun onError(id: String?, code: Int) { /* handle error */ }
})
tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tts_id")
```

### TTS Mute Toggle

Add `🔊/🔇` button in bottom toolbar that stops TTS mid-utterance:

```kotlin
// ChatUiState.kt — add field
data class ChatUiState(
    ...
    val ttsEnabled: Boolean = true,
)

// ChatViewModel.kt — toggle with immediate stop
fun toggleTts() {
    val newState = !_uiState.value.ttsEnabled
    _uiState.update { it.copy(ttsEnabled = newState) }
    if (!newState) voiceRepository.stopTts()  // kill current utterance
}

// VoiceRepository.kt — stop method
fun stopTts() { try { tts?.stop() } catch (_: Exception) {} }

// ChatViewModel.kt — check before speaking
private suspend fun synthesizeAndPlay(text: String) {
    if (!_uiState.value.ttsEnabled) return  // skip if muted
    _uiState.update { it.copy(isPlaying = true) }
    voiceRepository.speak(text)
    _uiState.update { it.copy(isPlaying = false) }
    if (autoRestartVoice) { delay(300); startListeningCycle() }
}
```

**BottomToolbar button**: `VolumeUp` (colored) when enabled, `VolumeOff` (grey) when muted. Use `Icons.Default.VolumeUp` / `Icons.Default.VolumeOff`.

### Why NOT proxy-based TTS

Each playback approach was tested and failed on this device:
| Approach | Result |
|----------|--------|
| ExoPlayer + OGG | Silent, STATE_ENDED never fired |
| AudioTrack + PCM | write() blocked forever |
| MediaPlayer + WAV | Silent (audio routing issue) |
| **Android TextToSpeech.speak()** | ✅ Works |

### Pinned Chat in Hermes GUI

To group all phone messages into one session in the desktop GUI:
```kotlin
// AuthInterceptor.kt
.addHeader("X-Hermes-Session-Id", "android-app")
```
All phone messages appear as one chat in Hermes GUI. App dialog list (Room DB) stays independent.

### Recording fallback (if SpeechRecognizer unavailable)

```kotlin
// MediaRecorder with AAC/MP4 for max compatibility
recorder.apply {
    setAudioSource(MediaRecorder.AudioSource.MIC)
    setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
    setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
    setAudioSamplingRate(16000)
    setAudioChannels(1)
    setAudioEncodingBitRate(32000)
    setOutputFile(file.absolutePath)
    prepare(); start()
}
```

OGG/Opus recording works on API 29+ but AAC/MP4 is safer for older devices. The voice proxy auto-detects format from magic bytes.

### Voice Proxy (TTS only — now DEPRECATED for production)

**CURRENT APPROACH: Android TextToSpeech + SpeechRecognizer are preferred. The proxy is a fallback only.**

A simple HTTP server (`voice_proxy.py`) on port 8647:

- `GET /health` — liveness check
- `POST /tts` — `{text: "..."}` → Hermes TTS → ffmpeg OGG→WAV → audio/wav binary
- `POST /stt` — fallback: raw audio bytes → local faster-whisper → `{transcript: "..."}`

The proxy imports from Hermes venv. For TTS, it calls `text_to_speech_tool(text=text)` which returns JSON with `file_path` key, then converts OGG→WAV via ffmpeg.

**Start the proxy:**
```bash
/home/user/.hermes/hermes-agent/venv/bin/python3 /home/user/dev/Opencode/voice_proxy.py &
```

**Watchdog (auto-restart):**
```bash
while true; do
  curl -s --max-time 2 http://localhost:8647/health > /dev/null || \
    /home/user/.hermes/hermes-agent/venv/bin/python3 /home/user/dev/Opencode/voice_proxy.py &
  sleep 15
done
```

## Network Connectivity

### Problem: Phone on different subnet than PC

Phone IP `10.4.x.x` cannot reach PC IP `192.168.0.x`. Use `adb reverse`:

```bash
export ADB=/home/user/Android/Sdk/platform-tools/adb
adb reverse tcp:8643 tcp:8642   # Hermes API
adb reverse tcp:8647 tcp:8647   # Voice proxy
adb reverse tcp:8089 tcp:8089   # OpenAI relay
```

Then the app uses `http://localhost:8643` as the API URL.

### Multi-URL failover

The app supports primary + fallback URLs with `HealthCheckManager`:
- Pings `/health` every 30 seconds
- 3 consecutive failures → switch to fallback
- 2 consecutive successes on primary → switch back
- UI indicator: green (WiFi), blue (Tailscale), red (offline)

### Public IP + Port Forwarding (for cellular access)

When the phone is on a different network (cellular, remote WiFi), use the public IP with port forwarding or a tunnel.

**Option A: Public IP + Router Port Forwarding**

1. Find public IP: `curl ifconfig.me` → `<YOUR_VPS_IP>`
2. Router: forward TCP port 8643 → `<YOUR_LOCAL_IP>:8643`
3. App default URL: `http://<YOUR_VPS_IP>:8643`
4. On Jetson: `socat TCP-LISTEN:8643,reuseaddr,fork TCP:127.0.0.1:8642 &`

**IMPORTANT**: Cannot test from the Jetson itself (hairpin NAT). Must test from phone on mobile data.
**Socat dies**: Use the Python TCP proxy (`/home/user/dev/Opencode/tcp_proxy.py`) instead — it's more reliable.

**Option B: SSH Reverse Tunnel (PREFERRED)**

When ISP blocks inbound connections, the BEST solution is an SSH reverse tunnel to a VPS (if available), or a free service as fallback.

**Primary: Own VPS with SSH -R (fast, permanent URL)**
```bash
# Enables GatewayPorts on VPS, copies SSH key, creates tunnel:
ssh -o ServerAliveInterval=10 -R 0.0.0.0:8643:localhost:8643 root@your-vps "while true; do sleep 30; done"
```

**Fallback: localhost.run (free, no registration)**
```bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
    -R 80:localhost:8642 nokey@localhost.run
# Output: https://<YOUR_TUNNEL_URL>
```

See `hermes-android-gui` skill for full VPS tunnel setup and cellular testing patterns.

## Agent Presets vs Personas

These are DIFFERENT concepts — keep both in the UI:

| | Agent Presets | Personas |
|---|---|---|
| **Source** | `agent/agents.py` (10 built-in) | `config.yaml` personalities (15) |
| **Purpose** | Tool/capability profile | Style/tone of voice |
| **Examples** | general, build, plan, review | noir, shakespeare, pirate, catgirl |
| **System prompt** | "You are the Build agent..." | "Arrr! Ye be talkin' to Captain..." |
| **Both sent** | Yes — persona prompt appended AFTER agent prompt |

## Receiving SSE Streaming in Kotlin

Critical pattern: do NOT use `@Streaming suspend fun` in Retrofit 2.9 — it closes the connection prematurely. Use `Call<ResponseBody>` + `call.execute()` in `Dispatchers.IO`:

```kotlin
// HermesApi.kt
@Streaming
@POST("v1/chat/completions")
fun chatCompletionStream(@Body request: ChatRequest): Call<ResponseBody>

// ChatRepository.kt
suspend fun streamMessage(...): Flow<SseEvent> = flow {
    val call: Call<ResponseBody> = api.chatCompletionStream(request)
    val response: Response<ResponseBody> = withContext(Dispatchers.IO) { call.execute() }
    // ... parse SSE stream
}.flowOn(Dispatchers.IO)
```

Also: set `HttpLoggingInterceptor.Level.HEADERS` (NOT BODY) — BODY level buffers the entire SSE stream causing timeouts.

## Sharing Sessions to Mobile

To make research/analysis from a Hermes session readable as a standalone dialog in the Android app, inject it into `state.db` as a new session with `source='import'` and a unique title (use `📱 ` prefix). Full recipe: `references/sharing-sessions-to-mobile.md`.\n\n## Common Pitfalls

1. **OGG recording fails silently** — `MediaRecorder` with OGG/Opus requires API 29+. If `startRecording` returns false, check API level and fall back to AAC/MP4.
2. **STT returns empty transcript** — faster-whisper model not loaded or API error. Test directly. Prefer Android SpeechRecognizer over proxy whisper.
3. **AudioTrack blocks forever** — must call `track.play()` BEFORE `track.write()`. Better yet, use MediaPlayer+WAV.
4. **Gradle cache poisoning** — after significant code changes, do `rm -rf app/build && ./gradlew assembleDebug --no-build-cache`.
5. **ADB on ARM64** — use the QEMU wrapper at `/home/user/Android/Sdk/platform-tools/adb`.
6. **Voice proxy dies** — always run with a watchdog loop.
7. **TTS silent/hung** — check proxy health first. If WAV is valid, the issue is Android playback.
8. **Kotlin `suspendCancellableCoroutine<Boolean>`** — lambda return type must match. `MediaPlayer.setOnErrorListener` returns `Boolean` — add `true` at end of lambda.
9. **Hairpin NAT blocks self-testing** — port forwarding cannot be tested from the same machine. Test from mobile data.
10. **"Every second message" fails** — OkHttp reuses closed SSE connections. Fix: `.retryOnConnectionFailure(true)` in OkHttpClient builder AND application-level SSE retry (see `hermes-android-gui/references/sse-retry-pattern.md`).
11. **SSE streaming — use `Call<ResponseBody>` not `suspend fun`** — Retrofit 2.9 `@Streaming suspend fun` closes connection prematurely. Use `Call.execute()` in `Dispatchers.IO`.
12. **HttpLoggingInterceptor.Level.BODY kills SSE** — BODY buffers the entire stream. Use `Level.HEADERS`.
13. **Log.d() invisible on Honor/Huawei** — hilogd suppresses debug-level logs. Use `Log.i()`.
14. **OpenCode protocol events in chat** — `step_start` JSON blobs leak into `delta.content`. Filter with `filterProtocolJson()` (see `hermes-android-gui/references/protocol-event-filter.md`).

## Debugging Voice Issues (Systematic Approach)

When voice doesn't work, instrument BOTH sides before changing anything:

**On phone (adb):**
```bash
adb logcat -c && adb logcat -s VoiceRepo:D ChatVM:D
# Press mic → watch for: "STT ready", "STT result", "TTS done"
```

**On PC (proxy):**
```bash
curl -s http://localhost:8647/health  # proxy alive?
curl -s -X POST http://localhost:8647/tts -d '{"text":"тест"}' ...  # TTS works?
curl -s -X POST http://localhost:8647/stt --data-binary @file.ogg   # STT works?
```

**Correlate:** If proxy returns valid data but phone shows error → network (ADB reverse). If phone shows no logs at all → app not updated (Gradle cache). If proxy fails → restart with watchdog. Fix ONE component at a time, verify, then move on.

See `references/voice-pipeline-lessons.md` for the full voice pipeline test matrix and debugging recipe.
