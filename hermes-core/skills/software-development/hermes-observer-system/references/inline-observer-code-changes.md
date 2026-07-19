# Inline Observer Notes — Code Changes (2026-06-27)

Pavel wanted observer findings visible after each LLM response, not just in Neo4j.
Two files were modified to add per-turn inline observer notes.

## agent/observer.py

Added `_format_observer_notes()` function and changed `on_post_llm_call()` to return a string.

### `_format_observer_notes(auditor_findings, critic_findings, ideas, mutations, entities)`

Builds a compact markdown block showing only non-trivial findings:

```
🔍 **Auditor:**
  🚨 Possible non-verified claim detected: 'should work'
  ⚠️ Very short response (42 chars)

🎯 **Critic:**
  🎯 Overly manual instruction pattern

💡 **Ideas:**
  [unheard] Research paper discussed — queue for education graph ingestion

🧬 **Mutations:**
  `plan2.md:observer_checkpoints`: Ensure all 4 observers write to Neo4j (conf=85%)

📚 **Entities:** `ADAS`, `Neo4j`, `Hermes`, `Telegram`
```

Filtering rules:
- Auditor: only HIGH (🚨) and MEDIUM (⚠️) — skip INFO/LOW
- Critic: skip category "clean"
- Ideas: value >= 7 only
- Mutations: max 2 shown
- Entities: max 5 shown
- If ALL filtered out → returns "" (no noise)

### `on_post_llm_call()` return value

Changed from `return` / `return None` to `return _format_observer_notes(...)`.

Stores intermediate results before the batch write loop:
```python
auditor_findings = _auditor_analyze(resp, turn_count)
critic_findings = _critic_analyze(resp)
entities = _curator_extract(resp)
# ... batch write to Neo4j unchanged ...
return _format_observer_notes(auditor_findings, critic_findings, ideas, mutations, entities)
```

## agent/conversation_loop.py (line ~4848)

Changed from fire-and-forget to capture-and-append:

```python
# OLD:
_obs_llm(agent.session_id, final_response or "", turn_count)

# NEW:
obs_notes = _obs_llm(agent.session_id, final_response or "", turn_count)
if obs_notes and final_response:
    final_response = final_response + "\n\n---\n" + obs_notes
```

The `---` separator is a horizontal rule in markdown, visually separating main response from observer block.

## Verification

Both files pass `py_compile`:
```bash
python3 -c "import py_compile; py_compile.compile('agent/observer.py', doraise=True)"
python3 -c "import py_compile; py_compile.compile('agent/conversation_loop.py', doraise=True)"
```

Changes take effect on Hermes restart (modules are imported at startup, not hot-reloaded).
