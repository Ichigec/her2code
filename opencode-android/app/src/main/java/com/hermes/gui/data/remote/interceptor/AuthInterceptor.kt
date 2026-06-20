package com.hermes.gui.data.remote.interceptor

import android.util.Log
import com.hermes.gui.data.remote.HealthCheckManager
import com.hermes.gui.data.settings.SettingsDataStore
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val settingsDataStore: SettingsDataStore,
    private val healthCheckManager: HealthCheckManager
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        var request = chain.request()
        val originalUrl = request.url

        val settings = settingsDataStore.getSettings()
        val apiUrl = settings.primaryUrl
        val apiKey = settings.apiKey

        Log.i("HermesGUI", "Auth: backend=${settings.backendMode}, url=$apiUrl")

        // Rewrite URL
        if (apiUrl.isNotBlank()) {
            val baseUrl = apiUrl.trimEnd('/').toHttpUrlOrNull()
            if (baseUrl != null) {
                val newUrl = originalUrl.newBuilder()
                    .scheme(baseUrl.scheme)
                    .host(baseUrl.host)
                    .port(baseUrl.port)
                    .build()
                request = request.newBuilder().url(newUrl).build()
                Log.d("HermesGUI", "Rewritten to: $newUrl")
            } else {
                Log.e("HermesGUI", "PARSE FAILED: '$apiUrl'")
            }
        } else {
            Log.w("HermesGUI", "URL empty")
        }

        // Add auth header
        if (apiKey.isNotBlank()) {
            request = request.newBuilder()
                .addHeader("Authorization", "Bearer $apiKey")
                .build()
        }

        Log.d("HermesGUI", "Final: ${request.url}")
        return chain.proceed(request)
    }
}
