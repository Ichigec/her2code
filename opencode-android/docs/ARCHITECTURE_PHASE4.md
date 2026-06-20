# Архитектура Phase 4: Voice Chat, Personas, Multi-URL

> **Статус:** Дизайн-документ  
> **Дата:** 2026-06-12  
> **Целевая версия:** 1.1.0+  
> **Базис:** Текущий MVVM + Clean Architecture, Jetpack Compose, Hilt, Room, OkHttp/Retrofit, SSE

---

## 1. Сводка изменений (что добавить / изменить / удалить)

### 1.1 Новые файлы (18 шт.)

```
app/src/main/java/com/hermes/gui/
├── data/
│   ├── connectivity/
│   │   ├── ConnectivityManager.kt          # Определение Wi-Fi/Mobile + health-check + fallback
│   │   └── UrlProvider.kt                  # Интерфейс + реализация: выбор URL из цепочки
│   └── remote/
│       └── AudioStreamClient.kt            # OkHttp streaming для Opus аудио
├── domain/
│   ├── audio/
│   │   ├── AudioManager.kt                 # Оркестратор: запись → Opus → HTTP / TTS → воспроизведение
│   │   ├── AudioRecorder.kt                # MediaProjection/AudioRecord → Opus encoder
│   │   ├── OpusEncoder.kt                  # Native Opus encoder (JNI или Oboe/Opus)
│   │   ├── OpusDecoder.kt                  # Native Opus decoder для TTS-ответа
│   │   └── AudioPlayer.kt                  # ExoPlayer/MediaPlayer для воспроизведения TTS
│   └── model/
│       └── Persona.kt                      # Модель персоны: id, name, description, icon, systemPrompt
├── ui/
│   ├── chat/components/
│   │   ├── PersonaSelector.kt              # Dropdown с 15 персонами
│   │   └── VoiceCallButton.kt              # Кнопка голосового звонка в ChatInputBar
│   ├── voice/
│   │   ├── VoiceCallScreen.kt              # Экран активного звонка (fullscreen)
│   │   └── VoiceCallViewModel.kt           # ViewModel голосового звонка
│   └── navigation/
│       └── BottomToolbar.kt                # Вынесен из NavGraph.kt в отдельный файл
└── util/
    └── NetworkUtil.kt                      # Вспомогательные функции: тип сети, ping
```

### 1.2 Изменяемые файлы (12 шт.)

| Файл | Характер изменений |
|------|-------------------|
| `NavGraph.kt` | Убрать `BottomToolbar` inline, заменить на `PersonaSelector` вместо H/OC+, добавить VoiceCallScreen |
| `Screen.kt` | Добавить `VoiceCall` в sealed class |
| `ChatViewModel.kt` | Добавить управление персоной, убрать backendMode, добавить voice-режим |
| `ChatUiState.kt` | Убрать `showModelSelector`, `showAgentSelector`, добавить voice-состояние |
| `ChatInputBar.kt` | Добавить `VoiceCallButton` |
| `ChatScreen.kt` | Минимальные изменения (передать persona в ChatInputBar) |
| `SettingsViewModel.kt` | Убрать `backendMode`, `openCodeApiUrl/Key`, добавить `personaId`, `urlList` |
| `SettingsUiState` (в `SettingsViewModel.kt`) | Переименовать `connectionStatus` → `urlStatuses: Map<String, ConnectionStatus>` |
| `SettingsRepository.kt` | Убрать `updateBackendMode`, `updateOpenCodeApiUrl/Key`, добавить `updatePersonaId`, `updateFallbackUrls` |
| `SettingsDataStore.kt` | Убрать `BackendMode`, поля `openCodeApiUrl/Key`, добавить `selectedPersona`, `primaryUrl`, `fallbackUrl`, `urlList` |
| `AppSettings` (в `SettingsDataStore.kt`) | Убрать `backendMode`, `openCodeApiUrl`, `openCodeApiKey`; добавить `selectedPersona`, `primaryUrl`, `fallbackUrl` |
| `AuthInterceptor.kt` | Убрать ветвление H/OC+, использовать `UrlProvider` для определения текущего URL |
| `ChatRepository.kt` | Добавить метод `streamAudio()` для отправки Opus и получения TTS |
| `HermisApi.kt` | Добавить эндпоинты: `POST v1/audio/stt` (Opus→Text), `POST v1/audio/tts` (Text→Audio) |
| `AppModule.kt` | Добавить провайдеры: `ConnectivityManager`, `UrlProvider`, `AudioManager`, `ExoPlayer` |
| `Constants.kt` | Заменить `HERMES_AGENTS` на 15 персон `PERSONAS`, убрать `BackendMode`-зависимые функции |
| `DialogRepository.kt` | Убрать параметр `backendMode` из `createConversation()` |
| `ConversationEntity.kt` | Убрать поле `backendMode` |
| `ConversationDao.kt` | Убрать `getConversationsByMode()` |
| `build.gradle.kts` | Добавить зависимости: ExoPlayer, Opus codec, Connectivity |

### 1.3 Удаляемые файлы (2 шт.)

```
app/src/main/java/com/hermes/gui/ui/chat/components/ModelSelector.kt   # (переиспользовать для PersonaSelector)
app/src/main/java/com/hermes/gui/ui/chat/components/AgentSelector.kt   # (слить в PersonaSelector)
```

### 1.4 Удаляемые enum/классы

