---
name: hermes-voice-integration
description: Integrate voice/audio (STT/TTS) with Hermes — API endpoints, audio formats, client-side patterns for Android/web/desktop.
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags: [hermes, voice, stt, tts, audio, android, integration]
    related_skills: [hermes-agent]
---

# Hermes Voice Integration

How to add voice input (STT) and voice output (TTS) to Hermes clients — mobile apps, web UIs, desktop apps, gateways.

**Key constraint:** Hermes STT/TTS is **file-based** — no WebSocket, no WebRTC, no streaming audio. Audio is sent as complete files, responses come as complete files. Real-time voice-to-voice (phone-call style) requires external infrastructure.

## Trigger conditions

Load this skill when:
- User asks to add voice/audio to a Hermes client (mobile, web, desktop)
- User asks about Hermes STT or TTS capabilities, endpoints, or formats
- User asks how to send audio to Hermes or get speech output
- User mentions "voice chat", "голосовой чат", "voice-to-voice"

## ⚠️ CRITICAL: No REST audio endpoints on the API server

**`POST /api/audio/transcribe` and `POST /api/audio/speak` return 404 on the Hermes API server** (port 8642/8643). These are NOT exposed as HTTP endpoints. STT/TTS are **internal Python tools** (`tools/transcription_tools.py`, `tools/tts_tool.py`) accessible only to the agent loop and Gateway, not via the OpenAI-compatible API server.

The API server serves only: `/v1/chat/completions`, `/v1/models`, `/v1/toolsets`, `/health`.

**Consequence:** Any client (mobile app, web UI, external service) that needs STT/TTS must either:
- Use a **voice proxy** (lightweight HTTP wrapper that calls Hermes internal tools — see below)
- Use the Gateway's platform-specific audio handling (Telegram voice messages, Discord voice channels)
- Use external STT/TTS services directly (Groq, OpenAI, ElevenLabs)

## Voice Proxy — The working pattern

When the API server doesn't expose audio endpoints, create a lightweight Python HTTP proxy on the host that wraps Hermes internal tools:

```
POST /stt  — raw audio bytes → {"transcript": "..."}
POST /tts  — JSON {"text": "..."} → audio/ogg binary
GET /health — {"status": "ok"}
```

**Key implementation details:**
- Import from `tools.transcription_tools` and `tools.tts_tool` via `sys.path` pointing to `~/.hermes/hermes-agent/`
- `text_to_speech_tool()` returns a **JSON string**, not a dict — must `json.loads()` before accessing fields
- TTS output is **OGG Opus** when using Piper/localai provider — detect MIME type from file extension
- STT accepts raw audio bytes, saves to temp file, calls `transcribe_audio()`
- Run via: `cd <project> && python3 voice_proxy.py`
- Keep alive with a watchdog script (health-check every 10s, restart if dead)
- Forward to clients via `adb reverse tcp:8647 tcp:8647` (USB) or Tailscale mesh-IP (cellular)

See the `android-hermes-app` skill's voice section for a full proxy script at `/home/user/dev/Opencode/voice_proxy.py`.

## STT (Speech-to-Text) — Internal tool

**Tool:** `tools/transcription_tools.py::transcribe_audio(file_path: str) → dict`
**Return:** `{"success": True, "transcript": "...", "provider": "local"}`

Supported formats: `.mp3, .mp4, .mpeg, .mpga, .m4a, .wav, .webm, .ogg, .aac, .flac`. Max 25 MB.

Providers (config in `~/.hermes/config.yaml` → `stt:`): `local` (faster-whisper, free), `groq`, `openai`, `mistral`, `xai`, `elevenlabs`.

## TTS (Text-to-Speech) — Internal tool

**Tool:** `tools.tts_tool.py::text_to_speech_tool(text: str) → str`
**Return:** JSON string: `{"success": true, "file_path": "/home/user/.hermes/audio_cache/tts_*.ogg", ...}`
**⚠️ The return is a JSON *string*, not a dict — `json.loads()` before use.**

Providers: `edge` (default, free), `elevenlabs`, `openai`, `mistral`, `xai`, `gemini`, `neutts`, `kittentts`, `piper` (local VITS, 44 languages). Output: Opus `.ogg` for Piper/localai, MP3 for others.

## Critical limitation: No streaming

