# VCS baseline + canonical plan preflight

Session-derived pattern from Multi-Agent Runtime work: before continuing a long orchestration after context compaction or error-ledger recovery, create a small executable preflight that proves the project has a reviewable baseline and canonical plan.

## Problem signals

- `git status` fails because the project is not a repository.
- `.hermes/plans/*.md` is missing even though chat/todos reference a plan.
- Context-compaction summary preserves an old pending todo, but disk artifacts/tests may show the slice is already done.
- Error ledger has open items, but there is no rollback point before the next slice.

## Durable fix

Add a project-level preflight module (naming is project-specific) that returns a report with:

- `status`: `READY | DEGRADED | BLOCKED`
- `git_ready`: boolean
- `plan_ready`: boolean
- `ready_for_diff_review`: boolean
- `plan_path`: selected canonical plan path, if any
- `issues`: tuple/list of exact reasons

Minimum checks:

1. Run `git status --short` from the project root.
2. Run `git diff --stat` from the project root.
3. Locate `.hermes/plans/*.md`.
4. Validate required plan sections:
   - `## OWNERSHIP`
   - `## Bite-sized TDD Tasks`
   - `## Principles Checklist`
   - `## Verification Commands`

## TDD acceptance scenarios

| Scenario | Expected |
|----------|----------|
| No git repo + no plan | `BLOCKED`, `git_ready=False`, `plan_ready=False` |
| Git repo + no plan | `DEGRADED`, `git_ready=True`, `plan_ready=False` |
| Git repo + plan missing required sections | `DEGRADED`, issue names missing sections |
| Git repo + complete canonical plan | `READY`, `ready_for_diff_review=True`, no issues |

## Completion checklist

Before declaring the baseline slice complete, capture real evidence:

```bash
pytest tests/test_vcs_plan_preflight.py -q
pytest tests/ -q
python - <<'PY'
from <project>.orchestrator.vcs_plan_preflight import VcsPlanPreflight
r = VcsPlanPreflight('.').inspect()
print('status=', r.status.value)
print('ready_for_diff_review=', r.ready_for_diff_review)
print('git_ready=', r.git_ready)
print('plan_ready=', r.plan_ready)
print('issues=', r.issues)
PY
git status --short
git log --oneline -1
```

Also write `docs/tests/<slice>.md` with the evidence and update the error ledger summary row and detailed section.

## Pitfalls

- Do not continue feature/provider/plugin work while both git and canonical plan are absent; establish the baseline first.
- Do not rely on compressed-session todo state alone. Verify disk state and tests before marking a recovered task complete.
- Do not present a baseline commit as full feature success; it is only a safety gate for the next slice.
- Keep env/provider/dependency repair separate from VCS/plan repair unless the user explicitly asks to combine them.
