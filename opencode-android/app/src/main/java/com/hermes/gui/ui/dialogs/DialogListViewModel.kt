package com.hermes.gui.ui.dialogs

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hermes.gui.data.repository.DialogRepository
import com.hermes.gui.domain.model.Conversation
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class DialogListViewModel @Inject constructor(
    private val dialogRepository: DialogRepository
) : ViewModel() {

    private val _conversations = MutableStateFlow<List<Conversation>>(emptyList())
    val conversations: StateFlow<List<Conversation>> = _conversations.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    init {
        loadConversations("HERMES")
    }

    private fun loadConversations(mode: String) {
        viewModelScope.launch {
            dialogRepository.getConversationsByMode(mode).collect { convs ->
                _conversations.value = convs
                _isLoading.value = false
            }
        }
    }

    fun deleteConversation(id: String) {
        viewModelScope.launch {
            dialogRepository.deleteConversation(id)
        }
    }

    fun deleteAllConversations() {
        viewModelScope.launch {
            dialogRepository.deleteAllConversations()
        }
    }
}
