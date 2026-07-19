# Managerial Oversight Checklist

Orchestrator runs these 6 checks at EVERY quality gate. Red flag = return agent for rework.

## 1. Requirement propagation
- **When**: Phase 1 → 2 → 3 → 4 → 8.5
- **Check**: Every acceptance criterion from Requirements doc appears in System Analysis, Architecture, and Tester's traceability matrix
- **Red flag**: «Пользователь хотел автономные тесты» — а в `docs/tests/<slug>.md` нет traceability matrix с этим требованием
- **Action**: Return to Tester with: «Requirement REQ-X from docs/requirements/<slug>.md is missing in your test matrix. Add test cases for it.»

## 2. Root cause resolution
- **When**: Phase 2 → 6 → 8.5
- **Check**: Developer's code addresses the 5-Whys root cause, not a symptom
- **Red flag**: Fixed the symptom (e.g., restarted service), root cause untouched (e.g., memory leak)
- **Action**: Return to Developer with: «This fix addresses the symptom, not the root cause. Re-read System Analysis §Root Cause and fix the actual cause.»

## 3. Goal tree completion
- **When**: Phase 2 → 6.5 → 8.5
- **Check**: Each sub-goal from the goal tree has corresponding code AND a passing test
- **Red flag**: Sub-goal exists in System Analysis but has no implementation or no test coverage
- **Action**: Return to Tech Lead with: «Sub-goal X from System Analysis goal tree is not addressed. Assign to a developer.»

## 4. Context completeness
- **When**: Every `delegate_task()` call
- **Check**: The context you pass contains ALL requirements that agent needs. Re-read the source artifact before delegating.
- **Red flag**: Agent asks «what are the acceptance criteria?» when they're in Requirements doc already
- **Action**: Re-delegate with full context. Do NOT answer the agent — fix the context.

## 5. Agent accountability
- **When**: After every phase
- **Check**: Read the agent's output artifact. Did they do what you asked? Or did they produce an empty file or claim «done» without evidence?
- **Red flag**: Artifact file exists but content is generic/empty; or agent summary says «completed» but no file was written
- **Action**: Return to agent with: «Your artifact at [path] does not contain the requested output. Re-do and write the complete artifact.»

## 6. Tester autonomy
- **When**: Phase 8.5
- **Check**: Tester's report has real terminal/browser output for every test. No «проверь сам», no «test it yourself», no `clarify` usage.
- **Red flag**: Test report contains «пользователь должен проверить», or `UNTESTABLE` without a one-sentence justification, or uses `clarify`
- **Action**: 🔴 Critical — return to Tester with: «You asked the user to test. This is forbidden. Re-run all tests autonomously using terminal/browser/read_file.»

## 7. Reality check (v1.5)
- **When**: After phases 6 (Implement), 8 (Deployment), 8.5 (Acceptance Test)
- **Check**: Оркестратор САМ запускает проверочную команду: `curl health`, `git diff --stat`, build. Не верит сабагенту на слово.
- **Red flag**: Sub-agent claims «server running on port 8643» but `curl localhost:8643/health` returns nothing or error
- **Action**: Return to agent with the specific command you ran and its output: «I ran `curl localhost:8643/health` and got `Connection refused`. Your claim is false. Fix and re-verify.»
