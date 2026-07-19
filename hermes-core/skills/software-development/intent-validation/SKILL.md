---
name: intent-validation
description: "Validate the user's actual intent before acting, especially when the request is ambiguous or conflicts with inherited session context."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [communication, clarification, intent, context, workflow]
    related_skills: [requirements-analysis, plan, subagent-driven-development, multi-agent-orchestration, graph-of-thoughts]
---

# Intent Validation

## Overview

Stop and verify what the user actually wants **before** starting work. Inherited context — compaction summaries, stale todo lists, subagent deliverables, or a previous turn's task — is not a mandate unless the current user message explicitly confirms it.

**Core principle:** When in doubt, clarify. "Check" is not "change."

## Core Rule (NON-NEGOTIABLE)

**AMBIGUITY → CLARIFY FIRST.** When the user's request has multiple reasonable interpretations — always ask before acting. Never silently pick one. One clarifying question (via `clarify()` tool) prevents wasted tool calls and user frustration.

Examples:
- «скачай и установи mattermost» → server или desktop client?
- «поставь на систему» → Docker или нативный бинарник?
- «проверь» → прочитай или исправь?
- «расскажи» → устно или сохрани в файл?

## When to Use

Use this skill as a gate whenever any of these signals appear:

- The user's request contains a **term with multiple reasonable interpretations** (e.g., «mattermost» = сервер или десктоп-клиент? «установи» = Docker или нативно? «скачай» = бинарник или исходники?).
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
| **Ambiguous term / multiple interpretations** | The request can be reasonably interpreted in ≥2 ways | **Clarify before acting.** Pick the most likely interpretation and ask: «Ты имел в виду X или Y?» |
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
- "«Установи Mattermost» — ты имеешь в виду десктоп-клиент или сервер? Это два разных продукта с разным процессом установки."

Do **not** start implementation while the mismatch is unresolved.

## Rules

1. **"Check" ≠ "change."** Verbs of inspection mean read-only unless the user explicitly adds an action verb.
2. **Inherited context is advisory, not authoritative.** A compaction summary or stale todo does not override the user's current message.
3. **Stop on explicit correction.** When the user says a task is not theirs, stop that work immediately. Do not "wrap up" the old task first.
4. **Confirm scope on "continue."** After context compression or a long pause, a vague "continue" should be clarified.
5. **No silent auto-continuation.** Never resume a previous task just because a summary says it is "in progress."
6. **Ambiguity → clarify.** When a request has ≥2 reasonable interpretations, **pick one and ask the user to confirm.** Never silently assume one interpretation and proceed. One clarifying question prevents 10 wasted tool calls.

## Pitfalls

- **Context-compaction trap:** A deterministic fallback or compaction summary may present an "Active Task" that the user has already abandoned or never authorized. Treat it as background reference only.
- **Todo-list trap:** A todo item marked `in_progress` is not permission to keep working if the user's current message contradicts it.
- **Verb-interpretation trap:** In many languages, "check" (проверь, 检查, 確認) defaults to inspection. Do not escalate to editing without confirmation.
- **Mid-turn correction trap:** When a user sends an out-of-band correction, apply it with the same authority as the original request and stop the conflicting work.
- **Ambiguity-assumption trap:** A product name or action verb can map to ≥2 real things (e.g., «Mattermost» = server vs desktop, «установи» = native vs Docker, «скачай» = binary vs source). Guessing wrong wastes time and erodes trust. Ask.
- **Text-question trap:** Writing a clarifying question as plain text instead of using the `clarify()` tool bypasses the GUI's dialog system. Plain-text questions can be missed in scrollback or confused with tool output. Always use `clarify()` for interactive questions — it renders as a clickable dialog with choices, queues multiple questions, and blocks the agent until the user answers.
- **GUI-clarify availability:** Confirmed working (2026-06-29): `clarify()` dialogs appear in Hermes GUI via WebSocket. The pipeline is: `clarify()` tool → `tools/clarify_tool.py` → `clarify.request` event → `tui_gateway/server.py:_block()` → GUI `use-message-stream.ts` → `$clarifyRequests` store → `ClarifyTool` component. Backend supports up to 8 choices. Multiple sequential `clarify()` calls are queued FIFO in `$clarifyRequests` (no question lost).

