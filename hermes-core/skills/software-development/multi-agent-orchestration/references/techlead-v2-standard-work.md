# Tech Lead v2: StandardWork, Jidoka, Handoff — Reference

Implemented 2026-06-24. Agent files: `~/.hermes/agents/techlead-agent.md` (393 lines), `~/.hermes/agents/jidoka-evaluator.md` (201 lines).

---

## StandardWork Contract Format

Every task in the plan receives a StandardWork contract BEFORE delegation to a developer:

```markdown
### StandardWork #N: <Task Name>

| Поле | Значение |
|------|----------|
| **Task** | One-sentence task description |
| **Type** | implementation / bugfix / refactor / test |
| **Complexity** | L1 (trivial) … L5 (architectural change) |
| **Risk** | LOW / MEDIUM / HIGH |
| **Files** | Exact file paths |
| **Test files** | Exact test file paths |
| **Stage** | Skeptic (1) / Pragmatic (2) / Creative (3) / Maverick (4) |

#### Acceptance Criteria
1. Criterion 1 — specific and verifiable
2. ...

#### Verification
```
pytest <test_path> -x -q --cov=<module> --cov-report=term-missing
mypy <file> --ignore-missing-imports
grep -n "<import_statement>" <orchestrator.py>
```

#### Jidoka Evaluation Criteria
- [ ] All acceptance criteria met
- [ ] Import contract fulfilled (grep verification)
- [ ] No duplication with existing modules
- [ ] Edge cases handled
- [ ] Code passes KISS check (no premature abstractions)

#### Model & Budget
| Параметр | Значение |
|----------|----------|
| **Model** | kimi-k2.7-code (L1-L2) / deepseek-v4-pro (L3-L5) |
| **Context budget** | L1:10K L2:25K L3:50K L4:100K L5:150K tokens |
| **Time budget** | L1:30s L2:60s L3:120s L4:240s L5:360s |

#### Dependencies
- Depends on: SW#X, SW#Y
- Required by: SW#Z
- Parallel with: SW#A, SW#B
```

---

## Jidoka Evaluation Workflow

```
Developer returns code + handoff
           │
           ▼
    ┌──────────────┐
    │JidokaEvaluator│  ← SPAWNED AS SEPARATE sub-agent
    │ (skeptical)   │     System prompt: "Твоя задача — НЕ подтвердить
    │               │     что код работает, а НАЙТИ проблемы."
    │ Checks EVERY  │
    │ acceptance    │
    │ criterion     │
    │ individually  │
    └──────┬────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
  PASS           FAIL
    │             │
    │      Specific issues:
    │      "Criterion #3: parse('') → None. Expected ParseError."
    │      "Criterion #5: coverage 78% below 90% threshold."
    │             │
    │      Tech Lead review → ANDON escalation
    │      • Stop-the-line
    │      • Retry ≤2 with feedback
    │      • Kaizen record
    │
    ▼
  Tech Lead review (checklist) → ACCEPT → merge
```

---

## JidokaEvaluator System Prompt (injected via context)

```
Ты — Jidoka Evaluator. Твоя задача — НЕ подтвердить что код работает,
а НАЙТИ проблемы. Будь скептичен. Проверь КАЖДЫЙ acceptance criterion.
Проверь import contracts. Проверь граничные случаи.
Самооценка разработчика — игнорируй.
Верни: PASS (все критерии выполнены) или FAIL (конкретные issues с номерами критериев).
```

---

## Ownership Matrix Format

```markdown
### §OWNERSHIP
| File | Developer Stage | StandardWork # | Complexity |
|------|:---------------:|:--------------:|:----------:|
| plugins/foo/interface.py | Skeptic (1) | SW#0 | L2 |
| plugins/foo/bar.py | Skeptic (1) | SW#1 | L3 |
| plugins/foo/parser.py | Pragmatic (2) | SW#2 | L3 |
| plugins/foo/writer.py | Creative (3) | SW#3 | L4 |
| plugins/foo/orchestrator.py | TECH LEAD | — | — |
```

