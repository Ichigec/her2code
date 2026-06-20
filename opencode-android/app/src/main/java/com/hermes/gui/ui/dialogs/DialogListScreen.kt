package com.hermes.gui.ui.dialogs

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.DeleteForever
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import com.hermes.gui.ui.dialogs.components.DialogItem
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.hermes.gui.domain.model.Conversation
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DialogListScreen(
    onConversationClick: (String) -> Unit,
    viewModel: DialogListViewModel = hiltViewModel()
) {
    val conversations by viewModel.conversations.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    var showDeleteAllDialog by remember { mutableStateOf(false) }
    var conversationToDelete by remember { mutableStateOf<String?>(null) }

    Box(modifier = Modifier.fillMaxSize()) {
        when {
            isLoading -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            }
            conversations.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Нет сохранённых диалогов",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                    )
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(8.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    // Delete all button at the top
                    item {
                        if (conversations.isNotEmpty()) {
                            TextButton(
                                onClick = { showDeleteAllDialog = true },
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Icon(
                                    Icons.Default.DeleteForever,
                                    contentDescription = null,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Удалить все диалоги", style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }

                    items(conversations, key = { it.id }) { conversation ->
                        DialogItem(
                            conversation = conversation,
                            onClick = { onConversationClick(conversation.id) },
                            onDelete = { conversationToDelete = conversation.id }
                        )
                    }
                }
            }
        }

        // Delete single conversation dialog
        conversationToDelete?.let { id ->
            AlertDialog(
                onDismissRequest = { conversationToDelete = null },
                title = { Text("Удалить диалог") },
                text = { Text("Вы уверены, что хотите удалить этот диалог?") },
                confirmButton = {
                    Button(
                        onClick = {
                            viewModel.deleteConversation(id)
                            conversationToDelete = null
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error
                        )
                    ) {
                        Text("Удалить")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { conversationToDelete = null }) {
                        Text("Отмена")
                    }
                }
            )
        }

        // Delete all conversations dialog
        if (showDeleteAllDialog) {
            AlertDialog(
                onDismissRequest = { showDeleteAllDialog = false },
                title = { Text("Удалить все диалоги") },
                text = { Text("Вы уверены, что хотите удалить ВСЕ диалоги? Это действие нельзя отменить.") },
                confirmButton = {
                    Button(
                        onClick = {
                            viewModel.deleteAllConversations()
                            showDeleteAllDialog = false
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error
                        )
                    ) {
                        Text("Удалить все")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showDeleteAllDialog = false }) {
                        Text("Отмена")
                    }
                }
            )
        }
    }
}
