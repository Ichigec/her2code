# SSE Retry Pattern for Tunnel Stability

## Problem
Through tunnels (SSH/VPS, serveo, cloudflared), SSE streams break with `java.io.IOException: unexpected end of stream`.
Occurs on EVERY SECOND message because OkHttp reuses connections, but the server closes them (`Connection: close` header).

## Solution: Two-layer retry

### Layer 1: OkHttp retryOnConnectionFailure (AppModule.kt)
```kotlin
OkHttpClient.Builder()
    .retryOnConnectionFailure(true)
    .connectTimeout(30, TimeUnit.SECONDS)
    .readTimeout(120, TimeUnit.SECONDS)
    .writeTimeout(30, TimeUnit.SECONDS)
    .build()
```

### Layer 2: ChatRepository streamMessage retry loop
When SSE parse emits "unexpected end" error, retry up to 2 times with exponential backoff:
- Attempt 0: normal request
- Attempt 1: delay 1s, new call
- Attempt 2: delay 2s, new call → emit error if fails

```kotlin
var attempt = 0
val maxRetries = 2
while (attempt <= maxRetries) {
    if (attempt > 0) delay((1000L * attempt).coerceAtMost(3000L))
    val call = api.chatCompletionStream(request)
    var streamBroken = false
    try {
        val response = withContext(Dispatchers.IO) { call.execute() }
        if (response.isSuccessful) {
            sseClient.parseStream(body).flowOn(Dispatchers.IO).collect { event ->
                if (event is SseEvent.Error) {
                    val msg = event.message ?: ""
                    if (msg.contains("unexpected end") || msg.contains("stream error")) {
                        streamBroken = true
                    } else { emit(event) }
                } else { emit(event) }
            }
            if (streamBroken) { attempt++; continue }
            return@flow  // success
        }
    } catch (e: Exception) { attempt++ }
}
```

### Layer 3: ChatViewModel saves partial content on error
When SSE breaks mid-response, save whatever was collected:
```kotlin
is SseEvent.Error -> {
    val partialText = collectedContent.toString()
    if (partialText.isNotBlank()) finalizeMessage(conversationId)
    _uiState.update { it.copy(isStreaming = false, error = event.message) }
}
```
