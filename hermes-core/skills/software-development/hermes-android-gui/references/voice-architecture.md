# Voice Architecture: Hermes Android GUI

## Full pipeline

```
User speech
    │
    ▼
MediaRecorder (OGG/Opus, 16kHz mono, 32kbps)
    │  voice_input_*.ogg (~40KB for 8 sec)
    ▼
VoiceRepository.transcribe()
    │  OkHttp POST → http://localhost:8647/stt
    ▼
Voice Proxy (Python HTTP server)
    │  temp file → tools.transcription_tools.transcribe_audio()
    │  faster-whisper (local, model: base)
    ▼
JSON: {"transcript": "распознанный текст"}
    │
    ▼
ChatViewModel.sendMessage(transcript)
    │  Hermes API SSE streaming
    ▼
LLM text response (streamed via SSE)
    │  SseEvent.Done → synthesizeAndPlay(text)
    ▼
VoiceRepository.synthesize(text)
    │  OkHttp POST → http://localhost:8647/tts
    ▼
Voice Proxy
    │  tools.tts_tool.text_to_speech_tool(text)
    │  Piper TTS → OGG file
    │  ffmpeg -i in.ogg -ar 16000 -ac 1 -sample_fmt s16 out.wav
    ▼
WAV bytes (16kHz, 16-bit, mono PCM)
    │
    ▼
VoiceRepository.playAudio()
    │  AudioTrack: play() → write(pcm) → sleep(duration) → stop()
    ▼
Speaker output
```

## Voice Proxy (voice_proxy.py)

HTTP-сервер на порту 8647:
- `GET /health` → `{"status": "ok"}`
- `POST /stt` — бинарное тело (OGG/WAV/MP3), возвращает `{"transcript": "..."}`
- `POST /tts` — JSON `{"text": "..."}`, возвращает WAV бинарник

Запускается из Hermes venv (нужен доступ к `tools.transcription_tools` и `tools.tts_tool`).

## Форматы

| Этап | Формат | Причина |
|------|--------|---------|
| Запись | OGG/Opus 16kHz mono | Android MediaRecorder, малый размер |
| STT | Любой (OGG/WAV/MP3) | faster-whisper принимает всё |
| TTS output | WAV 16kHz 16-bit PCM | AudioTrack требует raw PCM |
| Playback | AudioTrack PCM | 100% надёжно на всех устройствах |

## Почему не ExoPlayer/MediaPlayer

- ExoPlayer: `STATE_ENDED` не срабатывает для OGG → корутина висит
- MediaPlayer: не играет OGG из cacheDir → без звука
- AudioTrack: прямой PCM, синхронный, всегда работает

## Почему ffmpeg, а не прямая отдача OGG

Piper TTS выдаёт OGG. Android AudioTrack не умеет декодить OGG — нужен raw PCM. 
ffmpeg конвертирует на серверной стороне (быстро, ~50ms для 5 сек аудио).
