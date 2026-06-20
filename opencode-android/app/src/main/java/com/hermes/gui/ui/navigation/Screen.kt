package com.hermes.gui.ui.navigation

sealed class Screen(val route: String) {
    data object Chat : Screen("chat")
    data class ChatWithId(val conversationId: String) : Screen("chat/{conversationId}") {
        companion object {
            const val ROUTE_WITH_ARGS = "chat/{conversationId}"
        }
    }
    data object DialogList : Screen("dialogs")
    data object Settings : Screen("settings")
}
