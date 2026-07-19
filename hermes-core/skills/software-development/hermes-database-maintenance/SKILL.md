---
name: hermes-database-maintenance
description: Maintain the Hermes state.db — bulk session cleanup, VACUUM, disk file cleanup, recovering from observer session floods. Use when user asks to delete sessions, clean up the database, or the session list is overgrown.
version: 1.0.0
---

# Hermes Database Maintenance

Bulk session management and state.db maintenance. The `hermes sessions delete` CLI works for one-off deletions but is unusably slow at scale (538 sessions × interactive prompts = minutes). For bulk operations, go direct to SQLite.

## Triggers

- User asks to delete sessions, clean up history, or "удали все сессии"
- `state.db` is large (500MB+) and growing
- Observer/cron session floods — hundreds of near-empty sessions cluttering the sidebar
- After mass deletions — always VACUUM

## Quick Start

```bash
# See what you're dealing with
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM sessions"
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM messages"
ls -lh ~/.hermes/state.db
```

## Bulk Delete All Sessions Except Current

⚠️ **WARNING**: This is a nuclear option. Before proceeding, **always survey titled sessions** — the user may have `/title`-named sessions they consider important. Hermes has no "pin" feature for sessions; titled sessions are the closest proxy. Ask the user or at minimum print the list before deleting.

**Step 0: Survey titled sessions (MANDATORY)**
```bash
sqlite3 ~/.hermes/state.db "SELECT id, title FROM sessions WHERE title IS NOT NULL AND title != '' ORDER BY started_at DESC"
```

**Step 1: Backup**
```bash
cp ~/.hermes/state.db ~/.hermes/state.db.bak.$(date +%Y%m%d_%H%M%S)
```

**Step 2: Delete via SQLite** (current session ID is visible in `hermes sessions list`)

```bash
python3 -c "
import sqlite3
db = '/home/user/.hermes/state.db'
current = 'YYYYMMDD_HHMMSS_xxxxxx'  # replace with actual current session ID

conn = sqlite3.connect(db)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA foreign_keys=ON')

# Messages first (FK constraint)
cur = conn.execute('DELETE FROM messages WHERE session_id != ?', (current,))
print(f'Deleted {cur.rowcount} messages')

# Then sessions
cur = conn.execute('DELETE FROM sessions WHERE id != ?', (current,))
print(f'Deleted {cur.rowcount} sessions')

conn.commit()

# Rebuild FTS indexes
conn.execute(\"INSERT INTO messages_fts(messages_fts) VALUES('rebuild')\")
conn.commit()
conn.close()
print('Done')
"
```

**Step 3: VACUUM to reclaim disk space**
```bash
sqlite3 ~/.hermes/state.db "VACUUM"
```

**Step 4: Clean disk files**
```bash
rm -f ~/.hermes/sessions/request_dump_*.json ~/.hermes/sessions/*.jsonl
```

**Step 5: Verify and re-check for stragglers** — observer/cron processes may spawn new sessions during cleanup. Run a final check:

```bash
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM sessions"
hermes sessions list
```

If stragglers appeared, repeat Step 2 for the new IDs, then VACUUM again.

## Individual Session Deletion (CLI)

For one-offs, use the CLI — but remember `--yes`:

```bash
hermes sessions delete --yes SESSION_ID
```

Without `--yes`, the command prompts for confirmation and hangs in non-interactive contexts.

## Bulk Prune by Age

```bash
hermes sessions prune --older-than 0 --yes   # delete ALL (keeps current)
hermes sessions prune --older-than 30 --yes  # older than 30 days
```

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| `hermes sessions delete` prompts for confirmation | Add `--yes` / `-y` flag |
| DB still large after deleting all sessions | Must run `VACUUM` — SQLite doesn't release freed pages automatically |
| Sessions keep spawning during cleanup | Observer processes or slash_workers are running. Disable BOTH the plugin (`~/.hermes/hermes-agent/plugins/observer-hook/__init__.py`) AND the shell hook (`~/.hermes/hooks/observer-hook/handler.py`) before cleanup. See `session-maintenance` skill for full cascade analysis |
| **User had titled sessions they wanted to keep** | Hermes has no "pin" feature. Titled sessions (`/title`) are the user's equivalent. Always survey `SELECT id, title FROM sessions WHERE title IS NOT NULL` BEFORE bulk deletion. Ask user which to preserve. |
| `DELETE FROM sessions` fails due to FK constraint | Delete `messages` first, then `sessions` |
| `state.db` locked | Hermes uses WAL mode — concurrent reads are fine, but avoid writes while Hermes is mid-turn |
| FTS search broken after bulk delete | Rebuild: `INSERT INTO messages_fts(messages_fts) VALUES('rebuild')` |
| Ghost slash_workers keep running after DB deletion | `ps aux | grep slash_worker` — these are TUI gateway workers tied to old session keys. They survive DB deletion. Kill them with `pkill -f slash_worker` if needed |
| `source='unknown'` ghost sessions | `ensure_session()` defaults to `source="unknown"`. Include in bulk delete: `WHERE source IN ('observer','unknown')` |

## DB Schema Reference

```sql
-- Main tables
sessions(id, source, title, started_at, message_count, archived, ...)
messages(id, session_id, role, content, ...)  -- FK → sessions(id)
messages_fts  -- FTS5 virtual table over messages
```

Key columns: `sessions.archived` (0=active, 1=archived), `sessions.source` (cli, tui, cron, unknown).

## Reference Files

- `references/bulk-session-cleanup.md` — detailed walkthrough with real numbers from a 538→1 session cleanup
- `references/observer-cascade-deep-analysis.md` — full code-level analysis of observer cascade: dual infrastructure (plugin + shell hook), `_is_observer_session()` gaps, ghost sessions with `source='unknown'`, cascade chain diagram, 5 solution variants
- `references/observer-cascade-example.md` — real example of observer cascade in action
- `references/session-crash-diagnostics.md` — investigating silently-crashed sessions (context exhaustion, dead-end probes, recovery)
- See also: `session-maintenance` skill — covers observer cascade root cause analysis, dual observer infrastructure (plugin + shell hook), `_is_observer_session()` gaps, and 5 solution variants with code-level detail
