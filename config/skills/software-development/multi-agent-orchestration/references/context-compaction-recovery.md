# Context Compaction Recovery for Long Orchestration Cycles

Use this reference when a long 10-phase orchestration cycle is interrupted by context compaction, fallback summaries, or a partially preserved todo list.

## Trigger

Apply when the next turn contains a compaction/handoff summary and the active task is still inside an orchestration cycle, especially Phase 6.5/8.5/10 quality closure.

## Recovery protocol

1. **Treat the latest user message as authoritative.** Use the compaction summary only as background continuity; do not replay completed phases unless current files prove they are missing.
2. **Read the current todo state first.** If the todo list survived, it is the fastest source of active phase state.
3. **Verify the filesystem instead of trusting the summary.** Check required code, tests, docs, and observation artifacts exist before claiming completion.
4. **Prefer evidence closure over narrative closure.** Re-run or inspect the actual verification gates relevant to the pending phase: targeted tests, full pytest, compile/typecheck, SAST/secrets scan, traceability matrix, artifact existence.
5. **Close only the preserved active item.** Do not restart Phase 0 or re-run the whole cycle unless evidence shows the project state is inconsistent.
6. **Record degraded facts explicitly.** If subagent/model routing was unavailable and the parent session substituted local verification, note it in `.observations/` and Phase 10.

## Phase 10 evidence bundle checklist

A final orchestration report should have concrete proof for each of these:

- Targeted tests for newly added modules.
- Full regression suite for the project.
- Syntax/compile check for changed Python modules.
- Type/static checks when configured (`mypy`, project linter, etc.).
- Security scan or documented fallback (`bandit`, `semgrep`, `gitleaks`, dependency scan as applicable).
- Acceptance traceability matrix mapping requirements to tests or justified deviations.
- File existence verification for every artifact named in the final answer.
- Clear caveat for any degraded orchestration mode, including which agents/phases were substituted and why objective gates still pass.

## Anti-patterns

- Declaring success from a compaction summary alone.
- Repeating already-completed phases because the summary is incomplete.
- Hiding degraded orchestration behind normal wording.
- Treating artifact writes as proof without reading/statting or running tests.
