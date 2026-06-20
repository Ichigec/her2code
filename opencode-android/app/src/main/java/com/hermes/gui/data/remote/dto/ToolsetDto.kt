package com.hermes.gui.data.remote.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class ToolsetsResponse(
    val `object`: String = "list",
    val platform: String? = null,
    val data: List<ToolsetDto> = emptyList()
)

@JsonClass(generateAdapter = true)
data class ToolsetDto(
    val name: String,
    val label: String? = null,
    val description: String? = null,
    val enabled: Boolean = false,
    val configured: Boolean = false,
    val tools: List<String> = emptyList()
)

@JsonClass(generateAdapter = true)
data class CapabilitiesResponse(
    val `object`: String,
    val platform: String? = null,
    val model: String? = null,
    val auth: AuthInfo? = null,
    val runtime: RuntimeInfo? = null,
    val features: FeaturesInfo? = null,
    val endpoints: Map<String, EndpointInfo>? = null
)

@JsonClass(generateAdapter = true)
data class AuthInfo(
    val type: String? = null,
    val required: Boolean = false
)

@JsonClass(generateAdapter = true)
data class RuntimeInfo(
    val mode: String? = null,
    @Json(name = "tool_execution") val toolExecution: String? = null,
    @Json(name = "split_runtime") val splitRuntime: Boolean = false,
    val description: String? = null
)

@JsonClass(generateAdapter = true)
data class FeaturesInfo(
    @Json(name = "chat_completions") val chatCompletions: Boolean = true,
    @Json(name = "chat_completions_streaming") val chatCompletionsStreaming: Boolean = true
)

@JsonClass(generateAdapter = true)
data class EndpointInfo(
    val method: String? = null,
    val path: String? = null
)

@JsonClass(generateAdapter = true)
data class HealthResponse(
    val status: String = "ok",
    val platform: String? = null
)
