# Android Voice Chat for Hermes — Lessons Learned

## Architecture

```
Phone (Android)                    Server (Jetson/PC)
├── STT: Google SpeechRecognizer    ├── Hermes LLM API (:8642)
├── TTS: Google TTS / Piper         ├── Voice proxy (:8647)
└── Chat: OkHttp SSE streaming      └── cloudflared tunnel (→ internet)
```

## STT: Use Android SpeechRecognizer (not proxy whisper)

Android's built-in `SpeechRecognizer` (Google) outperforms proxy-based whisper:
- **Speed**: ~2-3 seconds end-to-end (whisper on CPU is 4-30 sec)
- **Quality**: Google's models are better than `base`/`medium` whisper
- **No server dependency**: Works even if proxy is down

```kotlin
val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
recognizer.setRecognitionListener(object : RecognitionListener {
    // MUST implement ALL methods including onEvent()
    override fun onResults(results: Bundle?) {
        val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull() ?: ""
    }
    override fun onError(error: Int) { /* handle */ }
    override fun onEvent(eventType: Int, params: Bundle?) {} // REQUIRED
})
val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
}
recognizer.startListening(intent)
```

## TTS: Android TTS for reliability, proxy Piper for quality

| TTS Engine | Speed | Quality | Reliability |
|-----------|-------|---------|-------------|
| Android TTS (Google) | Instant | Good | ✅ 100% |
| Proxy Piper (LocalAI) | 0.4s | Good (Irina) | ⚠️ needs proxy |
| Proxy Edge (cloud) | 5-15s | Best (Svetlana) | ❌ slow |

**Recommendation**: Use Android TTS for latency-sensitive voice chat. Use proxy Piper for better voice quality when speed matters less.

## Critical Bug: `collectedContent.clear()` before reading

In SSE `Done` handler, `finalizeMessage()` calls `collectedContent.clear()`. If you read `collectedContent.toString()` AFTER `finalizeMessage()`, you get an empty string → TTS never fires.

```kotlin
// WRONG:
is SseEvent.Done -> {
    finalizeMessage(conversationId)
    val content = collectedContent.toString() // EMPTY!
    synthesizeAndPlay(content)
}

// CORRECT:
is SseEvent.Done -> {
    val content = collectedContent.toString() // Save BEFORE clear
    finalizeMessage(conversationId)
    synthesizeAndPlay(content)
}
```

## Tunneling for Cellular Access

The Jetson is behind ISP NAT → port forwarding doesn't work for inbound connections.

**Working solutions (no registration):**
1. **Cloudflare Tunnel** (`cloudflared`): `cloudflared tunnel --url http://127.0.0.1:8642 --protocol http2`
   - URL changes on restart: `https://<random>.trycloudflare.com`
   - More reliable than localhost.run
2. **localhost.run** (SSH): `ssh -R 80:localhost:8642 nokey@localhost.run`
   - Less reliable, SSH can hang

**Not working:**
- Public IP + router port forwarding → ISP blocks inbound
- ngrok → requires free account auth token

## Android Development Patterns

### Suspend functions with callbacks
```kotlin
suspend fun speak(text: String): Boolean = withContext(Dispatchers.Main) {
    suspendCancellableCoroutine { cont ->
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onDone(id: String?) { cont.resume(true) }
            override fun onError(id: String?) { cont.resume(false) }
        })
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "id")
        cont.invokeOnCancellation { tts?.stop() }
    }
}
```

### MediaPlayer for WAV playback
```kotlin
MediaPlayer().apply {
    setDataSource(file.absolutePath)
    prepare()
    start()
    setOnCompletionListener { /* cleanup */ }
    setOnErrorListener { _, _, _ -> /* cleanup */; true } // MUST return true
}
```

### Build gotchas
- Gradle cache can prevent code changes from taking effect: use `rm -rf app/build && ./gradlew assembleDebug --no-build-cache`
- `adb reverse tcp:8643 tcp:8642` dies on USB disconnect — need to re-run
- `adb shell pm clear com.hermes.gui.debug` to reset app data between builds
- `adb install -r` for reinstall without uninstalling

