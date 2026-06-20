package com.hermes.gui.data.repository

import com.hermes.gui.data.settings.AppSettings
import com.hermes.gui.data.settings.SettingsDataStore
import com.hermes.gui.data.settings.ThemeMode
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SettingsRepository @Inject constructor(
    private val settingsDataStore: SettingsDataStore
) {

    val settingsFlow: Flow<AppSettings> = settingsDataStore.settingsFlow

    suspend fun updatePrimaryUrl(url: String) = settingsDataStore.updatePrimaryUrl(url)

    @Deprecated("Use updatePrimaryUrl instead", ReplaceWith("updatePrimaryUrl(url)"))
    suspend fun updateApiUrl(url: String) = settingsDataStore.updateApiUrl(url)

    suspend fun updateFallbackUrl(url: String) = settingsDataStore.updateFallbackUrl(url)

    suspend fun updateApiKey(key: String) = settingsDataStore.updateApiKey(key)

    suspend fun updateSelectedModel(model: String) = settingsDataStore.updateSelectedModel(model)

    suspend fun updateSelectedPersona(persona: String) = settingsDataStore.updateSelectedPersona(persona)

    suspend fun updateSelectedAgent(agent: String) = settingsDataStore.updateSelectedAgent(agent)

    suspend fun updateBackendMode(mode: String) = settingsDataStore.updateBackendMode(mode)

    suspend fun updateSystemPrompt(prompt: String) = settingsDataStore.updateSystemPrompt(prompt)

    suspend fun updateThemeMode(mode: ThemeMode) = settingsDataStore.updateThemeMode(mode)

    suspend fun updateStreamingEnabled(enabled: Boolean) =
        settingsDataStore.updateStreamingEnabled(enabled)

    suspend fun updateCodeExecutionEnabled(enabled: Boolean) =
        settingsDataStore.updateCodeExecutionEnabled(enabled)

    suspend fun updateFullCycleEnabled(enabled: Boolean) =
        settingsDataStore.updateFullCycleEnabled(enabled)

    suspend fun updateEnabledTools(tools: Set<String>) = settingsDataStore.updateEnabledTools(tools)

    suspend fun updateEnabledMcpServers(servers: Set<String>) =
        settingsDataStore.updateEnabledMcpServers(servers)
}
