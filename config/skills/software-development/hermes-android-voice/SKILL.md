---
name: hermes-android-voice
description: "Build voice chat for Hermes Android client — STT, TTS, audio playback, SSE integration, ADB networking. Covers what works, what doesn't, and critical bugs."
version: 2.0.0
category: software-development
metadata:
  hermes:
    tags: [hermes, android, voice, stt, tts, kotlin, jetpack-compose, speechrecognizer, texttospeech]
    related_skills: [hermes-agent]
---

# Hermes Android Voice Chat

Voice chat integration for Hermes Android client (Kotlin + Jetpack Compose). Full pipeline: STT → LLM → TTS → auto-restart loop.

## Architecture (proven working)

```
Phone (Android)                          PC (Server)
├── SpeechRecognizer (Google STT)  ←── fast, free, high quality
├── TextToSpeech (Google TTS)      ←── built-in, reliable, neural Russian
│                                  ├── Hermes LLM (port 8643)
│                                  └── ADB reverse localhost:8643→8642
```

**Do NOT use a voice proxy for STT or TTS on User's setup.** The proxy approach (faster-whisper + Piper TTS via LocalAI) was tested extensively and failed:
- Whisper model crashes on LocalAI GPU (Jetson ARM64)
- CPU faster-whisper (medium model) takes 4+ seconds per request
- Piper TTS via proxy → ExoPlayer/MediaPlayer/AudioTrack ALL fail to produce audible output on Honor API 36
- Proxy dies randomly without watchdog

## STT: Android SpeechRecognizer (Google)

Use Android's built-in `SpeechRecognizer`. No server, no proxy, no API keys.

```kotlin
suspend fun listenAndTranscribe(context: Context): Result<String> =
    suspendCancellableCoroutine { cont ->
        val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull() ?: ""
                recognizer.destroy()
                cont.resume(Result.success(text))
            }
            override fun onError(error: Int) {
                val msg = when(error) {
                    SpeechRecognizer.ERROR_NO_MATCH -> "Не распознано"
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Не слышно"
                    SpeechRecognizer.ERROR_NETWORK -> "Нет сети"
                    else -> "Ошибка $error"
                }
                recognizer.destroy()
                cont.resume(Result.failure(Exception(msg)))
            }
            override fun onReadyForSpeech(p: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(p: Bundle?) {}
            override fun onRmsChanged(r: Float) {}
            override fun onBufferReceived(b: ByteArray?) {}
            override fun onEvent(e: Int, p: Bundle?) {}
        })
        recognizer.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
        })
        cont.invokeOnCancellation { recognizer.destroy() }
    }
```

Requires `RECORD_AUDIO` permission (manifest + runtime request).

## TTS: Android TextToSpeech (Google TTS)

**The ONLY reliable TTS approach on User's Honor API 36 device.**

ExoPlayer, MediaPlayer, and AudioTrack ALL failed silently:
- ExoPlayer: `STATE_ENDED` never fires, coroutine hangs
- MediaPlayer: no sound for OGG/Opus, no error
- AudioTrack: `write()` blocks indefinitely even with correct `play()`→`write()` ordering

```kotlin
// Init once (e.g., when voice mode starts)
private var tts: TextToSpeech? = null
fun initTts(context: Context) {
    if (tts != null) return
    tts = TextToSpeech(context) { status ->
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale("ru")
        }
    }
}

// Speak — suspends until playback completes
suspend fun speak(text: String): Boolean = withContext(Dispatchers.Main) {
    suspendCancellableCoroutine { cont ->
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onDone(id: String?) { cont.resume(true) }
            override fun onError(id: String?) { cont.resume(false) }
            override fun onStart(id: String?) {}
        })
        val result = tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tts_id")
        if (result != TextToSpeech.SUCCESS) cont.resume(false)
        cont.invokeOnCancellation { tts?.stop() }
    }
}
```

Google TTS must be installed with Russian language pack:
```bash
adb shell dumpsys package com.google.android.tts | grep splits
# Should show: config.ru
```

## Voice UX: Toggle mode with auto-cycle

**Use toggle (tap on/off), NOT long-press.** Long-press is undiscoverable.

