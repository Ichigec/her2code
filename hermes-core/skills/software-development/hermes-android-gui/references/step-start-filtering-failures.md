# step_start filtering failures

OpenCode+ API agents generate protocol events (`step_start`) as SSE stream content.
Every attempt to filter them client-side has failed — documented here to prevent re-attempts.

## Attempt 1: Per-chunk string check

```kotlin
// SseClient.kt — check each delta.content for protocol markers
if (delta?.content != null) {
    val text = delta.content
    if (!text.contains("\"type\":\"step_start\"") &&
        !text.contains("\"sessionID\":\"ses_")) {
        emit(SseEvent.Content(text))
    }
}
```

**Result:** Works for single-chunk JSON, but content is streamed character-by-character.
Individual characters like `{`, `"` pass through. Full JSON object never detected.

## Attempt 2: Character-by-character buffer with brace depth

```kotlin
// SseClient.kt — state machine tracking brace depth
val contentBuf = StringBuilder()
var inJson = false
var braceDepth = 0
var inString = false
var escaped = false

for (ch in text) {
    if (inJson) {
        contentBuf.append(ch)
        // ... track braces, strings, escapes
        if (braceDepth == 0 && !inString) {
            val json = contentBuf.toString()
            if (!isProtocolEvent(json)) emit(SseEvent.Content(json))
            // else: skip
        }
    } else if (ch == '{') {
        // start buffering
    } else {
        emit(SseEvent.Content(ch.toString()))
    }
}
```

**Result:** `inJson` gets stuck true when brace depth never reaches 0
(e.g., malformed JSON or `{` inside string without matching `}`).
All subsequent content is swallowed. User sees nothing.

## Attempt 3: filterProtocolJson() in ChatViewModel

```kotlin
// ChatViewModel.kt — strip protocol JSON from accumulated text
private fun filterProtocolJson(text: String): String {
    // find `{...}` objects, skip if contains step_start or sessionID
}
```

**Result:** We confirmed via Python test: 249-char input → 0-char output.
Model outputs ONLY the step_start JSON with no text after it.
Filtering leaves nothing. `responseText.isBlank()` → message never saved.
`responseText length=1` in logs — one remaining char (maybe `\n`).

## Attempt 4: Post-hoc replacement in Done handler

```kotlin
is SseEvent.Done -> {
    val displayText = if (responseText.startsWith("{\"type\":\"step_start\"") &&
        !responseText.contains("\"content\":"))
        "Агент не ответил. Попробуйте ещё раз."
    else responseText
    finalizeMessage(conversationId, displayText)
}
```

**Result:** Works as fallback — shows friendly message when agent produces no text.
But doesn't solve the root problem.

## ROOT CAUSE

OpenCode+ agents output `step_start` as their response content.
This is server-side behavior — the model generates protocol events, not chat text.
Client-side filtering can never fix a response that contains nothing else.

## SOLUTION

Separate backends:
- **H mode**: LiteLLM (clean LLM text, no protocol)
- **OC+ mode**: OpenCode+ agents (accept step_start as valid response)

Unified proxy routes by model name — same URL for both modes.
