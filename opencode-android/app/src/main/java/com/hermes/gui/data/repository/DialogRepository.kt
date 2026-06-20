package com.hermes.gui.data.repository

import com.hermes.gui.data.local.dao.ConversationDao
import com.hermes.gui.data.local.dao.MessageDao
import com.hermes.gui.data.local.entity.ConversationEntity
import com.hermes.gui.data.local.entity.MessageEntity
import com.hermes.gui.domain.model.Conversation
import com.hermes.gui.domain.model.Message
import com.hermes.gui.domain.model.MessageRole
import com.hermes.gui.domain.model.ToolCall
import com.hermes.gui.domain.model.ToolResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DialogRepository @Inject constructor(
    private val conversationDao: ConversationDao,
    private val messageDao: MessageDao
) {

    fun getAllConversations(): Flow<List<Conversation>> {
        return conversationDao.getAllConversations().map { entities ->
            entities.map { it.toDomain() }
        }
    }

    fun getConversationsByMode(mode: String): Flow<List<Conversation>> {
        return conversationDao.getConversationsByMode(mode).map { entities ->
            entities.map { it.toDomain() }
        }
    }

    suspend fun getConversation(id: String): Conversation? {
        val conv = conversationDao.getConversationById(id) ?: return null
        val messages = messageDao.getMessagesList(id)
        return conv.toDomain(messages.map { it.toDomain() })
    }

    suspend fun getMessages(conversationId: String): Flow<List<Message>> {
        return messageDao.getMessagesByConversation(conversationId).map { entities ->
            entities.map { it.toDomain() }
        }
    }

    suspend fun createConversation(
        title: String = "Новый диалог",
        modelId: String = "hermes-agent",
        agentId: String = "default",
        systemPrompt: String? = null,
        backendMode: String = "HERMES"
    ): Conversation {
        val id = UUID.randomUUID().toString()
        val now = System.currentTimeMillis()
        val entity = ConversationEntity(
            id = id,
            title = title,
            modelId = modelId,
            agentId = agentId,
            backendMode = backendMode,
            systemPrompt = systemPrompt,
            createdAt = now,
            updatedAt = now
        )
        conversationDao.insertConversation(entity)
        return entity.toDomain()
    }

    suspend fun insertMessage(conversationId: String, message: Message) {
        val entity = message.toEntity(conversationId)
        messageDao.insertMessage(entity)
        conversationDao.updateTitle(
            conversationId,
            generateTitle(conversationId)
        )
    }

    suspend fun insertMessages(conversationId: String, messages: List<Message>) {
        messageDao.insertMessages(messages.map { it.toEntity(conversationId) })
        conversationDao.updateTitle(
            conversationId,
            generateTitle(conversationId)
        )
    }

    suspend fun updateSessionId(conversationId: String, sessionId: String) {
        conversationDao.updateSessionId(conversationId, sessionId)
    }

    suspend fun deleteConversation(id: String) {
        val conv = conversationDao.getConversationById(id) ?: return
        conversationDao.deleteConversation(conv)
    }

    suspend fun deleteAllConversations() {
        conversationDao.deleteAllConversations()
    }

    private suspend fun generateTitle(conversationId: String): String {
        val messages = messageDao.getMessagesList(conversationId)
        val firstUserMessage = messages.firstOrNull { it.role == "user" }
        return firstUserMessage?.content?.take(50)?.replace("\n", " ") ?: "Новый диалог"
    }
}

// Extension functions for entity ↔ domain mapping
private fun ConversationEntity.toDomain(messages: List<Message> = emptyList()): Conversation {
    return Conversation(
        id = id,
        title = title,
        modelId = modelId,
        agentId = agentId,
        backendMode = backendMode,
        systemPrompt = systemPrompt,
        sessionId = sessionId,
        messages = messages,
        createdAt = createdAt,
        updatedAt = updatedAt
    )
}

private fun MessageEntity.toDomain(): Message {
    return Message(
        id = id,
        conversationId = conversationId,
        role = MessageRole.fromString(role),
        content = content,
        toolCalls = toolCallsJson?.let { parseToolCalls(it) } ?: emptyList(),
        toolResults = toolResultsJson?.let { parseToolResults(it) } ?: emptyList(),
        timestamp = timestamp,
        tokenCount = tokenCount
    )
}

private fun Message.toEntity(conversationId: String): MessageEntity {
    return MessageEntity(
        id = id,
        conversationId = conversationId,
        role = role.value,
        content = content,
        toolCallsJson = if (toolCalls.isNotEmpty()) serializeToolCalls(toolCalls) else null,
        toolResultsJson = if (toolResults.isNotEmpty()) serializeToolResults(toolResults) else null,
        timestamp = timestamp,
        tokenCount = tokenCount
    )
}

private fun parseToolCalls(json: String): List<ToolCall> {
    return try {
        val arr = JSONArray(json)
        (0 until arr.length()).map { i ->
            val obj = arr.getJSONObject(i)
            val func = obj.getJSONObject("function")
            ToolCall(
                id = obj.getString("id"),
                name = func.getString("name"),
                arguments = func.getString("arguments")
            )
        }
    } catch (_: Exception) { emptyList() }
}

private fun serializeToolCalls(toolCalls: List<ToolCall>): String {
    val arr = JSONArray()
    toolCalls.forEach { tc ->
        val obj = JSONObject()
        obj.put("id", tc.id)
        obj.put("type", "function")
        val func = JSONObject()
        func.put("name", tc.name)
        func.put("arguments", tc.arguments)
        obj.put("function", func)
        arr.put(obj)
    }
    return arr.toString()
}

private fun parseToolResults(json: String): List<ToolResult> {
    return try {
        val arr = JSONArray(json)
        (0 until arr.length()).map { i ->
            val obj = arr.getJSONObject(i)
            ToolResult(
                toolCallId = obj.getString("tool_call_id"),
                content = obj.getString("content")
            )
        }
    } catch (_: Exception) { emptyList() }
}

private fun serializeToolResults(results: List<ToolResult>): String {
    val arr = JSONArray()
    results.forEach { r ->
        val obj = JSONObject()
        obj.put("tool_call_id", r.toolCallId)
        obj.put("content", r.content)
        arr.put(obj)
    }
    return arr.toString()
}
