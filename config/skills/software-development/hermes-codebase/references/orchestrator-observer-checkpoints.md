# Orchestrator Observer Checkpoints

Pattern for feeding phase artifacts to Auditor, Critic, and Idea Generator
**after every orchestration phase** — not just at Phase 10.

## Why checkpoints matter

The three observers (Auditor, Critic, Idea Generator) are spawned at Phase 1 as
silent leaf agents. Without checkpoints, they have NO access to phase artifacts
until Phase 10 — by then, they've missed 9 phases of data and can only produce
shallow reports.

Checkpoints give each observer the artifact AS IT IS PRODUCED, allowing them to
accumulate rich observations across the entire cycle.

## Pattern

After every phase delegation returns AND the artifact passes structural validation:

```
# 1. Read the artifact yourself
read_file("<artifact_path>")

# 2. Batch-delegate to all three observers (parallel, fire-and-forget)
delegate_task(
  tasks=[
    {
      goal: "Auditor checkpoint: проанализируй артефакт фазы N.",
      context: "Фаза: <name>. Артефакт: <path>. Краткое содержание: <2-3 sentences>. Прочитай и запиши: качество делегирования, полнота контекста, потери информации, ошибки.",
      toolsets: ["file_ro", "search_files", "session_search"],
      model: "gpt-5.5",
      provider: "custom:openai"
    },
    {
      goal: "Critic checkpoint: проанализируй артефакт фазы N.",
      context: "Фаза: <name>. Артефакт: <path>. Содержание: <summary>. Три вопроса: (1) Что лишнее? (2) Что мешает? (3) Почему появилось?",
      toolsets: ["file_ro", "search_files", "session_search"],
      model: "gpt-5.5",
      provider: "custom:openai"
    },
    {
      goal: "Idea Generator checkpoint: найди идеи в артефакте фазы N.",
      context: "Фаза: <name>. Артефакт: <path>. Содержание: <summary>. Вопросы: (1) Какие идеи не услышаны? (2) Кого с кем связать? (3) Где взять недостающую информацию? (4) Как оптимизировать пайплайн?",
      toolsets: ["file_ro", "search_files", "session_search", "memory", "skills"],
      model: "gpt-5.5",
      provider: "custom:openai"
    }
  ]
)
```

## Rules

- **Fire-and-forget** — don't wait for checkpoint results before next phase
- **After structural validation** — only feed the artifact if it passes the mandatory sections check
- **Include a summary** — 2-3 sentences in the context so observers don't need to read the entire artifact cold
- **Each observer accumulates** — they build their report incrementally, synthesise at Phase 10
- **Checkpoint failures are non-blocking** — log and continue

## Phase → Artifact mapping

| Phase | Artifact | Observer focus |
|-------|----------|----------------|
| 1 | `docs/requirements/<slug>.md` | Completeness, actor coverage, NFR specificity |
| 2 | `docs/system-analysis/<slug>.md` | Root cause depth, goal tree, WSM accuracy, **codebase-guardrail conflicts** |
| 3 | `docs/research/<slug>.md` | Source quality, citation gaps, RQ coverage |
| 4 | `docs/architecture/<slug>.md` | Module boundaries, over-engineering risk, missing contracts |
| 5 | `.hermes/plans/<ts>-<slug>.md` | Task granularity, file ownership, YAGNI violations |
| 6 | Code (`git diff --stat`) | Dead code, complexity, copy-paste |
| 6.5 | Verification report | False positives, missed deviations |
| 7 | SAST report | False positives, missed vulnerabilities |
| 8 | Deployment log | Configuration drift, missing health checks |
| 8.5 | `docs/tests/<slug>.md` | Coverage gaps, untestable excuses, traceability holes |
| 9 | `docs/research-post/<slug>.md` | Hypothesis validity, surprise quality, evidence strength |

## Location in plan.md

The checkpoint section lives in `~/.hermes/agents/plan.md`, between "Context flow"
and "Delegate failure protocol", as `### Observer checkpoints — MANDATORY after EVERY phase`.

## Phase-specific methodology notes

For the full Idea Generator methodology adapted per phase — including the Phase 2
codebase-cross-referencing technique, output format, and pitfalls — see
[`idea-generator-checkpoint-methodology.md`](idea-generator-checkpoint-methodology.md).

Phase 2 (System Analysis) in particular benefits from **real codebase verification**:
the SysAnalysis artifact often makes architectural decisions (D1–D8) that sound
internally consistent but conflict with existing code guardrails (e.g. claiming a
"system provider" will coexist with external plugins when `MemoryManager.add_provider()`
has a `_has_external` lock). Always cross-reference Phase 2 decisions against the
actual implementation files listed in the methodology reference.
