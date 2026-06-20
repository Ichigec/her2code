package com.hermes.gui.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hermes.gui.data.remote.HealthCheckManager
import com.hermes.gui.data.repository.ChatRepository
import com.hermes.gui.data.repository.SettingsRepository
import com.hermes.gui.data.repository.ToolRepository
import com.hermes.gui.data.settings.AppSettings
import com.hermes.gui.data.settings.ThemeMode
import com.hermes.gui.domain.model.Toolset
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val settings: AppSettings = AppSettings(),
    val toolsets: List<Toolset> = emptyList(),
    val isLoadingToolsets: Boolean = false,
    val connectionStatus: ConnectionStatus = ConnectionStatus.UNKNOWN
)

enum class ConnectionStatus {
    UNKNOWN, CHECKING, CONNECTED, DISCONNECTED
}

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settingsRepository: SettingsRepository,
    private val toolRepository: ToolRepository,
    private val chatRepository: ChatRepository,
    private val healthCheckManager: HealthCheckManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    val connectionMode: StateFlow<HealthCheckManager.ConnectionMode> =
        healthCheckManager.connectionMode

    init {
        viewModelScope.launch {
            settingsRepository.settingsFlow.collect { settings ->
                _uiState.update { it.copy(settings = settings) }
            }
        }
        loadToolsets()
    }

    private fun loadToolsets() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoadingToolsets = true) }
            toolRepository.fetchToolsets().onSuccess { toolsets ->
                _uiState.update { it.copy(toolsets = toolsets, isLoadingToolsets = false) }
            }.onFailure {
                _uiState.update { it.copy(isLoadingToolsets = false) }
            }
        }
    }

    fun testConnection() {
        viewModelScope.launch {
            _uiState.update { it.copy(connectionStatus = ConnectionStatus.CHECKING) }
            chatRepository.checkHealth().onSuccess {
                _uiState.update { it.copy(connectionStatus = ConnectionStatus.CONNECTED) }
            }.onFailure { e ->
                _uiState.update { it.copy(connectionStatus = ConnectionStatus.DISCONNECTED) }
            }
        }
    }

    fun updatePrimaryUrl(url: String) {
        viewModelScope.launch { settingsRepository.updatePrimaryUrl(url) }
    }

    @Deprecated("Use updatePrimaryUrl instead", ReplaceWith("updatePrimaryUrl(url)"))
    fun updateApiUrl(url: String) {
        viewModelScope.launch { settingsRepository.updateApiUrl(url) }
    }

    fun updateFallbackUrl(url: String) {
        viewModelScope.launch { settingsRepository.updateFallbackUrl(url) }
    }

    fun updateApiKey(key: String) {
        viewModelScope.launch { settingsRepository.updateApiKey(key) }
    }

    fun updateSelectedModel(model: String) {
        viewModelScope.launch { settingsRepository.updateSelectedModel(model) }
    }

    fun updateSelectedPersona(persona: String) {
        viewModelScope.launch { settingsRepository.updateSelectedPersona(persona) }
    }

    fun updateSelectedAgent(agent: String) {
        viewModelScope.launch { settingsRepository.updateSelectedAgent(agent) }
    }

    fun updateSystemPrompt(prompt: String) {
        viewModelScope.launch { settingsRepository.updateSystemPrompt(prompt) }
    }

    fun updateThemeMode(mode: ThemeMode) {
        viewModelScope.launch { settingsRepository.updateThemeMode(mode) }
    }

    fun updateStreamingEnabled(enabled: Boolean) {
        viewModelScope.launch { settingsRepository.updateStreamingEnabled(enabled) }
    }

    fun updateCodeExecutionEnabled(enabled: Boolean) {
        viewModelScope.launch { settingsRepository.updateCodeExecutionEnabled(enabled) }
    }

    fun toggleTool(toolName: String) {
        val current = _uiState.value.settings.enabledTools.toMutableSet()
        if (toolName in current) current.remove(toolName) else current.add(toolName)
        viewModelScope.launch { settingsRepository.updateEnabledTools(current) }
    }

    fun toggleMcpServer(serverName: String) {
        val current = _uiState.value.settings.enabledMcpServers.toMutableSet()
        if (serverName in current) current.remove(serverName) else current.add(serverName)
        viewModelScope.launch { settingsRepository.updateEnabledMcpServers(current) }
    }

    fun refreshToolsets() {
        loadToolsets()
    }

    fun toggleBackend() {
        val current = _uiState.value.settings.backendMode
        val next = if (current == "hermes") "opencode" else "hermes"
        viewModelScope.launch {
            settingsRepository.updateBackendMode(next)
            // Switch model to match backend
            val model = if (next == "hermes") "qwen3.6-35b-heretic" else "hermes-agent"
            settingsRepository.updateSelectedModel(model)
        }
    }
}