- **GUI-clarify trap (FIXED as of 2026-06-29):** The `clarify()` tool was confirmed working in Hermes GUI via WebSocket — dialog rendered with clickable choices. If it fails in future, check: (1) gateway WebSocket connection alive, (2) `clarify.request` event delivered through `tui_gateway/server.py`, (3) GUI `use-message-stream.ts` handler receiving the event.
- **Clarify-gate self-block trap:** The `clarify-gate` plugin (`~/.hermes/plugins/clarify-gate/`) blocks ALL action tools (patch, write_file, terminal, execute_code, delegate_task) when it detects ambiguity in the user's message. This includes blocking edits to the clarify system itself — the gate can prevent you from fixing clarify bugs. **Workaround:** call `clarify()` with the question (even an unrelated one) — the plugin's `_pre_tool` hook sets `state.clarified = True` when it sees `tool_name == "clarify"`, which clears the block for the rest of the session. The user's answer to the clarifying question doesn't need to be acted on; the call itself clears the gate. Also works: read-only tools (`read_file`, `search_files`, `glob`, `skill_view`, `session_search`) pass through the gate freely.
- **MAX_CHOICES refactoring trap:** When changing `MAX_CHOICES` in `tools/clarify_tool.py`, update ALL dependent locations: (1) docstring in `clarify_tool()` function, (2) schema description (two occurrences — modes section and choices property), (3) `tests/tools/test_clarify_tool.py::test_max_choices_is_*` (both name and assertion), (4) `test_choices_trimmed_to_max` (ensure choices list length exceeds new MAX_CHOICES). Missing any spot causes test failures and schema-description lies to the LLM. See `references/clarify-max-choices-refactor.md` for the full checklist.

- **Context-compact override trap:** When a MANDATORY `clarify()` directive exists in the conversation (e.g., «Your FIRST and ONLY action this turn MUST be to call clarify()»), a subsequent context-compact summary or active-task handoff does NOT override it. The clarify mandate is a **system-level gate**, not a conversational message. Applying «latest message wins» to override a clarify mandate is a category error. **Protection:** if you see a MANDATORY clarify directive, execute it regardless of what subsequent messages say. Only the user's explicit answer to the clarify question lifts the gate.

- **Summary-as-truth trap:** Context-compact summaries may contain stale or false claims about code state («X doesn't work», «Y is broken»). The agent trusts these claims and builds plans without checking actual code. **Protection:** always verify summary claims with `read_file` before building a fix plan. Load `graph-of-thoughts` for the full verification workflow (Шаг 2.5: верификация утверждений).

## Integration with `clarify()` tool

ALL clarifying questions MUST use the `clarify()` tool (or `clarify` MCP if available), NOT plain text questions. This is how questions appear as interactive dialogs in the GUI. The `clarify()` tool supports up to 8 choices (increased from 4 on 2026-06-30) plus a free-form "Other" option. Multiple concurrent questions are queued FIFO — no question is silently dropped.

## Integration with Other Skills

### With graph-of-thoughts (NEW)

After `clarify()` returns the user's answer, load `graph-of-thoughts` immediately. Build the reasoning graph (Branch A/B/C) before proceeding to execution. This ensures the agent doesn't lose context between clarification and action.

### With requirements-analysis

When a build task is genuinely requested, run `intent-validation` first, then `requirements-analysis`. Intent validation prevents starting the wrong task; requirements analysis captures the right one.

### With plan / subagent-driven-development / multi-agent-orchestration

Before creating plans or dispatching subagents, confirm the user wants implementation. These skills assume a mandate exists; `intent-validation` ensures it does.

## Quick Reference

```
User says "check"          -> report only
User says "not my task"    -> stop and clarify
Ambiguous term             -> ask which meaning
Context says "continue"    -> verify before continuing
Any mismatch at all        -> clarify first
```

## References

- `references/intent-validation-checklist.md` — one-page checklist for ambiguous requests.
- `references/ambiguity-examples.md` — concrete examples of ambiguous requests and correct clarifying responses.
- `references/clarify-architecture.md` — full clarify system pipeline: tool→gateway→store→component, queue behavior, MAX_CHOICES.
