# Hermes Audio API — Android Integration Notes

## Constraints
Hermes **does not** support streaming audio. No WebSocket, no WebRTC, no Server-Sent Events for audio.

## STT (Speech-to-Text): `POST /api/audio/transcribe`

**Input:** JSON with `audio` field as base64 data URL.
```json
{"audio": "data:audio/ogg;base64,T2dnRwA..."}
```

**Output:**
```json
{"transcript": "Hello world"}
```

**Supported formats:** `.mp3, .mp4, .mpeg, .mpga, .m4a, .wav, .webm, .ogg, .aac, .flac`
**Max file size:** 25 MB
**Provider:** local faster-whisper (default, model `base`) — requires `pip install faster-whisper`
**Config:** `~/.hermes/config.yaml` → `stt:` section

## TTS (Text-to-Speech): `POST /api/audio/speak`

**Input:** JSON
```json
{"text": "Hello from Hermes"}
```

**Output:**
```json
{"data_url": "data:audio/mpeg;base64,//uQxAAAA..."}
```

**Provider:** edge TTS (default, free) — no API key needed
**Config:** `~/.hermes/config.yaml` → `tts:` section

## Android Implementation

### Recording: MediaRecorder + Opus
```kotlin
val recorder = MediaRecorder()
recorder.setAudioSource(MediaRecorder.AudioSource.MIC)
recorder.setOutputFormat(MediaRecorder.OutputFormat.OGG)
recorder.setAudioEncoder(MediaRecorder.AudioEncoder.OPUS)
recorder.setAudioSamplingRate(16000)
recorder.setAudioEncodingBitRate(32000)
recorder.setOutputFile(file.absolutePath)
recorder.prepare()
recorder.start()
```

Requires Android 10+ (API 29+) for Opus encoder.

### Playback: MediaPlayer from base64
```kotlin
val bytes = Base64.decode(base64Data, Base64.DEFAULT)
val tempFile = File(context.cacheDir, "tts_${UUID.randomUUID()}.mp3")
tempFile.writeBytes(bytes)
val player = MediaPlayer().apply {
    setDataSource(tempFile.absolutePath)
    prepare()
    start()
    setOnCompletionListener { tempFile.delete() }
}
```