- `BackendMode` enum (из `SettingsDataStore.kt`) — удалить полностью
- Поля `openCodeApiUrl`, `openCodeApiKey` (из `AppSettings`) — удалить
- `HERMES_AGENTS` / `OPENCODE_AGENTS` списки (из `Constants.kt`) — заменить на `PERSONAS`
- Функции: `agentsForMode()`, `modelsForMode()`, `promptForAgent()` — переписать без mode

---

## 2. Новая структура пакетов (финальная)

```
com.hermes.gui/
├── data/
│   ├── connectivity/          # NEW: управление соединениями
│   │   ├── ConnectivityManager.kt
│   │   └── UrlProvider.kt
│   ├── local/
│   │   ├── AppDatabase.kt
│   │   ├── dao/
│   │   │   ├── ConversationDao.kt       # убрать getConversationsByMode
│   │   │   └── MessageDao.kt
│   │   └── entity/
│   │       ├── ConversationEntity.kt    # убрать backendMode
│   │       └── MessageEntity.kt
│   ├── remote/
│   │   ├── AudioStreamClient.kt         # NEW: Opus-стриминг
│   │   ├── HermesApi.kt                # + stt/tts эндпоинты
│   │   ├── SseClient.kt
│   │   ├── dto/                         # + AudioRequest, TtsResponse DTOs
│   │   │   ├── AudioRequest.kt          # NEW
│   │   │   ├── TtsResponse.kt           # NEW
│   │   │   └── ... (существующие)
│   │   └── interceptor/
│   │       └── AuthInterceptor.kt       # переписан на UrlProvider
│   ├── repository/
│   │   ├── ChatRepository.kt           # + streamAudio()
│   │   ├── DialogRepository.kt         # убрать backendMode параметр
│   │   ├── SettingsRepository.kt       # убрать H/OC+, добавить persona/urls
│   │   └── ToolRepository.kt
│   └── settings/
│       └── SettingsDataStore.kt         # переписан без BackendMode
├── di/
│   └── AppModule.kt                    # + новые провайдеры
├── domain/
│   ├── audio/                           # NEW: аудиоподсистема
│   │   ├── AudioManager.kt
│   │   ├── AudioRecorder.kt
│   │   ├── AudioPlayer.kt
│   │   ├── OpusEncoder.kt
│   │   └── OpusDecoder.kt
│   └── model/
│       ├── AgentPreset.kt
│       ├── Conversation.kt             # убрать backendMode
│       ├── Message.kt
│       ├── Persona.kt                   # NEW
│       └── Toolset.kt
├── ui/
│   ├── chat/
│   │   ├── ChatScreen.kt
│   │   ├── ChatUiState.kt              # + voiceCallState
│   │   ├── ChatViewModel.kt            # + persona, voice
│   │   └── components/
│   │       ├── ChatInputBar.kt         # + VoiceCallButton
│   │       ├── MessageBubble.kt
│   │       ├── PersonaSelector.kt       # NEW: replaces ModelSelector+AgentSelector
│   │       ├── ToolProgressCard.kt
│   │       ├── VoiceCallButton.kt       # NEW
│   │       └── ...
│   ├── dialogs/
│   │   ├── DialogListScreen.kt
│   │   ├── DialogListViewModel.kt
│   │   └── components/
│   │       └── DialogItem.kt
│   ├── navigation/
│   │   ├── BottomToolbar.kt             # NEW: вынесен из NavGraph
│   │   ├── NavGraph.kt                  # изменён
│   │   └── Screen.kt                    # + VoiceCall
│   ├── settings/
│   │   ├── SettingsScreen.kt            # одна секция URL вместо двух
│   │   ├── SettingsViewModel.kt         # убрать H/OC+ поля
│   │   └── components/
│   │       ├── ApiSettingsSection.kt    # переиспользован с Multi-URL
│   │       └── ...
│   ├── theme/
│   │   ├── Color.kt, Theme.kt, Type.kt
│   └── voice/                           # NEW: экран звонка
│       ├── VoiceCallScreen.kt
│       └── VoiceCallViewModel.kt
└── util/
    ├── Constants.kt                     # 15 персон вместо H/OC+ агентов
    ├── MarkdownRenderer.kt
    └── NetworkUtil.kt                   # NEW
```

---

## 3. BottomToolbar без H/OC+ — с PersonaSelector

### 3.1 Вынос BottomToolbar в отдельный файл

**Файл:** `ui/navigation/BottomToolbar.kt`

```kotlin
@Composable
fun BottomToolbar(
    selectedPersona: Persona,
    onPersonaClick: () -> Unit,
    onDialogsClick: () -> Unit,
    onModelClick: () -> Unit
) {
    Surface(...) {
        Row(...) {
            // 1. Кнопка персоны (вместо H/OC+ toggle)
            FilledTonalButton(onClick = onPersonaClick) {
                Icon(selectedPersona.icon, ...)
                Text(selectedPersona.displayName)
                Icon(Icons.Default.ArrowDropDown, ...) // индикатор dropdown
            }

            // 2. Диалоги
            FilledIconButton(onClick = onDialogsClick) {
                Icon(Icons.Default.History, ...)
            }

            // 3. Модель (существующая кнопка)
            FilledIconButton(onClick = onModelClick) {
                Icon(Icons.Default.Psychology, ...)
            }
        }
    }
}
```

### 3.2 PersonaSelector Dropdown

**Файл:** `ui/chat/components/PersonaSelector.kt`