Rules: 1 file = 1 developer. Interfaces → Stage 1. Orchestrator → TECH LEAD merge.

---

## Import Contracts Format

```markdown
### §IMPORT CONTRACTS
| Consumer | Import | Producer | Symbol |
|----------|--------|----------|--------|
| orchestrator.py | ← | bar.py | Bar |
| orchestrator.py | ← | parser.py | Parser |
| bar.py | ← | interface.py | IFoo (Protocol) |
```

Each contract is grep-verifiable by DevOps Engineer (Phase 6a).

---

## Developer Handoff Template

```markdown
## Developer Handoff: StandardWork #N

### Твоя задача
[One-sentence from StandardWork]

### Что ты должен прочитать
- Architecture artifact: docs/architecture/<slug>.md
- Interface file: plugins/foo/interface.py

### Что ты должен произвести
- plugins/foo/module.py — implementation
- plugins/foo/tests/test_module.py — unit tests

### Import Contracts (ОБЯЗАТЕЛЬНО)
- Your module MUST be imported in orchestrator.py
- Your module imports: ...

### Acceptance Criteria
[List from StandardWork]

### Kaizen Rules
[List from Kaizen ledger relevant to this task type]

### Budget
- Model: X | Context budget: Y tokens | Time: Z seconds

### Handoff (что вернуть кроме кода)
- Concerns: что может быть проблемой в будущем?
- Deviations: где отошёл от архитектуры и почему?
- Findings: что обнаружил в кодовой базе?
- Feedback: насколько StandardWork был полезен?
```

---

## Dependency DAG Format

```
         [SW#0: interfaces.py]
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
[SW#1:    [SW#2:    [SW#3:
 bar.py]   parser.py]  writer.py]    ← PARALLEL (ReWOO-style)
    │         │         │
    └─────────┼─────────┘
              ▼
        [SW#4: orchestrator.py]
```

Parallel groups: tasks with no mutual dependencies spawn simultaneously. Max 3-5 per group.

---

## Cost-Aware Routing Table

| Complexity | Example | Model | Provider | Context Budget | Time Budget |
|:----------:|---------|-------|----------|:--------------:|:-----------:|
| L1-L2 | Typo, import, small bugfix | kimi-k2.7-code | custom:kimi | 10-25K | 30-60s |
| L3-L4 | New module, refactoring | deepseek-v4-pro | deepseek | 50-100K | 120-240s |
| L5 | Architectural change, algorithm | deepseek-v4-pro | deepseek | 150K | 360s |

---

## Kaizen Ledger Format (JSON Lines)

`.hermes/kaizen/<slug>.ledger`:

```json
{"rule_id":"KZ#1","failure":"Dev violated import contract for module Y","root_cause":"Import contract not passed in context","permanent_rule":"Always include import contracts in dev context + grep verify","injection":"pre-worker hook","date":"2026-06-24","cycle":"<slug>"}
```

Rules migrate to Education Graph (Neo4j) via Knowledge Curator post-deploy.

---

## KanbanLog Format (JSON Lines)

`.hermes/kanban/<slug>.log`:

```json
{"event":"plan_start","ts":"...","task_count":7,"dev_count":3}
{"event":"sw_created","ts":"...","sw_id":"SW#0","file":"plugins/foo/interface.py"}
{"event":"checkpoint","ts":"...","dag_state":{"completed":["SW#0"],"in_progress":["SW#1","SW#2"],"pending":["SW#3","SW#4"]}}
{"event":"jidoka_eval","ts":"...","sw_id":"SW#1","verdict":"PASS"}
{"event":"andon_trigger","ts":"...","sw_id":"SW#2","severity":"HIGH","reason":"Import contract broken"}
```

Resume from last checkpoint on crash.
