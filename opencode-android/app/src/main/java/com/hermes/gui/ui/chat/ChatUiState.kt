package com.hermes.gui.ui.chat

import com.hermes.gui.domain.model.Message

data class ChatUiState(
    val messages: List<Message> = emptyList(),
    val streamingContent: String = "",
    val isStreaming: Boolean = false,
    val isRecording: Boolean = false,
    val isVoiceActive: Boolean = false,
    val isPlaying: Boolean = false,
    val ttsEnabled: Boolean = true,
    val fullCycleEnabled: Boolean = true,
    val isLoading: Boolean = false,
    val error: String? = null,
    val currentConversationId: String? = null,
    val showModelSelector: Boolean = false,
    val showPersonaSelector: Boolean = false,
    val showTerminalConfirm: TerminalConfirmState? = null,
    val toolProgress: List<ToolProgressItem> = emptyList()
)

data class TerminalConfirmState(
    val command: String,
    val toolCallId: String
)

data class ToolProgressItem(
    val toolCallId: String,
    val functionName: String,
    val status: ToolProgressStatus
)

enum class ToolProgressStatus {
    RUNNING, COMPLETED, ERROR
}