```kotlin
@Composable
fun PersonaSelector(
    personas: List<Persona>,          // 15 персон из Constants
    selectedPersonaId: String,
    onSelectPersona: (String) -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(onDismissRequest = onDismiss) {
        LazyColumn {
            items(personas) { persona ->
                ListItem(
                    headlineContent = { Text(persona.displayName) },
                    supportingContent = { Text(persona.description) },
                    leadingContent = { Icon(persona.icon, ...) },
                    trailingContent = {
                        if (persona.id == selectedPersonaId)
                            Icon(Icons.Default.Check, ...)
                    },
                    modifier = Modifier.clickable {
                        onSelectPersona(persona.id)
                        onDismiss()
                    }
                )
            }
        }
    }
}
```

---

## 4. Модель Persona

**Файл:** `domain/model/Persona.kt`

```kotlin
data class Persona(
    val id: String,              // "general", "build", "review", etc.
    val displayName: String,     // "Генерал", "Сборщик", "Ревьюер"
    val description: String,     // "Универсальный ассистент с полным доступом"
    val systemPrompt: String,    // Полный системный промпт
    val icon: ImageVector,       // Иконка Material
    val temperature: Float? = null,       // Опциональный temperature override
    val reasoningEffort: String? = null,  // null/"low"/"medium"/"high"
)
```

**15 персон** в `Constants.kt` (объединённый список, без разделения на H/OC+):

| ID | DisplayName |
|----|-------------|
| general | Генерал |
| build | Сборщик |
| plan | Планировщик |
| review | Ревьюер |
| safe | Безопасный |
| explore | Исследователь |
| scout | Разведчик |
| deep-explore | Глубокий анализ |
| claw | Claw |
| composter | Компостер |
| teacher | Учитель |
| poet | Поэт |
| debugger | Отладчик |
| architect | Архитектор |
| devops | DevOps |

---

## 5. AudioManager — компонент аудиоподсистемы

### 5.1 Класс AudioManager (оркестратор)

**Файл:** `domain/audio/AudioManager.kt`

```kotlin
@Singleton
class AudioManager @Inject constructor(
    private val audioRecorder: AudioRecorder,
    private val audioPlayer: AudioPlayer,
    private val audioStreamClient: AudioStreamClient,
    private val connectivityManager: ConnectivityManager,
    @ApplicationContext private val context: Context
) {
    private val _callState = MutableStateFlow(VoiceCallState.Idle)
    val callState: StateFlow<VoiceCallState> = _callState.asStateFlow()

    private var recordingJob: Job? = null
    private var playbackJob: Job? = null

    /**
     * Начать голосовой звонок:
     * 1. Проверить permissions (RECORD_AUDIO)
     * 2. Открыть микрофон
     * 3. Начать Opus-энкодинг → HTTP-стриминг
     * 4. Получать SSE-ответы (текст + TTS аудио)
     * 5. Воспроизводить TTS аудио
     * 6. Отображать транскрипцию
     */
    suspend fun startCall(scope: CoroutineScope) { ... }

    suspend fun endCall() { ... }

    fun muteMicrophone() { ... }
    fun unmuteMicrophone() { ... }
    fun setSpeakerMode(enabled: Boolean) { ... }
}

sealed class VoiceCallState {
    data object Idle : VoiceCallState()
    data object Connecting : VoiceCallState()
    data class Active(
        val transcription: String = "",     // Транскрипция сказанного
        val response: String = "",          // Текст ответа (стриминг)
        val isSpeaking: Boolean = false     // Идёт TTS-воспроизведение
    ) : VoiceCallState()
    data class Error(val message: String) : VoiceCallState()
}
```

### 5.2 AudioRecorder

**Файл:** `domain/audio/AudioRecorder.kt`

```kotlin
class AudioRecorder @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private var audioRecord: AudioRecord? = null
    private val opusEncoder = OpusEncoder()  // Native wrapper

    /**
     * Захват аудио с микрофона:
     * - Sample rate: 48000 Hz (Opus fullband)
     * - Channels: mono
     * - Format: PCM 16-bit
     * - Буфер: 960 samples (20ms frame) → Opus-энкодинг
     *
     * Возвращает Flow<ByteArray> — Opus-кодированные фреймы
     */
    fun startRecording(): Flow<ByteArray> = callbackFlow { ... }

    fun stopRecording() { ... }
}
```

### 5.3 OpusEncoder / OpusDecoder

**Файлы:** `domain/audio/OpusEncoder.kt`, `domain/audio/OpusDecoder.kt`

```kotlin
// Использовать библиотеку концентратора Opus:
// implementation("com.github.theeze:opuscodec:1.0.0")  // или JNI-wrapper

class OpusEncoder {
    // Opus application: VOIP (оптимально для речи)
    // Bitrate: 32000 bps (речь, хорошее качество)
    // Frame size: 20ms (960 samples @ 48kHz)
    fun encode(pcmData: ShortArray): ByteArray { ... }
    fun release() { ... }
}

class OpusDecoder {
    fun decode(opusData: ByteArray): ShortArray { ... }
    fun release() { ... }
}
```

### 5.4 AudioPlayer

**Файл:** `domain/audio/AudioPlayer.kt`

```kotlin
class AudioPlayer @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private var mediaPlayer: MediaPlayer? = null
    private val opusDecoder = OpusDecoder()

    /**
     * Воспроизведение TTS-аудио:
     * - Получает Opus-фреймы из SSE-стрима
     * - Декодирует Opus → PCM
     * - Записывает в AudioTrack для потокового воспроизведения
     */
    suspend fun playAudioStream(audioFlow: Flow<ByteArray>) { ... }

    fun stop() { ... }
}
```

### 5.5 AudioStreamClient

**Файл:** `data/remote/AudioStreamClient.kt`

