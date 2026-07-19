# SSE Retry Pattern for ChattRepository

When the SSH tunnel dies mid-stream, OkHttp throws `IOException: unexpected end of stream`. 
The fix: wrap `streamMessage()` in a retry loop that detects stream errors and reconnects.

## Pattern (ChatRepository.kt)

```kotlin
fun streamMessage(...): Flow<SseEvent> = flow {
    var attempt = 0
    val maxRetries = 2

    while (attempt <= maxRetries) {
        if (attempt > 0) {
            delay((1000L * attempt).coerceAtMost(3000L))  // 1s → 2s backoff
        }

        val call: Call<ResponseBody> = api.chatCompletionStream(request)
        var streamBroken = false

        try {
            val response = withContext(Dispatchers.IO) { call.execute() }
            if (response.isSuccessful) {
                val body = response.body()!!
                sseClient.parseStream(body).flowOn(Dispatchers.IO).collect { event ->
                    if (event is SseEvent.Error) {
                        val msg = event.message ?: ""
                        if (msg.contains("unexpected end") || msg.contains("stream error")) {
                            streamBroken = true  // trigger retry
                        } else {
                            emit(event)  // real error — show to user
                        }
                    } else {
                        emit(event)  // normal content — emit
                    }
                }
                if (streamBroken) { attempt++; continue }
                return@flow  // success
            }
        } catch (e: Exception) {
            if (attempt >= maxRetries) {
                emit(SseEvent.Error("Connection error after retries: ${e.message}"))
            }
            attempt++
        }
    }
}
```

## Related: Save partial content on SSE error (ChatViewModel)

```kotlin
is SseEvent.Error -> {
    val partialText = collectedContent.toString()
    if (partialText.isNotBlank()) {
        finalizeMessage(conversationId)  // save what we got
    }
    _uiState.update { it.copy(isStreaming = false, error = event.message) }
}
```

## Why OkHttp retryOnConnectionFailure is NOT enough

`retryOnConnectionFailure(true)` reconnects for initial HTTP connection failures but does NOT
retry for SSE streaming body failures. The response body is already opened, so OkHttp can't
safely retry without replaying the request body. Application-level retry is required.
