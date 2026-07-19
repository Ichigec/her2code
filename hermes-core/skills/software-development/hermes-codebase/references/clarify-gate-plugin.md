# clarify-gate Plugin

Plugin at `~/.hermes/plugins/clarify-gate/__init__.py`.

## Purpose

Two-layer enforcement of mandatory `clarify()` calls when user requests are
ambiguous:

- **Layer 1 (pre_llm_call):** Scans user message for ambiguous terms. If found,
  injects a hard instruction forcing `clarify()` as the first action.
- **Layer 2 (pre_tool_call):** Blocks action tools if `clarify()` hasn't been
  called yet for this session's turn.

## Architecture

### Ambiguity Detection

```python
AMBIGUOUS_PRODUCTS: dict[str, str] = {
    "mattermost": "Mattermost SERVER (self-hosted) or DESKTOP client?",
    # "hermes" was REMOVED — too broad for daily Hermes development
    "postgres": "PostgreSQL SERVER or just psql CLIENT?",
    ...
}

AMBIGUOUS_TERMS: dict[str, list[str]] = {
    "установи": ["docker", "binary/pkg", "snap/flatpak", "source build"],
    "почини": ["code bug", "config", "data", "process/infra"],
    ...
}
```

`_detect(user_message)` checks the message against both dictionaries (case-
insensitive). Returns the ambiguity question or `None`.

### Session State (IN-MEMORY — THE BUG)

```python
class _State:
    needs_clarify: str | None = None
    clarified: bool = False

_sessions: dict[str, _State] = {}  # ← LOST ON GATEWAY RESTART
```

State is keyed by `session_id`. On gateway restart (crash, SIGTERM, manual
restart), this dict is wiped clean — all sessions lose their `clarified` flag.

### Tool Classification

```python
READ_ONLY = frozenset({
    "read_file", "search_files", "glob", "list", "skill_view",
    "skills_list", "memory", "session_search", "clarify",
})

ACTION_TOOLS = frozenset({
    "web_search", "web_extract", "browser_navigate", "browser_click",
    "terminal", "execute_code", "write_file", "patch", "delegate_task",
    "image_generate", "cronjob",
})
```

When `needs_clarify` is set and `clarified` is False:
- READ_ONLY tools → allowed (so agent can investigate)
- ACTION_TOOLS → BLOCKED with `⛔ AMBIGUITY NOT RESOLVED`
- Other tools (not in either set) → allowed (fallback)

Calling `clarify()` sets `state.clarified = True` and clears `needs_clarify`,
unblocking all tools.

## The Crash Sequence

```
1. User sends message containing "hermes" (e.g. "hermes gui упал")
2. _pre_llm() detects "hermes" in AMBIGUOUS_PRODUCTS
3. _sessions[session_id].needs_clarify = "Hermes Agent (AI), Android app, or desktop GUI?"
4. Agent calls clarify() → user answers → state.clarified = True → tools work
5. GUI crashes → gateway restarts → _sessions dict wiped
6. User sends new message containing "hermes" (e.g. "hermes gui только что упал")
7. _pre_llm() detects "hermes" again → new _State (clarified=False)
8. ALL action tools blocked → agent appears frozen/dead
```

## Fix Applied (July 2026)

Removed `"hermes"` from `AMBIGUOUS_PRODUCTS` — the word appears in almost every
message during Hermes development work, making the ambiguity check counter-
productive.

```python
AMBIGUOUS_PRODUCTS: dict[str, str] = {
    "mattermost": "Mattermost SERVER (self-hosted) or DESKTOP client?",
    # "hermes" removed — too broad for daily Hermes development work
    "postgres": "PostgreSQL SERVER or just psql CLIENT?",
    ...
}
```

## Permanent Fix (NOT YET IMPLEMENTED)

Persist `_sessions` state to SQLite or a JSON file so it survives gateway
restarts. Alternatively, use `session_id` to look up whether the user has
already clarified in this session from the session DB.

## Related Files

- Plugin: `~/.hermes/plugins/clarify-gate/__init__.py`
- Hooks: registers `pre_llm_call` and `pre_tool_call`
- Hook system: `plugins/observability/` docs, `run_agent.py` hook dispatch
- Affected tools: all in `ACTION_TOOLS` frozenset
