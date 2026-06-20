package com.hermes.gui.ui.navigation

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.hermes.gui.ui.chat.ChatScreen
import com.hermes.gui.ui.chat.ChatViewModel
import com.hermes.gui.ui.chat.components.AgentSelector
import com.hermes.gui.ui.chat.components.ModelSelector
import com.hermes.gui.ui.chat.components.PersonaSelector
import com.hermes.gui.ui.dialogs.DialogListScreen
import com.hermes.gui.ui.settings.SettingsScreen
import com.hermes.gui.ui.settings.SettingsViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NavGraph() {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination
    val isSettingsOpen = currentDestination?.route == Screen.Settings.route

    // Shared ViewModels scoped to Activity — one instance for the whole app
    val chatViewModel: ChatViewModel = hiltViewModel()
    val chatUiState by chatViewModel.uiState.collectAsStateWithLifecycle()
    val settingsViewModel: SettingsViewModel = hiltViewModel()
    val settingsUiState by settingsViewModel.uiState.collectAsStateWithLifecycle()
    val connectionMode by settingsViewModel.connectionMode.collectAsStateWithLifecycle()

    // Dialog visibility controlled at NavGraph level
    var showPersonaSelector by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            if (!isSettingsOpen) {
                TopAppBar(
                    title = {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            val isChat = currentDestination?.route == Screen.Chat.route ||
                                currentDestination?.route?.startsWith("chat/") == true
                            FilterChip(
                                selected = isChat,
                                onClick = {
                                    navController.navigate(Screen.Chat.route) {
                                        popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                },
                                label = { Text("Чат") },
                                leadingIcon = { Icon(Icons.Default.Chat, null, Modifier.size(18.dp)) }
                            )
                            val isDialogs = currentDestination?.route == Screen.DialogList.route
                            FilterChip(
                                selected = isDialogs,
                                onClick = {
                                    navController.navigate(Screen.DialogList.route) {
                                        popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                },
                                label = { Text("Диалоги") },
                                leadingIcon = { Icon(Icons.Default.History, null, Modifier.size(18.dp)) }
                            )
                        }
                    },
                    actions = {
                        IconButton(onClick = { navController.navigate(Screen.Settings.route) }) {
                            Icon(Icons.Default.Settings, "Настройки")
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
                )
            } else {
                TopAppBar(
                    title = { Text("Настройки") },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.Default.ArrowBack, "Назад")
                        }
                    },
                    actions = {
                        IconButton(onClick = { settingsViewModel.refreshToolsets() }) {
                            Icon(Icons.Default.Refresh, "Обновить")
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
                )
            }
        },
        bottomBar = {
            if (!isSettingsOpen) {
                BottomToolbar(
                    connectionMode = connectionMode,
                    backendMode = settingsUiState.settings.backendMode,
                    onToggleBackend = { settingsViewModel.toggleBackend() },
                    ttsEnabled = chatUiState.ttsEnabled,
                    onToggleTts = { chatViewModel.toggleTts() },
                    fullCycleEnabled = chatUiState.fullCycleEnabled,
                    onToggleFullCycle = { chatViewModel.toggleFullCycle() },
                    onDialogsClick = {
                        navController.navigate(Screen.DialogList.route) {
                            popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onPersonaClick = { showPersonaSelector = true }
                )
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Chat.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Chat.route) {
                ChatScreen(
                    viewModel = chatViewModel
                )
            }
            composable(
                route = "chat/{conversationId}",
                arguments = listOf(navArgument("conversationId") { type = NavType.StringType })
            ) { backStackEntry ->
                val conversationId = backStackEntry.arguments?.getString("conversationId") ?: ""
                ChatScreen(
                    conversationId = conversationId,
                    viewModel = chatViewModel
                )
            }
            composable(Screen.DialogList.route) {
                DialogListScreen(
                    onConversationClick = { convId ->
                        navController.navigate("chat/$convId")
                    }
                )
            }
            composable(Screen.Settings.route) {
                SettingsScreen(viewModel = settingsViewModel)
            }
        }
    }

    // Global dialogs
    if (showPersonaSelector) {
        PersonaSelector(
            selectedPersona = settingsUiState.settings.selectedPersona,
            onSelectPersona = { settingsViewModel.updateSelectedPersona(it) },
            onDismiss = { showPersonaSelector = false }
        )
    }
}

@Composable
private fun BottomToolbar(
    connectionMode: com.hermes.gui.data.remote.HealthCheckManager.ConnectionMode,
    backendMode: String,
    onToggleBackend: () -> Unit,
    ttsEnabled: Boolean,
    onToggleTts: () -> Unit,
    fullCycleEnabled: Boolean,
    onToggleFullCycle: () -> Unit,
    onDialogsClick: () -> Unit,
    onPersonaClick: () -> Unit
) {
    val connectionColor = when (connectionMode) {
        com.hermes.gui.data.remote.HealthCheckManager.ConnectionMode.WIFI ->
            androidx.compose.ui.graphics.Color(0xFF4CAF50)
        com.hermes.gui.data.remote.HealthCheckManager.ConnectionMode.TAILSCALE ->
            androidx.compose.ui.graphics.Color(0xFF2196F3)
        com.hermes.gui.data.remote.HealthCheckManager.ConnectionMode.OFFLINE ->
            androidx.compose.ui.graphics.Color(0xFFF44336)
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .navigationBarsPadding(),
        shadowElevation = 8.dp,
        color = MaterialTheme.colorScheme.surface
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 🔌 H ↔ OC+ switch — prominent, model-aware
            Row(verticalAlignment = Alignment.CenterVertically) {
                val isHermes = backendMode == "hermes"
                FilledTonalButton(
                    onClick = onToggleBackend,
                    modifier = Modifier.height(36.dp),
                    colors = ButtonDefaults.filledTonalButtonColors(
                        containerColor = if (isHermes) 
                            connectionColor.copy(alpha = 0.2f) 
                        else 
                            MaterialTheme.colorScheme.tertiaryContainer
                    )
                ) {
                    Icon(
                        imageVector = if (isHermes) Icons.Default.Person else Icons.Default.SmartToy,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                        tint = if (isHermes) connectionColor else MaterialTheme.colorScheme.onTertiaryContainer
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        text = if (isHermes) "Hermes" else "OpenCode+",
                        style = MaterialTheme.typography.labelMedium
                    )
                }
            }

            Spacer(modifier = Modifier.width(4.dp))

            // 🔊 TTS toggle
            FilledIconButton(
                onClick = onToggleTts,
                modifier = Modifier.size(36.dp),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = if (ttsEnabled)
                        MaterialTheme.colorScheme.primaryContainer
                    else
                        MaterialTheme.colorScheme.surfaceVariant
                )
            ) {
                Icon(
                    if (ttsEnabled) Icons.Default.VolumeUp else Icons.Default.VolumeOff,
                    "Озвучка",
                    Modifier.size(18.dp)
                )
            }

            Spacer(modifier = Modifier.width(4.dp))

            // 🔄 Full Cycle toggle — /agent plan prefix
            FilledIconButton(
                onClick = onToggleFullCycle,
                modifier = Modifier.size(36.dp),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = if (fullCycleEnabled)
                        MaterialTheme.colorScheme.primaryContainer
                    else
                        MaterialTheme.colorScheme.surfaceVariant
                )
            ) {
                Icon(
                    if (fullCycleEnabled) Icons.Default.Refresh else Icons.Default.Refresh,
                    if (fullCycleEnabled) "Оркестратор Вкл" else "Оркестратор Выкл",
                    Modifier.size(18.dp),
                    tint = if (fullCycleEnabled)
                        MaterialTheme.colorScheme.primary
                    else
                        MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(modifier = Modifier.width(4.dp))

            // 🎭 Persona button
            FilledIconButton(
                onClick = onPersonaClick,
                modifier = Modifier.size(40.dp),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = MaterialTheme.colorScheme.tertiaryContainer
                )
            ) {
                Icon(Icons.Default.Face, "Персона", Modifier.size(20.dp))
            }

            Spacer(modifier = Modifier.width(8.dp))

            // 🎭 Persona button

            // 📜 History button
            FilledIconButton(
                onClick = onDialogsClick,
                modifier = Modifier.size(40.dp),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                )
            ) {
                Icon(Icons.Default.History, "Диалоги", Modifier.size(20.dp))
            }
        }
    }
}
