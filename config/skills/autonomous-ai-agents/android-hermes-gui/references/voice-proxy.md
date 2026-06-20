# Voice Proxy Reference

## TTS tool (`text_to_speech_tool`)

The Hermes `text_to_speech_tool(text=...)` function:
- Returns a **JSON string** (not dict), must `json.loads()` before use
- Does NOT accept a `provider` parameter — uses configured provider from `config.yaml`
- Default provider: Piper TTS via LocalAI (`localai-piper`) → outputs OGG/Opus
- Output format: `{"success": true, "file_path": "/home/user/.hermes/audio_cache/tts_*.ogg", ...}`
- File exists at `file_path` — read it and delete after use
- Also has `media_tag` field with `MEDIA:/path/to/file`

## STT tool (`transcribe_audio`)

The Hermes `transcribe_audio(path)` function:
- Accepts path to audio file (.wav, .ogg, .mp3, .mp4, .m4a, etc.)
- Returns dict with `transcript` field
- Uses faster-whisper (local) by default
- Max file size: 25 MB

## Voice Proxy Endpoints

### `POST /stt`
- Accepts raw audio bytes (any format: WAV, OGG, MP4, AAC)
- Returns `{"transcript": "..."}`

### `POST /tts`
- Accepts `{"text": "..."}`
- Returns binary OGG/Opus audio (Content-Type: audio/ogg)
- Sample rate: 24000 Hz, mono

## ADB Reverse Setup

```bash
export ADB=/home/user/Android/Sdk/platform-tools/adb
$ADB reverse tcp:8643 tcp:8642   # Hermes chat API
$ADB reverse tcp:8647 tcp:8647   # Voice proxy
$ADB reverse tcp:8089 tcp:8089   # OpenAI relay (optional)
$ADB reverse --list               # Check active reverses
```

Reverses are LOST on USB disconnect. Re-run after reconnecting.

## ExoPlayer for OGG playback

Android MediaPlayer has poor OGG/Opus support. Use ExoPlayer:

```kotlin
// build.gradle.kts
implementation("androidx.media3:media3-exoplayer:1.3.0")

// Kotlin
val player = ExoPlayer.Builder(context).build()
player.setMediaItem(MediaItem.fromUri(file.toURI().toString()))
player.prepare()
player.play()
```

Listener: `androidx.media3.common.Player.Listener` (NOT the old `ExoPlayer.Listener`)
- `onPlaybackStateChanged(ExoPlayer.STATE_ENDED)` → done
- `onPlayerError(PlaybackException)` → error