```kotlin
@Singleton
class AudioStreamClient @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val urlProvider: UrlProvider
) {
    /**
     * Отправляет Opus-фреймы через streaming POST на /v1/audio/stt
     * Content-Type: audio/opus
     * Transfer-Encoding: chunked
     *
     * Ответ: SSE-стрим с событиями:
     *   - event: stt.transcription → текст сказанного
     *   - event: chat.delta → текст ответа (как обычный SSE)
     *   - event: tts.audio → Opus-фрейм для воспроизведения
     */
    fun streamAudio(
        audioFlow: Flow<ByteArray>,
        personaId: String,
        modelId: String
    ): Flow<AudioSseEvent> = flow { ... }
}

sealed class AudioSseEvent {
    data class Transcription(val text: String) : AudioSseEvent()
    data class ChatDelta(val content: String) : AudioSseEvent()
    data class TtsAudio(val opusFrame: ByteArray) : AudioSseEvent()
    data class ToolStart(val toolCallId: String, val name: String) : AudioSseEvent()
    data class ToolComplete(val toolCallId: String, val result: String) : AudioSseEvent()
    data class Done(val usage: Usage?) : AudioSseEvent()
    data class Error(val message: String) : AudioSseEvent()
}
```

---

## 6. ConnectivityManager — Multi-URL с авто-fallback

### 6.1 ConnectivityManager

**Файл:** `data/connectivity/ConnectivityManager.kt`

```kotlin
@Singleton
class ConnectivityManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val connectivityManager =
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as android.net.ConnectivityManager

    /**
     * Определяет текущий тип сети
     */
    fun getNetworkType(): NetworkType {
        val network = connectivityManager.activeNetwork ?: return NetworkType.NONE
        val caps = connectivityManager.getNetworkCapabilities(network) ?: return NetworkType.NONE
        return when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> NetworkType.WIFI
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> NetworkType.MOBILE
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> NetworkType.ETHERNET
            caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) -> NetworkType.VPN
            else -> NetworkType.OTHER
        }
    }

    /**
     * Наблюдаем за изменением сети
     */
    fun observeNetworkType(): Flow<NetworkType> = callbackFlow { ... }

    /**
     * Health-check URL (GET /health с таймаутом 3с)
     */
    suspend fun checkUrl(url: String): Result<Long> { // latency ms
        // OkHttp HEAD или GET /health
    }
}

enum class NetworkType {
    WIFI, MOBILE, ETHERNET, VPN, OTHER, NONE
}
```

### 6.2 UrlProvider

**Файл:** `data/connectivity/UrlProvider.kt`

```kotlin
@Singleton
class UrlProvider @Inject constructor(
    private val connectivityManager: ConnectivityManager,
    private val settingsDataStore: SettingsDataStore
) {
    private val _currentUrl = MutableStateFlow<String?>(null)
    val currentUrl: StateFlow<String?> = _currentUrl.asStateFlow()

    private val _urlStatus = MutableStateFlow<Map<String, UrlStatus>>(emptyMap())
    val urlStatus: StateFlow<Map<String, UrlStatus>> = _urlStatus.asStateFlow()

    /**
     * Определяет приоритетный URL на основе networkType:
     *
     * Wi-Fi  → primaryUrl  (<YOUR_LOCAL_IP>:8643)
     * Mobile → fallbackUrl  (100.x.x.x:8643 Tailscale)
     * VPN    → primaryUrl (Tailscale — как локальная сеть)
     *
     * Авто-fallback: если primaryUrl не отвечает → пробуем fallbackUrl
     */
    fun resolveUrl(networkType: NetworkType): String {
        val settings = settingsDataStore.getSettings()
        return when (networkType) {
            NetworkType.WIFI, NetworkType.ETHERNET -> settings.primaryUrl
            NetworkType.MOBILE -> settings.fallbackUrl
            NetworkType.VPN -> settings.primaryUrl
            else -> settings.primaryUrl
        }
    }

    /**
     * Проверить все URL из списка и выбрать первый работающий
     */
    suspend fun healthCheckAll(): String? {
        val settings = settingsDataStore.getSettings()
        for (url in listOf(settings.primaryUrl, settings.fallbackUrl)) {
            val result = connectivityManager.checkUrl(url)
            if (result.isSuccess) {
                _currentUrl.value = url
                return url
            }
        }
        return null
    }
}

data class UrlStatus(
    val url: String,
    val latencyMs: Long?,
    val reachable: Boolean,
    val lastChecked: Long = System.currentTimeMillis()
)
```

### 6.3 Изменения в AuthInterceptor

```kotlin
class AuthInterceptor @Inject constructor(
    private val urlProvider: UrlProvider,
    private val settingsDataStore: SettingsDataStore
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        var request = chain.request()
        val originalUrl = request.url
        val settings = settingsDataStore.getSettings()

        // Единый URL из UrlProvider (уже выбранный с учётом сети)
        val apiUrl = urlProvider.currentUrl.value ?: settings.primaryUrl
        val apiKey = settings.apiKey

        // Rewrite URL
        val baseUrl = apiUrl.trimEnd('/').toHttpUrlOrNull()
        if (baseUrl != null) {
            request = request.newBuilder()
                .url(originalUrl.newBuilder()
                    .scheme(baseUrl.scheme)
                    .host(baseUrl.host)
                    .port(baseUrl.port)
                    .build())
                .build()
        }

        // Auth header
        if (apiKey.isNotBlank()) {
            request = request.newBuilder()
                .addHeader("Authorization", "Bearer $apiKey")
                .build()
        }

        return chain.proceed(request)
    }
}
```

