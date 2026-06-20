# AudioTrack PCM Playback Pattern

## The Problem

ExoPlayer and MediaPlayer both failed to reliably play OGG/Opus audio on the target Android device (Honor, API 36):
- **ExoPlayer**: produced no audible output, `STATE_ENDED` callback never fired, coroutine hung indefinitely
- **MediaPlayer**: `setDataSource(file)` on OGG from cache directory threw exceptions or silently failed

## The Solution: AudioTrack + Raw PCM

Convert OGG to WAV/PCM on the server side (via ffmpeg), send raw WAV bytes to Android, play via AudioTrack. Guaranteed to work on all devices.

## Server-side: OGG → WAV conversion

Add to the voice proxy's TTS handler:
```python
subprocess.run(["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1",
    "-sample_fmt", "s16", wav_path], capture_output=True, timeout=10)
```

## Android-side: AudioTrack playback

```kotlin
suspend fun playAudio(audioData: ByteArray): Boolean = withContext(Dispatchers.IO) {
    // 1. Parse WAV header (44 bytes)
    val sampleRate = ((audioData[24].toInt() and 0xFF)
        or ((audioData[25].toInt() and 0xFF) shl 8)
        or ((audioData[26].toInt() and 0xFF) shl 16)
        or ((audioData[27].toInt() and 0xFF) shl 24))
    
    val pcmSize = audioData.size - 44
    val pcmData = ShortArray(pcmSize / 2)
    for (i in 0 until pcmSize / 2) {
        pcmData[i] = ((audioData[44 + i * 2 + 1].toInt() shl 8)
            or (audioData[44 + i * 2].toInt() and 0xFF)).toShort()
    }
    
    // 2. Build AudioTrack with SPEECH content type
    val track = AudioTrack.Builder()
        .setAudioAttributes(AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            .build())
        .setAudioFormat(AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .setSampleRate(sampleRate)
            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
            .build())
        .setBufferSizeInBytes(AudioTrack.getMinBufferSize(
            sampleRate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT))
        .build()
    
    // 3. CRITICAL: play() BEFORE write() — writing before play blocks forever
    track.play()
    track.write(pcmData, 0, pcmData.size)
    
    // 4. Wait for audio to finish
    val durationMs = (pcmData.size * 1000L / sampleRate) + 200
    Thread.sleep(durationMs.coerceAtMost(15000))
    
    track.stop()
    track.release()
}
```

## Key Pitfalls

1. **`play()` before `write()`** — writing PCM to an un-started AudioTrack blocks indefinitely
2. **Buffer too small** — use `getMinBufferSize()`, not a hardcoded value
3. **ExoPlayer `STATE_ENDED`** — this callback is unreliable on some devices
4. **No file I/O** — AudioTrack plays from memory, no temp files needed
