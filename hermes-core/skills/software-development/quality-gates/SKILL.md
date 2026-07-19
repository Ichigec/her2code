---
name: quality-gates
description: "Design and implement mandatory, unbypassable quality gates for every code change. Covers enforcement-first architecture — git hooks, GatePassport HMAC, traceability matrix, Test-First pattern. Pavel's preference: gates must be PHYSICAL barriers LLM cannot ignore."
version: 1.0.0
metadata:
  hermes:
    tags: [quality-gates, enforcement, git-hooks, traceability, test-first, tdd]
    trigger_phrases:
      - "quality gate"
      - "gate runner"
      - "обязательные проверки"
      - "тест должен пройти"
      - "тесты обязательны"
      - "невозможно пропустить"
      - "mandatory gates"
      - "enforcement"
      - "Test-First"
      - "traceability matrix"
    pitfall_phrases:
      - "Критик плохой результат"
      - "cut everything"
      - "solo dev don't need"
      - "пропустить gate"
      - "обойти проверку"
      - "--no-verify"
      - "можно отключить"
---

# Quality Gates — Enforcement-First Architecture

## Pavel's Principle

> **Gates must be PHYSICAL barriers LLM cannot ignore.** Prompt instructions (`plan.md`) are insufficient — they can be bypassed. Real enforcement lives in: git hooks, Python code in tool implementations, HMAC-signed passports verified server-side.

## When to Load This Skill

- User says "сделай проверки обязательными", "тесты должны быть всегда", "gate не должен пропускаться"
- You're designing quality infrastructure for code changes
- User talks about traceability (REQ → code → test → security → acceptance)
- You're integrating quality checks into the orchestrator or git workflow
- User rejected a "cut everything / solo dev / YAGNI" approach — **Pavel wants robust enforcement, not minimalism**

## Architecture: 3-Layer Enforcement

```
Layer 3: VPS pre-deploy-gate.sh      ← HMAC-SHA256 GatePassport verification
Layer 2: Code-level tool enforcement  ← write_file/patch trigger gate check
Layer 1: Git hooks (filesystem)       ← pre-commit, commit-msg, pre-push
```

**Layer 1 (Git hooks)** is already built in `~/.hermes/gates/hooks/`:
- `pre-commit` — runs build-gate + test-gate (speed mode). Blocks commit on FAIL.
- `commit-msg` — requires `GatePassport:cycle_id:hmac16` in commit message. Blocks `--no-verify` bypass.
- `pre-push` — runs ALL 7 mandatory gates. Blocks push on FAIL.

**Layer 2 (Code-level)** — modify Hermes's `write_file`/`patch` implementation to call `quality_gate_runner.py` after code writes. On FAIL: revert file via `git checkout` and return diagnostic to LLM. This is the IRON LAYER — LLM physically cannot persist broken code.

**Layer 3 (VPS)** — `pre-deploy-gate.sh` on the deploy server verifies HMAC-signed GatePassport before accepting deploy. Invalid or expired → deploy rejected.

## Mandatory Gates (7 of 8)

Only **deployment-gate** is optional (requires live service). All others are in `MANDATORY_GATES`:

| Gate | Threshold | What it checks |
|------|-----------|----------------|
| build-gate | 1.0 | Project compiles (compileall/Gradle/tsc) |
| test-gate | 1.0 | All tests pass (pytest/Gradle/Jest) |
| coverage-gate | 0.80 | Line coverage ≥ threshold (pytest-cov) |
| security-gate | 1.0 | 0 Critical/High findings (bandit+semgrep+gitleaks+pip-audit) |
| integration-gate | 1.0 | Neo4j: 0 orphaned imports, 0 broken calls |
| business-analysis-gate | 1.0 | **ROOT** — every REQ has code+test+security+acceptance |
| acceptance-gate | 1.0 | HTTP acceptance tests from traceability |

## Test-First Architecture

**Pavel's requirement:** tests must be designed FROM requirements, BEFORE any code is written. Hierarchy:

```
User (approves tests)
  └─ Test (approved — IMMUTABLE without user re-approval)
       └─ Code (must conform to test — NEVER changes test)
```

Two distinct cycles:

| Cycle | Trigger | What changes | What stays |
|-------|---------|-------------|-----------|
| Test Rejection | User: "тест не нравится" | Test rewritten, user re-approves | Code |
| Code Fix | Gate: test FAIL | Code rewritten | Test (approved) |

## Fast-Fail with Topological Sort