```
🎙️ Tap mic → voice mode ON
├── "🎙️ Слушаю..." (red bar) — SpeechRecognizer listening
├── "🧠 Думаю..." (purple bar) — LLM processing
├── "🔊 Отвечаю..." (blue bar) — TTS speaking
└── Auto-restart listening (cycle)
🎙️ Tap mic again → voice mode OFF
```

## CRITICAL BUG: collectedContent.clear() before TTS

In the SSE streaming `Done` handler, `finalizeMessage()` calls `collectedContent.clear()`. If TTS reads `collectedContent` AFTER clear, it gets an empty string and TTS never fires.

```kotlin
// ❌ BROKEN
is SseEvent.Done -> {
    finalizeMessage(conversationId)      // clears collectedContent
    val content = collectedContent.toString()  // EMPTY
    synthesizeAndPlay(content)           // never called
}

// ✅ FIXED
is SseEvent.Done -> {
    val responseText = collectedContent.toString()  // save BEFORE clear
    finalizeMessage(conversationId)
    if (autoRestartVoice && responseText.isNotBlank()) {
        viewModelScope.launch { synthesizeAndPlay(responseText) }
    }
}
```

## ADB Reverse for USB Connectivity

When phone is on different network (USB tethering, 10.4.x.x):
```bash
adb reverse tcp:8643 tcp:8642   # Hermes API
```

Default URL: `http://localhost:8643` (works via ADB reverse).

For cellular/WiFi fallback, use multi-URL with HealthCheckManager (auto-failover between primary and fallback URLs).

## TTS Provider Notes (for server-side TTS if ever needed)

Hermes TTS configured via `~/.hermes/config.yaml`:

| Provider | Speed | Quality | Notes |
|----------|-------|---------|-------|
| `localai-piper` | 0.4s | OK (Irina) | Local GPU, WAV output |
| `edge` | ~10s | Great (Svetlana) | Microsoft cloud |

Switch: `hermes config set tts.provider localai-piper`

If using server-side TTS, convert OGG/MP3 to WAV 16kHz mono PCM via ffmpeg:
```bash
ffmpeg -y -i input.ogg -ar 16000 -ac 1 -sample_fmt s16 output.wav
```

## TTS Toggle Button

Add a 🔊/🔇 toggle in BottomToolbar to enable/disable voice responses mid-conversation:

```kotlin
// In ChatViewModel
fun toggleTts() {
    val newState = !_uiState.value.ttsEnabled
    _uiState.update { it.copy(ttsEnabled = newState) }
    if (!newState) voiceRepository.stopTts()  // Stop current utterance
}

// In synthesizeAndPlay
if (!_uiState.value.ttsEnabled) return  // Skip TTS if disabled

// In VoiceRepository
fun stopTts() { try { tts?.stop() } catch (_: Exception) {} }
```

BottomToolbar shows `VolumeUp` (синий) when enabled, `VolumeOff` (серый) when disabled.

## TTS Pre-initialization

Call `initTts()` when voice mode starts, NOT lazily on first use:

```kotlin
// In ChatViewModel.startVoiceMode()
voiceRepository.initTts(application.applicationContext)
```

## Connectivity: Cloudflared Tunnel (MOST RELIABLE for cellular access)

When ISP blocks inbound connections (common on residential IPs) or VPN interferes with routing, use Cloudflared. **This was the only tunnel that worked reliably on User's network.**

```bash
# Download once
curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o /tmp/cloudflared
chmod +x /tmp/cloudflared

# Start tunnel (HTTP2 — more reliable than QUIC on some networks)
/tmp/cloudflared tunnel --url http://127.0.0.1:8642 --protocol http2

# Extract URL from log
grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cf.log
```

**Auto-restart + auto-URL extraction:**
```bash
while true; do
  /tmp/cloudflared tunnel --url http://127.0.0.1:8642 --protocol http2 2>/tmp/cf.log
  sleep 3
done
```

**Caveats:**
- URL changes every restart
- If tunnel 404s/530s, cloudflared process died — restart and get new URL
- Can't test from same machine (traffic routes through Cloudflare edge, won't hairpin)

## Connectivity: localhost.run (free, no registration — but LESS STABLE)

Also works as SSH reverse tunnel. BUT on User's network, the SSH connection often hangs before delivering the URL. Cloudflared is preferred.

## Connectivity: Public IP + Port Forwarding

