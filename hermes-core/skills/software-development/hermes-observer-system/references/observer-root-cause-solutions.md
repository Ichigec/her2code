# Observer Root Cause Solutions — 2026-06-29 Analysis

Five patterns discovered by observers on 2026-06-29, all from one causal chain:
user asks agent "who am I?" → agent dives into codebase (150K tokens, 0 answers) →
observer tries to analyze → session_search fails → observer dies silently →
meta-observer criticizes observer → no fixes implemented.

## Pattern 1: Agent doesn't know itself (no self-introspection)

**Root**: `apply_agent()` in `agent/agents.py:653-723` mutates AIAgent fields but
the LLM never sees these metadata in system prompt.

**Fix**: Identity injection block in `apply_agent()` after line 713:

```python
# agent/agents.py — insert after line 713 (after ephemeral_system_prompt set)

_identity = [
    "[Agent Identity]",
    f"Active preset: {agent_def.label or agent_def.id}",
    f"Preset ID: {agent_def.id}",
    f"Toolsets: {', '.join(agent_def.toolsets) if agent_def.toolsets else 'default'}",
    f"Reasoning: {agent_def.reasoning or 'default'}",
]
if agent_def.model:
    _identity.append(f"Model: {agent_def.model}")
if hasattr(agent_obj, 'platform'):
    _identity.append(f"Platform: {agent_obj.platform or 'unknown'}")
if hasattr(agent_obj, 'session_id'):
    _identity.append(f"Session: {agent_obj.session_id}")

_identity_block = "\n".join(_identity) + "\n\n"
existing = agent_obj.ephemeral_system_prompt or ""
agent_obj.ephemeral_system_prompt = _identity_block + existing
```

**Effect**: ~15 lines, 0 new dependencies. Agent instantly answers self-referential
questions from system prompt — no codebase reads needed.

---

## Pattern 2: Observers die silently (no graceful degradation)

**Root**: `conversation_loop.py:4871-4900` — deep observer prompt has no fallback
instruction. Observer hits truncated data and loops 3 times → dies silently.
`except Exception: pass` swallows all failures.

**Fix A — Prompt fallback contract** (conversation_loop.py:4871, prepend to goal):

```
CRITICAL: If session_search fails after 2 attempts with different approaches,
DO NOT EXIT SILENTLY. Instead, produce exactly ONE observation:
'⚠ Observer failure: unable to read session — [error type]. Partial analysis unavailable.'
This ensures failures are visible rather than silent.
```

**Fix B — Runtime watchdog** (conversation_loop.py, after line 4900):

```python
# After deep observer block — log own failure to Neo4j
if _should_deep and (not results or results[0].get("status") != "completed"):
    from datetime import datetime, timezone
    from agent.observer import _write
    _write(
        "CREATE (f:AuditFinding {session_id:$sid, phase:$phase, severity:$sev, "
        "finding:$finding, recommendation:$rec, timestamp:$ts})",
        {"sid": sid, "phase": "observer-self-check", "sev": "HIGH",
         "finding": f"Deep observer on turn {_obs_turn} produced ZERO output",
         "rec": "Investigate session_search output for this session",
         "ts": datetime.now(timezone.utc).isoformat()}
    )
```

---

## Pattern 3: session_search breaks observers (3 bugs)

### Bug A: Truncation without pagination

**File**: `tools/session_search_tool.py:177-223` (`_read_session`)

**Fix**: Add `offset`/`limit` to `_read_session`:

```python
def _read_session(db, session_id: str, head: int = 20, tail: int = 10,
                  offset: int = 0, limit: int = None) -> str:
    ...
    if offset > 0 or limit is not None:
        start = max(0, offset)
        end = start + (limit or 50) if limit is not None else total
        window = shaped[start:end]
        truncated = end < total
    else:
        truncated = total > head + tail
        window = shaped[:head] + shaped[-tail:] if truncated else shaped
    ...
```

Expose via `session_search()` at line 564 — extract `offset`/`limit` from kwargs.

### Bug B: Lineage rejection blocks observer scrolls

**File**: `tools/session_search_tool.py:301-308` (`_scroll`)

**Fix**: Skip lineage check for observer sessions:

```python
# Line 301 — wrap existing check
if current_session_id:
    current_meta = db.get_session(current_session_id) or {}
    if current_meta.get("source") != "observer":
        a_root = _resolve_to_parent(db, session_id)
        c_root = _resolve_to_parent(db, current_session_id)
        if a_root and c_root and a_root == c_root:
            return tool_error("scroll rejected...", success=False)
```

### Bug C: Message ID confusion across sessions

**File**: `tools/session_search_tool.py` — `_shape_message()` function

**Fix**: Add `_session_id` to every shaped message:

```python
if session_id:
    shaped["_session_id"] = session_id
```

---

## Pattern 4: Asymmetric agent switching (partially fixed)

**Status**: Desktop (`desktop-controller.tsx:264`) already uses `agents.activate` RPC.
REST API (`api_server.py:1037`) already accepts `agent_id`. Finding is partially stale.

**Remaining fixes**:

A. Update stale comment at `desktop-controller.tsx:249-252`
B. Persist `$activeAgentPresetId` via `persistentAtom` in `store/session.ts`
C. Document `agent_id` in REST API schema

---

## Pattern 5: Fix gap (63 proposals → 2 implementations)

**Root**: Mutations stored in Neo4j, no process to execute them.

**Fix**: Weekly Mutation Review cron:

```bash
hermes cron create \
  --name "observer-mutation-review" \
  --schedule "0 10 * * 0" \
  --prompt "Query Neo4j for Mutation nodes WHERE status IN ['proposed','no_status'].
    Group by target component. Pick TOP 3 by confidence × impact.
    For each: read relevant source file, propose concrete patch, implement.
    UPDATE mutation SET status='implemented' in Neo4j.
    Post summary to Telegram @raicomml."
```

---

## Implementation priority

| Priority | Pattern | Effort | Impact |
|----------|---------|--------|--------|
| 1 | #1 Identity injection | 15 lines | Prevents entire cascade |
| 2 | #2b Observer watchdog | 20 lines | Catches silent failures |
| 3 | #3a Truncation pagination | 15 lines | Unblocks observer reads |
| 4 | #3b Lineage rejection | 5 lines | Unblocks observer scrolls |
| 5 | #2a Observer fallback prompt | 5 lines | Reduces silent deaths |
| 6 | #3c Message ID prefix | 3 lines | Prevents ID confusion |
| 7 | #4a Stale comment | 3 lines | Documentation |
| 8 | #4b Preset persistence | 3 lines | UX fix |
| 9 | #5 Mutation review cron | 1 command | Process fix |
