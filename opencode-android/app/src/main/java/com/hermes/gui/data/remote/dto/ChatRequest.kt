package com.hermes.gui.data.remote.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class ChatRequest(
    val model: String,
    val messages: List<ChatMessage>,
    val stream: Boolean = false,
    val tools: List<ToolDefinition>? = null,
    @Json(name = "tool_choice") val toolChoice: String? = null,
    val temperature: Float? = null,
    @Json(name = "max_tokens") val maxTokens: Int? = null
)

@JsonClass(generateAdapter = true)
data class ChatMessage(
    val role: String,
    val content: String,
    val name: String? = null,
    @Json(name = "tool_calls") val toolCalls: List<ToolCall>? = null,
    @Json(name = "tool_call_id") val toolCallId: String? = null
)

@JsonClass(generateAdapter = true)
data class ToolCall(
    val id: String,
    val type: String = "function",
    val function: FunctionCall
)

@JsonClass(generateAdapter = true)
data class FunctionCall(
    val name: String,
    val arguments: String
)

@JsonClass(generateAdapter = true)
data class ToolDefinition(
    val type: String = "function",
    val function: ToolFunction
)

@JsonClass(generateAdapter = true)
data class ToolFunction(
    val name: String,
    val description: String,
    val parameters: Map<String, Any?> = emptyMap()
)
