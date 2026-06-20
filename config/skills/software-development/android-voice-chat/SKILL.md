---
name: android-voice-chat
description: Build real-time voice chat into Android apps connecting to Hermes. STT, TTS, audio playback patterns and pitfalls.
version: 1.0.0
category: software-development
tags: [android, voice, stt, tts, speech-recognition, text-to-speech, kotlin, jetpack-compose]
---

# Android Voice Chat with Hermes

Proven patterns for adding voice chat to an Android app backed by Hermes Agent.

## Architecture Decision

| Component | Best choice | Why |
|-----------|------------|-----|
| **STT** | `SpeechRecognizer` (Google) | Free, fast (~2s), high quality. No proxy needed. |
| **TTS** | `TextToSpeech` (Google TTS) | Built-in, reliable, neural Russian voices. No proxy. |
| **LLM** | Hermes API (port 8643) | SSE streaming works reliably |

**Do NOT use** for STT:
- `faster-whisper` on CPU — too slow (4-30s per request)
- LocalAI whisper — GPU memory issues on Jetson
- Proxy-based STT — adds latency, proxy dies

**Do NOT use** for TTS playback:
- `ExoPlayer` — `STATE_ENDED` never fires for OGG on some devices
- `AudioTrack` — `write()` blocks forever if buffer too small
- `MediaPlayer` with internal cache files — may play silently due to audio routing

## Critical Pitfalls

### 1. `collectedContent.clear()` order
**The number one bug**: if `finalizeMessage()` clears `collectedContent` before TTS reads the response text, TTS is silently skipped.

```kotlin
// ❌ BROKEN — TTS never fires because content is already cleared
finalizeMessage(conversationId)
val text = collectedContent.toString() // EMPTY!

// ✅ CORRECT — save before clearing
val responseText = collectedContent.toString()
finalizeMessage(conversationId)
synthesizeAndPlay(responseText)
```

### 2. `suspendCancellableCoroutine` type mismatch
When using `suspendCancellableCoroutine<Boolean>`, the lambda body must return `Boolean` (not `Unit`). All `cont.resume()` calls happen inside callbacks, so the lambda itself returns `Unit`. Fix: ensure the resume path is the last expression.

```kotlin
// ❌ BROKEN — try-catch returns Unit, not Boolean
suspendCancellableCoroutine<Boolean> { cont ->
    try { ... cont.resume(true) } catch { cont.resume(false) }
}

// ✅ CORRECT — no try-catch wrapping the coroutine body
suspendCancellableCoroutine<Boolean> { cont ->
    player.setOnCompletionListener { cont.resume(true) }
    player.setOnErrorListener { _, _, _ -> cont.resume(false); true }
    // last expression is Unit — but that's OK because resume happens via callbacks
}
```

### 3. MediaRecorder `setOnErrorListener` return type
`MediaPlayer.setOnErrorListener` expects a lambda returning `Boolean`. Add `true` at the end.

### 4. `Thread.sleep` on main thread
TTS initialization is async. Don't `Thread.sleep(500)` on the main thread to wait for it. Instead, use the `onInit` callback with `suspendCancellableCoroutine`.

## VoiceRepository Pattern

```kotlin
@Singleton
class VoiceRepository @Inject constructor() {
    private var speechRecognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null

    // Pre-init TTS when voice mode starts
    fun initTts(context: Context) {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) tts?.language = Locale("ru")
        }
    }

    // STT: Google SpeechRecognizer listens directly from mic
    suspend fun listenAndTranscribe(context: Context): Result<String> =
        suspendCancellableCoroutine { cont ->
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
            // ... RecognitionListener → onResults → cont.resume(text)
            // ... onError → cont.resume(failure)
        }

    // TTS: Android TextToSpeech
    suspend fun speak(text: String): Boolean = withContext(Dispatchers.Main) {
        suspendCancellableCoroutine { cont ->
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onDone(id: String?) { cont.resume(true) }
                override fun onError(id: String?, code: Int) { cont.resume(false) }
            })
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tts_id")
        }
    }

    // Stop TTS mid-utterance (for mute toggle)
    fun stopTts() { tts?.stop() }
}
```

## AndroidManifest.xml

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
```

Request permission at runtime via `ActivityResultContracts.RequestPermission`.

## TTS Voice Quality

Google TTS is the default on Android. To ensure high-quality neural voices:
1. Install Google TTS from Play Store if not pre-installed
2. Download Russian voice pack in Settings → Language & Input → Text-to-Speech
3. The device must have `com.google.android.tts` package with `config.ru` split

Verify: `adb shell dumpsys package com.google.android.tts | grep config.ru`

## TTS Toggle (Mute During Playback)

Add `🔊/🔇` toggle button that stops TTS mid-utterance:

```kotlin
// ChatViewModel
fun toggleTts() {
    val newState = !_uiState.value.ttsEnabled
    _uiState.update { it.copy(ttsEnabled = newState) }
    if (!newState) voiceRepository.stopTts()  // immediate stop
}

// VoiceRepository
fun stopTts() { try { tts?.stop() } catch (_: Exception) {} }

// Skip TTS when disabled
private suspend fun synthesizeAndPlay(text: String) {
    if (!_uiState.value.ttsEnabled) return
    // ... speak
}
```

## Pinned Chat in Hermes GUI

To group all phone messages into one session visible in desktop GUI:

```kotlin
// AuthInterceptor.kt
request = request.newBuilder()
    .addHeader("Authorization", "Bearer $apiKey")
    .addHeader("X-Hermes-Session-Id", "android-app")  // fixed session ID
    .build()
```

⚠️ Without this header, each message creates a new session, cluttering the GUI.

## Reference Files

- `references/collected-content-clear-bug.md` — SSE Done handler race condition
- `references/android-audio-playback-issues.md` — ExoPlayer/AudioTrack/MediaPlayer failures

## Voice Proxy (fallback, not recommended)

If Android TTS is not available, a Python proxy wraps Hermes STT/TTS:

```
POST /stt  — audio file → JSON {"transcript": "..."}
POST /tts  — JSON {"text": "..."} → WAV binary
GET /health
```

Piper TTS via LocalAI is fast (0.4s) but medium quality. Edge TTS is cloud-based (~10s latency).
The proxy must convert all audio formats to WAV via ffmpeg for reliable Android playback.

Start proxy: `python3 voice_proxy.py` (needs `faster-whisper` for STT fallback).
