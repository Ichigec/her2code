package com.hermes.gui.data.remote

import com.hermes.gui.data.remote.dto.*
import okhttp3.ResponseBody
import retrofit2.Call
import retrofit2.Response
import retrofit2.http.*

interface HermesApi {

    @GET("health")
    suspend fun health(): Response<HealthResponse>

    @GET("v1/models")
    suspend fun getModels(): Response<ModelsResponse>

    @GET("v1/toolsets")
    suspend fun getToolsets(): Response<ToolsetsResponse>

    @GET("v1/capabilities")
    suspend fun getCapabilities(): Response<CapabilitiesResponse>

    @POST("v1/chat/completions")
    suspend fun chatCompletion(
        @Body request: ChatRequest
    ): Response<ChatResponse>

    @POST("v1/chat/completions")
    @Streaming
    fun chatCompletionStream(
        @Body request: ChatRequest
    ): Call<ResponseBody>

    // Session management
    @GET("api/sessions")
    suspend fun listSessions(
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): Response<SessionsResponse>

    @POST("api/sessions")
    suspend fun createSession(
        @Body request: CreateSessionRequest
    ): Response<SessionResponse>

    @GET("api/sessions/{id}")
    suspend fun getSession(
        @Path("id") sessionId: String
    ): Response<SessionResponse>

    @GET("api/sessions/{id}/messages")
    suspend fun getSessionMessages(
        @Path("id") sessionId: String
    ): Response<MessagesResponse>

    @DELETE("api/sessions/{id}")
    suspend fun deleteSession(
        @Path("id") sessionId: String
    ): Response<Map<String, Any?>>

    @POST("api/sessions/{id}/chat")
    suspend fun sessionChat(
        @Path("id") sessionId: String,
        @Body request: SessionChatRequest
    ): Response<ChatResponse>

    // Voice endpoints
    @POST("api/audio/transcribe")
    suspend fun transcribe(
        @Body request: TranscribeRequest
    ): Response<TranscriptionResponse>

    @POST("api/audio/speak")
    suspend fun speak(
        @Body request: SpeakRequest
    ): Response<SpeakResponse>
}

data class SessionChatRequest(
    val message: String,
    val model: String? = null
)
