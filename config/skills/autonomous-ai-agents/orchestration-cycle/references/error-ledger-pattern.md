# Error Ledger Pattern — Session Note

Use this reference when an orchestration run produces multiple defects/deviations but the user wants to continue implementation instead of stopping for a full cleanup pass.

## Trigger phrase / situation

- User says: «зафиксируем все ошибки, чтобы исправить потом, и продолжим».
- Phase 10/Auditor/Critic found several issues with different risk profiles.
- Context compression may preserve stale todos, so chat state cannot be the only source of truth.

## Pattern

1. Create/update `docs/backlog/known-issues-<slug>.md`.
2. Assign stable IDs (`<SLUG>-ERR-001`), severity, status, area, symptom, evidence, next action.
3. Maintain two synchronized views:
   - top summary table for quick triage;
   - detailed issue sections with evidence, root cause, fix plan, acceptance test, resolution.
4. Add `Next-Slice Input` and `Rule for Continuing Development` at the bottom.
5. Continue only with the issue(s) that block the selected slice; do not batch unrelated debts.
6. When an issue is fixed, update both summary row and detailed section with real verification output.

## Example lifecycle

- `MAR-ERR-009` started as `OPEN`: Observer checkpoint substrate existed but no `QualityGateRunner` automated phase events/observer respawn.
- Fix slice added `RuntimeEvent` + `QualityGateRunner`.
- Verification evidence included RED import failure, targeted pytest pass, full regression, compile, and type checks.
- Ledger was updated to `RESOLVED`, and next-slice input moved to `MAR-ERR-010`.

## Compression recovery rule

If context compression says a todo is still `in_progress`, verify current disk state before acting:

```bash
pytest tests/ -q
# plus read docs/backlog/known-issues-<slug>.md and inspect relevant files
```

If ledger and tests show the slice is complete, close the stale todo and continue from `Next-Slice Input`.

## Pitfalls

- Do not leave summary table saying `RESOLVED` while detail section still says `OPEN`.
- Do not mix env mutations (`pip`, credentials, provider config), VCS changes (`git init`), and runtime feature work in one slice unless explicitly requested.
- Do not fabricate subagent/auditor results when delegation is degraded; record degraded mode and replace with real local evidence.
