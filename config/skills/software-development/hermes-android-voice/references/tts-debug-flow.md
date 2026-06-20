# TTS Debug Flow — June 2026

Full debugging journey for voice chat on Honor API 36 Android device.

## Working TTS pipeline (final)

```
TextToSpeech.speak(text) → Google TTS engine → speaker
```

This was the ONLY approach that produced audible output. All other methods failed.

## Failed approaches (tested and rejected)

| Method | Symptom | Root cause |
|--------|---------|------------|
| ExoPlayer + OGG | `STATE_ENDED` never fires, coroutine hangs | ExoPlayer state machine doesn't emit ENDED for OGG on this device |
| ExoPlayer + WAV | No sound, coroutine hangs | Same as above |
| MediaPlayer + OGG | No sound, no error | MediaPlayer doesn't support Opus/OGG on this device |
| MediaPlayer + MP3 (Edge TTS) | No sound | MediaPlayer silently fails |
| AudioTrack + WAV PCM | `write()` blocks indefinitely | AudioTrack stops consuming buffer, even with play()→write() ordering |
| AudioTrack + WAV PCM (write before play) | `write()` blocks indefinitely | Opposite order also fails |

## Bug: collectedContent.clear() before TTS

See SEC-1 in skill body. This was discovered by an external analysis ("другой чат") and was the root cause of TTS never being called despite the SSE Done handler running correctly.

## Transcript evidence

Session logs from proc_795f99af1b9d (successful STT with LocalAI whisper):
```
VoiceRepo: Recording stopped: size=41392
VoiceRepo: STT response: 200
VoiceRepo: STT body: {"transcript": "если чувак говорит пять лет занимался бэкэндом..."}
```

Later sessions with broken whisper:
```
VoiceRepo: STT body: {"transcript": ""}  // LocalAI whisper model failed to load
```

## Device info
- Honor phone, Android 16 (API 36)
- Google TTS installed with `config.ru` split
- Connected via USB (ADB reverse for networking)
- RECORD_AUDIO permission granted
