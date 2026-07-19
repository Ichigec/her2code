# Degraded Orchestration Mode — when delegate_task/provider routing fails

Session pattern captured from Multi-Agent Runtime Phase 2 (2026-06-15).

## Trigger

Use degraded mode only when the user explicitly asked the orchestrator to continue the full cycle and one of these blocks normal delegation:

- `delegate_task` children fail because the requested provider/model route returns an API error.
- Batch delegation repeatedly interrupts children before they can produce artifacts.
- Required role routing is specified, but Hermes' current `delegate_task` interface cannot enforce the requested per-child model/provider.

Do **not** treat this as a normal shortcut. It is an exception path.

## Rule

Never silently skip the phase. Either:

1. re-launch on a verified route, or
2. if the user explicitly asked to continue, run the phase locally in degraded mode and record the deviation.

## Required degraded-mode safeguards

1. **Create a visible deviation note** in `.observations/` or `docs/deviation-log.md`:
   - which agent/phase could not run normally,
   - exact blocker,
   - what local substitute was used,
   - what evidence will compensate for missing independent subagent review.
2. **Keep role boundaries logically separated** even if one orchestrator session executes them:
   - separate preflight, implementation, security, acceptance, and final report artifacts;
   - do not merge all reasoning into an untraceable narrative.
3. **Use real verification output, not claims**:
   - full test suite output,
   - targeted tests,
   - acceptance smoke command output,
   - scanner output for SAST/secret checks where applicable.
4. **Record line/file inventory** for new artifacts if git is unavailable.
5. **Final report must say DEGRADED where applicable**, but may still return PASS if objective gates pass.

## Example evidence bundle

```text
## full regression pytest
113 passed in 0.25s

## targeted phase pytest
20 passed in 0.12s

## acceptance smoke
smoke=PASS
checkpoint_chain_length=2
save_ms_p95=0.054
load_ms_p95=0.005

## SAST/secrets
bandit: clean
semgrep: clean
gitleaks: no leaks found
```

## Anti-patterns

- Saying “subagents reviewed it” when delegation actually failed.
- Continuing without a written deviation note.
- Treating degraded mode as permission to skip TDD, SAST, or acceptance traceability.
- Asking Pavel to verify manually when terminal/ADB/curl/pytest can verify it autonomously.

## Recovery after degraded mode

At the start of the next phase, attempt to restore normal orchestration:

1. verify the provider/model route,
2. run a small single-child delegate_task smoke before launching a batch,
3. if successful, respawn Auditor/Critic/Idea Generator with the degraded-mode artifact as prior context.
