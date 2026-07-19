# Gap Fixes: State-Poisoning & AGENTS.md Pollution

Concrete implementation plan for the two highest-priority observer findings
(2026-07-01). Both are blocking: gap 1 silently degrades the knowledge pipeline,
gap 2 wastes 40-60% of input tokens in every observer/cron session.

## Gap 1: State-Poisoning in knowledge-curator-ingest-llm.py

**Severity:** CRITICAL — 2+ observer cycles flagged this, unfixed.
**Root cause:** Line 218 saves `state[pstr] = h` unconditionally, even when
`call_llm()` returns `None` (ConnectionRefused, timeout, bad JSON). A single
llama.cpp crash marks ALL unprocessed files as "done" with zero knowledge
ingested.

### Fix: `/home/user/.hermes/scripts/knowledge-curator-ingest-llm.py`, lines 206-222

```python
# BEFORE (bug):
        if dry_run:
            print(f"[dry-run] {path.name} ({len(content)} chars)")
        else:
            entities = call_llm(path.name, content)
            if entities:
                n = ingest_entities(entities, path)
                total_ingested += n
                names = ", ".join(e["name"][:30] for e in entities[:3])
                print(f"{path.name}: {len(entities)} entities → {n} ingested ({names}...)")
            else:
                print(f"{path.name}: no entities extracted")

        state[pstr] = h        # ← BUG: saved unconditionally
        processed += 1
```

```python
# AFTER (fixed):
        if dry_run:
            print(f"[dry-run] {path.name} ({len(content)} chars)")
            state[pstr] = h
            processed += 1
        else:
            entities = call_llm(path.name, content)
            if entities is None:
                # LLM error (ConnectionRefused, timeout, bad JSON) — retry next run
                print(f"{path.name}: LLM extraction failed, will retry")
                continue
            elif entities:
                n = ingest_entities(entities, path)
                total_ingested += n
                names = ", ".join(e["name"][:30] for e in entities[:3])
                print(f"{path.name}: {len(entities)} entities → {n} ingested ({names}...)")
            else:
                # entities == []: LLM responded, nothing extractable
                print(f"{path.name}: no entities extracted")
            state[pstr] = h
            processed += 1
```

### Key distinction

| `call_llm()` return | Meaning | Action |
|---|---|---|
| `None` | LLM error (HTTP exception, bad response) | `continue` — don't save hash, retry next run |
| `[]` | LLM responded, nothing to extract | Save hash — file genuinely empty |
| `[{...}, ...]` | Entities extracted | Save hash — success |

### Verification

```bash
# Kill llama.cpp to simulate LLM failure
kill $(pgrep -f llama.cpp)

# Run curator — should print "LLM extraction failed, will retry" for each file
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py

# Verify state was NOT updated for failed files
python3 -c "
import json
d = json.load(open('/home/user/.hermes/skills/.curator_state'))
print(f'State entries: {len(d)}')
"
# Count should NOT have increased for the run where LLM was dead
```

---

## Gap 2: AGENTS.md Context Pollution

**Severity:** HIGH — 3+ observer cycles flagged this, unfixed.
**Root cause:** Two injection points for AGENTS.md into observer/cron sessions:

| Injection point | Mechanism | Impact |
|---|---|---|
| **System prompt** (startup) | `build_context_files_prompt()` via `agent/system_prompt.py` | ~12K chars once per session |
| **Tool output** (every call) | `SubdirectoryHintTracker.check_tool_call()` via `agent/subdirectory_hints.py` | **24-69K chars PER tool call** ← main culprit |

The system prompt injection is a one-time cost. The tool output injection
amplifies across every `terminal()`, `read_file()`, and `search_files()` call —
observer sessions doing Neo4j writes via `curl` get both `~/.hermes/AGENTS.md`
(12K) and `~/.hermes/hermes-agent/AGENTS.md` (57K) appended to every tool result.

### Fix 2a (primary): Gate SubdirectoryHintTracker in tool_executor.py

**File:** `/home/user/.hermes/hermes-agent/agent/tool_executor.py`, lines 1387-1393

```python
# BEFORE:
        # Discover subdirectory context files from tool arguments
        subdir_hints = agent._subdirectory_hints.check_tool_call(function_name, function_args)
        if subdir_hints:
            if _is_multimodal_tool_result(function_result):
                _append_subdir_hint_to_multimodal(function_result, subdir_hints)
            else:
                function_result += subdir_hints
```

```python
# AFTER:
        # Discover subdirectory context files from tool arguments.
        # Skip for sessions that don't need project context (cron, observer, subagents).
        if not agent.skip_context_files:
            subdir_hints = agent._subdirectory_hints.check_tool_call(function_name, function_args)
            if subdir_hints:
                if _is_multimodal_tool_result(function_result):
                    _append_subdir_hint_to_multimodal(function_result, subdir_hints)
                else:
                    function_result += subdir_hints
```

**Coverage:**

| Session type | `skip_context_files` | Effect |
|---|---|---|
| delegate_task subagents | `True` (delegate_tool.py:1162) | ✅ Already covered |
| Cron without workdir | `True` (scheduler.py:1797) | ✅ Already covered |
| Cron with workdir | `False` | Keeps AGENTS.md — needed for project work |
| Observer CLI (`hermes -z`) | `False` | ❌ NOT covered — needs Fix 2b |
| Interactive user | `False` | Keeps AGENTS.md — user needs it |

### Fix 2b (supplementary): Force skip for observer CLI sessions

**File:** `/home/user/.hermes/hermes-agent/agent/agent_init.py`, after line 299

```python
# AFTER line 299 (agent.skip_context_files = skip_context_files):
    agent.skip_context_files = skip_context_files
    # Observer subagent sessions don't need project context files.
    # HERMES_OBSERVER_SUBAGENT=1 is set by observer_worker.py:165.
    if os.environ.get("HERMES_OBSERVER_SUBAGENT") == "1":
        agent.skip_context_files = True
```

This env var is already set by `observer_worker.py` line 165. Observer sessions
via `delegate_task()` already have `skip_context_files=True` from line 1162 of
`delegate_tool.py`. This fix closes the last remaining path: CLI observer via
`hermes -z`.

### Verification

```bash
# Check AGENTS.md no longer appears in observer tool output
hermes chat -q "session_search(session_id='20260701_040707_6e7562')" \
  --yolo -m deepseek-v4-pro --provider deepseek --source observer 2>&1 \
  | grep -c "Subdirectory context discovered"
# Should be: 0

# Verify interactive sessions still work
hermes chat "прочитай AGENTS.md и скажи сколько там фаз" --yolo 2>&1 \
  | grep "AGENTS.md"
# Should find and show context
```

## Rebuild after applying fixes

Fix 2a and 2b are Python changes — restart dashboard:
```bash
# Close hermes gui, then reopen
hermes gui
```

Fix 1 is a standalone script — no restart needed, takes effect on next cron run.

## Related Skills

- `hermes-observer-system` — full observer architecture, pitfall catalog
- `hermes-codebase` — navigating the Hermes Agent codebase