GateScheduler in `~/.hermes/gates/runner.py`:
1. **BA Gate always runs FIRST** (Level 0, alone) — catches traceability gaps instantly
2. Remaining gates run in parallel by dependency level
3. **Fast-fail:** first FAIL cancels all remaining gates
4. Collected results from already-completed futures before returning

## 🔒 Developer Agent Enforcement (Layer 2.5)

**Pavel's key insight:** `plan.md` prompt instructions are insufficient — orchestrator LLM can ignore them. The REAL enforcement lives in the developer agent prompts themselves, where the agent that writes code CANNOT return control without passing gates.

All 4 developer agents in `~/.hermes/agents/dev/` have been modified to mandate gate runner after every code change:

| Agent | File | Rule |
|-------|------|------|
| dev-skeptic | `~/.hermes/agents/dev/dev-skeptic.md` | Gate runner after EVERY write_file/patch → loop until ALL_PASSED |
| dev-pragmatic | `~/.hermes/agents/dev/dev-pragmatic.md` | Same. FAIL → diagnostic → fix → re-run |
| dev-creative | `~/.hermes/agents/dev/dev-creative.md` | Same. 3+ failures → escalate to Maverick |
| dev-maverick | `~/.hermes/agents/dev/dev-maverick.md` | Same. 5 attempts → USER. «Even Maverick cannot skip gates.» |

Each agent's prompt now contains:

```
## 🔒 Quality Gate (MANDATORY — after EVERY code change)
**This is NON-NEGOTIABLE. You CANNOT return control without passing ALL gates.**

1. Run: terminal("python3 ~/.hermes/scripts/quality_gate_runner.py --json --mode speed --workdir <WORKDIR>")
2. Parse JSON: ALL_PASSED → proceed. FAILED → read action.diagnostic → fix code → GOTO 1.
3. Loop until ALL_PASSED. Same diagnostic ×3 → escalate.
```

**Escalation terminology changed:** All 4 agents now escalate on `Gates ALL_PASSED` / `Gates FAIL` (not `Тесты PASS/FAIL`). They pass `gate runner diagnostic (JSON action block)` to the next stage, not raw test output.

**Why this works:** The developer agent LITERALLY cannot return control to the orchestrator without passing gates — this is embedded in its workflow. Even Maverick, who breaks all rules, must loop through gate checks.

```bash
# Generate traceability from requirements
python3 ~/.hermes/scripts/generate_traceability.py docs/requirements/<slug>.md

# Run all gates — used by orchestrator and git hooks
python3 ~/.hermes/scripts/quality_gate_runner.py --json --mode speed
python3 ~/.hermes/scripts/quality_gate_runner.py --json --mode balanced

# Install git hooks on a project
cp ~/.hermes/gates/hooks/* .git/hooks/ && chmod +x .git/hooks/*
```

## Pitfalls

### Design/Architecture Pitfalls

- **Critic over-zealousness:** the Critic observer tends to recommend cutting everything for "solo dev." Pavel rejects this — he wants robust enforcement, not minimalism. When Critic says "cut Neo4j / cut IntegrationGate / cut AcceptanceGate / you're solo dev" — push back. Pavel has sophisticated infrastructure (Jetson, Neo4j graph, 29 agents, VPS, Android app).
- **`--no-verify` is NOT a bypass:** the `commit-msg` hook checks for GatePassport regardless of `--no-verify`. The `--no-verify` flag only skips `pre-commit`, not `commit-msg`.
- **BA Gate runs first, alone:** ensures traceability gaps surface immediately, before any code checks waste time.
- **AcceptanceGate in speed mode:** was previously disabled. Now mandatory. Will fail with "no service" diagnostic → orchestrator routes to `fix_phase=8, fix_agent=deployment`. This is intentional — it signals that deployment is needed.
- **GatePassport expiry:** 30 minutes. Re-run gates before deploy if passport is stale.

### Known Implementation Gaps (2026-06-22 Idea Generator)

These are **real bugs/absences** discovered in the current implementation. Fix before using in production cycles:

