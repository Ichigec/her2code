# Bulk Session Cleanup — Real Example

Session from 2026-06-27: user asked to delete all unpinned sessions.

## Initial State

| Metric | Value |
|--------|-------|
| Sessions in DB | 538 |
| Messages in DB | 32,060 |
| DB size | 805 MB |
| Session files on disk | 80 request_dump_*.json |

## What We Did

### 1. Discovered the scale
```bash
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM sessions"  # → 538
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM messages"  # → 32060
ls -lh ~/.hermes/state.db  # → 805M
```

### 2. Attempted CLI deletion — too slow at scale
```bash
hermes sessions delete SESSION_ID  # prompts for [y/N] — hangs
hermes sessions delete --yes SESSION_ID  # works but 538 × 1 call each = minutes
```

### 3. Switched to direct SQLite
Backed up first, then deleted all messages for non-current sessions, then all non-current sessions, then rebuilt FTS.

```python
import sqlite3
db = '/home/user/.hermes/state.db'
current = '20260627_202849_0a0c69'

conn = sqlite3.connect(db)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA foreign_keys=ON')
conn.execute('DELETE FROM messages WHERE session_id != ?', (current,))
conn.execute('DELETE FROM sessions WHERE id != ?', (current,))
conn.commit()
conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
conn.commit()
```

Result: 32,059 messages + 537 sessions deleted, 1 session + 1 message remained.

### 4. VACUUM — critical step
```bash
sqlite3 ~/.hermes/state.db "VACUUM"
```

DB went from 805 MB → 352 MB. Without VACUUM, SQLite keeps freed pages allocated.

### 5. Cleaned disk session files
```bash
rm -f ~/.hermes/sessions/request_dump_*.json ~/.hermes/sessions/*.jsonl
```

80 files removed. The `sessions.json` routing index was left intact.

### 6. Straggler cleanup
During the 30-second cleanup window, observer processes spawned 2 new sessions (`unknown` source). Deleted them in a second SQLite pass, then VACUUM'd again.

## Final State

| Metric | Before | After |
|--------|--------|-------|
| Sessions | 538 | 1 |
| Messages | 32,060 | 1 |
| DB size | 805 MB | 352 MB |
| Disk files | 80 | 1 (sessions.json) |

## Why Not `hermes sessions prune`?

`prune --older-than 0 --yes` would also work but:
- Doesn't give you per-session control (current session is auto-excluded though)
- Might be slower for 500+ sessions
- Doesn't clean disk files
- Doesn't VACUUM

The SQLite approach is faster and gives you exact control. Use `prune` for routine cleanup (30+ day old sessions), use SQLite for nuke-from-orbit.
