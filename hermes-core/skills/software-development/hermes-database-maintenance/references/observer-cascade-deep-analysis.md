# Observer Cascade: Deep Code Analysis

Full code-level analysis of observer session creation, filtering, and cascade mechanics.
Produced from reading the Hermes codebase at `~/.hermes-docker/hermes-agent/`.

## Files involved

| File | Role |
|------|------|
| `plugins/observer-hook/__init__.py` | Python plugin: 3 hooks (on_session_start, post_llm_call, on_session_end) |
| `plugins/observer-hook/observer.py` | Legacy observer plugin (duplicate, simpler — no activity gate) |
| `~/.hermes/hooks/observer-hook/handler.py` | Shell hook: duplicate Neo4j writes on agent:start/agent:end/session:end |
| `~/.hermes/scripts/observer_worker.py` | Worker script: spawns 4 `hermes chat --source observer` subprocesses |
| `tools/delegate_tool.py` | `delegate_task()` + `_build_child_agent()` — in-process subagent creation |
| `run_agent.py` | `AIAgent._ensure_db_session()` — calls `create_session(source=platform)` |
| `hermes_state.py` | `SessionDB.create_session()`, `ensure_session()`, `list_sessions_rich()` |
| `tui_gateway/server.py` | GUI session listing: `session.list` and `session.most_recent` RPCs |
| `hermes_cli/main.py` | CLI `hermes sessions list` and `hermes sessions browse` |

## Session creation path comparison

| Path | source | parent_session_id | How | Hidden in GUI? |
|------|--------|-------------------|-----|----------------|
| TUI (normal) | `tui` | `NULL` | `cli.py:6768` → `create_session(source="tui")` | No (root) |
| CLI (`hermes chat`) | `cli` | `NULL` | `cli.py:6770` → `create_session(source=HERMES_SESSION_SOURCE)` | No (root) |
| `delegate_task` child | inherits parent `platform` (usually `tui`) | `parent.session_id` | `run_agent.py:511` → `_ensure_db_session()` → `create_session(source=self.platform)` | Yes (child-exclusion clause in `list_sessions_rich`) |
| `observer_worker.py` | `observer` | `NULL` | `hermes chat --source observer` → `create_session(source="observer")` | **No** (root, not in deny-list) |
| `observer_worker.py` delegate child | inherits `tui` | observer session_id | `delegate_task` → `_build_child_agent(platform="tui")` | Partially (child-exclusion) |
| Cron job | `cron` | `NULL` | Cron scheduler → `hermes chat` → `create_session(source="cron")` | No (root) |
| `ensure_session()` fallback | `unknown` | `NULL` | `hermes_state.py:1311` → `ensure_session(source="unknown")` | **No** (root, not in deny-list) |
| Third-party tool | `tool` | `NULL` | `--source tool` → `create_session(source="tool")` | Yes (in deny-list) |

**Key difference**: `delegate_task` is the only path that sets `parent_session_id`, enabling `list_sessions_rich`'s child-exclusion clause to hide them. `observer_worker.py` spawns **root sessions** via subprocess — they're invisible to child-exclusion.

## Source resolution: platform wins over env

`run_agent.py:509` — the authoritative source resolution:

```python
def _ensure_db_session(self) -> None:
    source = self.platform or os.environ.get("HERMES_SESSION_SOURCE", "cli")
    #         ↑ WINS        ↑ fallback if platform is None
```

**Critical**: `self.platform` takes precedence over `HERMES_SESSION_SOURCE` env var.
- `hermes chat --source observer` → `AIAgent(platform="cli")` → `source="cli"` wins...
  BUT `cli.py:6770` calls `create_session(source=HERMES_SESSION_SOURCE)` BEFORE
  `_ensure_db_session()` runs, so the DB row is created with `source="observer"` first.
  `_ensure_db_session()` then hits `INSERT OR IGNORE` → row already exists → skipped.
- `delegate_task` children → `platform=parent.platform` → `source="tui"` or `"cli"` (NOT `"observer"`)
- If `platform=None` (rare, e.g. background_review without explicit platform) → env fallback → `source="observer"`

This explains why 48 observer→observer children exist in the DB: their `platform` was `None`,
so `HERMES_SESSION_SOURCE="observer"` from the env (inherited from observer_worker.py) won.

## The `--source observer` flow

```
observer_worker.py:159-167
  subprocess.run([HERMES_CLI, "chat", "-q", prompt, "--source", "observer"])
       │
       ├─ main.py:2110-2111  → os.environ["HERMES_SESSION_SOURCE"] = "observer"
       │
       ├─ HermesCLI.__init__() → _init_agent()
       │    └─ cli.py:5248  → AIAgent(platform="cli")
       │    └─ cli.py:6770  → create_session(source="observer")  ← from env, FIRST write
       │         INSERT OR IGNORE INTO sessions (id, source='observer', parent=NULL)
       │
       └─ AIAgent._ensure_db_session() → run_agent.py:509
            source = "cli" or env("observer") = "cli"  ← platform wins
            but INSERT OR IGNORE → row already exists → SKIPPED

RESULT: source="observer", parent_session_id=NULL
```

