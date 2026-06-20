# Voice Proxy Setup & Audio Integration

## Problem: Hermes API has no REST audio endpoints

The Hermes API server (`/v1/chat/completions`, `/v1/models`, `/v1/toolsets`) does NOT expose STT/TTS as REST. Both `/api/audio/transcribe` and `/api/audio/speak` return **404**.

STT and TTS are internal Python tools (`tools/transcription_tools.py`, `tools/tts_tool.py`) accessible only to the agent loop.

## Solution: `voice_proxy.py` (port 8647)

A lightweight `http.server` wrapper at `/home/user/dev/Opencode/voice_proxy.py` that:
- Imports Hermes internal tools via `sys.path` → `~/.hermes/hermes-agent/`
- Exposes `POST /stt` — accepts raw audio bytes, returns `{"transcript": "..."}`
- Exposes `POST /tts` — accepts `{"text": "..."}`, returns `audio/ogg` binary
- Exposes `GET /health` — `{"status": "ok"}`

### Start the proxy

```bash
cd /home/user/dev/Opencode && python3 voice_proxy.py
# Uses system python3 — Hermes tools are importable from sys.path
```

The proxy binds to `0.0.0.0:8647`.

### Key implementation details

1. **`text_to_speech_tool()` returns a JSON string, NOT a dict.** Must `json.loads()` before accessing `.get("file_path")`.

2. **TTS output is OGG Opus** (not MP3) when using `localai-piper` provider. Detect MIME type from file extension:
   ```python
   if audio_path.endswith(".ogg") or audio_path.endswith(".opus"):
       mime = "audio/ogg"
   elif audio_path.endswith(".wav"):
       mime = "audio/wav"
   else:
       mime = "audio/mpeg"
   ```

3. **STT accepts raw audio bytes.** Saves to temp file with detected extension (`.ogg`, `.wav`, `.mp3`), calls `transcribe_audio()`, cleans up.

4. **TTS also stores result in `media_tag`** — fallback parsing: `media_tag.split("MEDIA:")[1].strip()`.

### Test from command line

```bash
# Health
curl http://localhost:8647/health

# TTS
curl -X POST http://localhost:8647/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Привет, User!"}' \
  -o /tmp/test.ogg
file /tmp/test.ogg  # → Ogg data, Opus audio

# STT (send audio file directly)
curl -X POST http://localhost:8647/stt \
  --data-binary @/tmp/recording.ogg \
  -H "Content-Type: audio/ogg"
# → {"transcript": "привет как дела"}
```

## Docker Voice-Assistant Infrastructure

User's machine has a running voice-assistant Docker stack:

| Container | Port | Purpose |
|-----------|------|---------|
| `voice-assistant-openai-stack-relay` | 127.0.0.1:8089→8088 | LiteLLM proxy: `/v1/chat/completions`, `/v1/models` |
| `voice-assistant-opencode-adapter` | 127.0.0.1:8798-8799 | OpenCode integration |
| `voice-assistant-openhands-adapter` | 127.0.0.1:8791, 8797 | OpenHands integration |
| `voice-assistant-clawcode-adapter` | 127.0.0.1:8790, 8796 | ClawCode integration |
| `voice-assistant-agent-registry` | 127.0.0.1:8794 | Agent registry |
| `voice-assistant-skills-manager` | 127.0.0.1:8795 | Skills management |

The relay lists STT/TTS models (`stt-whisper-cuda-turbo`, `tts-ru-default`, etc.) in `/v1/models` but audio endpoints return 404 — only chat completions work. Use `voice_proxy.py` for audio.

### Relay test

```bash
# List models (includes STT/TTS/LLM/agent entries)
curl http://localhost:8089/v1/models | jq '.data[].id'

# Chat completion works
curl http://localhost:8089/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

## ADB Reverse Setup (Phone Access)

```bash
ADB=/home/user/Android/Sdk/platform-tools/adb

# Core services
$ADB reverse tcp:8643 tcp:8642   # Hermes API via socat
$ADB reverse tcp:8647 tcp:8647   # Voice proxy

# Optional
$ADB reverse tcp:8089 tcp:8089   # OpenAI relay (more LLM models)

# Verify
$ADB reverse --list

# Test from phone
$ADB shell "curl -s http://localhost:8643/health"
$ADB shell "curl -s http://localhost:8647/health"
```

**Pitfall:** ADB reverse tunnels are lost on USB disconnect. Re-run on reconnect. For persistent access without USB, use Tailscale mesh IP or the Fallback URL field in app settings.

## Android Voice Flow

```
🎙️ Push-to-talk (VoiceInputButton)
    │
    ▼
MediaRecorder (Opus/OGG, 16kHz mono)
    │
    ▼
OkHttp POST localhost:8647/stt  (raw audio bytes)
    │
    ▼
voice_proxy.py → transcribe_audio() → faster-whisper
    │
    ▼
Text → ChatViewModel.sendMessage() → Hermes LLM (SSE)
    │
    ▼
Response text → OkHttp POST localhost:8647/tts
    │
    ▼
voice_proxy.py → text_to_speech_tool() → Piper TTS
    │
    ▼
OkHttp response body (OGG bytes) → MediaPlayer → 🔊 speaker
```

The Android `VoiceRepository` is self-contained (no Retrofit dependency) — uses OkHttp directly with `VOICE_PROXY_URL = "http://localhost:8647"`.
