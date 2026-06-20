package com.hermes.gui.domain.model

data class Conversation(
    val id: String,
    val title: String,
    val modelId: String = "hermes-agent",
    val agentId: String = "default",
    val backendMode: String = "HERMES",
    val systemPrompt: String? = null,
    val sessionId: String? = null,
    val messages: List<Message> = emptyList(),
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
) {
    val lastMessage: Message?
        get() = messages.maxByOrNull { it.timestamp }

    val preview: String
        get() = lastMessage?.content?.take(100)?.replace("\n", " ") ?: ""
}
