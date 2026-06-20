# Critical Bug: collectedContent.clear() Race

## Symptom
TTS never plays. No VoiceRepo TTS logs. Text response appears, but voice output is silently skipped. Voice mode stops after response.

## Root Cause
In the SSE `Done` handler, `finalizeMessage()` calls `collectedContent.clear()`. If the response text is read AFTER clear(), it's empty:

```
06-13 01:47:29 SSE: [DONE] received
// finalizeMessage() — clears collectedContent
// collectedContent.toString() — EMPTY STRING
// content.isNotBlank() — FALSE
// synthesizeAndPlay() — NEVER CALLED
```

## Fix
Save `collectedContent.toString()` to a local variable BEFORE calling `finalizeMessage()`:

```kotlin
is SseEvent.Done -> {
    val responseText = collectedContent.toString()  // SAVE FIRST
    finalizeMessage(conversationId)                  // THEN clear
    if (autoRestartVoice && responseText.isNotBlank()) {
        viewModelScope.launch { synthesizeAndPlay(responseText) }
    }
}
```

## Verification Logs (working)
```
VoiceRepo: TTS: requesting '<response text>'
VoiceRepo: TTS: response 200, body size=25054
VoiceRepo: TTS: got 25054 bytes, playing...
VoiceRepo: TTS done
```
