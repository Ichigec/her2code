package com.hermes.gui.data.remote.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class ChatResponse(
    val id: String? = null,
    val `object`: String? = null,
    val created: Long? = null,
    val model: String? = null,
    val choices: List<Choice>? = null,
    val usage: Usage? = null,
    val error: ApiError? = null
)

@JsonClass(generateAdapter = true)
data class Choice(
    val index: Int? = null,
    val message: ResponseMessage? = null,
    val delta: Delta? = null,
    @Json(name = "finish_reason") val finishReason: String? = null
)

@JsonClass(generateAdapter = true)
data class ResponseMessage(
    val role: String? = null,
    val content: String? = null,
    @Json(name = "tool_calls") val toolCalls: List<ToolCallDto>? = null
)

@JsonClass(generateAdapter = true)
data class Delta(
    val role: String? = null,
    val content: String? = null,
    @Json(name = "tool_calls") val toolCalls: List<ToolCallDelta>? = null
)

@JsonClass(generateAdapter = true)
data class ToolCallDelta(
    val index: Int? = null,
    val id: String? = null,
    val type: String? = null,
    val function: FunctionDelta? = null
)

@JsonClass(generateAdapter = true)
data class FunctionDelta(
    val name: String? = null,
    val arguments: String? = null
)

@JsonClass(generateAdapter = true)
data class ToolCallDto(
    val id: String? = null,
    val type: String? = null,
    val function: FunctionCallDto? = null
)

@JsonClass(generateAdapter = true)
data class FunctionCallDto(
    val name: String? = null,
    val arguments: String? = null
)

@JsonClass(generateAdapter = true)
data class Usage(
    @Json(name = "prompt_tokens") val promptTokens: Int? = null,
    @Json(name = "completion_tokens") val completionTokens: Int? = null,
    @Json(name = "total_tokens") val totalTokens: Int? = null
)

@JsonClass(generateAdapter = true)
data class ApiError(
    val message: String? = null,
    val type: String? = null,
    val code: String? = null
)
