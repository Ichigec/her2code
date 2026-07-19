# Phase 10 Idea Generator — Quality Gates System (2026-06-22)

## Unheard Ideas (Design→Implementation Gaps)

### 🔴 GAP-1: `update_traceability.py` — missing; pipeline depends on it
Architecture §5.3 specifies it. Data flow §8.1 shows `terminal("python3 update_traceability.py traceability.yaml --code")`. File does not exist. Traceability matrix stays `uncovered` forever without manual updates.

### 🔴 GAP-2: AcceptanceGate returns PASS when NO tests defined
`acceptance_gate.py:139-146` — check `AC-NO-TESTS-DEFINED` has `passed=True`. Absence of acceptance tests should not be a pass.

### 🔴 GAP-3: IntegrationGate silently skips when Neo4j unavailable
`integration_gate.py:32-46` — returns `passed=True, score=1.0` with "gate skipped". Integration checks silently bypassed whenever Neo4j is down.

### 🔴 GAP-4: SecurityGate confuses "tool not installed" with "vulnerability found"
`security_gate.py:101-120` — returns `severity="High"` for missing binary. Agent loops trying to "fix code" when the fix is `pip install bandit`.

### 🟠 GAP-5: BA Gate `_parse_simple_yaml` uses placeholder values
`business_analysis_gate.py:227-234` — fallback parser sets `["placeholder"]` for all fields. Without pyyaml, BA Gate ALWAYS passes (placeholder ≠ empty).

### 🟠 GAP-6: `deploy/` directory is empty
`~/.hermes/gates/deploy/` — no files. VPS `pre-deploy-gate.sh` does not exist on disk. Layer 3 enforcement is architecture-only.

### 🟠 GAP-7: PreFlightGate not integrated into quality_gate_runner
`orchestrator_gate.py` exists separately. Not registered as a gate plugin. Two gate runners live in parallel.

### 🟡 GAP-8: Dev agents reference `terminal()` — verify tool name matches Hermes API
All 4 dev-*.md prompts instruct: `terminal("python3 ...")`. If `terminal` is not a registered Hermes tool name, Layer 2.5 enforcement is broken.

### 🟡 GAP-9: No gate for frontend (HTML/JS/CSS)
`npm audit`, `eslint`, `stylelint` not covered. TypeScript projects only get `tsc --noEmit`.

### 🟡 GAP-10: Gate History DB SQL views not created
`v_regressions`, `v_stuck`, `v_cycle_metrics` defined in architecture but `_ensure_schema()` in `history_db.py` does not create them.

### 🟡 GAP-11: `runner.py:200` uses `results[0].gate_name` as `cycle_id`
Bug — should be `cycle_id` from CLI parameter, not first gate's name.

### 🟢 GAP-12: No incremental mode for BA Gate
BA Gate always runs full. Speed mode could check only REQs touched by changed files.

## Connections (Unsynthesized Links)

| # | From | Link | To |
|---|------|------|-----|
| MC-1 | `quality_gate_runner.py` | Integrate as gate plugin | `orchestrator_gate.py` |
| MC-2 | `IntegrationGate` (codebase graph) | Cross-graph queries | Education Graph + Claw Graph |
| MC-3 | Gate history DB | Auditor read path | Auditor (#13) |
| MC-4 | `generate_traceability.py` | Auto-call after code | `update_traceability.py` (missing) |
| MC-5 | Dev agent prompts | Real tool API name | Hermes tool registry |
| MC-6 | SecurityGate | `npm audit` / container scan | TypeScript/Kotlin projects |
| MC-7 | GatePassport HMAC | Auditor integrity check | `audit.db` → `gate_history.db` |

## Pipeline Optimizations

1. **PO-1: Gate timeouts not enforced in runner** — `_run_single()` calls `gate.check()` without timeout wrapping.
2. **PO-2: Mode config not passed to gates** — `artifacts["mode"]` not set, gates can't adapt.
3. **PO-3: Three YAML parsers diverge** — runner, BA gate, and acceptance gate each have different YAML loading (with/without pyyaml fallback).
4. **PO-4: Commit-msg hook blocks ALL commits** — `pre-commit` hook doesn't auto-add GatePassport to commit message.
5. **PO-5: `--dry-run` flag missing** — no way to validate config without executing gates.

## Creative Proposals

- **CP-1:** Gate Performance Regression Detector — compare duration between cycles
- **CP-2:** Gate-as-Code — auto-generate curl acceptance tests from criteria text via LLM
- **CP-3:** Flaky Test Detector Gate — re-run failed tests N times in quality mode
- **CP-4:** Cross-Project Gate Consistency Check — compare metrics across projects
- **CP-5:** Gate Time Budget Enforcer — global timeout for all gates
- **CP-6:** Automated Fix Proposal from Gate Diagnostic — specialized fix-proposer agent
- **CP-7:** Gate Reputation System — track false positives per gate, auto-demote to WARN

## Priority Matrix

| ID | Impact | Effort | Priority |
|----|--------|--------|----------|
| GAP-2 (AcceptanceGate false-PASS) | CRITICAL | 5 LOC | P0 |
| GAP-5 (BA Gate placeholder bypass) | CRITICAL | 80 LOC | P0 |
| GAP-8 (Dev agent terminal API) | CRITICAL | 20 LOC ×4 | P0 |
| PO-4 (Commit-msg blocks all) | CRITICAL | 30 LOC | P0 |
| GAP-1 (Missing update_traceability) | HIGH | 200 LOC | P1 |
| GAP-3 (IntegrationGate silent skip) | HIGH | 10 LOC | P1 |
| PO-1 (Gate timeout enforcement) | HIGH | 40 LOC | P1 |
| MC-1 (PreFlightGate integration) | HIGH | 100 LOC | P1 |