Hermes has **no WebSocket, no WebRTC, no chunked HTTP audio streaming**. Both STT and TTS operate on complete files.

- **Voice messages / toggle-based voice chat**: record → send file → get transcript → process → TTS file → play. Works well via proxy.
- **Real-time voice-to-voice (phone call style)**: NOT possible through Hermes alone.

## Architecture: Toggle-based voice chat (recommended UX)

Instead of push-to-talk (hold-to-record), use a **tap-to-toggle** cycle:

```
User taps 🎙️ → voice mode ON → auto-listen (8s max)
→ silence/stop → STT → transcript → send to LLM → SSE streaming
→ on Done → TTS → play audio → auto-restart listening
→ User taps 🎙️ → voice mode OFF
```

**UX states** (show a `VoiceStatusBar` between messages and input):
| State | Text | Color |
|-------|------|-------|
| Listening | 🎙️ Слушаю... | Red (errorContainer) |
| Transcribing/LLM | 🧠 Думаю... | Tertiary (tertiaryContainer) |
| Playing TTS | 🔊 Отвечаю... | Blue (primaryContainer) |

**Mic button colors:**
- Grey `MicOff` = voice mode OFF
- Primary `Mic` = voice mode ON, listening
- Red `Mic` (pulsing) = recording
- Tertiary `Mic` = playing TTS response
## Pitfalls

1. **API server has NO audio endpoints.** `/api/audio/transcribe` and `/api/audio/speak` return 404. Use the voice proxy pattern instead.
2. **`text_to_speech_tool()` returns a JSON string, not a dict.** Must `json.loads(result)` before accessing fields like `file_path`.
3. **TTS output format varies by provider.** Piper/localai produces OGG Opus. Edge produces MP3. Detect MIME type from `os.path.splitext(file_path)`.
4. **Voice proxy dies on SSH disconnect or idle.** Use a watchdog script that health-checks every 10 seconds and restarts if needed.
5. **ADB reverse tunnels are lost on USB disconnect.** Re-run `adb reverse` commands on each reconnect. Store Wi-Fi IP as fallback URL in app settings.
6. **Opus recording needs API 29+ on Android.** For older devices, fall back to AAC or use the `Concentus` Java Opus encoder library.
7. **STT provider first-run delay.** If `local` faster-whisper model isn't downloaded, first transcription will be slow (model download ~150 MB). Pre-warm by calling the endpoint once.
8. **Long-press gestures unreliable on some Android devices.** Use simple `onClick` toggle for voice mode instead.

## Android integration

See `references/android-voice.md` for full Kotlin implementation patterns.

Quick reference for the VoiceRepository (proxy-based):
```kotlin
// STT: send raw Opus bytes via OkHttp
val request = Request.Builder()
    .url("http://localhost:8647/stt")  // or Tailscale IP for cellular
    .post(audioBytes.toRequestBody("audio/ogg".toMediaType()))
    .build()

// TTS: send JSON, receive OGG bytes
val json = JSONObject().apply { put("text", text) }
val request = Request.Builder()
    .url("http://localhost:8647/tts")
    .post(json.toString().toRequestBody("application/json".toMediaType()))
    .build()
```

Key Android components for toggle-based voice chat:
- `VoiceInputButton` — toggle (tap on/off), shows color-coded state
- `VoiceStatusBar` — animated bar showing "🎙️ Слушаю...", "🧠 Думаю...", "🔊 Отвечаю..."
- `ChatViewModel.toggleVoice()` — enters/exits the voice chat cycle
- Auto-restart: after TTS playback completes → `delay(300)` → `startListeningCycle()`

## Pitfalls

1. **Base64 overhead:** Audio files are base64-encoded in JSON. For long recordings, this can exceed request limits. Keep recordings < 30 seconds for reliable STT.
2. **TTS one-shot:** The `/api/audio/speak` response audio file is deleted after reading. If the client fails to decode/play, the audio is lost — no retry without re-synthesizing.
3. **STT provider fallback:** If `local` faster-whisper model isn't downloaded, first transcription will be slow (model download). Pre-warm by calling the endpoint once.
4. **Opus on Android:** `MediaRecorder` with Opus needs API 29+. For older devices, fall back to AAC or use `Concentus` Java Opus encoder.