---

## 7. Навигация: NavGraph, Screen, ChatViewModel, ChatRepository

### 7.1 Screen.kt — новый экран

```kotlin
sealed class Screen(val route: String) {
    data object Chat : Screen("chat")
    data class ChatWithId(val conversationId: String) : Screen("chat/{conversationId}") {
        companion object { const val ROUTE_WITH_ARGS = "chat/{conversationId}" }
    }
    data object DialogList : Screen("dialogs")
    data object Settings : Screen("settings")
    data object VoiceCall : Screen("voice_call")     // NEW
}
```

### 7.2 NavGraph.kt — изменения

```kotlin
@Composable
fun NavGraph() {
    // ... существующий код ...

    Scaffold(
        topBar = { /* ... без изменений ... */ },
        bottomBar = {
            if (!isSettingsOpen) {
                BottomToolbar(
                    selectedPersona = settingsUiState.settings.selectedPersona, // NEW
                    onPersonaClick = { showPersonaSelector = true },            // NEW
                    onDialogsClick = { ... },
                    onModelClick = { showModelSelector = true }
                )
            }
        }
    ) { innerPadding ->
        NavHost(...) {
            // ... существующие маршруты ...

            composable(Screen.VoiceCall.route) {           // NEW
                VoiceCallScreen(
                    onEndCall = { navController.popBackStack() }
                )
            }
        }
    }

    // PersonaSelector — вместо AgentSelector
    if (showPersonaSelector) {
        PersonaSelector(
            personas = Constants.PERSONAS,
            selectedPersonaId = settingsUiState.settings.selectedPersonaId,
            onSelectPersona = { settingsViewModel.updateSelectedPersona(it) },
            onDismiss = { showPersonaSelector = false }
        )
    }

    // ModelSelector — остаётся без изменений
    if (showModelSelector) {
        ModelSelector(...)  // больше не зависит от BackendMode
    }
}
```

### 7.3 ChatViewModel — изменения

```kotlin
@HiltViewModel
class ChatViewModel @Inject constructor(
    private val chatRepository: ChatRepository,
    private val dialogRepository: DialogRepository,
    private val settingsRepository: SettingsRepository,
    private val audioManager: AudioManager        // NEW: инжектируем
) : ViewModel() {

    // ... существующий код ...

    // ===== Voice call management =====
    fun startVoiceCall() {
        viewModelScope.launch {
            _uiState.update { it.copy(voiceCallActive = true) }
            audioManager.startCall(viewModelScope)
        }
    }

    fun endVoiceCall() {
        viewModelScope.launch {
            audioManager.endCall()
            _uiState.update { it.copy(voiceCallActive = false) }
        }
    }

    // observe voice call state
    init {
        viewModelScope.launch {
            audioManager.callState.collect { state ->
                when (state) {
                    is VoiceCallState.Active -> {
                        _uiState.update {
                            it.copy(
                                voiceTranscription = state.transcription,
                                streamingContent = state.response
                            )
                        }
                    }
                    // ...
                }
            }
        }
    }

    // sendMessage — перестаёт использовать backendMode
    private suspend fun startStreaming(conversationId: String) {
        // ...
        val settings = settingsRepository.settingsFlow.first()

        // Теперь personaId вместо (backendMode, selectedAgent)
        val systemPrompt = Constants.promptForPersona(settings.selectedPersonaId)
        // ... остальное без изменений ...
    }
}
```

### 7.4 ChatRepository — новый метод для голоса

```kotlin
@Singleton
class ChatRepository @Inject constructor(
    private val api: HermesApi,
    private val sseClient: SseClient,
    private val audioStreamClient: AudioStreamClient,  // NEW
    private val settingsDataStore: SettingsDataStore
) {
    // streamMessage() — без изменений (использует persona вместо backendMode)

    /**
     * Потоковая отправка аудио с получением SSE-ответа (TTS + текст)
     */
    fun streamAudioConversation(
        audioFlow: Flow<ByteArray>,
        personaId: String,
        modelId: String
    ): Flow<AudioSseEvent> = audioStreamClient.streamAudio(audioFlow, personaId, modelId)
}
```

---

## 8. Топология потоков данных: Голосовой звонок

