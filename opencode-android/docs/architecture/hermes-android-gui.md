# Architecture: Hermes Android GUI
**Requirements:** [docs/requirements/hermes-android-gui.md](../requirements/hermes-android-gui.md)
**Research:** [docs/research/hermes-android-gui.md](../research/hermes-android-gui.md)
**Date:** 2026-06-12

---

## 1. Architectural Decision Records

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-1 | **MVVM + Clean Architecture** | Separation of concerns, testability, Compose-idiomatic |
| ADR-2 | **Single-module (app only)** | MVP simplicity, avoids multi-module build complexity |
| ADR-3 | **Jetpack Compose + Material 3** | Modern declarative UI, first-class Android support |
| ADR-4 | **Hilt for DI** | Official Android DI, integrates with ViewModel/Compose |
| ADR-5 | **Retrofit + OkHttp** | Industry standard for Android HTTP |
| ADR-6 | **Room for persistence** | Official Android SQLite wrapper, Flow support |
| ADR-7 | **DataStore for settings** | Modern replacement for SharedPreferences |
| ADR-8 | **Kotlin Coroutines + Flow** | Structured concurrency, reactive streams |
| ADR-9 | **Coil for avatars/images** | Lightweight image loading |
| ADR-10 | **No WebView dependency** | Native Compose only, smaller APK |

---

## 2. Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Compose UI Screens                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │   │
│  │  │ChatScreen│ │DialogList│ │SettingsScreen    │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │   │
│  │       │            │               │              │   │
│  │  ┌────┴────────────┴───────────────┴──────────┐   │   │
│  │  │          ViewModels (StateFlow)             │   │   │
│  │  │  ChatVM  │  DialogListVM  │  SettingsVM    │   │   │
│  │  └────┬─────┴───────┬────────┴───────┬────────┘   │   │
│  └───────┼─────────────┼────────────────┼────────────┘   │
├──────────┼─────────────┼────────────────┼────────────────┤
│          │     DOMAIN LAYER             │                │
│  ┌───────┴─────────────┴────────────────┴────────────┐  │
│  │  UseCases / Repositories (interfaces only)         │  │
│  │  ChatUseCase │ DialogUseCase │ SettingsUseCase    │  │
│  └───────┬─────────────┬────────────────┬────────────┘  │
├──────────┼─────────────┼────────────────┼────────────────┤
│          │       DATA LAYER               │               │
│  ┌───────┴──────┐ ┌────┴──────┐ ┌───────┴───────┐      │
│  │ HermesApi    │ │ Room DB   │ │ DataStore    │      │
│  │ (Retrofit)   │ │ (SQLite)  │ │ (Settings)   │      │
│  └──────────────┘ └───────────┘ └──────────────┘      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Package Structure

```
com.hermes.gui/
├── HermesApp.kt                    # Application class, Hilt entry
├── MainActivity.kt                 # Single Activity, Compose host
├── di/                             # Dependency Injection
│   ├── AppModule.kt               # Singletons: OkHttp, Retrofit, Room, DataStore
│   └── RepositoryModule.kt        # Repository bindings
├── data/
│   ├── remote/
│   │   ├── HermesApi.kt           # Retrofit interface
│   │   ├── SseClient.kt           # SSE streaming parser
│   │   ├── dto/                   # API request/response DTOs
│   │   │   ├── ChatRequest.kt
│   │   │   ├── ChatResponse.kt
│   │   │   ├── ModelDto.kt
│   │   │   ├── ToolsetDto.kt
│   │   │   └── SessionDto.kt
│   │   └── interceptor/
│   │       └── AuthInterceptor.kt # Bearer token injection
│   ├── local/
│   │   ├── AppDatabase.kt        # Room database
│   │   ├── dao/
│   │   │   ├── ConversationDao.kt
│   │   │   └── MessageDao.kt
│   │   └── entity/
│   │       ├── ConversationEntity.kt
│   │       └── MessageEntity.kt
│   ├── settings/
│   │   └── SettingsDataStore.kt   # Encrypted preferences
│   └── repository/
│       ├── ChatRepository.kt
│       ├── DialogRepository.kt
│       ├── SettingsRepository.kt
│       └── ToolRepository.kt
├── domain/
│   ├── model/
│   │   ├── Conversation.kt
│   │   ├── Message.kt
│   │   ├── ModelInfo.kt
│   │   ├── Toolset.kt
│   │   └── AppSettings.kt
│   └── usecase/
│       ├── SendMessageUseCase.kt
│       ├── StreamMessageUseCase.kt
│       ├── ManageDialogUseCase.kt
│       └── ExecuteTerminalUseCase.kt
├── ui/
│   ├── theme/
│   │   ├── Theme.kt
│   │   ├── Color.kt
│   │   └── Type.kt
│   ├── navigation/
│   │   ├── NavGraph.kt
│   │   └── Screen.kt
│   ├── chat/
│   │   ├── ChatScreen.kt
│   │   ├── ChatViewModel.kt
│   │   ├── ChatUiState.kt
│   │   └── components/
│   │       ├── MessageBubble.kt
│   │       ├── ChatInputBar.kt
│   │       ├── ModelSelector.kt
│   │       ├── AgentSelector.kt
│   │       ├── ToolProgressCard.kt
│   │       └── TerminalConfirmDialog.kt
│   ├── dialogs/
│   │   ├── DialogListScreen.kt
│   │   ├── DialogListViewModel.kt
│   │   └── components/
│   │       └── DialogItem.kt
│   └── settings/
│       ├── SettingsScreen.kt
│       ├── SettingsViewModel.kt
│       └── components/
│           ├── ApiSettingsSection.kt
│           ├── ToolSettingsSection.kt
│           ├── AppearanceSection.kt
│           └── ModelSettingsSection.kt
└── util/
    ├── MarkdownRenderer.kt
    ├── DateFormatter.kt
    └── Constants.kt
```

