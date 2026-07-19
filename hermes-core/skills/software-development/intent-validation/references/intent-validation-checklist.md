# Intent Validation Checklist

Use this checklist at the start of any turn where the user's request could be read as inspection-only or conflicts with inherited context.

## 1. Stop

- [ ] Do not execute a file edit, plan, or subagent dispatch yet.
- [ ] Ignore any "Active Task" from a compaction summary unless the user explicitly confirms it.

## 2. Inspect the latest user message

- [ ] Is the verb inspection-oriented? (check, review, verify, inspect, look at, tell me, explain, what does X mean)
- [ ] Is the user correcting or redirecting? (stop, not my task, I didn't ask, why are you doing X)
- [ ] Is the request vague? (continue, proceed, do that, go on)

## 3. Compare to inherited context

- [ ] Does the latest message explicitly authorize the work described in the active todo/context?
- [ ] Is there a topic drift or mismatch?
- [ ] Did the user previously say "don't edit without asking"?

## 4. Decide

| Case | Action |
|---|---|
| Inspection verb only | Report findings; do not edit |
| Correction/redirect | Stop conflicting work; clarify actual intent |
| Vague "continue" | Ask what specifically to continue |
| Explicit action verb + confirmed scope | Proceed |

## 5. Clarify if unsure

Use a direct question. Examples:

- "'Проверь' means 'inspect' to me. Should I edit anything or just report?"
- "The session summary mentions X, but your message is about Y. Which should I focus on?"
- "You previously asked me not to edit files without permission. Should I still treat this as read-only?"

## 6. Only then act

- [ ] If editing: confirm scope explicitly.
- [ ] If reporting: keep it concise and evidence-backed.
- [ ] If switching topics: update todos accordingly and do not resume the old task without new instruction.
