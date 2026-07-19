# Android Voice Integration Pattern

Complete Kotlin/Jetpack Compose implementation for push-to-talk voice messages with Hermes.

## Architecture

```
VoiceInputButton (Compose) → VoiceRepository → Hermes STT API → text
    → ChatViewModel (existing LLM flow) → Hermes TTS API → audio → MediaPlayer
```

## Key classes

### VoiceRepository — manages recording, STT, TTS, playback

```kotlin
@Singleton
class VoiceRepository @Inject constructor(
    private val api: HermesApi,
    @ApplicationContext private val context: Context
) {
    private var mediaRecorder: MediaRecorder? = null
    private var outputFile: File? = null
    private var mediaPlayer: MediaPlayer? = null

    fun startRecording(): File {
        outputFile = File(context.cacheDir, "voice_${System.currentTimeMillis()}.ogg")
        mediaRecorder = MediaRecorder(context).apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.OGG)
            setAudioEncoder(MediaRecorder.AudioEncoder.OPUS)
            setAudioSamplingRate(16000)
            setAudioEncodingBitRate(32000)
            setOutputFile(outputFile!!.absolutePath)
            prepare()
            start()
        }
        return outputFile!!
    }

    fun stopRecording(): File? {
        mediaRecorder?.apply {
            stop()
            release()
        }
        mediaRecorder = null
        return outputFile
    }

    suspend fun transcribe(audioFile: File): String {
        val bytes = audioFile.readBytes()
        val base64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
        val payload = """{"audio":"data:audio/ogg;base64,$base64"}"""
        val requestBody = payload.toRequestBody("application/json".toMediaType())
        val response = api.transcribe(requestBody)
        if (response.isSuccessful) {
            return response.body()?.transcript ?: ""
        }
        throw Exception("STT failed: ${response.code()}")
    }

    suspend fun synthesize(text: String): ByteArray {
        val requestBody = """{"text":${text.toJson()}}""".toRequestBody("application/json".toMediaType())
        val response = api.speak(requestBody)
        if (response.isSuccessful) {
            val body = response.body()?.string() ?: throw Exception("Empty TTS response")
            val json = JSONObject(body)
            val dataUrl = json.getString("data_url")
            // data_url format: "data:audio/mpeg;base64,..."
            val base64Audio = dataUrl.substringAfter("base64,")
            return Base64.decode(base64Audio, Base64.DEFAULT)
        }
        throw Exception("TTS failed: ${response.code()}")
    }

    fun playAudio(audioData: ByteArray) {
        val tempFile = File.createTempFile("tts_", ".mp3", context.cacheDir)
        tempFile.writeBytes(audioData)
        mediaPlayer = MediaPlayer().apply {
            setDataSource(tempFile.absolutePath)
            prepare()
            start()
            setOnCompletionListener {
                tempFile.delete()
                release()
            }
        }
    }
}
```

### HermesApi additions

```kotlin
@POST("api/audio/transcribe")
suspend fun transcribe(@Body body: RequestBody): Response<TranscriptionResponse>

@POST("api/audio/speak")
suspend fun speak(@Body body: RequestBody): Response<ResponseBody>
```

### VoiceInputButton — Compose push-to-talk

```kotlin
@Composable
fun VoiceInputButton(
    isRecording: Boolean,
    onStartRecording: () -> Unit,
    onStopRecording: () -> Unit
) {
    val scale = remember { Animatable(1f) }
    LaunchedEffect(isRecording) {
        if (isRecording) {
            // Pulsing animation
            launch {
                while (isActive) {
                    scale.animateTo(1.3f, tween(600))
                    scale.animateTo(1f, tween(600))
                }
            }
        } else {
            scale.snapTo(1f)
        }
    }

    IconButton(
        onClick = {},
        modifier = Modifier
            .graphicsLayer(scaleX = scale.value, scaleY = scale.value)
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = {
                        onStartRecording()
                        tryAwaitRelease()
                        onStopRecording()
                    }
                )
            }
    ) {
        Icon(
            Icons.Default.Mic,
            contentDescription = "Голос",
            tint = if (isRecording) Color.Red else MaterialTheme.colorScheme.onSurface
        )
    }
}
```

### ChatInputBar integration

```kotlin
Row {
    VoiceInputButton(isRecording, onStartRecording, onStopRecording)
    OutlinedTextField(...) // weight(1f)
    SendButton(...)
}
```

### ChatViewModel voice flow

```kotlin
fun startRecording() {
    voiceRepository.startRecording(context)
    _uiState.update { it.copy(isRecording = true) }
}

fun stopRecording() {
    viewModelScope.launch {
        val file = voiceRepository.stopRecording() ?: return@launch
        _uiState.update { it.copy(isRecording = false) }
        try {
            val transcript = voiceRepository.transcribe(file)
            file.delete()
            if (transcript.isNotBlank()) {
                voiceInputUsed = true // flag for TTS after response
                sendMessage(transcript)
            }
        } catch (e: Exception) {
            // Show error toast
        }
    }
}

// In SseEvent.Done handler:
if (voiceInputUsed) {
    voiceInputUsed = false
    synthesizeAndPlay(assistantText)
}
```

## AndroidManifest.xml

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

### Runtime permission request (in MainActivity)

```kotlin
private val requestPermissionLauncher = registerForActivityResult(
    ActivityResultContracts.RequestPermission()
) { isGranted ->
    if (!isGranted) {
        Toast.makeText(this, "Разрешите микрофон для голосового ввода", Toast.LENGTH_LONG).show()
    }
}

// Check before first voice use:
if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
    != PackageManager.PERMISSION_GRANTED) {
    requestPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
}
```

## Pitfalls on Android

1. **MediaRecorder Opus needs API 29+.** On older devices, use AAC or link `Concentus` Java Opus encoder.
2. **Base64 in JSON:** A 15-second Opus recording (~50 KB) becomes ~67 KB base64. JSON body ~67 KB — well within limits. Don't record > 60 seconds without chunking.
3. **MediaPlayer temp files:** Clean up in `setOnCompletionListener`. Don't leak temp files in cache dir.
4. **Audio focus:** Consider `AudioManager.requestAudioFocus()` for proper audio behavior with other apps.
5. **Foreground service:** If voice recording continues when app is backgrounded, use `foregroundServiceType="microphone"` (API 34+).