```
┌────────────┐    PCM 48kHz     ┌──────────────┐    Opus frames     ┌───────────────┐
│  Микрофон   │ ───────────────→ │ AudioRecorder │ ────────────────→ │  OpusEncoder   │
│ (AudioRecord)│   16bit mono    │   (capture)   │   960s/20ms frame │  (native JNI)  │
└────────────┘                  └──────────────┘                   └───────┬───────┘
                                                                           │
                                                                 Opus ByteArray (chunked)
                                                                           │
                                                                           ▼
                                                              ┌─────────────────────┐
                                                              │  AudioStreamClient   │
                                                              │  POST /v1/audio/stt  │
                                                              │  Content-Type:       │
                                                              │  audio/opus          │
                                                              └──────────┬──────────┘
                                                                         │
                                                           OkHttp streaming POST
                                                                         │
                                                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           HERMES SERVER                                               │
│                                                                                      │
│  ┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐     │
│  │ STT Engine   │────→│ Hermes Agent  │────→│ Conversation  │────→│  TTS Engine   │     │
│  │ (Whisper)   │     │  (LLM)        │     │  Manager      │     │  (Opus TTS)  │     │
│  │ Opus→Text   │     │  Text→Text    │     │  (streaming)  │     │  Text→Opus   │     │
│  └─────────────┘     └──────────────┘     └───────────────┘     └──────┬───────┘     │
│                                                                         │            │
└─────────────────────────────────────────────────────────────────────────┼────────────┘
                                                                          │
                                                          SSE stream (multipart)
                                                                          │
                   ┌──────────────────────────────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │              SSE Response Parser              │
    │  ┌───────────────────────────────────────┐    │
    │  │ event: stt.transcription              │    │
    │  │ data: {"text": "привет как дела"}     │───→│──→ ChatUiState.voiceTranscription
    │  └───────────────────────────────────────┘    │
    │  ┌───────────────────────────────────────┐    │
    │  │ data: {"choices":[{"delta":           │    │
    │  │   {"content":"Здравствуйте"}}]}       │───→│──→ ChatUiState.streamingContent
    │  └───────────────────────────────────────┘    │
    │  ┌───────────────────────────────────────┐    │
    │  │ event: tts.audio                      │    │
    │  │ data: <Opus binary frame>             │───→│──→ AudioPlayer (воспроизведение)
    │  └───────────────────────────────────────┘    │
    │  ┌───────────────────────────────────────┐    │
    │  │ event: hermes.tool.progress           │    │
    │  │ data: {"status":"running", ...}       │───→│──→ ToolProgress (существующий)
    │  └───────────────────────────────────────┘    │
    │  ┌───────────────────────────────────────┐    │
    │  │ data: [DONE]                          │───→│──→ VoiceCallState.Idle
    │  └───────────────────────────────────────┘    │
    └──────────────────────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │              AudioPlayer                      │
    │  Opus frames → OpusDecoder → PCM ShortArray  │
    │  → AudioTrack.write() → Динамик              │
    └──────────────────────────────────────────────┘

ПОТОКИ ДАННЫХ (стрелками):

1. [Микрофон] → PCM → [AudioRecorder] → Opus frames → [OkHttp POST] → [Hermes STT]
2. [Hermes STT] → текст → [Hermes LLM] → текст ответа → [Hermes TTS] → Opus frames
3. [Hermes] → SSE stream → [AudioStreamClient] → разбор событий:
   ├─ transcription → ChatUiState (показ текста пользователя)
   ├─ chat.delta  → ChatUiState.streamingContent (стриминг ответа — ТАК ЖЕ как обычный чат)
   ├─ tts.audio   → [OpusDecoder] → PCM → [AudioTrack] → [Динамик]
   ├─ tool.*      → ToolProgress (существующий механизм)
   └─ [DONE]      → VoiceCallState.Idle
```

---

## 9. Интеграция голоса с существующим SSE-стримингом чата

### 9.1 Принцип: голос и текст не должны ломать друг друга

**Решение:** `VoiceCallState` управляет блокировкой текстового ввода, но НЕ блокирует отображение сообщений.

```kotlin
// ChatUiState — добавленные поля
data class ChatUiState(
    // ... существующие поля ...

    // Voice call
    val voiceCallActive: Boolean = false,         // Активен ли звонок
    val voiceTranscription: String = "",           // Что пользователь сказал (STT)
    val voiceCallState: VoiceCallState = VoiceCallState.Idle
)
```

**ChatInputBar** — во время звонка показывает кнопку «Завершить звонок» вместо поля ввода:

```kotlin
@Composable
fun ChatInputBar(
    enabled: Boolean,
    isStreaming: Boolean,
    voiceCallActive: Boolean,            // NEW
    onSend: (String) -> Unit,
    onStop: () -> Unit,
    onStartVoiceCall: () -> Unit,        // NEW
    onEndVoiceCall: () -> Unit           // NEW
) {
    if (voiceCallActive) {
        // Режим звонка: только кнопка "Завершить"
        VoiceCallActiveBar(
            onEndCall = onEndVoiceCall,
            transcription = voiceTranscription
        )
    } else {
        // Обычный режим: поле ввода + кнопка микрофона
        Row {
            // Кнопка голосового звонка (микрофон)
            VoiceCallButton(onClick = onStartVoiceCall)

            // Существующее поле ввода
            TextField(...)
            SendButton(...)
        }
    }
}
```

### 9.2 VoiceCallScreen (fullscreen)

Когда пользователь в звонке, можно развернуть fullscreen:

```kotlin
@Composable
fun VoiceCallScreen(
    viewModel: ChatViewModel = hiltViewModel(),
    onEndCall: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            // Аватар персоны (пульсирующий при TTS)
            PulsingAvatar(persona = uiState.selectedPersona)

            // Транскрипция (что пользователь сказал)
            Text(uiState.voiceTranscription, color = Color.White.copy(alpha = 0.6f))

            // Ответ (стриминг текста)
            Text(uiState.streamingContent, color = Color.White)

            // Кнопка завершения
            IconButton(onClick = {
                viewModel.endVoiceCall()
                onEndCall()
            }) {
                Icon(Icons.Default.CallEnd, tint = Color.Red)
            }
        }
    }
}
```

### 9.3 Сосуществование голосового и текстового стримов

