# Sharing Sessions as Mobile-Readable Dialogs

When you've produced research or analysis in a Hermes session and want User to read it in the Android app as a standalone dialog, inject it into `state.db` as a new session.

## Why state.db injection

The Android app reads session lists from `state.db` (via Hermes API). New sessions appear immediately — no API calls, no file transfers. Just a SQLite INSERT and the app picks them up on next refresh.

## Step-by-step

### 1. Find source session(s)

Use `session_search` to locate the sessions whose messages you want to share:

```bash
sqlite3 ~/.hermes/state.db "SELECT id, title, message_count FROM sessions WHERE id IN ('id1', 'id2')"
```

### 2. Insert as new sessions

```python
import sqlite3, time, random, string

db = sqlite3.connect("/home/user/.hermes/state.db")

old_sessions = [
    ("OLD_ID_HERE", "Desired Display Title"),
    # ... more sessions
]

ts = time.time()
for old_id, title in old_sessions:
    # CRITICAL: titles must be UNIQUE (see Pitfalls below)
    title = f"📱 {title}"  # prefix ensures uniqueness
    
    suffix = ''.join(random.choices(string.hexdigits.lower(), k=6))
    date_part = time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
    new_id = f"{date_part}_{suffix}"
    ts += 1
    
    # Get metadata from original
    old = db.execute("SELECT model, cwd FROM sessions WHERE id=?", (old_id,)).fetchone()
    model, cwd = old if old else ("deepseek-v4-pro", "/home/user")
    
    # Create session record
    db.execute("""
        INSERT INTO sessions (id, source, model, started_at, message_count,
            tool_call_count, input_tokens, output_tokens, title, cwd)
        VALUES (?, 'import', ?, ?, 0, 0, 0, 0, ?, ?)
    """, (new_id, model, ts, title, cwd))
    
    # Copy messages (user-visible content only)
    messages = db.execute("""
        SELECT role, content, tool_calls, tool_name, timestamp, token_count,
               finish_reason, reasoning, reasoning_content
        FROM messages WHERE session_id=? AND active=1 ORDER BY id
    """, (old_id,)).fetchall()
    
    count = 0
    for msg in messages:
        role, content, tool_calls, tool_name, msg_ts, t_count, finish, reason, reason_content = msg
        db.execute("""
            INSERT INTO messages (session_id, role, content, tool_calls, tool_name,
                timestamp, token_count, finish_reason, reasoning, reasoning_content, observed, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
        """, (new_id, role, content, tool_calls, tool_name, msg_ts, t_count, finish, reason, reason_content))
        count += 1
    
    db.execute("UPDATE sessions SET message_count=? WHERE id=?", (count, new_id))

db.commit()
db.close()
```

### 3. Verify

```bash
hermes sessions list | grep "📱"
```

### 4. On the phone

Restart the app (swipe away + reopen) — it re-reads the session list from state.db and the new dialogs appear.

## Pitfalls

### UNIQUE INDEX on sessions(title)

```sql
CREATE UNIQUE INDEX idx_sessions_title_unique ON sessions(title) WHERE title IS NOT NULL;
```

**Duplicate titles cause `IntegrityError`.** Always make titles unique. The `📱 ` prefix is the convention used for mobile-shared sessions. If two shared sessions would have the same base title, append `(imported)` or a short disambiguator.

### Source tag 'import'

Use `source='import'` to distinguish injected sessions from normal ones. This allows bulk cleanup:

```bash
sqlite3 ~/.hermes/state.db "DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE source='import')"
sqlite3 ~/.hermes/state.db "DELETE FROM sessions WHERE source='import'"
```

### App restart required

The Android app caches the session list. New state.db entries won't appear until the app process restarts (swipe away + reopen).

### Exclude tool-call-only messages

The read view in the app skips messages with `role='tool'` and empty `content`. The injection script above copies ALL active messages. If you want a cleaner read, filter to `role IN ('user', 'assistant') AND content IS NOT NULL AND content != ''`.
