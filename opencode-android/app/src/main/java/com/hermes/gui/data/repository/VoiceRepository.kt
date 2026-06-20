package com.hermes.gui.data.repository

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume

@Singleton
class VoiceRepository @Inject constructor() {

    companion object {
        private const val TAG = "VoiceRepo"
    }

    private var speechRecognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    var isRecording: Boolean = false; private set

    fun initTts(context: Context) {
        if (tts != null) return
        tts = TextToSpeech(context) { status ->
            Log.i(TAG, "TTS init: $status")
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale("ru")
                Log.i(TAG, "TTS ready, Russian set")
            }
        }
    }

    suspend fun listenAndTranscribe(context: Context): Result<String> = suspendCancellableCoroutine { cont ->
        try {
            speechRecognizer?.destroy()
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
            isRecording = true
            speechRecognizer?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(p: Bundle?) {}
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(r: Float) {}
                override fun onBufferReceived(b: ByteArray?) {}
                override fun onEndOfSpeech() { isRecording = false }
                override fun onPartialResults(p: Bundle?) {}
                override fun onEvent(e: Int, p: Bundle?) {}
                override fun onResults(results: Bundle?) {
                    val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull() ?: ""
                    Log.i(TAG, "STT: '$text'")
                    cleanupRecognizer()
                    if (cont.isActive) cont.resume(Result.success(text))
                }
                override fun onError(error: Int) {
                    val msg = when(error) {
                        SpeechRecognizer.ERROR_NO_MATCH -> "Не распознано"
                        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Не слышно"
                        SpeechRecognizer.ERROR_NETWORK -> "Нет сети"
                        else -> "Ошибка $error"
                    }
                    cleanupRecognizer()
                    if (cont.isActive) cont.resume(Result.failure(Exception(msg)))
                }
            })
            speechRecognizer?.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            })
            cont.invokeOnCancellation { cleanupRecognizer() }
        } catch (e: Exception) {
            cleanupRecognizer()
            if (cont.isActive) cont.resume(Result.failure(e))
        }
    }

    fun stopListening() { speechRecognizer?.stopListening(); isRecording = false }
    private fun cleanupRecognizer() { try { speechRecognizer?.destroy() } catch (_: Exception) {}; speechRecognizer = null; isRecording = false }

    suspend fun speak(text: String): Boolean = withContext(Dispatchers.Main) {
        suspendCancellableCoroutine { cont ->
            val engine = tts
            if (engine == null) {
                Log.e(TAG, "TTS not initialized")
                if (cont.isActive) cont.resume(false)
                return@suspendCancellableCoroutine
            }
            engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(id: String?) {}
                override fun onDone(id: String?) {
                    Log.i(TAG, "TTS done")
                    if (cont.isActive) cont.resume(true)
                }
                @Deprecated("Use onError(id, errorCode) instead")
                override fun onError(id: String?) {
                    Log.e(TAG, "TTS error (deprecated)")
                    if (cont.isActive) cont.resume(false)
                }
                override fun onError(id: String?, errorCode: Int) {
                    Log.e(TAG, "TTS error: $errorCode")
                    if (cont.isActive) cont.resume(false)
                }
            })
            val result = engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tts_${System.currentTimeMillis()}")
            Log.i(TAG, "TTS speak: $result")
            if (result != TextToSpeech.SUCCESS) {
                if (cont.isActive) cont.resume(false)
            }
            cont.invokeOnCancellation { engine.stop() }
        }
    }

    fun stopTts() {
        try { tts?.stop() } catch (_: Exception) {}
    }

    fun cleanup() {
        cleanupRecognizer()
        try { tts?.stop(); tts?.shutdown() } catch (_: Exception) {}
        tts = null
    }
}
