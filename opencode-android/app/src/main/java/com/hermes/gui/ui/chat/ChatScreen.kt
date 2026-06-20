package com.hermes.gui.ui.chat

import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.hermes.gui.ui.chat.components.*
import kotlinx.coroutines.launch

@Composable
fun ChatScreen(
    conversationId: String? = null,
    viewModel: ChatViewModel
) {
    val uiState by viewModel.uiState.collectAsState()
    val listState = rememberLazyListState()
    val coroutineScope = rememberCoroutineScope()

    // Load conversation when specified
    LaunchedEffect(conversationId) {
        if (conversationId != null) {
            viewModel.loadConversation(conversationId)
        }
    }

    // Auto-scroll to bottom
    LaunchedEffect(uiState.messages.size, uiState.streamingContent) {
        if (uiState.messages.isNotEmpty() || uiState.streamingContent.isNotEmpty()) {
            coroutineScope.launch {
                listState.animateScrollToItem(
                    if (uiState.isStreaming) uiState.messages.size
                    else uiState.messages.size - 1
                )
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .imePadding()
    ) {
        // Chat content — takes all available space
        if (uiState.messages.isEmpty() && !uiState.isStreaming) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "Начните диалог с Hermes",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                    textAlign = TextAlign.Center
                )
            }
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(horizontal = 8.dp),
                contentPadding = PaddingValues(vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(uiState.messages, key = { it.id }) { message ->
                    MessageBubble(message = message)
                }

                if (uiState.isStreaming && uiState.streamingContent.isNotEmpty()) {
                    item(key = "streaming") {
                        MessageBubble(
                            message = com.hermes.gui.domain.model.Message(
                                id = "streaming", conversationId = "",
                                role = com.hermes.gui.domain.model.MessageRole.ASSISTANT,
                                content = uiState.streamingContent
                            ),
                            isStreaming = true
                        )
                    }
                } else if (uiState.isStreaming && uiState.streamingContent.isEmpty()) {
                    item(key = "thinking") {
                        ThinkingIndicator()
                    }
                }

                uiState.toolProgress.forEach { progress ->
                    item(key = "tool_${progress.toolCallId}") {
                        ToolProgressCard(progress = progress)
                    }
                }
            }
        }

        // Voice status bar — compact, non-blocking
        AnimatedVisibility(visible = uiState.isVoiceActive || uiState.isRecording || uiState.isPlaying || uiState.isStreaming) {
            Surface(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 2.dp),
                shape = RoundedCornerShape(8.dp),
                color = when {
                    uiState.isRecording -> MaterialTheme.colorScheme.errorContainer
                    uiState.isStreaming -> MaterialTheme.colorScheme.tertiaryContainer
                    uiState.isPlaying -> MaterialTheme.colorScheme.primaryContainer
                    else -> MaterialTheme.colorScheme.surfaceVariant
                }
            ) {
                Text(
                    text = when {
                        uiState.isRecording -> "🎙️ Слушаю..."
                        uiState.isStreaming -> "🧠 Думаю..."
                        uiState.isPlaying -> "🔊 Отвечаю..."
                        else -> ""
                    },
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelSmall
                )
            }
        }

        // Chat input bar — always at bottom, above keyboard
        ChatInputBar(
            enabled = !uiState.isStreaming,
            isStreaming = uiState.isStreaming,
            isVoiceActive = uiState.isVoiceActive,
            isRecording = uiState.isRecording,
            isPlaying = uiState.isPlaying,
            onSend = { viewModel.sendMessage(it) },
            onStop = { viewModel.stopGeneration() },
            onToggleVoice = { viewModel.toggleVoice() }
        )
    }

    // Error snackbar
    uiState.error?.let { error ->
        Box(modifier = Modifier.fillMaxSize()) {
            Snackbar(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(16.dp)
                    .navigationBarsPadding(),
                action = {
                    TextButton(onClick = { viewModel.dismissError() }) {
                        Text("OK")
                    }
                }
            ) { Text(error) }
        }
    }
}

@Composable
private fun ThinkingIndicator() {
    Row(
        modifier = Modifier.padding(8.dp).fillMaxWidth(),
        horizontalArrangement = Arrangement.Start
    ) {
        Surface(
            shape = MaterialTheme.shapes.medium,
            color = MaterialTheme.colorScheme.surfaceVariant,
            tonalElevation = 2.dp
        ) {
            Text(
                "Думаю...",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
