# Android Voice Debugging Reference

## Voice pipeline checklist
1. `curl localhost:8647/health` — proxy alive?
2. `adb reverse --list | grep 8647` — ADB tunnel active?
3. `adb shell curl localhost:8647/health` — phone reaches proxy?
4. `adb logcat -s VoiceRepo:D ChatVM:D` — watch voice logs
5. Permission: `adb shell dumpsys package com.hermes.gui.debug | grep RECORD_AUDIO` — must be `granted=true`

## TTS playback — always use Android TextToSpeech
```kotlin
val tts = TextToSpeech(context) { status -> ... }
tts.language = Locale("ru")
tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "id")
```
Never ExoPlayer or AudioTrack for TTS — they produce silent/hung playback.

## Recording — MediaRecorder OGG/Opus
- API 29+ required for Opus encoder
- Tested working on API 36 (Honor/Huawei)
- File size ~39KB for 8 seconds of speech
- Log: `VoiceRepo: Recording stopped: ... size=39404`

## STT — faster-whisper via proxy
- First request: 30-40s (model download + load)
- Cached requests: ~4s on medium model (CPU, int8)
- Empty transcript means model failed to load — check proxy logs

## Common errors

### `STT body: {"transcript": ""}`
Whisper model not loaded or LocalAI API failed.
Fix: Use local faster-whisper, not API-based provider.

### `NetworkOnMainThreadException`
STT/HTTP call on main thread. Wrap in `withContext(Dispatchers.IO)`.

### `Connection error: null` or `failed to connect to localhost`
- ADB reverse not set up
- Default URL wrong (should be `localhost:8643`, not `192.168.1.100`)
- Proxy process died

### `toggleVoice called, isVoiceActive=true` during recording
User tapped mic again while recording — this exits voice mode.
Normal behavior, not a bug.
