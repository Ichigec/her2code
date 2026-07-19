# Clarify Queue Implementation (2026-06-29)

## Problem

Hermes GUI's `clarify()` dialog only stored ONE question per session in `$clarifyRequests`. When the agent called `clarify()` multiple times before the user could answer, questions 2+ were silently dropped. User saw 3 of 6 agent questions.

## Root Cause

`store/clarify.ts` used `$clarifyRequests` as `Record<string, ClarifyRequest>` — a single slot per session. Each new `clarify.request` event overwrote the previous one.

## Fix: FIFO Queue

Changed `$clarifyRequests` to `Record<string, ClarifyRequest[]>` — an array per session:

```
Before: { "session-a": { question: "Q2", ... } }    // Q1 lost
After:  { "session-a": [{ question: "Q1" }, { question: "Q2" }] }
```

### Files changed

| File | Change |
|------|--------|
| `store/clarify.ts` | `ClarifyRequest` → `ClarifyRequest[]` queue, `setClarifyRequest` pushes, `clearClarifyRequest` pops |
| `store/clarify.test.ts` | 7 tests (FIFO order, head pop, mid-queue remove, cross-session scan) |
| `clarify-tool.tsx` | Queue length badge next to question |
| `tools/clarify_tool.py` | `MAX_CHOICES` 4 → 8 |

### Queue lifecycle

```
clarify("Q1") → queue: [Q1]
GUI shows Q1 + badge "1"
clarify("Q2") → queue: [Q1, Q2]
GUI shows Q1 + badge "2"    // user hasn't answered Q1 yet
user answers Q1 → pop → queue: [Q2]
GUI shows Q2 + badge "1"
user answers Q2 → pop → queue: []
GUI returns to normal chat
```

### Key API changes

```typescript
// setClarifyRequest now PUSHES (not replaces)
setClarifyRequest(request) → appends to session queue

// clearClarifyRequest returns next requestId for auto-advance
clearClarifyRequest(id, sid) → string | null  // next request's id

// New computed: queue depth
$clarifyQueueLength → number  // shown as badge in UI
```

### Text-question pitfall

Agent wrote text questions like "Какой вариант?" instead of using `clarify()` — these bypass the queue entirely. Always use the `clarify` tool for interactive questions.
