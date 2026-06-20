package com.hermes.gui.ui.chat.components

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@Composable
fun VoiceStatusBar(
    isVoiceActive: Boolean,
    isRecording: Boolean,
    isPlaying: Boolean,
    isStreaming: Boolean,
    modifier: Modifier = Modifier
) {
    AnimatedVisibility(
        visible = isVoiceActive,
        enter = fadeIn() + expandVertically(),
        exit = fadeOut() + shrinkVertically()
    ) {
        val (text, color) = when {
            isRecording -> "🎙️ Слушаю..." to MaterialTheme.colorScheme.errorContainer
            isStreaming -> "🧠 Думаю..." to MaterialTheme.colorScheme.tertiaryContainer
            isPlaying -> "🔊 Отвечаю..." to MaterialTheme.colorScheme.primaryContainer
            else -> "🎤 Голосовой чат активен" to MaterialTheme.colorScheme.surfaceVariant
        }

        Box(
            modifier = modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 4.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(color)
                .padding(horizontal = 16.dp, vertical = 8.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = text,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurface,
                textAlign = TextAlign.Center
            )
        }
    }
}
