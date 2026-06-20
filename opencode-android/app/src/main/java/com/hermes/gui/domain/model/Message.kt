package com.hermes.gui.domain.model

data class Message(
    val id: String,
    val conversationId: String,
    val role: MessageRole,
    val content: String,
    val toolCalls: List<ToolCall> = emptyList(),
    val toolResults: List<ToolResult> = emptyList(),
    val timestamp: Long = System.currentTimeMillis(),
    val tokenCount: Int? = null
)

enum class MessageRole(val value: String) {
    USER("user"),
    ASSISTANT("assistant"),
    SYSTEM("system"),
    TOOL("tool");

    companion object {
        fun fromString(value: String): MessageRole =
            entries.find { it.value == value } ?: USER
    }
}

data class ToolCall(
    val id: String,
    val name: String,
    val arguments: String
)

data class ToolResult(
    val toolCallId: String,
    val content: String
)