---

## 4. Database Schema (Room)

### ConversationEntity
```kotlin
@Entity(tableName = "conversations")
data class ConversationEntity(
    @PrimaryKey val id: String,          // UUID
    val title: String,                    // Auto-generated or manual
    val modelId: String,                  // e.g. "deepseek-v4-pro"
    val agentId: String,                  // e.g. "default", "technical"
    val systemPrompt: String?,            // Custom system prompt
    val sessionId: String?,               // Hermes session ID for continuity
    val createdAt: Long,                  // epoch millis
    val updatedAt: Long                   // epoch millis
)
```

### MessageEntity
```kotlin
@Entity(
    tableName = "messages",
    foreignKeys = [ForeignKey(
        entity = ConversationEntity::class,
        parentColumns = ["id"],
        childColumns = ["conversationId"],
        onDelete = ForeignKey.CASCADE
    )],
    indices = [Index("conversationId"), Index("timestamp")]
)
data class MessageEntity(
    @PrimaryKey val id: String,           // UUID
    val conversationId: String,           // FK → conversations
    val role: String,                     // "user" | "assistant" | "system" | "tool"
    val content: String,                  // Markdown text
    val toolCallsJson: String?,           // JSON array of tool calls
    val toolResultsJson: String?,         // JSON array of tool results
    val timestamp: Long,                  // epoch millis
    val tokenCount: Int?                  // Approximate token count
)
```

---

## 5. API Contract (Retrofit Interface)

```kotlin
interface HermesApi {
    @GET("health")
    suspend fun health(): HealthResponse

    @GET("v1/models")
    suspend fun getModels(): ModelsResponse

    @GET("v1/toolsets")
    suspend fun getToolsets(): ToolsetsResponse

    @GET("v1/capabilities")
    suspend fun getCapabilities(): CapabilitiesResponse

    @POST("v1/chat/completions")
    suspend fun chatCompletion(@Body request: ChatRequest): ChatResponse

    @POST("v1/chat/completions")
    @Streaming
    fun chatCompletionStream(@Body request: ChatRequest): ResponseBody

    // Session management
    @GET("api/sessions")
    suspend fun listSessions(@Query("limit") limit: Int = 50): SessionsResponse

    @POST("api/sessions")
    suspend fun createSession(@Body request: CreateSessionRequest): SessionResponse

    @GET("api/sessions/{id}/messages")
    suspend fun getSessionMessages(@Path("id") sessionId: String): MessagesResponse

    @DELETE("api/sessions/{id}")
    suspend fun deleteSession(@Path("id") sessionId: String)
}
```

---

## 6. Navigation Graph

```
NavHost(startDestination = "chat")
├── chat/{conversationId?}          # ChatScreen
│   └── BottomSheet: ModelSelector
│   └── BottomSheet: AgentSelector
│   └── Dialog: TerminalConfirmDialog
├── dialogs                          # DialogListScreen
└── settings                         # SettingsScreen
```

---

## 7. Data Flow — Streaming Chat

```
User types message
  │
  ▼
ChatScreen → ChatViewModel.sendMessage(text)
  │
  ▼
ChatViewModel:
  1. Save user message to Room (MessageEntity)
  2. Launch coroutine
  3. Call ChatRepository.streamMessage(conversation, messages)
  │
  ▼
ChatRepository:
  1. Build ChatRequest (model, messages, tools, stream=true)
  2. Call HermesApi.chatCompletionStream(request)
  3. Return Flow<SseEvent>
  │
  ▼
SseClient.parse(response.body):
  1. Read line-by-line from body.source()
  2. Parse "data: {...}" lines as JSON
  3. Emit SseEvent.Content(text) or SseEvent.ToolProgress(...)
  │
  ▼
ChatViewModel collects Flow:
  - SseEvent.Content → append to ChatUiState.streamingContent
  - SseEvent.ToolProgress → update ChatUiState.toolProgress
  - SseEvent.Done → finalize, save assistant message to Room
  │
  ▼
ChatScreen recomposes with ChatUiState changes
```

---

## 8. Security Architecture

| Concern | Implementation |
|---------|---------------|
| API Key storage | EncryptedSharedPreferences (Android Keystore) |
| Network | TLS pinning via OkHttp CertificatePinner |
| Code execution | Confirmation dialog before terminal commands |
| Input sanitization | Content validation, max length limits |
| Secure by default | No logs of API keys or message content in release |

---

## 9. Technology Stack

| Component | Library | Version |
|-----------|---------|---------|
| Language | Kotlin | 1.9.22 |
| Build | Gradle KTS | 8.2 |
| Compose BOM | androidx.compose | 2024.02 |
| Navigation | Navigation Compose | 2.7.7 |
| DI | Hilt | 2.50 |
| Network | Retrofit + OkHttp | 2.9.0 + 4.12.0 |
| JSON | Moshi / kotlinx.serialization | 1.15 / 1.6.2 |
| DB | Room | 2.6.1 |
| Settings | DataStore | 1.0.0 |
| Encryption | security-crypto | 1.1.0-alpha06 |
| Image | Coil Compose | 2.5.0 |
| Testing | JUnit5, MockK, Turbine | latest |

---

## 10. Theme & Design Tokens

- Material 3 Dynamic Color (Material You)
- Dark/Light/System theme
- Typography: System default with monospace for code blocks
- Spacing: 8dp grid system
- Corner radius: 16dp for message bubbles
- Animation: shared element transitions, typing indicator dots
