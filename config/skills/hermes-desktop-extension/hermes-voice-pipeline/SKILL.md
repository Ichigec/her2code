---
name: hermes-voice-pipeline
description: Voice STT/TTS pipeline for Hermes — proxy server, Android integration, model selection, debugging.
version: 1.0.0
metadata:
  tags: [voice, stt, tts, whisper, android, proxy]
---

# Hermes Voice Pipeline

End-to-end voice pipeline: STT via faster-whisper proxy + TTS via Android built-in engine (or Hermes TTS tools).

## Architecture

```
Android App                    PC (Linux)
  MediaRecorder (OGG/Opus)     
       │                        
       ▼                        
  HTTP POST /stt ──────────► voice_proxy.py (:8647)
       │                        ├─ GET /health
       │                        ├─ POST /stt  → faster-whisper → {"transcript":"..."}
       │                        └─ POST /tts  → Hermes text_to_speech_tool → WAV/OGG
       ▼                        
  LLM (Hermes API :8643)        
       │                        
       ▼                        
  Android TextToSpeech.speak()  ← preferred over proxy TTS + AudioTrack
```

## Voice Proxy

File: `voice_proxy.py` in the project root. Simple Python HTTPServer.

### Critical: model caching
```python
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
    return _whisper_model
```
Do NOT create a new WhisperModel on every request — it reloads the model from disk each time, taking 30-40 seconds.

### Model selection
| Model | Speed (cached) | Quality | Use case |
|-------|---------------|---------|----------|
| `tiny` | <1s | Poor | Testing only |
| `base` | ~2s | Mediocre | Fallback |
| `small` | ~3s | Acceptable | Low-resource devices |
| **`medium`** | **~4s** | **Good** | **Production default** |
| `large-v3` | 30s+ | Excellent | Offline batch processing |

### TTS on proxy
Proxy can also serve TTS via Hermes `text_to_speech_tool`. Converts OGG to WAV with ffmpeg for compatibility.
Prefer Android built-in TTS over proxy TTS — it's non-blocking, reliable, no network, no file I/O.

## Android Integration

### Recording: MediaRecorder OGG/Opus
```kotlin
MediaRecorder().apply {
    setAudioSource(MediaRecorder.AudioSource.MIC)
    setOutputFormat(MediaRecorder.OutputFormat.OGG)
    setAudioEncoder(MediaRecorder.AudioEncoder.OPUS)
    setAudioSamplingRate(16000)
    setAudioChannels(1)
    setAudioEncodingBitRate(32000)
    setOutputFile(file.absolutePath)
    prepare()
    start()
}
```
Requires API 29+. Works reliably on API 36+.

### TTS: Android TextToSpeech (RECOMMENDED)
```kotlin
val tts = TextToSpeech(context) { status -> ... }
tts.language = Locale("ru")
tts.setSpeechRate(0.9f)
tts.setOnUtteranceProgressListener(...) // for completion callback
tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "id")
```
This is the MOST RELIABLE approach. Avoid ExoPlayer and AudioTrack for TTS.

## Pitfalls

### 1. ExoPlayer + OGG = silent playback
ExoPlayer with OGG/Opus may play audio but produce NO SOUND on some Android devices.
The player reports `isPlaying=true` and `STATE_ENDED` may never fire.
**Fix:** Use Android TextToSpeech instead.

### 2. AudioTrack.write() hangs
AudioTrack.write() blocks until audio hardware consumes the buffer.
If play() is called AFTER write(), it blocks forever.
**Fix:** Call play() BEFORE write(). Even then, unreliable — prefer TTS.

### 3. LocalAI whisper model fails to load
Error: `rpc error: code = Unavailable desc = error reading from server: EOF`
The LocalAI container may list whisper models but fail to load them.
**Fix:** Use faster-whisper locally instead.

### 4. Voice proxy dies silently
Background Python processes may die when the shell session exits.
**Fix:** Run with `setsid` or use a watchdog script.

### 5. Room DB schema changes crash on reinstall
After schema changes, old APK's DB is incompatible → `IllegalStateException`.
**Fix:** `adb shell pm clear com.hermes.gui.debug` before reinstalling.

### 6. STT returns empty transcript
- Check proxy is running: `curl localhost:8647/health`
- Check ADB reverse: `adb reverse --list | grep 8647`
- Check model loaded: first request may take 30-40s for model download

## ADB connectivity
```bash
# Forward phone localhost → PC localhost
adb reverse tcp:8643 tcp:8642   # Hermes API
adb reverse tcp:8647 tcp:8647   # Voice proxy
adb reverse tcp:8089 tcp:8089   # LLM relay (optional)

# Check
adb reverse --list
```

## Support Files
- `scripts/voice_proxy.py` — production-ready voice proxy server
- `references/android-voice-debugging.md` — Android-specific debugging guide
