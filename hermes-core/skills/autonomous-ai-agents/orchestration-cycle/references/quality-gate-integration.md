# Quality Gate Runner — Orchestrator Integration

## Mandatory Checkpoints

The orchestrator MUST call `quality_gate_runner.py` before these phases:

| Checkpoint | Before Phase | Gates Run |
|-----------|-------------|-----------|
| CP-1 | Phase 7 (Security) | Build, Test, Coverage, BA |
| CP-2 | Phase 8 (Deploy) | All gates including Security |
| CP-3 | Phase 8.5 (Acceptance) | All gates including Deployment |
| CP-FINAL | Phase 9 (Post-Deploy) | All 8 gates → GatePassport |

## Protocol

```
terminal("python3 ~/.hermes/scripts/quality_gate_runner.py --json --workdir {workdir} --cycle-id {pid} --iteration {N}")

ЕСЛИ verdict == "ALL_PASSED":
    → Продолжить к следующей фазе
    → На CP-FINAL: сохранить GatePassport для деплоя

ЕСЛИ verdict == "FAILED":
    → Извлечь fix_phase, fix_agent, diagnostic из JSON раздела "action"
    → delegate_task(fix_agent, context=diagnostic + code_paths)
    → GOTO checkpoint (перепрогнать gates)

ЕСЛИ verdict == "GATE_RUNNER_CRASHED":
    → Логировать ошибку
    → Эскалировать к пользователю
```

## BA Gate Loop-Back

BusinessAnalysisGate is always Level 0 (runs alone, before all others). If it fails:
- Each failed check has `fix_phase`, `fix_agent`, and `diagnostic`
- BA-CODE fail → fix_phase=6, fix_agent=developer
- BA-TEST fail → fix_phase=6, fix_agent=developer  
- BA-SEC fail → fix_phase=7, fix_agent=security
- BA-AC fail → fix_phase=8, fix_agent=tester

## Escalation on Stuck

Quality Gate History DB (`~/.hermes/gate_history.db`) detects:
- **Regression:** score dropped vs previous iteration → counts as 2 failures
- **Stuck:** 3 consecutive runs with same diagnostic → escalate to user

## Pre-Flight Gate vs Quality Gate Runner

| | Pre-Flight Gate | Quality Gate Runner |
|---|---|---|
| Phase | 5.5 (once) | 6+ (every iteration) |
| Checks | Infrastructure (contracts, ports, env) | Code quality (build, test, coverage, security, BA, acceptance) |
| Blocking | Implementation start | Phase progression + deploy |
