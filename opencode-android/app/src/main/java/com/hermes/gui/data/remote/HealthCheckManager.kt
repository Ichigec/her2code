package com.hermes.gui.data.remote

import android.util.Log
import com.hermes.gui.data.settings.SettingsDataStore
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class HealthCheckManager @Inject constructor(
    private val settingsDataStore: SettingsDataStore
) {
    enum class ConnectionMode { WIFI, TAILSCALE, OFFLINE }

    companion object {
        private const val TAG = "HealthCheckManager"
        private const val HEALTH_CHECK_INTERVAL_MS = 30_000L
        private const val FAILURES_TO_SWITCH = 3
        private const val SUCCESSES_TO_RECOVER = 2
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val healthCheckClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    private val _activeUrl = MutableStateFlow(
        settingsDataStore.getSettings().primaryUrl
    )
    val activeUrl: StateFlow<String> = _activeUrl.asStateFlow()

    private val _connectionMode = MutableStateFlow(ConnectionMode.WIFI)
    val connectionMode: StateFlow<ConnectionMode> = _connectionMode.asStateFlow()

    private var consecutiveFailures = 0
    private var consecutiveSuccesses = 0
    private var usingFallback = false
    private var probingPrimary = false

    init {
        startHealthCheckLoop()
    }

    fun getCurrentUrl(): String = _activeUrl.value

    private fun startHealthCheckLoop() {
        scope.launch {
            while (isActive) {
                delay(HEALTH_CHECK_INTERVAL_MS)
                performHealthCheck()
            }
        }
    }

    private suspend fun performHealthCheck() {
        val targetUrl = if (probingPrimary) {
            settingsDataStore.getSettings().primaryUrl
        } else {
            _activeUrl.value
        }

        if (targetUrl.isBlank()) {
            updateConnectionMode(ConnectionMode.OFFLINE)
            return
        }

        val healthUrl = "${targetUrl.trimEnd('/')}/health"
        val request = Request.Builder()
            .url(healthUrl)
            .get()
            .build()

        try {
            val response = healthCheckClient.newCall(request).execute()
            val code = response.code
            response.close()

            if (code == 502) {
                // serveo.net warning page on first request — retry once
                Log.w(TAG, "Got 502 (serveo warning), retrying in 1s...")
                delay(1000)
                val retryResponse = healthCheckClient.newCall(request).execute()
                val retrySuccess = retryResponse.isSuccessful
                retryResponse.close()
                if (retrySuccess) {
                    onHealthSuccess()
                } else {
                    onHealthFailure()
                }
            } else if (code in 200..299) {
                onHealthSuccess()
            } else {
                onHealthFailure()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Health check failed for $healthUrl: ${e.message}")
            onHealthFailure()
        }
    }

    private fun onHealthSuccess() {
        consecutiveSuccesses++
        consecutiveFailures = 0

        if (probingPrimary) {
            if (consecutiveSuccesses >= SUCCESSES_TO_RECOVER) {
                // Primary is back — switch back
                val primaryUrl = settingsDataStore.getSettings().primaryUrl
                _activeUrl.value = primaryUrl
                usingFallback = false
                probingPrimary = false
                consecutiveSuccesses = 0
                updateConnectionMode(ConnectionMode.WIFI)
                Log.i(TAG, "Primary URL recovered, switched back to $primaryUrl")
            }
        } else if (usingFallback) {
            // We're on fallback and it's working — after success threshold, try probing primary
            if (consecutiveSuccesses >= SUCCESSES_TO_RECOVER) {
                probingPrimary = true
                consecutiveSuccesses = 0
                Log.i(TAG, "Fallback stable, probing primary...")
            }
        }
    }

    private fun onHealthFailure() {
        consecutiveFailures++
        consecutiveSuccesses = 0

        if (probingPrimary) {
            // Primary probe failed — stay on fallback
            probingPrimary = false
            consecutiveFailures = 0
            Log.w(TAG, "Primary probe failed, staying on fallback")
        } else if (!usingFallback && consecutiveFailures >= FAILURES_TO_SWITCH) {
            // Primary is down — switch to fallback
            val fallbackUrl = settingsDataStore.getSettings().fallbackUrl
            if (fallbackUrl.isNotBlank()) {
                _activeUrl.value = fallbackUrl
                usingFallback = true
                consecutiveFailures = 0
                updateConnectionMode(ConnectionMode.TAILSCALE)
                Log.w(TAG, "Primary failed $FAILURES_TO_SWITCH times, switching to fallback: $fallbackUrl")
            } else {
                updateConnectionMode(ConnectionMode.OFFLINE)
                Log.e(TAG, "Primary failed and no fallback configured")
            }
        } else if (usingFallback && consecutiveFailures >= FAILURES_TO_SWITCH) {
            // Fallback is also down
            updateConnectionMode(ConnectionMode.OFFLINE)
            Log.e(TAG, "Fallback also failed, going offline")
        }
    }

    private fun updateConnectionMode(mode: ConnectionMode) {
        if (_connectionMode.value != mode) {
            _connectionMode.value = mode
            Log.i(TAG, "Connection mode: $mode")
        }
    }
}
