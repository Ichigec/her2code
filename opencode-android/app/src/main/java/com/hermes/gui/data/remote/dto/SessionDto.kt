package com.hermes.gui.data.remote.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class SessionsResponse(
    val `object`: String = "list",
    val data: List<SessionDto> = emptyList(),
    val limit: Int? = null,
    val offset: Int? = null,
    @Json(name = "has_more") val hasMore: Boolean = false
)

@JsonClass(generateAdapter = true)
data class SessionDto(
    val id: String,
    val source: String? = null,
    @Json(name = "user_id") val userId: String? = null,
    val model: String? = null,
    val title: String? = null,
    @Json(name = "started_at") val startedAt: String? = null,
    @Json(name = "ended_at") val endedAt: String? = null,
    @Json(name = "end_reason") val endReason: String? = null,
    @Json(name = "message_count") val messageCount: Int? = null,
    @Json(name = "has_system_prompt") val hasSystemPrompt: Boolean = false,
    @Json(name = "last_active") val lastActive: String? = null,
    val preview: String? = null
)

@JsonClass(generateAdapter = true)
data class CreateSessionRequest(
    val id: String? = null,
    val model: String? = null,
    @Json(name = "system_prompt") val systemPrompt: String? = null,
    val title: String? = null
)

@JsonClass(generateAdapter = true)
data class SessionResponse(
    val `object`: String,
    val session: SessionDto? = null
)

@JsonClass(generateAdapter = true)
data class MessagesResponse(
    val `object`: String = "list",
    @Json(name = "session_id") val sessionId: String? = null,
    val data: List<MessageDto> = emptyList()
)

@JsonClass(generateAdapter = true)
data class MessageDto(
    val role: String? = null,
    val content: String? = null,
    @Json(name = "tool_calls") val toolCalls: List<ToolCallDto>? = null,
    @Json(name = "timestamp") val timestamp: String? = null
)
