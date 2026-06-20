package com.hermes.gui.ui.settings.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cloud
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.NetworkCheck
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.hermes.gui.data.remote.HealthCheckManager
import com.hermes.gui.ui.settings.ConnectionStatus

@Composable
fun ApiSettingsSection(
    title: String = "API-подключение",
    primaryUrl: String,
    fallbackUrl: String,
    apiKey: String,
    connectionStatus: ConnectionStatus,
    connectionMode: HealthCheckManager.ConnectionMode,
    onPrimaryUrlChange: (String) -> Unit,
    onFallbackUrlChange: (String) -> Unit,
    onApiKeyChange: (String) -> Unit,
    onTestConnection: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(modifier = Modifier.height(12.dp))

        // Connection indicator + status + test button
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth()
        ) {
            // Colored dot indicator for connection mode
            ConnectionIndicator(mode = connectionMode)

            Spacer(modifier = Modifier.width(10.dp))

            Icon(
                imageVector = when (connectionStatus) {
                    ConnectionStatus.CONNECTED -> Icons.Default.Cloud
                    ConnectionStatus.DISCONNECTED -> Icons.Default.CloudOff
                    else -> Icons.Default.Cloud
                },
                contentDescription = null,
                tint = when (connectionStatus) {
                    ConnectionStatus.CONNECTED -> MaterialTheme.colorScheme.tertiary
                    ConnectionStatus.DISCONNECTED -> MaterialTheme.colorScheme.error
                    else -> MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                },
                modifier = Modifier.size(20.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = when (connectionStatus) {
                    ConnectionStatus.UNKNOWN -> "Не проверено"
                    ConnectionStatus.CHECKING -> "Проверка..."
                    ConnectionStatus.CONNECTED -> "Подключено ✓"
                    ConnectionStatus.DISCONNECTED -> "Нет подключения ✗"
                },
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.weight(1f)
            )
            if (primaryUrl.isNotBlank()) {
                FilledTonalButton(
                    onClick = onTestConnection,
                    enabled = connectionStatus != ConnectionStatus.CHECKING,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                ) {
                    Icon(
                        Icons.Default.NetworkCheck,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Тест", style = MaterialTheme.typography.labelSmall)
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Primary URL
        OutlinedTextField(
            value = primaryUrl,
            onValueChange = onPrimaryUrlChange,
            label = { Text("Основной URL (WiFi)") },
            placeholder = { Text("http://<YOUR_LOCAL_IP>:8643") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            supportingText = { Text("Основной адрес Hermes API (локальная сеть)") }
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Fallback URL
        OutlinedTextField(
            value = fallbackUrl,
            onValueChange = onFallbackUrlChange,
            label = { Text("Резервный URL (Tailscale)") },
            placeholder = { Text("http://100.x.x.x:8643") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            supportingText = { Text("Резервный адрес через Tailscale (авто-переключение)") }
        )

        Spacer(modifier = Modifier.height(8.dp))

        // API Key
        OutlinedTextField(
            value = apiKey,
            onValueChange = onApiKeyChange,
            label = { Text("API-ключ") },
            placeholder = { Text("Введите API-ключ") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            supportingText = { Text("API_SERVER_KEY из .env Hermes") }
        )
    }
}

@Composable
fun ConnectionIndicator(
    mode: HealthCheckManager.ConnectionMode,
    modifier: Modifier = Modifier
) {
    val color = when (mode) {
        HealthCheckManager.ConnectionMode.WIFI -> MaterialTheme.colorScheme.tertiary
        HealthCheckManager.ConnectionMode.TAILSCALE -> MaterialTheme.colorScheme.primary
        HealthCheckManager.ConnectionMode.OFFLINE -> MaterialTheme.colorScheme.error
    }
    val label = when (mode) {
        HealthCheckManager.ConnectionMode.WIFI -> "WiFi"
        HealthCheckManager.ConnectionMode.TAILSCALE -> "Tailscale"
        HealthCheckManager.ConnectionMode.OFFLINE -> "Offline"
    }

    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier
    ) {
        Box(
            modifier = Modifier
                .size(12.dp)
                .clip(CircleShape)
                .background(color, CircleShape)
        )
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )
    }
}
