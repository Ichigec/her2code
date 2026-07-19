# Voice Pitfalls & Debugging Log

## Session: 2026-06-12 — Voice Chat Development

### Attempts that FAILED:

1. **ExoPlayer OGG playback**: Audio played silently on Honor device. `AVPlayer: isPlaying` appeared in logs but no sound. `STATE_ENDED` never fired → coroutine hung.

2. **AudioTrack WAV PCM**: `track.write()` before `track.play()` caused infinite block. Correct order `play()→write()` still hung — `Thread.sleep(durationMs)` unreliable.

3. **Proxy faster-whisper**: LocalAI's whisper model crashed on Jetson ARM64 (`error reading from server: EOF`). GPU backend not compiled for aarch64. Local faster-whisper `large-v3` took 30+ seconds on CPU, `medium` took 4 seconds. Model re-loaded on every request without caching.

4. **Proxy TTS → AudioTrack pipeline**: Hermes TTS → OGG → ffmpeg → WAV → AudioTrack. Multi-step fragile pipeline. `text_to_speech_tool()` returns JSON string, not dict — must `json.loads()`.

5. **Gradle cache**: APK not updating after code changes. User tested old APK. Symptom: `Log.d()` statements added to code never appeared in logcat. Fix: `rm -rf app/build && ./gradlew assembleDebug --no-build-cache`.

6. **Recording format switching**: Opus/OGG → AAC/MP4 → back to Opus/OGG. Each format change broke STT compatibility.

### What WORKED:

1. **Android SpeechRecognizer**: Direct microphone → text. Fast, free, high quality. No proxy needed. `RecognitionListener.onEndOfSpeech` → `onResults(results)` → transcript.

2. **Android TextToSpeech**: `TextToSpeech.speak()` → `UtteranceProgressListener.onDone()`. Reliable, no proxy needed. `suspendCancellableCoroutine` with `onDone` callback.

3. **SSE text chat**: Hermes API via OkHttp/Retrofit. `Call<ResponseBody>` + `call.execute()` in `Dispatchers.IO`. `flowOn(Dispatchers.IO)` for SSE parsing. NEVER `@Streaming suspend fun` in Retrofit 2.9.

4. **Voice status bar**: `AnimatedVisibility` with Russian labels. Compact, non-blocking.

### Key takeaway for future voice work:

**Android built-in APIs > custom proxy pipelines.** SpeechRecognizer + TextToSpeech are battle-tested, free, and work on every Android device. The proxy approach adds 3-5 failure points (model loading, network, format conversion, audio routing, playback state machines).
