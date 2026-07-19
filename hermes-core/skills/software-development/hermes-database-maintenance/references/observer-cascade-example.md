# Observer Cascade — Real-World Example (2026-07-01)

## Discovery

`hermes sessions list` showed 927 sessions. Investigation revealed:

```
source      count
observer    902    ← 97.3%
tui          16
cron          8
unknown       1
```

18 of the 902 had titles like `"Session analysis for auditor observer. Session: ..."` — checkpoint observer sessions spawned by plan2 orchestrator. The remaining 884 had NULL titles — `delegate_task` sub-agent sessions.

## Cascade mechanism

Two independent sources creating observer sessions simultaneously:

### Source 1: Observer-hook plugin
- `on_session_end` → checks activity gate (≥5 msg, ≥2 tool calls, ≥5K tokens)
- Spawns `observer_worker.py` via `subprocess.Popen`
- Worker uses `hermes chat -q` to run observer agent
- Observer agent calls `delegate_task` for its analysis → creates observer session

### Source 2: Plan2 persona delegate_task
- Plan2 persona instructs: after each phase, spawn all 4 observers via `delegate_task`
- Each `delegate_task` call creates a session with `source='observer'`
- Full cycle (10 phases × 4 observers + Phase 0 observers + Research sub-agents) = ~55 observer sessions

## Evidence from error logs

```
2026-07-01 23:44:00 WARNING [20260701_234110_5831b6] tools.delegate_tool: 
  delegation.max_concurrent_children=90: each child consumes API tokens independently.
```

Observer sessions were spawning their OWN observer sessions — exponential cascade:
- Observer session A spawns 4 observers → sessions B, C, D, E
- Session B spawns 4 more → sessions F, G, H, I
- etc.

## Cleanup results

| Metric | Before | After |
|--------|--------|-------|
| Total sessions | 927 | 26 |
| Observer sessions | 902 | 0 |
| state.db size | 821 MB | 197 MB |
| Messages | 14,346 | 2,640 |
| Space reclaimed | — | 626 MB |

## Why _is_observer_session() failed

The function checks:
1. `HERMES_OBSERVER_SUBAGENT` env var
2. Agent preset name contains observer keywords
3. System prompt mentions "observer"
4. User message mentions "session" + "observer"

But `delegate_task` sessions:
- Don't set `HERMES_OBSERVER_SUBAGENT`
- Have preset = the parent's preset (plan2), not observer names
- System prompt = the plan2 orchestrator prompt, not observer prompt
- User message = task description ("Auditor checkpoint Phase 3: ..."), but the function only checks for "session" + "observer" together

The missing check: `source='observer'` in state.db.
