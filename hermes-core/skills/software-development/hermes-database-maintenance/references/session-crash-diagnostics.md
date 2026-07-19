# Session Crash Diagnostics

How to investigate when a Hermes session dies silently — no error in the UI, just
the last user message hanging with no assistant response.

## Quick diagnostic flow

```
session_search(query="<session_id_or_topic>")   → find the session
session_search(session_id=..., around_message_id=<last_user_msg>, window=5)  → check tail
```

Key indicators in the scroll result:
- `messages_after: 0` — confirmed dead-end; model never responded
- `messages_after: >0` but truncated — session may have ended mid-response

## Root cause classification

| Symptom | Likely cause | Evidence to check |
|---------|-------------|-------------------|
| Last user msg, no response, `messages_after=0` | **Context window exhaustion** | Session length (200+ msgs), massive tool outputs (pip install logs, AGENTS.md dumps, filesystem scans), model with small window (e.g. GLM-5.2 128K) |
| Sequence of empty/null tool results → user asks for more → silence | Context exhaustion **combined with dead-end investigation** | Model probing for files that don't exist, returns empty, then can't fit re-planning into context |
| Session ends mid-tool-call | Provider timeout or connection drop | Check provider status, look for partial tool results |
| Multiple sessions created in rapid succession | User switched sessions manually (TUI: Ctrl+C → new) | `source` column, timestamps |
| Last user msg, model=GLM-5.2, `messages_after=0` | **GLM-5.2 silent failure** — Zhipu provider drops connection or returns empty response instead of throwing "context length exceeded" | Unlike GPT-4/DeepSeek which return explicit errors, GLM-5.2 just stops; Hermes client interprets empty response as session end |

## Context window exhaustion — detailed diagnosis

1. Scroll to session start: `session_search(session_id=..., around_message_id=<first_msg>, window=3)`
2. Note the model: `session_meta.model`
3. Estimate context: message_count × average_message_size + known_large_outputs
4. Compare to model's context window:

| Model | Context window |
|-------|---------------|
| GLM-5.2 | 128K tokens |
| GPT-4o | 128K tokens |
| Claude Sonnet 4 | 200K tokens |
| DeepSeek V3/V4 | 128K tokens |

Rule of thumb: 300+ messages with heavy tool outputs (filesystem scans, pip install logs, large file reads) → near-certain context exhaustion.

**Amplifier: Plan2 preset overhead.** The plan2 orchestrator preset (`~/.hermes/agents/plan2.md`) is 68KB/1,228 lines/~17K tokens. It's loaded even for meta-questions (not just full cycles), consuming ~13% of GLM-5.2's 128K window before the first message. Combined with 300+ messages and massive tool outputs, context exhaustion is nearly guaranteed. **Recommendation for GLM-5.2 sessions:** use a general preset for meta-questions, switch to plan2 only for full cycles.

## Dead-end investigation pattern

When the model probes for files/configs that don't exist and gets empty results:

```
user: "Can we launch GUI?"
model: [searches for ~/.hermes/config.yaml → empty]
model: [searches for pre-built GUI binary → not found]
model: [searches for node_modules → not found]
user: "We did this before — double your searches"
model: [tries to plan broader search… context full → silence]
```

The failure isn't the empty results — it's that the model can't re-scope its investigation because the context window is saturated with prior tool outputs.

## Recovery pattern

When you find a crashed session:
1. Scroll to the last user message to see what was asked
2. Scroll back ~10 messages to understand the task state
3. Start a fresh session — the previous model's context is unrecoverable
4. In the new session, pick up where it left off with a fresh context window