- **🔴 BA Gate false-PASS without pyyaml:** `business_analysis_gate.py` fallback parser `_parse_simple_yaml()` sets `["placeholder"]` for code_paths/test_ids/security_checks — placeholder values are treated as non-empty, so BA Gate **always passes** when pyyaml is not installed. Fix: either require pyyaml as a dependency, or implement full nested-list YAML parsing in the fallback.
- **🔴 AcceptanceGate false-PASS:** check `AC-NO-TESTS-DEFINED` has `passed=True`. A project with 0 acceptance tests gets a PASS — the gate is a no-op. Should either FAIL (fix_phase=1) or BA Gate should require acceptance_test_ids.
- **🔴 IntegrationGate silently skips when Neo4j unavailable:** returns `passed=True, score=1.0` with "gate skipped". Means integration checks are silently bypassed whenever Neo4j is down or misconfigured. Should either FAIL or at minimum record a WARN.
- **🔴 Commit-msg hook blocks ALL commits currently:** `pre-commit` hook runs gate runner but does NOT extract passport and auto-add it to commit message. Only `pre-push` hook saves passport to `/tmp/`. Until fixed, every code commit requires manual GatePassport insertion — workflow is broken.
- **🟠 SecurityGate confuses "tool not installed" with vulnerability:** returns `severity="High"` for missing binary (exit_code=-2). Agent loops trying to "fix code" when the fix is `pip install bandit`. Tool-not-installed should route to `fix_phase=0, fix_agent=orchestrator`.
- **🟠 Dev agent prompts reference `terminal()` tool:** all 4 dev agent files instruct `terminal("python3 ...")`. Verify this matches the actual Hermes tool name. If `terminal` is not a registered tool, Layer 2.5 enforcement (agent-level gate check) is non-functional.
- **🟠 `update_traceability.py` does not exist:** architecture docs and data flow reference it, but the file was never created. Without it, traceability matrix stays permanently `uncovered` unless manually edited.
- **🟠 `deploy/` directory is empty:** `~/.hermes/gates/deploy/` has no files. Layer 3 VPS enforcement (`pre-deploy-gate.sh`) is architecture-only — no implementation on disk.
- **🟠 `runner.py:200` — `results[0].gate_name` used as `cycle_id`:** should be the `cycle_id` string passed from CLI, not the name of the first gate. Breaks history DB grouping.
- **🟡 Gate History DB SQL views not created:** `v_regressions`, `v_stuck`, `v_cycle_metrics` are in architecture docs but `_ensure_schema()` in `history_db.py` doesn't create them. Python functions `detect_stuck()`/`detect_regression()` exist, but SQL views for direct querying are missing.
- **🟡 No gate timeout enforcement in runner:** `GateScheduler._run_single()` calls `gate.check()` without wrapping in a timeout. If a gate hangs (e.g., Gradle build takes 10 min), the entire runner blocks indefinitely.
- **🟡 Three divergent YAML loaders:** `quality_gate_runner.py`, `business_analysis_gate.py`, and `acceptance_gate.py` each have different YAML loading strategies with different pyyaml-fallback behavior. Unify into one `gates/utils/yaml_loader.py`.

## Project Files

- `~/.hermes/gates/` — gate plugins, runner, passport, history DB
- `~/.hermes/gates/config.yaml` — unified config (thresholds + modes + detection)
- `~/.hermes/gates/registry.py` — auto-discovery + `MANDATORY_GATES`
- `~/.hermes/scripts/quality_gate_runner.py` — CLI entry point
- `~/.hermes/scripts/generate_traceability.py` — REQ doc → traceability.yaml
- `~/.hermes/scripts/orchestrator_gate.py` — Pre-Flight Gate (separate; not yet integrated as gate plugin)
- `~/.hermes/gates/hooks/` — pre-commit, commit-msg, pre-push
- `/home/user/dev/codemes/quality-gates-architecture/` — architecture docs
- **PLANNED/MISSING:** `~/.hermes/scripts/update_traceability.py` — specified in architecture, not yet created
- **PLANNED/MISSING:** `~/.hermes/gates/deploy/` — empty directory; VPS pre-deploy-gate.sh not implemented

## References

- [`references/architecture-detail.md`](references/architecture-detail.md) — full architecture: GatePassport HMAC, dependency DAG, tamper-evidence table, modes
- [`references/test-first-flow.md`](references/test-first-flow.md) — Test-First Gate lifecycle: requirements → test design → user approval → code → gate check
- [`references/implementation-pitfalls.md`](references/implementation-pitfalls.md) — Import structure, property-vs-attribute, BA-Gate-Level-0, fast-fail collection, tools config injection, commit-msg bypass
- [`references/phase-10-idea-generator-2026-06-22.md`](references/phase-10-idea-generator-2026-06-22.md) — Full Phase 10 Idea Generator analysis: 12 design→implementation gaps, 7 unsynthesized connections, 5 pipeline optimizations, 7 creative proposals with priority matrix
