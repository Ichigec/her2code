# Observer Cascade — 2026-06-27 Incident

## Root Cause

`plugins/observer-hook/__init__.py` called `_spawn_observer_worker(sid)` on every `post_llm_call` (line 133-134). Each worker spawned 4 `hermes -z` observer subagents, each creating a new session. Observer sessions themselves triggered the hook → cascade.

## Timeline

- **2026-06-27 00:25** — `observer-hook/__init__.py` created with per-turn worker spawn
- **2026-06-27 00:19-00:39** — 232 sessions created in 20 minutes
  - 107 observer CLI sessions (observer subagents each creating sessions)
  - 102 unknown-source 0-message sessions (from `update_token_counters` backfill)
  - 1 real TUI session
- **00:37** — User notices "почему плодиться млн сессий?"
- **00:38** — Diagnosis complete: cascade identified
- **00:39** — Fix applied, processes killed, garbage cleaned

## Cascade Mechanism

```
Session A (real user session)
  → post_llm_call (turn 1)
    → _spawn_observer_worker(sid_A)
      → observer_worker.py --session-id sid_A
        → hermes -z "auditor observer..." → creates Session B1
        → hermes -z "critic observer..."   → creates Session B2
        → hermes -z "idea-generator..."    → creates Session B3
        → hermes -z "knowledge-curator..." → creates Session B4
          → Each B session triggers on_session_start hook
            → post_llm_call on B1
              → _spawn_observer_worker(sid_B1)  ← CASCADE
                → 4 more sessions...
```

The lock file mechanism (`/tmp/hermes_observer_locks/observer_<sid>.lock`) prevents duplicate processing for the SAME session ID, but each observer subagent gets a NEW session ID, so no lock blocks the cascade.

## Impact

```
state.db: 773 MB (before cleanup)
Sessions: 879 total, 209 garbage (107 observer-cli + 102 unknown)
Running processes: 24 hermes -z + 8 observer_worker.py
CPU/Memory: ~24 deepseek-v4-pro inference processes running simultaneously
```

## Fix Applied

### 1. Removed worker spawn from post_llm_call (plugins/observer-hook/__init__.py)

```diff
-    # Fire-and-forget spawn observer worker (lock prevents duplicates)
-    _spawn_observer_worker(sid)
-
```

### 2. Added cascade guard (_is_observer_session)

```python
OBSERVER_AGENT_NAMES = {"auditor", "critic", "idea-generator", "knowledge-curator"}

def _is_observer_session(kwargs: dict) -> bool:
    preset = str(kwargs.get("agent_prompt_label", kwargs.get("agent_preset", ""))).lower()
    if any(name in preset for name in OBSERVER_AGENT_NAMES):
        return True
    sp = str(kwargs.get("system_prompt", kwargs.get("system_message", "")))
    if any(f"{name} observer" in sp.lower() or f"agents/{name}.md" in sp.lower()
           for name in OBSERVER_AGENT_NAMES):
        return True
    return False
```

Applied to `on_session_start`, `post_llm_call`, and `on_session_end` — all return early if session is an observer subagent.

### 3. Removed fallback cron job

```bash
# Removed cron job c4e543ccefb2 (observer-worker-fallback, every 10m)
```

## Cleanup Commands

```bash
# Kill all observer processes
ps aux | grep -E "hermes.*observer|observer_worker" | grep -v grep | awk '{print $2}' | xargs kill

# Delete garbage sessions from state.db
sqlite3 ~/.hermes/state.db "
CREATE TEMP TABLE garbage AS
SELECT id FROM sessions WHERE source='cli' AND system_prompt LIKE '%observer%'
UNION SELECT id FROM sessions WHERE source='unknown' AND message_count=0;
DELETE FROM messages WHERE session_id IN (SELECT id FROM garbage);
DELETE FROM sessions WHERE id IN (SELECT id FROM garbage);
DROP TABLE garbage;
VACUUM;
"

# Clean Neo4j
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (t:ObserverTask) WHERE t.status = '\''queued'\'' DETACH DELETE t"}]}' \
  http://127.0.0.1:7474/db/neo4j/tx/commit

# Clean queue and locks
echo "" > ~/.hermes/observer_queue.jsonl
rm -f /tmp/hermes_observer_locks/observer_*.lock
```

## Verification

After fix:
- 0 observer processes running
- 670 sessions in state.db (down from 879)
- 742 MB state.db (down from 773 MB after VACUUM)
- No new garbage sessions being created
- Observer hook skips observer subagent sessions via `_is_observer_session()` guard

## v3 Follow-up (Same Day)

The cascade exposed a deeper architectural flaw: per-turn observer spawning is wrong regardless of cascade. Observers should analyze the FULL session arc, not individual LLM responses.

**v3 redesign (implemented 2026-06-27, ~00:45):**

| Aspect | v2 (broken) | v3 (fixed) |
|--------|------------|-----------|
| Trigger | `post_llm_call` (every turn) | `on_session_end` only |
| Queue | Neo4j + JSONL per turn | None (just count turns) |
| Worker spawn | Per turn (cascade!) | Once per session if meaningful |
| Context | Sparse (preset + turns) | Rich JSON: msgs, tools, tokens, preset, platform |
| Activity gate | None (every session) | Skip if msgs<5 AND tools<2 AND tok<5K |
| Observer prompt | Per-turn analysis | Full session arc (goal→errors→patterns→ideas) |

**Files changed:**
- `plugins/observer-hook/__init__.py` — v2 → v3 (activity gate, context-rich spawn)
- `scripts/observer_worker.py` — v2 → v3 (`--context-file`, rich prompts)
