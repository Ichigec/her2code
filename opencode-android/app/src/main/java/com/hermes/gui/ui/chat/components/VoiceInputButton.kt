package com.hermes.gui.ui.chat.components

import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

@Composable
fun VoiceInputButton(
    isVoiceActive: Boolean,
    isRecording: Boolean,
    isPlaying: Boolean,
    isEnabled: Boolean,
    onToggleVoice: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current

    // Pulsing animation when recording
    val pulseAnim = rememberInfiniteTransition(label = "pulse")
    val pulseScale by pulseAnim.animateFloat(
        initialValue = 1f, targetValue = 1.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ), label = "pulseScale"
    )

    Box(modifier = modifier.size(48.dp), contentAlignment = Alignment.Center) {
        // Pulsing red glow
        if (isRecording) {
            Box(
                Modifier.size(48.dp).scale(pulseScale).clip(CircleShape)
                    .background(MaterialTheme.colorScheme.error.copy(alpha = 0.3f))
            )
        }

        // Mic button — tap to toggle voice chat mode
        FilledIconButton(
            onClick = {
                vibrate(context)
                onToggleVoice()
            },
            modifier = Modifier.size(48.dp),
            enabled = isEnabled,
            colors = IconButtonDefaults.filledIconButtonColors(
                containerColor = when {
                    isRecording -> MaterialTheme.colorScheme.error
                    isPlaying -> MaterialTheme.colorScheme.tertiary
                    isVoiceActive -> MaterialTheme.colorScheme.primary
                    else -> MaterialTheme.colorScheme.surfaceVariant
                }
            )
        ) {
            Icon(
                imageVector = if (isVoiceActive) Icons.Default.Mic else Icons.Default.MicOff,
                contentDescription = when {
                    isRecording -> "Запись..."
                    isPlaying -> "Озвучка..."
                    isVoiceActive -> "Голосовой чат активен"
                    else -> "Начать голосовой чат"
                },
                modifier = Modifier.size(24.dp),
                tint = when {
                    isRecording -> MaterialTheme.colorScheme.onError
                    isVoiceActive -> MaterialTheme.colorScheme.onPrimary
                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                }
            )
        }
    }
}

private fun vibrate(context: android.content.Context) {
    try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (context.getSystemService(android.content.Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)
                ?.defaultVibrator?.vibrate(VibrationEffect.createOneShot(40, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            (context.getSystemService(android.content.Context.VIBRATOR_SERVICE) as? Vibrator)
                ?.vibrate(VibrationEffect.createOneShot(40, VibrationEffect.DEFAULT_AMPLITUDE))
        }
    } catch (_: Exception) {}
}