When VPN is **disabled** on the Jetson:
```bash
# Check if VPN is active
ip route get 8.8.8.8 | grep tun   # If output contains "tun", VPN is ON
nmcli -t device status | grep tun  # Alternative check

# Check public IP
curl -s ifconfig.me   # Example: <YOUR_PUBLIC_IP> (User's, without VPN)
                       # Example: <YOUR_VPS_IP> (with VPN)
```

If internet goes direct (no VPN), port forwarding on router works:
1. Router: TP-Link at <YOUR_ROUTER_IP>
2. Forward TCP 8643 → <YOUR_LOCAL_IP>:8643 (Virtual Servers section)
3. Use `http://<public-ip>:8643` in app

**VPN NOTE:** User's Jetson sometimes routes through a VPN tunnel. When VPN is active, port forwarding does NOT work because traffic exits through the VPN, not the router. Disable VPN first.

## Network Debugging

```bash
# Who provides internet?
ip route get 8.8.8.8              # Shows via what interface
curl -s ifconfig.me                # Public IP (changes with VPN on/off)
nmcli device status                # All network interfaces
```

**Hairpin NAT:** Can't test public IP from same machine. Test from phone on cellular data.

## Gradle Clean Build (ARM64 quirks)

When Gradle cache causes stale APK builds:

```bash
rm -rf app/build && ./gradlew assembleDebug --no-build-cache
# Never just ./gradlew assembleDebug if code changes aren't appearing
```

## Background Process Watchdog

socat and voice_proxy.py die randomly. Use simple watchdog loops. **Prefer Python TCP proxy over socat** — socat gets killed more frequently.

### Python TCP Proxy (reliable socat replacement)

```python
#!/usr/bin/env python3
"""Persistent TCP proxy: 0.0.0.0:8643 → 127.0.0.1:8642."""
import socket, threading

LISTEN = ("0.0.0.0", 8643)
TARGET = ("127.0.0.1", 8642)

def proxy(client, addr):
    try:
        backend = socket.create_connection(TARGET, timeout=30)
        def forward(src, dst):
            while True:
                data = src.recv(8192)
                if not data: break
                dst.sendall(data)
        t1 = threading.Thread(target=forward, args=(client, backend), daemon=True)
        t2 = threading.Thread(target=forward, args=(backend, client), daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()
    finally:
        try: client.close()
        except: pass
        try: backend.close()
        except: pass

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(LISTEN)
server.listen(50)
print(f"TCP proxy: {LISTEN} → {TARGET}", flush=True)

while True:
    client, addr = server.accept()
    threading.Thread(target=proxy, args=(client, addr), daemon=True).start()
```

Run with: `python3 /home/user/dev/Opencode/tcp_proxy.py &`

### Watchdog

```bash
# For any service that keeps dying
while true; do
  if ! curl -s --max-time 2 http://localhost:8643/health > /dev/null 2>&1; then
    python3 /path/to/tcp_proxy.py &
  fi
  sleep 15
done
```

## Pitfalls

- **Never call `finalizeMessage()` before capturing TTS text** from `collectedContent` — the method clears the buffer
- **Use Android TextToSpeech, not ExoPlayer/MediaPlayer/AudioTrack** for TTS playback
- **Use Android SpeechRecognizer, not whisper proxy** for STT
- **Toggle (tap), not long-press** for voice activation
- **`SpeechRecognizer` requires `onEvent` method** in RecognitionListener (Android API requirement)
- **`setOnErrorListener` on MediaPlayer must return `true`** — also: `suspendCancellableCoroutine<Boolean>` generic required for type safety
- **Voice proxy dies without watchdog** if used
- **LocalAI whisper fails on Jetson ARM64** — GPU backend not installed, CPU model too slow
- **ADB reverse disappears on USB reconnect** — must re-run after cable plug/unplug
- **ISP blocks inbound connections on residential IPs** — use localhost.run SSH tunnel (preferred) or Cloudflared
- **Gradle caches stale builds** — use `rm -rf app/build && --no-build-cache` when changes don't appear
- **Pre-init TTS on voice mode start**, not lazily — `TextToSpeech(context, listener)` is async
- **socat dies randomly** — use Python TCP proxy (`/home/user/dev/Opencode/tcp_proxy.py`) instead, with watchdog loop
