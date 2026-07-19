# GoT Example — OOM Killer Diagnosis: Why Hermes Desktop Crashed

## User request

«посмотри логи - почему упал hermes (причем несколько раз) в результате выполнения сессии 20260702_203717_b49469»

## Clarification

The request was ambiguous — "упал hermes" could mean backend crash, GUI crash, Android crash, or TUI gateway crash. `clarify()` was used with 5 options. User selected: **Desktop GUI (Electron) — краш самого окна/приложения**.

## Graph of Thoughts

```
ROOT: Почему Hermes Desktop (Electron) упал несколько раз во время сессии 20260702_203717_b49469?
├── Branch A: Electron crash (выбран пользователем)
│   ├── A1: Найти сессию в state.db + timestamp крашей → 20:37:17 start, 89 msgs, 36 tool calls
│   ├── A2: Найти crash dumps / Electron логи → Crashpad пустой, нет .dmp файлов
│   ├── A3: journalctl → OOM killer убил Hermes (PID 3719365) в 20:50:39
│   └── A4: Корреляция: сессия запускала llama-perplexity (22GB модель) через terminal(background=true)
├── Branch B: Backend краш (отвергнут — пользователь уточнил GUI)
│   └── B1: Backend логи использованы для контекста — сессия активна, end_reason=None
└── Branch C: Риски
    ├── C1: oom_score_adj=300 делает Hermes главной мишенью OOM killer
    └── C2: Запуск тяжёлых llama.cpp утилит через terminal() внутри Electron — бомба
```

## Verification (Step 2.5)

All Node A1 claims verified against real data:
- ✅ Session exists in state.db (not from summary) — queried directly
- ✅ Crashpad is empty — checked filesystem, no .dmp files
- ✅ OOM kills confirmed in journalctl — kernel logs, not assumptions
- ✅ Session was running llama-perplexity — read from messages table tool_calls column

Unlike the summary-trust-failure example, this GoT was built entirely from **primary sources** (kernel logs, database queries, filesystem inspection), not from context-compression summaries.

## Key Technique: OOM Forensics

The diagnostic path that identified the root cause:

1. **`journalctl` + grep "Out of memory: Killed"** → confirmed OOM, not app bug
2. **Crashpad empty** → no .dmp files = external SIGKILL, not Electron crash
3. **state.db messages query** → found `llama-perplexity` commands in session tool_calls
4. **`oom_score_adj` check** → Hermes=300, llama-perplexity=200 → Hermes killed first
5. **Timeline correlation** → 3 OOM waves matched to session activity

Full forensic workflow: → `local-model-serving/references/oom-killer-forensics.md`

## Synthesis

| Branch | Verdict | Finding |
|--------|---------|---------|
| A | Confirmed | OOM killer, not Electron bug — Crashpad empty, kernel logs show SIGKILL |
| B | Context only | Backend session was healthy — end_reason=None, still "running" |
| C | Risk materialized | `oom_score_adj=300` + 16.5GB llama-perplexity + 20 Docker containers = inevitable |

## Root Cause

`llama-perplexity` (run by the agent inside the session for PPL measurement of a 22GB model) consumed 16.5 GB RSS. Combined with 20+ Docker containers (~30-40 GB), 4 Electron apps, and 12.3/16 GB swap used, the system hit global OOM. The kernel killed Hermes first because `oom_score_adj=300` makes Electron the preferred OOM victim.

**Not an app bug.** The fix is operational (run heavy compute outside Hermes, reduce Docker footprint, increase swap), not a code change in Hermes.

## Lesson for GoT

This session demonstrates GoT working correctly:
1. **Clarify first** — 5 interpretations of "упал", user picked GUI crash
2. **Build graph with real data** — every node verified against primary sources
3. **Branch B kept for context** — backend logs confirmed session was healthy, narrowing the diagnosis
4. **Branch C predicted the cause** — oom_score_adj and heavy compute were identified as risks before full verification confirmed them
