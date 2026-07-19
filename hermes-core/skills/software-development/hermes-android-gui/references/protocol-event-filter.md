# Filtering OpenCode Protocol Events from SSE Content

OpenCode API sometimes leaks internal protocol events (`step_start`, `session_start`, `sessionID:ses_`) into SSE `choices[0].delta.content` character-by-character. These appear as raw JSON blobs in chat.

## Correct approach: SseClient buffer filter (WORKS)

The filter must live **inside SseClient.parseStream()**, between JSON parsing and `emit()`. Characters arrive one at a time via `delta.content`. Buffer them, track brace depth with string/escape awareness, and check completed JSON objects.

```kotlin
// State vars in parseStream() — persist across data: lines
val contentBuf = StringBuilder()
var inJson = false
var braceDepth = 0
var inString = false
var escaped = false

// Inside delta?.content branch:
for (ch in text) {
    if (inJson) {
        contentBuf.append(ch)
        if (escaped) { escaped = false; continue }
        when {
            ch == '\\' -> escaped = true
            ch == '"' -> inString = !inString
            !inString && ch == '{' -> braceDepth++
            !inString && ch == '}' -> braceDepth--
        }
        if (braceDepth == 0 && !inString) {
            val json = contentBuf.toString()
            inJson = false; contentBuf.clear()
            if (!isProtocolEvent(json)) {
                emit(SseEvent.Content(json))
            }
        }
    } else if (ch == '{') {
        inJson = true; braceDepth = 1
        inString = false; escaped = false
        contentBuf.clear(); contentBuf.append(ch)
    } else {
        emit(SseEvent.Content(ch.toString()))
    }
}

fun isProtocolEvent(json: String): Boolean =
    json.contains("\"type\":\"step_start\"") ||
    json.contains("\"sessionID\":\"ses_") ||
    json.contains("\"type\":\"step-start\"")
```

**Flush on [DONE]:** if buffer has residual content when stream ends, emit it as text.

## Why NOT filter in ChatViewModel (FAILS)

The `filterProtocolJson()` approach in ChatViewModel **removes ALL content** when the entire response is protocol JSON (250 chars of step_start → filter strips everything → `content.isNotBlank()` is false → message never saved → user sees nothing).

The protocol JSON is up to 250 characters. Removing it from the accumulated string leaves an empty string. Better to filter at the source (SseClient) where individual JSON objects can be identified and skipped before they accumulate.

## Why NOT filter in ChatRepository

Too late — content is already mixed with protocol events by the time it reaches the repository layer.

## Key implementation details

- **String tracking:** `inString` mode ignores `{` and `}` inside JSON string values
- **Escape tracking:** `escaped` mode prevents `\"` from toggling `inString`
- **Non-JSON passthrough:** characters outside `{...}` blocks are emitted immediately
- **Resilience:** if filter removes everything, the ChatViewModel `finalizeMessage` naturally skips blank content — user sees no response rather than protocol garbage
