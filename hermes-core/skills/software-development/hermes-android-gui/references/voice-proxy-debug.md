# Voice Proxy Debug Log — June 2026

## Final working state

STT and TTS both moved to Android on-device (SpeechRecognizer + TextToSpeech).
Voice proxy on :8647 is optional fallback.

## What was tried for TTS playback (all failed)

| Approach | Result |
|----------|--------|
| ExoPlayer + OGG file | No audio output, STATE_ENDED never fires, hangs forever |
| AudioTrack + PCM | track.write() blocks indefinitely even after track.play() |
| MediaPlayer + OGG from cacheDir | setDataSource() succeeds, prepare() succeeds, start() succeeds, no sound |
| MediaPlayer + WAV from proxy | Same — no audio |
| Android TextToSpeech | **WORKS** — reliable, clear audio, Russian voice |

## What was tried for STT (progression)

| Approach | Quality | Speed | Stability |
|----------|---------|-------|-----------|
| faster-whisper large-v3 (CPU) | Best | 30s+ | OK but slow |
| faster-whisper medium (CPU) | Good | 4s (cached) | OK |
| faster-whisper base (CPU) | Poor | 2s | OK |
| LocalAI whisper.cpp (GPU) | - | - | CRASHES |
| LocalAI faster-whisper (GPU) | - | - | Backend not installed |
| Android SpeechRecognizer | Best | 2-3s | STABLE |

## Jetson GPU status

- CUDA 13.0 available (nvidia-smi works)
- ctranslate2 in Hermes venv reports 0 CUDA devices
- LocalAI whisper backend fails: "could not load model: rpc error: EOF"
- Piper TTS via LocalAI works fine (0.4s)
- Edge TTS works (cloud, ~10s)

## Hermes Audio API

- Hermes API server (:8643) does NOT expose /api/audio/* endpoints
- Gateway has internal STT/TTS tools but no REST endpoints
- Only /v1/chat/completions, /v1/models, /v1/toolsets available
- Voice proxy wraps internal tools as HTTP

## ffmpeg conversion

OGG/Opus → WAV for Android playback:
```bash
ffmpeg -y -i input.ogg -ar 16000 -ac 1 -sample_fmt s16 output.wav
```
ffmpeg available at /usr/bin/ffmpeg.