### Honor/Huawei log filtering (CRITICAL)
Honor/Huawei devices run `hilogd` alongside AOSP `logd`. System property `hilog.tag=I` means only `Log.i()`, `Log.w()`, and `Log.e()` reach logcat — all `Log.d()` and `Log.v()` are silently dropped.

- **Symptom**: `adb logcat -s YourTag:D` returns nothing, even though the app is running and calling `Log.d()`.
- **Detection**: `adb shell getprop hilog.tag` → `I` means debug logs suppressed.
- **Fix**: Use `Log.i()` instead of `Log.d()` throughout the app.
- **Per-tag override DOES NOT WORK**: `adb shell setprop log.tag.VoiceRepo D` has no effect because hilogd filters first, before AOSP tag-level settings.
- **Reliable log capture**: `adb logcat -d --pid=$(adb shell pidof com.hermes.gui.debug)` — captures ALL logs from the app process regardless of tag or level.

### File corruption by subagent write_file
When subagents write Kotlin source files, they sometimes write `read_file` output (with `N|` line-number prefixes) back to disk instead of actual file content. 

- **Symptom**: KSP compilation fails with "Expecting a top level declaration" on every line.
- **Detection**: `hexdump -C file.kt | head -1` — if first bytes are `31 7c` = `1|`, the file is corrupted.
- **Fix**: `sed -i 's/^[0-9]\+|//' file.kt` removes line-number prefixes.
- **Verify**: `head -1 file.kt` should show `package com.hermes.gui...`, not `1|package ...`.

## Voice Proxy (optional — for non-Android TTS/STT)

Simple HTTP server wrapping Hermes tools:
```python
from faster_whisper import WhisperModel
model = WhisperModel("medium", device="cpu", compute_type="int8")  # Cache globally
# STT: POST /stt with raw audio → {"transcript": "..."}
# TTS: POST /tts with {"text": "..."} → WAV binary
```

## Voice Infrastructure Health Check

Quick verification that all voice components are alive:

```bash
# 1. Voice proxy on :8647 (STT/TTS)
curl -s --max-time 3 http://localhost:8647/health  # → {"status": "ok"}

# 2. Voice relay on :8089 (OpenAI-compatible API)
curl -s --max-time 3 http://localhost:8089/v1/models | jq '.data[].id' | grep -E "stt|tts"

# 3. ADB reverses (phone → PC tunnels)
adb reverse --list  # Must show: 8643→8642, 8647→8647, 8089→8089

# 4. Hermes API relay (socat)
ps aux | grep "socat.*8643"  # Must be running

# 5. Voice proxy watchdog
ps aux | grep "voice_proxy.py"  # Check proxy process + watchdog loop
```

### Voice chat TTS silent-killer checklist
When TTS produces no sound despite text responses arriving:
1. **`collectedContent` capture order** — `finalizeMessage()` clears `collectedContent`. Must capture BEFORE calling it.
2. **`ttsEnabled` flag** — `ChatUiState.ttsEnabled` defaults to `true`, but if set to `false` in state, `synthesizeAndPlay()` returns immediately without speaking.
3. **TTS engine init** — `voiceRepository.initTts(context)` must be called (voice mode start triggers it). Check `Log.i("VoiceRepo", "TTS init: ...")`.
4. **Russian voice data** — `adb shell dumpsys package com.google.android.tts | grep config.ru` — must show `config.ru` split.
5. **Media volume** — TTS plays on STREAM_MUSIC. Check `adb shell dumpsys audio | grep 'STREAM_MUSIC.*index'`.
6. **Honor log visibility** — if NO VoiceRepo/ChatVM logs appear, `adb shell getprop hilog.tag` — if `I`, use `adb logcat --pid=<PID>` instead of `-s` tag filter.
7. **App process running** — `adb shell pidof com.hermes.gui.debug` — if empty, launch via `adb shell am start -n com.hermes.gui.debug/com.hermes.gui.MainActivity`.
