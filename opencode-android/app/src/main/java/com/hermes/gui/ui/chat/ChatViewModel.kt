package com.hermes.gui.ui.chat

import android.app.Application
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hermes.gui.data.remote.SseEvent
import com.hermes.gui.data.remote.dto.ChatMessage
import com.hermes.gui.data.repository.ChatRepository
import com.hermes.gui.data.repository.DialogRepository
import com.hermes.gui.data.repository.SettingsRepository
import com.hermes.gui.data.repository.VoiceRepository
import com.hermes.gui.domain.model.Message
import com.hermes.gui.domain.model.MessageRole
import com.hermes.gui.util.Constants
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.io.File
import java.util.UUID
import javax.inject.Inject

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val chatRepository: ChatRepository,
    private val dialogRepository: DialogRepository,
    private val settingsRepository: SettingsRepository,
    private val voiceRepository: VoiceRepository,
    private val application: Application
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    private var streamJob: Job? = null
    private var currentAssistantMessageId: String? = null
    private val collectedContent = StringBuilder()
    private var autoRestartVoice = false  // auto-restart listening after TTS

    init {
        viewModelScope.launch { ensureConversation() }
    }

    private suspend fun ensureConversation() {
        val settings = settingsRepository.settingsFlow.first()
        val backendMode = if (settings.backendMode == "opencode") "OPENCODE_PLUS" else "HERMES"
        
        // Load persistent fullCycleEnabled
        _uiState.update { it.copy(fullCycleEnabled = settings.fullCycleEnabled) }

        // Fix: if model doesn't match backend, correct it
        if (settings.backendMode == "hermes" && settings.selectedModel == "hermes-agent") {
            settingsRepository.updateSelectedModel("openai/qwen3.6-35b-heretic")
        }
        if (settings.backendMode == "opencode" && settings.selectedModel != "hermes-agent" &&
            settings.selectedModel !in setOf("general","build","plan","review","safe","explore","scout","deep-explore","claw","composter")) {
            settingsRepository.updateSelectedModel("hermes-agent")
        }
        // Reuse most recent conversation for this backend
        val existingConv = dialogRepository.getConversationsByMode(backendMode)
            .firstOrNull()
            ?.maxByOrNull { it.updatedAt }
        
        val id = if (existingConv != null) {
            existingConv.id
        } else {
            val conv = dialogRepository.createConversation(
                backendMode = backendMode,
                title = if (backendMode == "OPENCODE_PLUS") "OpenCode+" else "Hermes"
            )
            conv.id
        }
        _uiState.update { it.copy(currentConversationId = id) }
        dialogRepository.getMessages(id).collect { messages ->
            _uiState.update { it.copy(messages = messages) }
        }
    }

    fun loadConversation(conversationId: String) {
        if (_uiState.value.currentConversationId == conversationId) return
        _uiState.update { it.copy(currentConversationId = conversationId) }
        viewModelScope.launch {
            dialogRepository.getMessages(conversationId).collect { messages ->
                _uiState.update { it.copy(messages = messages) }
            }
        }
    }

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || _uiState.value.isStreaming) return
        val convId = _uiState.value.currentConversationId ?: return

        // Prepend /agent plan when full cycle is enabled
        val finalText = if (_uiState.value.fullCycleEnabled && !trimmed.startsWith("/")) {
            "/agent plan $trimmed"
        } else {
            trimmed
        }

        val userMessage = Message(
            id = UUID.randomUUID().toString(),
            conversationId = convId,
            role = MessageRole.USER,
            content = finalText
        )
        viewModelScope.launch {
            dialogRepository.insertMessage(convId, userMessage)
            startStreaming(convId)
        }
    }

    // ==================== Voice Chat Mode ====================

    fun toggleVoice() {
        Log.i("ChatVM", "toggleVoice called, isVoiceActive=${_uiState.value.isVoiceActive}")
        if (_uiState.value.isVoiceActive) {
            stopVoiceMode()
        } else {
            startVoiceMode()
        }
    }

    private fun startVoiceMode() {
        autoRestartVoice = true
        voiceRepository.initTts(application.applicationContext)
        _uiState.update { it.copy(isVoiceActive = true) }
        startListeningCycle()
    }

    private fun stopVoiceMode() {
        autoRestartVoice = false
        voiceRepository.stopListening()
        _uiState.update { it.copy(isVoiceActive = false, isRecording = false, isPlaying = false) }
    }

    private fun startListeningCycle() {
        if (!autoRestartVoice) return
        _uiState.update { it.copy(isRecording = true) }
        viewModelScope.launch {
            val result = voiceRepository.listenAndTranscribe(application.applicationContext)
            _uiState.update { it.copy(isRecording = false) }
            
            result.onSuccess { transcript ->
                if (transcript.isNotBlank()) {
                    sendMessage(transcript)
                } else if (autoRestartVoice) {
                    delay(500)
                    startListeningCycle()
                }
            }.onFailure { error ->
                _uiState.update { it.copy(error = "Ошибка распознавания: ${error.message}") }
                if (autoRestartVoice) {
                    delay(1000)
                    startListeningCycle()
                }
            }
        }
    }

    private suspend fun synthesizeAndPlay(text: String) {
        if (!_uiState.value.ttsEnabled) return
        _uiState.update { it.copy(isPlaying = true) }
        voiceRepository.speak(text)
        _uiState.update { it.copy(isPlaying = false) }
        if (autoRestartVoice) {
            delay(300)
            startListeningCycle()
        }
    }

    fun toggleTts() {
        val newState = !_uiState.value.ttsEnabled
        _uiState.update { it.copy(ttsEnabled = newState) }
        if (!newState) {
            voiceRepository.stopTts()
        }
    }

    fun toggleFullCycle() {
        val newState = !_uiState.value.fullCycleEnabled
        _uiState.update { it.copy(fullCycleEnabled = newState) }
        viewModelScope.launch {
            settingsRepository.updateFullCycleEnabled(newState)
        }
    }

    // ==================== Streaming ====================

    private suspend fun startStreaming(conversationId: String) {
        collectedContent.clear()
        currentAssistantMessageId = UUID.randomUUID().toString()
        val settings = settingsRepository.settingsFlow.first()

        _uiState.update { it.copy(isStreaming = true, streamingContent = "", toolProgress = emptyList()) }

        val allMessages = _uiState.value.messages
        val apiMessages = buildApiMessages(allMessages, settings)

        streamJob = viewModelScope.launch {
            chatRepository.streamMessage(apiMessages).collect { event ->
                when (event) {
                    is SseEvent.Content -> {
                        collectedContent.append(event.text)
                        _uiState.update { it.copy(streamingContent = collectedContent.toString()) }
                    }
                    is SseEvent.ToolStart -> {
                        _uiState.update {
                            it.copy(toolProgress = it.toolProgress + ToolProgressItem(
                                toolCallId = event.toolCallId,
                                functionName = event.functionName,
                                status = ToolProgressStatus.RUNNING
                            ))
                        }
                    }
                    is SseEvent.ToolComplete -> {
                        _uiState.update {
                            it.copy(toolProgress = it.toolProgress.map { item ->
                                if (item.toolCallId == event.toolCallId)
                                    item.copy(status = ToolProgressStatus.COMPLETED)
                                else item
                            })
                        }
                    }
                    is SseEvent.Done -> {
                        val responseText = collectedContent.toString()
                        // If response is ONLY protocol JSON, show friendly message
                        val displayText = if (responseText.isNotBlank() &&
                            responseText.trimStart().startsWith("{\"type\":\"step_start\"") &&
                            !responseText.contains("\"content\":")) {
                            "Агент не ответил. Попробуйте ещё раз."
                        } else {
                            responseText
                        }
                        Log.i("ChatVM", "Done: responseText length=${responseText.length}, autoRestartVoice=$autoRestartVoice")
                        finalizeMessage(conversationId, displayText)
                        if (autoRestartVoice && responseText.isNotBlank()) {
                            Log.i("ChatVM", "Calling synthesizeAndPlay with: ${responseText.take(50)}...")
                            viewModelScope.launch { synthesizeAndPlay(responseText) }
                        }
                    }
                    is SseEvent.Error -> {
                        val partialText = collectedContent.toString()
                        if (partialText.isNotBlank()) {
                            finalizeMessage(conversationId)
                        }
                        _uiState.update { it.copy(isStreaming = false, error = event.message) }
                    }
                }
            }
        }
    }

    fun stopGeneration() {
        streamJob?.cancel()
        val convId = _uiState.value.currentConversationId
        if (convId != null) {
            viewModelScope.launch { finalizeMessage(convId) }
        }
    }

    private suspend fun finalizeMessage(conversationId: String, content: String = collectedContent.toString()) {
        if (content.isNotBlank() && currentAssistantMessageId != null) {
            val assistantMessage = Message(
                id = currentAssistantMessageId!!,
                conversationId = conversationId,
                role = MessageRole.ASSISTANT,
                content = content
            )
            dialogRepository.insertMessage(conversationId, assistantMessage)
        }
        _uiState.update { it.copy(isStreaming = false, streamingContent = "") }
        collectedContent.clear()
        currentAssistantMessageId = null
    }

    private fun buildApiMessages(
        messages: List<Message>,
        settings: com.hermes.gui.data.settings.AppSettings
    ): List<ChatMessage> {
        val result = mutableListOf<ChatMessage>()

        // Always add Hermes identity when in Hermes mode
        if (settings.backendMode == "hermes") {
            result.add(ChatMessage(role = "system", content = 
                "You are Hermes — an AI agent by Nous Research. " +
                "You run on Jetson ARM64 with NVIDIA GPU. " +
                "You have access to tools (terminal, file, web, browser) and can execute real actions. " +
                "Be concise, helpful, and proactive. " +
                "When asked who you are, say you are Hermes Agent running on User's Jetson."))
        }

        if (settings.selectedAgent != "general") {
            val agentPrompt = Constants.AGENT_PROMPTS[settings.selectedAgent]
            if (!agentPrompt.isNullOrBlank()) {
                result.add(ChatMessage(role = "system", content = agentPrompt))
            }
        }

        if (settings.selectedPersona != "default") {
            val personaPrompt = Constants.PERSONA_PROMPTS[settings.selectedPersona]
            if (!personaPrompt.isNullOrBlank()) {
                result.add(ChatMessage(role = "system", content = personaPrompt))
            }
        }

        if (settings.systemPrompt.isNotBlank()) {
            result.add(ChatMessage(role = "system", content = settings.systemPrompt))
        }

        messages.forEach { msg ->
            result.add(
                ChatMessage(
                    role = msg.role.value, content = msg.content,
                    toolCalls = msg.toolCalls.map { tc ->
                        com.hermes.gui.data.remote.dto.ToolCall(
                            id = tc.id,
                            function = com.hermes.gui.data.remote.dto.FunctionCall(
                                name = tc.name, arguments = tc.arguments
                            )
                        )
                    }.ifEmpty { null }
                )
            )
        }
        return result
    }

    fun toggleModelSelector() {
        _uiState.update { it.copy(showModelSelector = !it.showModelSelector) }
    }

    fun togglePersonaSelector() {
        _uiState.update { it.copy(showPersonaSelector = !it.showPersonaSelector) }
    }

    fun dismissError() {
        _uiState.update { it.copy(error = null) }
    }

    fun clearChat() {
        viewModelScope.launch {
            val convId = _uiState.value.currentConversationId
            if (convId != null) dialogRepository.deleteConversation(convId)
            val conv = dialogRepository.createConversation()
            _uiState.update { ChatUiState(currentConversationId = conv.id) }
        }
    }
}
