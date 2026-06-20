package com.hermes.gui.domain.model

data class Toolset(
    val name: String,
    val label: String,
    val description: String,
    val enabled: Boolean,
    val configured: Boolean,
    val tools: List<String> = emptyList()
)
