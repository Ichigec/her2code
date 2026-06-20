---
name: voice-chat-integration
description: Voice chat integration — STT/TTS pipeline, voice proxy architecture, Android voice, audio playback pitfalls.
version: 1.0.0
---

# Voice Chat Integration

Build voice-to-voice chat features on top of Hermes Agent. Covers STT pipeline, TTS configuration, voice proxy architecture, Android voice integration, and common audio playback pitfalls.

## Trigger conditions

Use this skill when the user asks to:
- Add voice/audio input or output to any Hermes-connected app
- Build a voice proxy or STT/TTS bridge
- Debug audio playback issues (MediaPlayer, AudioTrack, ExoPlayer)
- Configure TTS providers (Edge, Piper, ElevenLabs)
- Set up Android speech recognition or TTS
- Debug the voice pipeline (recording → STT → LLM → TTS → playback)

---

## Architecture

Two common architectures depending on reliability needs:

### A. On-device STT/TTS (RECOMMENDED — most reliable)
```
Phone: SpeechRecognizer → text → Hermes LLM → TextToSpeech.speak()
```
Uses Android built-in APIs. No proxy, no server-side audio processing. 
Most reliable across Android devices. Quality: Google TTS neural voices (ru-RU).

### B. Server-side STT/TTS (only when on-device quality insufficient)
```
Phone ──audio──► Voice Proxy :8647 ──► faster-whisper (STT)
Phone ◄──WAV─── Voice Proxy :8647 ◄── Hermes TTS → ffmpeg WAV
```
NOT recommended as primary approach. Proxy dies randomly, audio playback 
(ExoPlayer/MediaPlayer/AudioTrack) unreliable across devices, LocalAI whisper 
crashes on ARM64 Jetson.

---

## Voice UX: Toggle-based auto-cycle

**Use toggle on/off, not push-to-talk.** Users sharply distinguish:
- "голосовые сообщения" (voice messages = one-shot recording, BAD)
- "голосовой чат" (voice chat = tap-to-toggle, auto-cycle, GOOD)

```
🎙️ Tap → voice ON
  ├── 🎙️ Слушаю... (red status bar) — active recognition
  ├── 🧠 Думаю... (purple status bar) — LLM processing
  ├── 🔊 Отвечаю... (blue status bar) — TTS playback
  └── Auto-restart listening (cycle continues)
🎙️ Tap → voice OFF (stop TTS instantly, clear status)
```

Toggle button: 🔊 (blue=enabled) / 🔇 (gray=disabled). Must stop mid-utterance: `tts.stop()`.

Auto-cycle: after SSE Done + TTS complete, if `autoRestartVoice && ttsEnabled`, call `startListening()` again. This creates the continuous voice-to-voice loop.

---

## Voice Proxy (reference: `references/voice_proxy.py`)

A minimal HTTP server exposing:
- `GET /health` — status check
- `POST /stt` — accept audio bytes, return `{"transcript": "..."}`
- `POST /tts` — accept `{"text": "..."}`, return WAV audio

Key implementation notes:
- Use `faster-whisper` directly (import inside handler, first call loads model)
- Cache the model instance globally to avoid reloading on every request
- Convert TTS output (OGG/MP3) to WAV via ffmpeg for Android compatibility
- Detect audio format from magic bytes (RIFF=WAV, ID3=MP3)

---

## TTS Configuration

### Edge TTS (best free quality for Russian)
```bash
hermes config set tts.provider edge
hermes config set tts.edge.voice ru-RU-SvetlanaNeural   # female
# or ru-RU-DmitryNeural   # male
```

### Checking available voices
```python
import edge_tts, asyncio
voices = asyncio.run(edge_tts.VoicesManager.create())
ru = [v for v in voices.voices if 'ru' in v['Locale']]
```

### LocalAI Piper (offline, lower quality)
```bash
hermes config set tts.provider localai-piper
```

---

## Android Voice Pipeline

