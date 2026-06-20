package com.hermes.gui.domain.model

/**
 * Full agent preset — system prompt + tools + trajectory.
 * When applied, the system prompt is sent and only the specified tools are enabled.
 */
data class AgentPreset(
    val id: String,
    val name: String,
    val description: String,
    val systemPrompt: String = "",
    /** Toolset names that this agent can use (from Hermes: web, browser, terminal, file) */
    val enabledToolsets: Set<String> = emptySet(),
    /** Tool execution mode: "auto" (AI decides) or "require_user" (asks before each tool call) */
    val toolExecutionMode: String = "auto",
    /** Model temperature (0.0 - 1.0) */
    val temperature: Float? = null,
    /** Reasoning effort: null (default), "low", "medium", "high" */
    val reasoningEffort: String? = null
)
