package com.hermes.gui.data.settings

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

data class AppSettings(
    val primaryUrl: String = DEFAULT_API_URL,
    val fallbackUrl: String = "",
    val apiKey: String = DEFAULT_API_KEY,
    val backendMode: String = "hermes",
    val selectedModel: String = "qwen3.6-35b-heretic",
    val selectedPersona: String = "default",
    val selectedAgent: String = "general",
    val systemPrompt: String = "",
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val streamingEnabled: Boolean = true,
    val codeExecutionEnabled: Boolean = false,
    val fullCycleEnabled: Boolean = true,
    val enabledTools: Set<String> = emptySet(),
    val enabledMcpServers: Set<String> = emptySet()
) {
    companion object {
        const val DEFAULT_API_URL = "http://<YOUR_VPS_IP>:8643"
        const val DEFAULT_API_KEY = "tfpq7h9sUcrCjyFU3VuqAeq-IEpKT6Q6SgnC9iVQ5BPVJrRv"
    }
}

enum class ThemeMode {
    LIGHT, DARK, SYSTEM
}

@Singleton
class SettingsDataStore @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val encryptedPrefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "hermes_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    private val regularPrefs: SharedPreferences =
        context.getSharedPreferences("hermes_prefs", Context.MODE_PRIVATE)

    private val _settingsFlow = MutableStateFlow(loadSettings())
    val settingsFlow: Flow<AppSettings> = _settingsFlow.asStateFlow()

    private fun loadSettings(): AppSettings {
        return AppSettings(
            primaryUrl = regularPrefs.getString("primary_url", AppSettings.DEFAULT_API_URL) ?: AppSettings.DEFAULT_API_URL,
            fallbackUrl = regularPrefs.getString("fallback_url", "") ?: "",
            apiKey = encryptedPrefs.getString("api_key", AppSettings.DEFAULT_API_KEY) ?: AppSettings.DEFAULT_API_KEY,
            backendMode = regularPrefs.getString("backend_mode", "hermes") ?: "hermes",
            selectedModel = regularPrefs.getString("selected_model", AppSettings().selectedModel)
                ?: AppSettings().selectedModel,
            selectedPersona = regularPrefs.getString("selected_persona", "default") ?: "default",
            selectedAgent = regularPrefs.getString("selected_agent", "general") ?: "general",
            systemPrompt = regularPrefs.getString("system_prompt", "") ?: "",
            themeMode = try {
                ThemeMode.valueOf(
                    regularPrefs.getString("theme_mode", ThemeMode.SYSTEM.name) ?: ThemeMode.SYSTEM.name
                )
            } catch (_: Exception) { ThemeMode.SYSTEM },
            streamingEnabled = regularPrefs.getBoolean("streaming_enabled", true),
            codeExecutionEnabled = regularPrefs.getBoolean("code_execution_enabled", false),
            fullCycleEnabled = regularPrefs.getBoolean("full_cycle_enabled", true),
            enabledTools = regularPrefs.getStringSet("enabled_tools", emptySet()) ?: emptySet(),
            enabledMcpServers = regularPrefs.getStringSet("enabled_mcp_servers", emptySet()) ?: emptySet()
        )
    }

    suspend fun updatePrimaryUrl(url: String) {
        regularPrefs.edit().putString("primary_url", url).apply()
        emitUpdate()
    }

    @Deprecated("Use updatePrimaryUrl instead", ReplaceWith("updatePrimaryUrl(url)"))
    suspend fun updateApiUrl(url: String) {
        updatePrimaryUrl(url)
    }

    suspend fun updateFallbackUrl(url: String) {
        regularPrefs.edit().putString("fallback_url", url).apply()
        emitUpdate()
    }

    suspend fun updateApiKey(key: String) {
        encryptedPrefs.edit().putString("api_key", key).apply()
        emitUpdate()
    }

    suspend fun updateSelectedModel(model: String) {
        regularPrefs.edit().putString("selected_model", model).apply()
        emitUpdate()
    }

    suspend fun updateSelectedPersona(persona: String) {
        regularPrefs.edit().putString("selected_persona", persona).apply()
        emitUpdate()
    }

    suspend fun updateSelectedAgent(agent: String) {
        regularPrefs.edit().putString("selected_agent", agent).apply()
        emitUpdate()
    }

    suspend fun updateBackendMode(mode: String) {
        regularPrefs.edit().putString("backend_mode", mode).apply()
        emitUpdate()
    }

    suspend fun updateSystemPrompt(prompt: String) {
        regularPrefs.edit().putString("system_prompt", prompt).apply()
        emitUpdate()
    }

    suspend fun updateThemeMode(mode: ThemeMode) {
        regularPrefs.edit().putString("theme_mode", mode.name).apply()
        emitUpdate()
    }

    suspend fun updateStreamingEnabled(enabled: Boolean) {
        regularPrefs.edit().putBoolean("streaming_enabled", enabled).apply()
        emitUpdate()
    }

    suspend fun updateCodeExecutionEnabled(enabled: Boolean) {
        regularPrefs.edit().putBoolean("code_execution_enabled", enabled).apply()
        emitUpdate()
    }

    suspend fun updateFullCycleEnabled(enabled: Boolean) {
        regularPrefs.edit().putBoolean("full_cycle_enabled", enabled).apply()
        emitUpdate()
    }

    suspend fun updateEnabledTools(tools: Set<String>) {
        regularPrefs.edit().putStringSet("enabled_tools", tools).apply()
        emitUpdate()
    }

    suspend fun updateEnabledMcpServers(servers: Set<String>) {
        regularPrefs.edit().putStringSet("enabled_mcp_servers", servers).apply()
        emitUpdate()
    }

    /**
     * Synchronous read of current settings — used by AuthInterceptor (non-coroutine context).
     */
    fun getSettings(): AppSettings {
        return loadSettings()
    }

    private fun emitUpdate() {
        _settingsFlow.value = loadSettings()
    }
}
