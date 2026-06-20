package com.hermes.gui.data.repository

import com.hermes.gui.data.remote.HermesApi
import com.hermes.gui.data.remote.SseClient
import com.hermes.gui.data.remote.SseEvent
import com.hermes.gui.data.remote.dto.*
import com.hermes.gui.data.settings.SettingsDataStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import okhttp3.ResponseBody
import retrofit2.Call
import retrofit2.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ChatRepository @Inject constructor(
    private val api: HermesApi,
    private val sseClient: SseClient,
    private val settingsDataStore: SettingsDataStore
) {

    suspend fun sendMessage(
        messages: List<ChatMessage>,
        tools: List<ToolDefinition>? = null
    ): Result<ChatResponse> {
        return try {
            val settings = settingsDataStore.settingsFlow.firstOrNull()
            val request = ChatRequest(
                model = settings?.selectedModel ?: "hermes-agent",
                messages = messages,
                stream = false,
                tools = tools
            )
            val response = api.chatCompletion(request)
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("API error: ${response.code()} ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun streamMessage(
        messages: List<ChatMessage>,
        tools: List<ToolDefinition>? = null,
        temperature: Float? = null
    ): Flow<SseEvent> = flow {
        val settings = settingsDataStore.settingsFlow.firstOrNull()
        val request = ChatRequest(
            model = settings?.selectedModel ?: "hermes-agent",
            messages = messages,
            stream = true,
            tools = tools,
            temperature = temperature
        )

        var attempt = 0
        val maxRetries = 2

        while (attempt <= maxRetries) {
            if (attempt > 0) {
                val delayMs = (1000L * attempt).coerceAtMost(3000L)
                delay(delayMs)
            }

            val call: Call<ResponseBody> = api.chatCompletionStream(request)
            var streamBroken = false

            try {
                val response: Response<ResponseBody> = withContext(Dispatchers.IO) {
                    call.execute()
                }

                if (response.isSuccessful) {
                    val body = response.body()!!
                    sseClient.parseStream(body).flowOn(Dispatchers.IO).collect { event ->
                        if (event is SseEvent.Error) {
                            val msg = event.message ?: ""
                            if (msg.contains("unexpected end") || msg.contains("stream error")) {
                                streamBroken = true
                            } else {
                                emit(event)
                            }
                        } else {
                            emit(event)
                        }
                    }

                    if (streamBroken) {
                        attempt++
                        continue  // retry — connection dropped mid-stream
                    }
                    return@flow  // success
                } else {
                    val errorBody = response.errorBody()?.string() ?: "no error"
                    emit(SseEvent.Error("API error ${response.code()}: $errorBody"))
                    return@flow
                }
            } catch (e: Exception) {
                if (attempt >= maxRetries) {
                    emit(SseEvent.Error("Connection error after retries: ${e.message}"))
                }
                attempt++
            } finally {
                if (!call.isCanceled) call.cancel()
            }
        }
    }

    suspend fun checkHealth(): Result<Boolean> {
        return try {
            val response = api.health()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getModels(): Result<List<ModelDto>> {
        return try {
            val response = api.getModels()
            if (response.isSuccessful) {
                Result.success(response.body()?.data ?: emptyList())
            } else {
                Result.failure(Exception("Failed to fetch models"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getToolsets(): Result<List<ToolsetDto>> {
        return try {
            val response = api.getToolsets()
            if (response.isSuccessful) {
                Result.success(response.body()?.data ?: emptyList())
            } else {
                Result.failure(Exception("Failed to fetch toolsets"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
