package com.hermes.gui.ui.chat.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.random.Random

@Composable
fun WaveformIndicator(
    isActive: Boolean,
    modifier: Modifier = Modifier,
    barCount: Int = 5,
    color: Color = Color(0xFFE53935)
) {
    // Animate each bar with different phases
    val animValues = remember { List(barCount) { Animatable(0.3f) } }
    val scope = rememberCoroutineScope()

    LaunchedEffect(isActive) {
        if (isActive) {
            // Continuously animate bars with random heights
            while (true) {
                animValues.forEachIndexed { index, anim ->
                    val target = if (isActive) Random.nextFloat() * 0.7f + 0.3f else 0.3f
                    scope.launch {
                        anim.animateTo(
                            target,
                            animationSpec = tween(
                                durationMillis = 150 + index * 30,
                                easing = FastOutSlowInEasing
                            )
                        )
                    }
                }
                delay(200)
            }
        } else {
            animValues.forEach { anim ->
                scope.launch {
                    anim.animateTo(0.3f, animationSpec = tween(300))
                }
            }
        }
    }

    Canvas(
        modifier = modifier
            .height(24.dp)
            .width((barCount * 6).dp)
    ) {
        val barWidth = size.width / (barCount * 2f - 1f)
        val gap = barWidth

        animValues.forEachIndexed { index, anim ->
            val barHeight = size.height * anim.value
            val x = index * (barWidth + gap)
            val y = (size.height - barHeight) / 2f

            drawRect(
                color = color,
                topLeft = Offset(x, y),
                size = Size(barWidth, barHeight)
            )
        }
    }
}