```
                    ChatViewModel
                         │
          ┌──────────────┴──────────────┐
          │                             │
   streamMessage()              streamAudioCall()
   (текстовый SSE)              (голосовой SSE)
          │                             │
          ▼                             ▼
   ChatRepository              AudioStreamClient
   .streamMessage()            .streamAudio()
          │                             │
          ▼                             ▼
   SseClient.parseStream()     AudioStreamClient.parseAudioSse()
          │                             │
          ▼                             ▼
   SseEvent.Content ─────────→  ChatUiState.streamingContent  ←────── AudioSseEvent.ChatDelta
   SseEvent.ToolStart ───────→ ChatUiState.toolProgress      ←────── AudioSseEvent.ToolStart
   SseEvent.Done ────────────→ ChatUiState.isStreaming=false ←────── AudioSseEvent.Done
          │                             │
          └──────────┬──────────────────┘
                     │
              ОБЩЕЕ СОСТОЯНИЕ: ChatUiState
              - streamingContent (единый — используется обоими)
              - toolProgress (единый — используется обоими)
              - voiceCallActive (только для голоса)
              - voiceTranscription (только для голоса)
```

**Ключевой момент:** `streamingContent` в `ChatUiState` используется ОБОИМИ стримами — и текстовым, и голосовым. Поэтому:
- При голосовом звонке текстовый ответ ассистента отображается в том же `MessageBubble(isStreaming=true)`, что и при обычном чате
- При завершении звонка финальный ответ сохраняется в Room через тот же механизм `finalizeMessage()`

---

## 10. Изменения в SettingsDataStore и AppSettings

### 10.1 Новый AppSettings

```kotlin
data class AppSettings(
    // Единый URL + API-ключ
    val apiUrl: String = DEFAULT_API_URL,
    val apiKey: String = DEFAULT_API_KEY,

    // Multi-URL
    val primaryUrl: String = DEFAULT_PRIMARY_URL,    // Wi-Fi URL
    val fallbackUrl: String = DEFAULT_FALLBACK_URL,   // Tailscale URL
    val urlList: List<String> = emptyList(),           // Все известные URL

    // Персона
    val selectedPersona: Persona = Persona.DEFAULT,
    val selectedPersonaId: String = "general",

    // Модель
    val selectedModel: String = "hermes-agent",

    // Системный промпт (переопределение персоны)
    val systemPrompt: String = "",

    // Остальное без изменений
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val streamingEnabled: Boolean = true,
    val codeExecutionEnabled: Boolean = false,
    val enabledTools: Set<String> = emptySet(),
    val enabledMcpServers: Set<String> = emptySet()
)
```

### 10.2 Удалённые поля

- ~~`backendMode: BackendMode`~~ — УДАЛИТЬ
- ~~`openCodeApiUrl: String`~~ — УДАЛИТЬ
- ~~`openCodeApiKey: String`~~ — УДАЛИТЬ

### 10.3 Удалённый enum

- ~~`enum class BackendMode { HERMES, OPENCODE_PLUS }`~~ — УДАЛИТЬ полностью

---

## 11. Изменения в SettingsScreen

**До:**
```
┌─────────────────────────────┐
│ Hermes API                  │
│  URL: [_______________]     │
│  Key: [_______________]     │
│  [Тест]                     │
├─────────────────────────────┤
│ OpenCode+ API               │  ← УДАЛИТЬ
│  URL: [_______________]     │
│  Key: [_______________]     │
│  [Тест]                     │
├─────────────────────────────┤
│ Модель/Агент/Промпт         │
├─────────────────────────────┤
│ Оформление/Стриминг          │
├─────────────────────────────┤
│ Инструменты                  │
└─────────────────────────────┘
```

**После:**
```
┌─────────────────────────────┐
│ API-подключение             │
│  Primary URL (Wi-Fi):       │
│  [<YOUR_LOCAL_IP>:8643    ]    │
│  Fallback URL (Mobile):     │  ← НОВОЕ
│  [100.98.76.54:8643    ]    │
│  Статус: ● Wi-Fi ✓ (12ms)   │  ← НОВОЕ
│  API-ключ: [___________]    │
│  [Тест подключения]          │
├─────────────────────────────┤
│ Персона (15 шт dropdown)    │  ← НОВОЕ (вместо Агента)
│ Модель (существующий)       │
│ Системный промпт             │
├─────────────────────────────┤
│ Оформление/Стриминг          │
├─────────────────────────────┤
│ Инструменты                  │
└─────────────────────────────┘
```

---

## 12. План Dependency Injection (AppModule)

```kotlin
@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    // === Существующие ===
    @Provides @Singleton
    fun provideSettingsDataStore(@ApplicationContext c: Context): SettingsDataStore

    @Provides @Singleton
    fun provideOkHttpClient(authInterceptor: AuthInterceptor): OkHttpClient

    @Provides @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient, settingsDataStore: SettingsDataStore): Retrofit

    @Provides @Singleton
    fun provideHermesApi(retrofit: Retrofit): HermesApi

    @Provides @Singleton
    fun provideSseClient(): SseClient

    @Provides @Singleton
    fun provideAppDatabase(@ApplicationContext c: Context): AppDatabase

    // === NEW ===
    @Provides @Singleton
    fun provideConnectivityManager(@ApplicationContext c: Context): ConnectivityManager

    @Provides @Singleton
    fun provideUrlProvider(
        connectivityManager: ConnectivityManager,
        settingsDataStore: SettingsDataStore
    ): UrlProvider

    @Provides @Singleton
    fun provideAudioStreamClient(
        okHttpClient: OkHttpClient,
        urlProvider: UrlProvider
    ): AudioStreamClient

    @Provides @Singleton
    fun provideAudioRecorder(@ApplicationContext c: Context): AudioRecorder

    @Provides @Singleton
    fun provideAudioPlayer(@ApplicationContext c: Context): AudioPlayer

    @Provides @Singleton
    fun provideAudioManager(
        audioRecorder: AudioRecorder,
        audioPlayer: AudioPlayer,
        audioStreamClient: AudioStreamClient,
        connectivityManager: ConnectivityManager,
        @ApplicationContext c: Context
    ): AudioManager
}
```

