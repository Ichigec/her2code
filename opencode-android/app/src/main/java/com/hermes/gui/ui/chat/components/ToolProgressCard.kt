package com.hermes.gui.ui.chat.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.HourglassEmpty
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.hermes.gui.ui.chat.ToolProgressItem
import com.hermes.gui.ui.chat.ToolProgressStatus

@Composable
fun ToolProgressCard(
    progress: ToolProgressItem,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = when (progress.status) {
                    ToolProgressStatus.RUNNING -> Icons.Default.HourglassEmpty
                    ToolProgressStatus.COMPLETED -> Icons.Default.CheckCircle
                    ToolProgressStatus.ERROR -> Icons.Default.Build
                },
                contentDescription = null,
                tint = when (progress.status) {
                    ToolProgressStatus.RUNNING -> MaterialTheme.colorScheme.primary
                    ToolProgressStatus.COMPLETED -> MaterialTheme.colorScheme.tertiary
                    ToolProgressStatus.ERROR -> MaterialTheme.colorScheme.error
                },
                modifier = Modifier.size(20.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = when (progress.status) {
                    ToolProgressStatus.RUNNING -> "Выполняется: ${progress.functionName}"
                    ToolProgressStatus.COMPLETED -> "Завершено: ${progress.functionName}"
                    ToolProgressStatus.ERROR -> "Ошибка: ${progress.functionName}"
                },
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}
