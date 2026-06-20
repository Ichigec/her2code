package com.hermes.gui.ui.settings.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun ModelSettingsSection(
    selectedModel: String,
    selectedAgent: String,
    systemPrompt: String,
    onModelChange: (String) -> Unit,
    onAgentChange: (String) -> Unit,
    onSystemPromptChange: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = "Модель и агент",
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(modifier = Modifier.height(12.dp))

        OutlinedTextField(
            value = selectedModel,
            onValueChange = onModelChange,
            label = { Text("Модель") },
            placeholder = { Text("hermes-agent") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        Spacer(modifier = Modifier.height(8.dp))

        OutlinedTextField(
            value = selectedAgent,
            onValueChange = onAgentChange,
            label = { Text("Агент (персона)") },
            placeholder = { Text("default") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        Spacer(modifier = Modifier.height(8.dp))

        OutlinedTextField(
            value = systemPrompt,
            onValueChange = onSystemPromptChange,
            label = { Text("Системный промпт") },
            placeholder = { Text("Дополнительные инструкции для AI (опционально)") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 3,
            maxLines = 5
        )
    }
}