---

## 13. Новые DTO для аудио

**Файл:** `data/remote/dto/AudioRequest.kt`

```kotlin
@JsonClass(generateAdapter = true)
data class AudioSttRequest(
    @Json(name = "model") val model: String = "whisper-1",
    @Json(name = "language") val language: String = "ru"
)
```

**Файл:** `data/remote/dto/TtsResponse.kt`

```kotlin
// TTS-ответ не требует специального DTO — это бинарный Opus-поток
// Но метаданные:
@JsonClass(generateAdapter = true)
data class TtsMetadata(
    @Json(name = "format") val format: String = "opus",
    @Json(name = "sample_rate") val sampleRate: Int = 48000,
    @Json(name = "channels") val channels: Int = 1
)
```

---

## 14. Новые зависимости в build.gradle.kts

```kotlin
dependencies {
    // ... существующие ...

    // ExoPlayer (для TTS-воспроизведения)
    implementation("androidx.media3:media3-exoplayer:1.3.1")
    implementation("androidx.media3:media3-exoplayer-hls:1.3.1")

    // Opus codec (JNI wrapper)
    implementation("com.github.theeze:opuscodec:1.0.0")

    // Или альтернативно — через Oboe
    // implementation("com.google.oboe:oboe:1.7.0")

    // Connectivity (уже есть в SDK 26+, но для обратной совместимости)
    // Не требует отдельных зависимостей — ConnectivityManager встроен в Android SDK
}
```

---

## 15. Резюме: карта изменений по слоям

| Слой | Файл | Действие |
|------|------|----------|
| **Data/Settings** | `SettingsDataStore.kt` | ✏️ Убрать BackendMode, openCode*/apiKey; добавить primaryUrl, fallbackUrl, selectedPersonaId |
| **Data/Settings** | `AppSettings` | ✏️ Убрать backendMode, openCodeApiUrl, openCodeApiKey; добавить persona поля |
| **Data/Settings** | `SettingsRepository.kt` | ✏️ Убрать H/OC+ методы, добавить updatePersonaId, updateUrls |
| **Data/Remote** | `AuthInterceptor.kt` | ✏️ Переписать на UrlProvider вместо H/OC+ ветвления |
| **Data/Remote** | `HermesApi.kt` | ✏️ Добавить stt/tts эндпоинты |
| **Data/Remote** | `AudioStreamClient.kt` | 🆕 |
| **Data/Remote** | `SseClient.kt` | Без изменений |
| **Data/Remote/DTO** | `AudioRequest.kt`, `TtsResponse.kt` | 🆕 |
| **Data/Local** | `ConversationEntity.kt` | ✏️ Убрать backendMode |
| **Data/Local** | `ConversationDao.kt` | ✏️ Убрать getConversationsByMode |
| **Data/Repository** | `ChatRepository.kt` | ✏️ Добавить streamAudioConversation() |
| **Data/Repository** | `DialogRepository.kt` | ✏️ Убрать backendMode из createConversation |
| **Data/Connectivity** | `ConnectivityManager.kt`, `UrlProvider.kt` | 🆕 |
| **Domain/Audio** | `AudioManager.kt`, `AudioRecorder.kt`, `AudioPlayer.kt`, `OpusEncoder.kt`, `OpusDecoder.kt` | 🆕 |
| **Domain/Model** | `Persona.kt` | 🆕 |
| **Domain/Model** | `Conversation.kt` | ✏️ Убрать backendMode |
| **UI/Chat** | `ChatViewModel.kt` | ✏️ Убрать backendMode, добавить voice + persona |
| **UI/Chat** | `ChatUiState.kt` | ✏️ Добавить voiceCallState, убрать showModelSelector/showAgentSelector |
| **UI/Chat/Components** | `ChatInputBar.kt` | ✏️ Добавить VoiceCallButton |
| **UI/Chat/Components** | `PersonaSelector.kt` | 🆕 |
| **UI/Chat/Components** | `VoiceCallButton.kt` | 🆕 |
| **UI/Chat/Components** | `AgentSelector.kt` | 🗑️ Удалить |
| **UI/Chat/Components** | `ModelSelector.kt` | ✏️ Переписать без BackendMode-зависимости |
| **UI/Navigation** | `BottomToolbar.kt` | 🆕 (вынесен из NavGraph) |
| **UI/Navigation** | `NavGraph.kt` | ✏️ Заменить H/OC+ на PersonaSelector, добавить VoiceCallScreen |
| **UI/Navigation** | `Screen.kt` | ✏️ Добавить VoiceCall |
| **UI/Settings** | `SettingsViewModel.kt` | ✏️ Убрать H/OC+, добавить personaId, urls |
| **UI/Settings** | `SettingsScreen.kt` | ✏️ Одна секция URL вместо двух, добавить PersonaSelector |
| **UI/Voice** | `VoiceCallScreen.kt`, `VoiceCallViewModel.kt` | 🆕 |
| **DI** | `AppModule.kt` | ✏️ Добавить провайдеры для новых компонентов |
| **Util** | `Constants.kt` | ✏️ Заменить H/OC+ агентов на 15 PERSONAS |
| **Util** | `NetworkUtil.kt` | 🆕 |
| **Build** | `build.gradle.kts` | ✏️ Добавить ExoPlayer, Opus зависимости |

**Условные обозначения:** 🆕 новый файл | ✏️ изменить | 🗑️ удалить

---

*Конец архитектурного документа Phase 4.*