### STT: SpeechRecognizer (Google, fast)
```kotlin
SpeechRecognizer.createSpeechRecognizer(context).apply {
    setRecognitionListener(object : RecognitionListener {
        override fun onResults(results: Bundle?) {
            val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
            // send text to LLM
        }
        override fun onError(error: Int) { /* handle */ }
        // implement all other interface methods
    })
    startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
    })
}
```

### TTS: Android TextToSpeech (RECOMMENDED)
```kotlin
// Init once (e.g., when voice mode starts)
fun initTts(context: Context) {
    tts = TextToSpeech(context) { status ->
        if (status == TextToSpeech.SUCCESS) tts?.language = Locale("ru")
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

Google TTS with Russian language pack provides neural-quality voices.
No network, no proxy, no audio format issues.

### TTS: Server-side (fallback, unreliable on some Android devices)
ExoPlayer, MediaPlayer, and AudioTrack ALL showed issues on tested devices:
- ExoPlayer: STATE_ENDED never fires → coroutine hangs
- MediaPlayer: silent for OGG/Opus on Honor API 36
- AudioTrack: write() blocks indefinitely

If server-side TTS is required, convert output to WAV 16kHz mono PCM via ffmpeg
and use MediaPlayer with WAV files (ONLY format confirmed working).

---

## Critical Pitfalls

### PITFALL: Reading collectedContent after finalizeMessage clears it
`finalizeMessage()` calls `collectedContent.clear()`. If you read `collectedContent.toString()` AFTER `finalizeMessage()`, you get an empty string. Always save the content FIRST:
```kotlin
// WRONG
finalizeMessage(conversationId)
val text = collectedContent.toString()  // ALWAYS EMPTY

// RIGHT
val text = collectedContent.toString()
finalizeMessage(conversationId)
// use `text` for TTS
```

### PITFALL: AudioTrack.write() before play() blocks forever
`AudioTrack.write()` blocks until the audio hardware consumes data. If `play()` hasn't been called yet, the write blocks indefinitely. Always call `track.play()` BEFORE `track.write()`.

### PITFALL: ExoPlayer STATE_ENDED may never fire on some devices
ExoPlayer's playback state machine sometimes doesn't emit STATE_ENDED for OGG/Opus on certain Android devices. Use a timeout fallback or prefer MediaPlayer for simple file playback.

### PITFALL: MediaPlayer cannot play OGG from cacheDir on some devices
OGG/Opus playback via MediaPlayer works unreliably across Android versions. Convert TTS output to WAV (PCM) for guaranteed playback.

### PITFALL: SpeechRecognizer.Listener requires ALL interface methods
Implement all RecognitionListener methods including `onEvent()`, `onPartialResults()`, etc. Missing methods cause compile errors.

### PITFALL: TTS engine.init may not have completed before speak() is called
`TextToSpeech(context, onInitListener)` initializes asynchronously. Either wait for the listener callback or pre-initialize TTS at app startup.

---

## Voice quality comparison

| Provider | Quality | Latency | Network | Russian | Reliability |
|----------|---------|---------|---------|---------|-------------|
| Android Google TTS | ⭐⭐⭐⭐ | Instant | None | ✅ Neural | ✅✅✅ Most reliable |
| Edge TTS (Svetlana) | ⭐⭐⭐⭐⭐ | ~10s | Required | ✅ Natural | ✅✅ |
| Piper (LocalAI) | ⭐⭐⭐ | ~0.4s | Local | ✅ Robotic | ✅✅ |
| ElevenLabs | ⭐⭐⭐⭐⭐ | ~2s | Required | ✅ Premium | ✅ |

---

## ADB Reverse for local development

Phone connects to PC services via ADB reverse tunneling:
```bash
adb reverse tcp:8643 tcp:8642   # Hermes API (main)
adb reverse --list               # verify
```

Phone then uses `http://localhost:8643` → PC `127.0.0.1:8642`.
Reverse disappears on USB reconnect — re-run.

Voice proxy (8647) is DEPRECATED for STT/TTS — use Android on-device SpeechRecognizer + TextToSpeech instead.

---

## Related files

- Voice proxy server: `references/voice_proxy.py`
