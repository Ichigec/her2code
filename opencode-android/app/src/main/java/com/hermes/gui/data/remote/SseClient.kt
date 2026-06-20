package com.hermes.gui.data.remote

import android.util.Log
import com.hermes.gui.data.remote.dto.*
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import okhttp3.ResponseBody
import java.io.BufferedReader
import java.io.InputStreamReader

sealed class SseEvent {
    data class Content(val text: String) : SseEvent()
    data class ToolStart(
        val toolCallId: String,
        val functionName: String,
        val functionArgs: String?
    ) : SseEvent()
    data class ToolComplete(
        val toolCallId: String,
        val functionName: String,
        val result: String?
    ) : SseEvent()
    data class Done(
        val finishReason: String? = null,
        val usage: Usage? = null
    ) : SseEvent()
    data class Error(val message: String) : SseEvent()
}

class SseClient {

    private val moshi = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()

    private val chatResponseAdapter = moshi.adapter(ChatResponse::class.java)
    private val toolProgressAdapter = moshi.adapter(ToolProgressEvent::class.java)

    fun parseStream(responseBody: ResponseBody): Flow<SseEvent> = flow {
        Log.i("HermesGUI", "SSE: parseStream STARTED")
        try {
            val stream = responseBody.byteStream()
            val reader = BufferedReader(InputStreamReader(stream))
            var line: String?
            var lineCount = 0

            while (reader.readLine().also { line = it } != null) {
                val currentLine = line ?: continue
                lineCount++

                if (currentLine.startsWith("data: ")) {
                    val data = currentLine.removePrefix("data: ").trim()

                    if (data == "[DONE]") {
                        Log.i("HermesGUI", "SSE: [DONE] after $lineCount lines")
                        emit(SseEvent.Done())
                        continue
                    }

                    try {
                        val response = chatResponseAdapter.fromJson(data)
                        if (response != null) {
                            val choice = response.choices?.firstOrNull()
                            val delta = choice?.delta
                            val finishReason = choice?.finishReason

                            if (finishReason != null) {
                                emit(SseEvent.Done(finishReason, response.usage))
                            } else if (delta?.content != null) {
                                emit(SseEvent.Content(delta.content))
                            }
                            delta?.toolCalls?.forEach { tc ->
                                if (tc.function?.name != null) {
                                    emit(
                                        SseEvent.ToolStart(
                                            toolCallId = tc.id ?: "",
                                            functionName = tc.function.name ?: "",
                                            functionArgs = tc.function.arguments
                                        )
                                    )
                                }
                            }
                        }
                    } catch (_: Exception) { continue }
                }
            }
            Log.i("HermesGUI", "SSE: stream ended, $lineCount lines")
        } catch (e: Exception) {
            Log.e("HermesGUI", "SSE: ERROR ${e.javaClass.simpleName}: ${e.message}")
            emit(SseEvent.Error("SSE stream error: ${e.message}"))
        } finally {
            responseBody.close()
        }
    }

    companion object {
        data class ToolProgressEvent(
            val toolCallId: String? = null,
            val functionName: String? = null,
            val functionArgs: String? = null,
            val status: String? = null,
            val result: String? = null
        )
    }
}
