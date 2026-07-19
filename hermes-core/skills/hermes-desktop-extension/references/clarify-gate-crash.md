# Clarify-Gate Plugin Crash — RCA 2026-07-03

## Symptom

After Hermes gateway restarts (crash, manual restart, Electron relaunch),
ALL action tools (terminal, write_file, patch, execute_code, delegate_task)
return:

```
⛔ AMBIGUITY NOT RESOLVED

Hermes Agent (AI), Android app, or desktop GUI?

Call `clarify()` with structured choices FIRST.
```

Read-only tools (read_file, search_files, glob, skill_view) still work.
The agent appears unresponsive to the user — looks like a GUI crash.

## Root Cause

**File:** `~/.hermes/plugins/clarify-gate/__init__.py`

The clarify-gate plugin enforces a two-layer clarify gate:

1. **Layer 1 (pre_llm_call):** Detects ambiguous terms in user messages.
   If found, injects a MANDATORY clarify instruction.
2. **Layer 2 (pre_tool_call):** Blocks action tools until `clarify()` is called.

State is stored in an **in-memory dict**:

```python
_sessions: dict[str, _State] = {}  # ← LOST on gateway restart
```

### Crash chain

```
1. Gateway restarts (crash/relaunch) → _sessions dict cleared
2. User sends message containing "hermes" (e.g., "hermes gui упал")
3. _detect() matches "hermes" in AMBIGUOUS_PRODUCTS → needs_clarify = True
4. pre_tool_call blocks ALL action tools (terminal, write_file, etc.)
5. Agent can't execute anything → appears frozen to user
```

### Why "hermes" was in AMBIGUOUS_PRODUCTS

```python
AMBIGUOUS_PRODUCTS: dict[str, str] = {
    "hermes": "Hermes Agent (AI), Android app, or desktop GUI?",
    ...
}
```

This was intended for first-time setup ambiguity ("set up hermes" → which
component?). But for daily Hermes development work, EVERY message containing
"hermes" triggers the gate after a restart.

## Fix

**Remove "hermes" from AMBIGUOUS_PRODUCTS** in
`~/.hermes/plugins/clarify-gate/__init__.py`:

```python
AMBIGUOUS_PRODUCTS: dict[str, str] = {
    "mattermost": "Mattermost SERVER (self-hosted) or DESKTOP client?",
    # "hermes" removed — too broad for daily Hermes development work
    "postgres": "PostgreSQL SERVER or just psql CLIENT?",
    ...
}
```

## Diagnostic Path

When tools are blocked by an unknown source:

1. **Search for the error string in the codebase:**
   ```
   search_files("AMBIGUITY NOT RESOLVED", path="~/.hermes")
   ```
   This finds the plugin file that generates the message.

2. **Read the plugin code** to understand the blocking logic.

3. **Check errors.log for plugin load failures:**
   ```
   grep "Failed to load plugin" ~/.hermes/logs/errors.log
   ```
   In this case, `observer-hook` also failed to load (`__init__.py.disabled`),
   which was a separate but compounding issue.

4. **Check gateway.log** for restart events — look for SIGTERM/SIGINT entries
   that indicate the gateway crashed and restarted.

## Related Issues Found During Diagnosis

### observer-hook plugin not loading

```
WARNING: Failed to load plugin 'observer-hook': No __init__.py
```

**Fix:** Rename `__init__.py.disabled` → `__init__.py`:
```bash
mv plugins/observer-hook/__init__.py.disabled plugins/observer-hook/__init__.py
```

### Agent file corruption (triple line-number prefixes)

Files in `~/.hermes/agents/plan3/*.md` had corrupted content:
```
1|1|1|---
2|2|2|label: Plan3 · Requirements
```

Instead of:
```
---
label: Plan3 · Requirements
```

**Cause:** read_file → write_file cycles where line-number prefixes from
read_file output became embedded in the file content.

**Fix script:** `scripts/strip-line-numbers.py`

## Prevention

1. **Broad terms in AMBIGUOUS_PRODUCTS:** Avoid adding product names that
   appear in everyday work messages. "hermes", "opencode", "android" are
   too common for users who work on those projects daily.

2. **In-memory plugin state:** Plugins that use module-level dicts for
   session state lose that state on gateway restart. Either:
   - Persist to SQLite/JSON
   - Accept the reset and ensure re-detection doesn't block normal work
   - Use `is_first_turn` flag to only trigger on genuine first turns

3. **Plugin load failures:** Check `errors.log` for `Failed to load plugin`
   warnings after every gateway restart. Disabled plugins (`.disabled`
   suffix) should be intentional, not accidental.

## Git Workflow for Hermes Changes (Pavel's preference)

Before making improvements to Hermes, save the working state:

```bash
# 1. Commit any uncommitted work
git add -A && git commit -m "snapshot: stable-YYYY-MM-DD"

# 2. Tag the stable point
git tag -a stable-YYYY-MM-DD -m "Stable snapshot — all components working"

# 3. Create dev branch for experimental changes
git branch dev && git checkout dev

# 4. Make changes on dev, test, verify

# 5. When ready: merge to main, or rollback
git checkout main && git merge dev                            # promote
git checkout dev && git reset --hard stable-YYYY-MM-DD        # rollback
```

Also backup config files separately (they contain API keys, not in git):
```bash
cp ~/.hermes/config.yaml ~/.hermes/backups/config.yaml.stable-YYYY-MM-DD
cp ~/.hermes/.env ~/.hermes/backups/.env.stable-YYYY-MM-DD
```

This workflow was established 2026-07-03 for Hermes Agent + Android app.
