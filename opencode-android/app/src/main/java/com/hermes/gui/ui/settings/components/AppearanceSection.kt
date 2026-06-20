package com.hermes.gui.ui.settings.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.hermes.gui.data.settings.ThemeMode

@Composable
fun AppearanceSection(
    themeMode: ThemeMode,
    streamingEnabled: Boolean,
    codeExecutionEnabled: Boolean,
    onThemeModeChange: (ThemeMode) -> Unit,
    onStreamingToggle: (Boolean) -> Unit,
    onCodeExecutionToggle: (Boolean) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = "Оформление и поведение",
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(modifier = Modifier.height(12.dp))

        // Theme
        Text(
            text = "Тема",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )
        Spacer(modifier = Modifier.height(4.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            ThemeMode.entries.forEach { mode ->
                FilterChip(
                    selected = themeMode == mode,
                    onClick = { onThemeModeChange(mode) },
                    label = {
                        Text(
                            when (mode) {
                                ThemeMode.LIGHT -> "Светлая"
                                ThemeMode.DARK -> "Тёмная"
                                ThemeMode.SYSTEM -> "Системная"
                            }
                        )
                    }
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Streaming toggle
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Стриминг",
                    style = MaterialTheme.typography.bodyMedium
                )
                Text(
                    text = "Потоковый вывод ответов в реальном времени",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
            Switch(
                checked = streamingEnabled,
                onCheckedChange = onStreamingToggle
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Code execution toggle
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Исполнение кода",
                    style = MaterialTheme.typography.bodyMedium
                )
                Text(
                    text = "Разрешить выполнение команд на хосте (требует подтверждения)",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
            Switch(
                checked = codeExecutionEnabled,
                onCheckedChange = onCodeExecutionToggle
            )
        }
    }
}
