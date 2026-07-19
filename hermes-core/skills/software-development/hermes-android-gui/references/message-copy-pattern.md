# Long-Press to Copy Messages

Added to `MessageBubble.kt` via Compose `combinedClickable`.

## Implementation

```kotlin
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import android.content.ClipData
import android.content.ClipboardManager
import android.widget.Toast

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun MessageBubble(message: Message, isStreaming: Boolean = false) {
    val context = LocalContext.current

    Surface(
        modifier = Modifier
            .combinedClickable(
                onClick = { },  // normal click — do nothing
                onLongClick = {
                    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    val clip = ClipData.newPlainText("message", message.content)
                    clipboard.setPrimaryClip(clip)
                    Toast.makeText(context, "Скопировано", Toast.LENGTH_SHORT).show()
                }
            ),
        // ... shape, color, content
    )
}
```

## Notes
- `combinedClickable` is in `foundation` (not material3) — requires `@OptIn(ExperimentalFoundationApi::class)`
- Toast is simple and non-intrusive — no need for Snackbar
- Works on both user messages and assistant responses
- `onClick = { }` — empty lambda, no action on normal tap
