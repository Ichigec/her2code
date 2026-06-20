package com.hermes.gui.ui.settings

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.hermes.gui.ui.settings.components.*

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel
) {
    val uiState by viewModel.uiState.collectAsState()
    val connectionMode by viewModel.connectionMode.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        ApiSettingsSection(
            title = "Hermes API",
            primaryUrl = uiState.settings.primaryUrl,
            fallbackUrl = uiState.settings.fallbackUrl,
            apiKey = uiState.settings.apiKey,
            connectionStatus = uiState.connectionStatus,
            connectionMode = connectionMode,
            onPrimaryUrlChange = { viewModel.updatePrimaryUrl(it) },
            onFallbackUrlChange = { viewModel.updateFallbackUrl(it) },
            onApiKeyChange = { viewModel.updateApiKey(it) },
            onTestConnection = { viewModel.testConnection() }
        )

        HorizontalDivider()

        ModelSettingsSection(
            selectedModel = uiState.settings.selectedModel,
            selectedAgent = uiState.settings.selectedPersona,
            systemPrompt = uiState.settings.systemPrompt,
            onModelChange = { viewModel.updateSelectedModel(it) },
            onAgentChange = { viewModel.updateSelectedPersona(it) },
            onSystemPromptChange = { viewModel.updateSystemPrompt(it) }
        )

        HorizontalDivider()

        AppearanceSection(
            themeMode = uiState.settings.themeMode,
            streamingEnabled = uiState.settings.streamingEnabled,
            codeExecutionEnabled = uiState.settings.codeExecutionEnabled,
            onThemeModeChange = { viewModel.updateThemeMode(it) },
            onStreamingToggle = { viewModel.updateStreamingEnabled(it) },
            onCodeExecutionToggle = { viewModel.updateCodeExecutionEnabled(it) }
        )

        HorizontalDivider()

        ToolSettingsSection(
            toolsets = uiState.toolsets,
            enabledTools = uiState.settings.enabledTools,
            isLoading = uiState.isLoadingToolsets,
            onToggleTool = { viewModel.toggleTool(it) },
            onRefresh = { viewModel.refreshToolsets() }
        )

        Spacer(modifier = Modifier.height(16.dp))
    }
}
