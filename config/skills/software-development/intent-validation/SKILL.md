---
name: intent-validation
description: "Validate the user's actual intent before acting, especially when the request is ambiguous or conflicts with inherited session context."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [communication, clarification, intent, context, workflow]
    related_skills: [requirements-analysis, plan, subagent-driven-development, multi-agent-orchestration]
---

# Intent Validation

## Overview

Stop and verify what the user actually wants **before** starting work. Inherited context — compaction summaries, stale todo lists, subagent deliverables, or a previous turn's task — is not a mandate unless the current user message explicitly confirms it.

**Core principle:** When in doubt, clarify. "Check" is not "change."

## When to Use

Use this skill as a gate whenever any of these signals appear:

- The user uses verbs like **check**, **review**, **verify**, **look at**, **inspect**, **tell me about**, or **what does X mean**.
- The user's current message is much shorter or vaguer than the active task context suggests.
- The user says the current task **"is not my task"**, **"I didn't ask for this"**, or **"stop doing X"**.
- A context-compaction summary or inherited todo list pushes you toward actions the user has not explicitly requested.
- The user replies **"continue"** after a context compaction, but you are unsure what they expect to continue.
- The user corrects your style, format, or workflow mid-turn.

## The Gate

Run this gate **before** reading files for implementation, creating plans, dispatching subagents, or editing anything.

### 1. Compare user message to inherited context

Read the latest user message first. Then compare it to:

- Any active todo list
- Any context-compaction summary
- Any previous "continue"/"proceed" instructions
- Any deliverable a subagent or earlier turn left in progress

Ask: **Does the user's latest message explicitly authorize the work the inherited context is pushing me toward?**

### 2. Classify the request

| Signal | Interpretation | Default action |
|---|---|---|
| "Check / review / verify / look at" | Read-only investigation | Report findings; **do not edit** |
| "Explain / what does X mean" | Information request | Answer concisely; **do not edit** |
| "Fix / change / implement / do" | Mutation request | Proceed after confirming scope |
| "Continue / proceed / go on" | Resume prior task | Verify scope with the user first if context is ambiguous |
| "Stop / not my task / I didn't ask" | Cancel / redirect | Halt immediately and clarify |

### 3. If there is any mismatch, clarify

Use `clarify` or ask directly. Example prompts:

- "You said 'check runtime changes.' Do you want me to report the current git status/diff, or start implementing something?"
- "The session context points to child-session UI work, but your message suggests a different topic. Should I continue that work or switch?"
- "'Проверь' can mean 'inspect' or 'fix.' Should I edit files or just report what I find?"

Do **not** start implementation while the mismatch is unresolved.

## Rules

1. **"Check" ≠ "change."** Verbs of inspection mean read-only unless the user explicitly adds an action verb.
2. **Inherited context is advisory, not authoritative.** A compaction summary or stale todo does not override the user's current message.
3. **Stop on explicit correction.** When the user says a task is not theirs, stop that work immediately. Do not "wrap up" the old task first.
4. **Confirm scope on "continue."** After context compression or a long pause, a vague "continue" should be clarified.
5. **No silent auto-continuation.** Never resume a previous task just because a summary says it is "in progress."

## Pitfalls

- **Context-compaction trap:** A deterministic fallback or compaction summary may present an "Active Task" that the user has already abandoned or never authorized. Treat it as background reference only.
- **Todo-list trap:** A todo item marked `in_progress` is not permission to keep working if the user's current message contradicts it.
- **Verb-interpretation trap:** In many languages, "check" (проверь, 检查, 確認) defaults to inspection. Do not escalate to editing without confirmation.
- **Mid-turn correction trap:** When a user sends an out-of-band correction, apply it with the same authority as the original request and stop the conflicting work.

## Integration with Other Skills

### With requirements-analysis

When a build task is genuinely requested, run `intent-validation` first, then `requirements-analysis`. Intent validation prevents starting the wrong task; requirements analysis captures the right one.

### With plan / subagent-driven-development / multi-agent-orchestration

Before creating plans or dispatching subagents, confirm the user wants implementation. These skills assume a mandate exists; `intent-validation` ensures it does.

## Quick Reference

```
User says "check"          -> report only
User says "not my task"    -> stop and clarify
Context says "continue"    -> verify before continuing
Any mismatch at all        -> clarify first
```

## References

- `references/intent-validation-checklist.md` — one-page checklist for ambiguous requests.
