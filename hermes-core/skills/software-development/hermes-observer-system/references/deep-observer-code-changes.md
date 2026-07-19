# Deep Observer — Code Changes (2026-06-27)

Pavel wanted LLM-based observer subagents running IN the same session, adding findings to the chat.
The deep observer spawns a single subagent via `delegate_task()` every Nth turn.

## conversation_loop.py (after inline observer block)

```python
# ── Deep observer: single LLM subagent, brief synthesis, same session ──
# Only on turn 1 (initial) and every 5th turn thereafter (to limit latency)
_obs_turn = getattr(agent, "_user_turn_count", 0)
if _obs_turn in (1, 5, 10, 15, 20) or (_obs_turn > 0 and _obs_turn % 5 == 0):
    try:
        import json as _json
        from tools.delegate_tool import delegate_task as _delegate
        sid = agent.session_id
        goal = (
            f"You are a session observer. Briefly analyze the conversation so far "
            f"and provide 3-5 concise, valuable observations. Be SHORT — max 120 words total.\n\n"
            f"Use session_search(session_id='{sid}') to read the full conversation.\n\n"
            f"Cover these angles BRIEFLY:\n"
            f"1. Quality: any issues with responses, unverified claims, or missing steps?\n"
            f"2. Efficiency: any waste, repetition, or unnecessary complexity?\n"
            f"3. Ideas: what could be improved about the agent, tools, or workflow?\n"
            f"4. Knowledge: what entities, patterns, or facts emerged?\n\n"
            f"Format: 3-5 bullet points, each 1 line. No fluff, no intros, just observations."
        )
        # Tag deep-observer subagent sessions so they don't
        # clutter the main session list (filtered by excludeSources).
        _prev_source = os.environ.get("HERMES_SESSION_SOURCE")
        os.environ["HERMES_SESSION_SOURCE"] = "observer"
        try:
            obs_json = _delegate(
                goal=goal,
                context=f"Session {sid}, turn {_obs_turn}. Analyze the ENTIRE session arc.",
                toolsets=["session_search"],
                parent_agent=agent,
                role="leaf",
                max_iterations=4,
            )
        finally:
            if _prev_source is None:
                os.environ.pop("HERMES_SESSION_SOURCE", None)
            else:
                os.environ["HERMES_SESSION_SOURCE"] = _prev_source
        obs_data = _json.loads(obs_json) if isinstance(obs_json, str) else obs_json
        results = obs_data.get("results", [])
        if results and results[0].get("status") == "completed":
            deep_notes = results[0].get("summary", "").strip()
            if 30 < len(deep_notes) < 800 and final_response:
                final_response = final_response + "\n\n---\n🧠 **Deep Observer:**\n" + deep_notes
    except Exception:
        pass
```

## Key design decisions

| Decision | Rationale |
|----------|----------|
| ONE subagent, not 4 | 4 parallel subagents = 4× latency (40-80s). One covers all angles in ~10-20s |
| Turn-gated (1, 5, 10, 15, 20, 25...) | Every-turn would add 10-20s delay to EVERY response. Every 5th = acceptable |
| `max_iterations=4` | Tight leash. Observer only needs to read session + produce bullets |
| `toolsets=["session_search"]` | Only tool needed — reads conversation arc from session DB |
| `role="leaf"` | Prevents recursive delegation (observer spawning observers) |
| `parent_agent=agent` | Critical: passes current AIAgent so subagent inherits model/provider |
| Sanity filter: 30-800 chars | Rejects empty/failed results and overly verbose outputs |

## Source tagging (added 2026-06-27)

The `delegate_task()` call runs subagents **in the same Python process** — the
`--source observer` CLI flag does NOT apply. Instead, `HERMES_SESSION_SOURCE` is
set in the environment before the call and restored after (save/restore pattern):

```python
_prev_source = os.environ.get("HERMES_SESSION_SOURCE")
os.environ["HERMES_SESSION_SOURCE"] = "observer"
try:
    obs_json = _delegate(...)
finally:
    if _prev_source is None:
        os.environ.pop("HERMES_SESSION_SOURCE", None)
    else:
        os.environ["HERMES_SESSION_SOURCE"] = _prev_source
```

**Why this matters**: Without this, deep observer sessions get `source='cli'`
(the default in `run_agent.py:509`) and cannot be filtered by the desktop
`excludeSources: ['observer']` — they clutter the main session list exactly
like the observer cascade bug.

**Why save/restore**: The parent TUI session must keep its original source tag.
Without restore, subsequent DB writes would re-tag the parent as 'observer'.

For details see `references/session-source-tagging.md`.

## Programmatic delegate_task() API

The internal `delegate_task()` function in `tools/delegate_tool.py` can be called directly (not through tool layer):

```python
from tools.delegate_tool import delegate_task

result_json = delegate_task(
    goal="Task description",
    context="Background info",
    toolsets=["terminal", "file"],
    parent_agent=my_agent,    # the current AIAgent instance
    role="leaf",              # or "orchestrator"
    max_iterations=50,        # optional
    model=None,               # inherit from parent
    provider=None,            # inherit from parent
)
```

Returns a JSON string. Parse with `json.loads()`:
```python
data = json.loads(result_json)
for r in data["results"]:
    print(r["status"])       # "completed", "failed", "timeout", etc.
    print(r["summary"])      # the subagent's final_response
    print(r["duration_seconds"])
```

This is the SAME function the tool layer calls — it's not a separate internal-only API.
