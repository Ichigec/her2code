# Voice Pipeline Lessons (2026-06-13)

## What worked

| Component | Approach | Result |
|-----------|----------|--------|
| STT | Android SpeechRecognizer | ✅ Instant, free, high quality Russian |
| LLM | Hermes API SSE streaming | ✅ Always worked |
| TTS generation | Hermes proxy + ffmpeg OGG→WAV | ✅ Reliable WAV output |
| TTS playback | MediaPlayer + WAV file | ✅ Native support, simple callbacks |
| Recording fallback | MediaRecorder OGG/Opus | ✅ Works on API 29+ |

## What failed

| Component | Approach | Failure mode |
|-----------|----------|-------------|
| STT | Proxy + faster-whisper CPU | 4-30 sec latency, model quality issues |
| STT | LocalAI whisper.cpp | Model load error (OOM on Jetson) |
| STT | LocalAI faster-whisper GPU | Backend not installed |
| TTS playback | ExoPlayer + OGG | Silent, STATE_ENDED never fired |
| TTS playback | AudioTrack + PCM | Write blocked, buffer issues |
| TTS | Android TextToSpeech | Engine not available for Russian on Honor |

## Architecture Decision

**Primary:** SpeechRecognizer (STT) + Proxy WAV→MediaPlayer (TTS)
**Fallback:** MediaRecorder OGG → Proxy whisper (STT) + same TTS

## Key files

- `/home/user/dev/Opencode/voice_proxy.py` — HTTP proxy for TTS (port 8647)
- `/home/user/dev/Opencode/app/.../VoiceRepository.kt` — Android voice logic
- `/home/user/dev/Opencode/app/.../ChatViewModel.kt` — Voice chat cycle

## Debugging recipe

```bash
# 1. Check proxy
curl -s http://localhost:8647/health

# 2. Test TTS end-to-end
curl -s -X POST http://localhost:8647/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"Привет"}' -o /tmp/test.wav
file /tmp/test.wav  # Should be: RIFF WAVE audio, 16-bit mono 16000 Hz

# 3. Check ADB reverse
adb reverse --list | grep 8647

# 4. Watch phone logs
adb logcat -c && adb logcat -s VoiceRepo:D ChatVM:D

# 5. Full rebuild if stale APK
rm -rf app/build && ./gradlew assembleDebug --no-build-cache
```