`observer_worker.py` sets `HERMES_OBSERVER_SUBAGENT=1` in the subprocess env, which `_is_observer_session()` checks first — but this doesn't survive if the subprocess itself spawns children via `delegate_task` (children inherit `os.environ` but the flag may not reach all code paths).

**Single source confirmed**: grep across entire `~/.hermes/` and `~/.hermes-docker/hermes-agent/`
shows `--source observer` and `HERMES_SESSION_SOURCE: observer` appear ONLY in `observer_worker.py`.
Removing `--source observer` does NOT affect agent presets — it's purely a DB tag.

## DB evidence (2026-07-05 snapshot)

```
source    count   total_msgs
observer  112     829          (41 orphan/parent=NULL, 71 with_parent)
tui       65      8104         (real sessions)
unknown   26      0            (all 0-msg ghosts from ensure_session)
cron      16      348          (working cron jobs)
cli       15      27           (CLI sessions)
```

Observer parent breakdown (71 children with parent_session_id):
```
parent_source | count
observer      | 48    (cascade: observer→observer, via platform=None env fallback)
tui           | 11    (delegate_task from TUI sessions)
cli           | 12    (delegate_task from CLI sessions)
```

## `_is_observer_session()` — three gaps

```python
# __init__.py:75-94
def _is_observer_session(kwargs: dict) -> bool:
    # Gap 1: env-var gate — works for direct observer_worker.py calls,
    #         but doesn't propagate to all delegate_task grandchildren
    if os.environ.get("HERMES_OBSERVER_SUBAGENT"):
        return True

    # Gap 2: preset gate — delegate_task doesn't set agent_prompt_label
    preset = str(kwargs.get("agent_prompt_label", kwargs.get("agent_preset", ""))).lower()
    if any(name in preset for name in OBSERVER_AGENT_NAMES):
        return True

    # Gap 3: system_prompt gate — delegate_task passes ephemeral_system_prompt,
    #         NOT system_prompt/system_message → gate never fires
    sp = str(kwargs.get("system_prompt", kwargs.get("system_message", "")))
    if any(f"{name} observer" in sp.lower() ...):
        return True

    # Gap 4: user message gate — fragile substring match
    user_msg = str(kwargs.get("user_message", kwargs.get("message", "")))
    if ("session" in user_msg.lower() and "observer" in user_msg.lower()):
        return True
    return False

    # MISSING: no check of source column in state.db by session_id
```

## ObserverManager: dead import

`on_session_end` (line 199-205) tries:
```python
from agent.observer_manager import ObserverManager
if not ObserverManager.is_session_end_enabled():
    return
```
The module `agent/observer_manager.py` does **not exist** in the codebase. The `except Exception: pass` swallows the `ImportError`, so the config-gate is never enforced — observer always fires if activity gate passes.

## Existing cleanup tools in hermes_state.py

- `prune_empty_ghost_sessions()` — deletes `source='tui'`, `title IS NULL`, `ended_at IS NOT NULL`, no messages, older than 24hr. Does NOT target `source='unknown'`.
- `finalize_orphaned_compression_sessions()` — marks orphaned compression children with `end_reason='orphaned_compression'`.
- `list_sessions_rich(exclude_sources=...)` — the main listing function with deny-list support.

## Five solution variants

### Variant 1: Deny-list expansion (quick fix)
Add `"observer"` and `"unknown"` to deny-lists at 4 locations. Hides from GUI/CLI but doesn't stop cascade.

### Variant 2: Fix `_is_observer_session()` with DB source check
Add `sqlite3.connect(STATE_DB).execute("SELECT source FROM sessions WHERE id=?", (sid,))` check. Stops cascade at source. ~15 lines.

### Variant 3: Propagate observer env-var through delegate_task
Set `child._force_session_source = "observer"` in `_build_child_agent` when parent is observer. Modify `_ensure_db_session` to check `_force_session_source`. ~10 lines, 2 files.

### Variant 4: Disable observer-hook entirely
```bash
mv ~/.hermes/hermes-agent/plugins/observer-hook/__init__.py{,.disabled}
mv ~/.hermes/hooks/observer-hook/handler.py{,.disabled}
```
Zero cascade, zero analytics. 2 commands.

### Variant 5: Rewrite observer_worker.py to use delegate_task
Replace `subprocess.run([HERMES_CLI, "chat", "--source", "observer", ...])` with in-process `delegate_task` calls. Observer sessions become children (hidden by child-exclusion). ~100 lines refactor.
