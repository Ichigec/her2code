#!/usr/bin/env python3
"""
Quality Gate Runner — mandatory quality gates CLI.

Usage:
    python3 quality_gate_runner.py [--json] [--workdir PATH] [--mode MODE]

Exit codes:
    0 — ALL_PASSED
    1 — FAILED
    2 — GATE_RUNNER_CRASHED
    3 — GATE_RUNNER_TAMPERED
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path


def _setup_path():
    """Add gates package to sys.path."""
    hermes_dir = Path(__file__).resolve().parent.parent  # ~/.hermes/
    if str(hermes_dir) not in sys.path:
        sys.path.insert(0, str(hermes_dir))


def _verify_self_integrity() -> bool:
    """Verify that this script has not been tampered with."""
    runner_path = Path(__file__).resolve()
    hash_file = Path.home() / ".hermes" / "gates" / ".runner-hash"

    actual_hash = _sha256_file(runner_path)

    if not hash_file.exists():
        # First run — store reference hash
        hash_file.parent.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(actual_hash)
        hash_file.chmod(0o600)
        return True

    expected_hash = hash_file.read_text().strip()
    if actual_hash != expected_hash:
        print(json.dumps({
            "verdict": "GATE_RUNNER_TAMPERED",
            "error": (
                "Gate runner has been modified since last verified run. "
                "Integrity check failed. Restore from backup or reinstall."
            ),
            "action": {
                "fix_phase": 0,
                "fix_agent": "orchestrator",
                "diagnostic": "Gate runner tampered. SHA256 mismatch.",
            },
        }))
        return False

    # Update hash (normal — e.g. after updates)
    hash_file.write_text(actual_hash)
    return True


def _sha256_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_yaml_config(path: str) -> dict:
    """Load YAML config, falling back to JSON."""
    content = Path(path).read_text()
    if content.strip().startswith("{"):
        return json.loads(content)
    try:
        import yaml
        return yaml.safe_load(content)
    except ImportError:
        # Minimal YAML: just return empty for now
        print("  ⚠ pyyaml not installed, using default config", file=sys.stderr)
        return {}


def main():
    _setup_path()

    # Self-integrity check
    if not _verify_self_integrity():
        sys.exit(3)

    # ── Parse args ──────────────────────────────────────────────────────────
    json_mode = "--json" in sys.argv
    workdir = os.getcwd()
    mode = "balanced"
    cycle_id = ""
    iteration = 0

    for i, arg in enumerate(sys.argv):
        if arg == "--workdir" and i + 1 < len(sys.argv):
            workdir = sys.argv[i + 1]
        elif arg == "--mode" and i + 1 < len(sys.argv):
            mode = sys.argv[i + 1]
        elif arg == "--cycle-id" and i + 1 < len(sys.argv):
            cycle_id = sys.argv[i + 1]
        elif arg == "--iteration" and i + 1 < len(sys.argv):
            iteration = int(sys.argv[i + 1])

    if not cycle_id:
        cycle_id = f"{Path(workdir).name}_{time.strftime('%Y%m%d_%H%M%S')}"

    # ── Load config ─────────────────────────────────────────────────────────
    config_path = Path.home() / ".hermes" / "gates" / "config.yaml"
    config = {}
    if config_path.exists():
        config = _load_yaml_config(str(config_path))

    # ── Run gates ───────────────────────────────────────────────────────────
    try:
        from gates.runner import GateScheduler
        from gates.passport import generate_passport
        from gates.history_db import record_run

        scheduler = GateScheduler(config, mode)

        # Build artifacts dict
        artifacts = {
            "cycle_id": cycle_id,
            "iteration": iteration,
            "mode": mode,
        }

        # Load traceability if it exists
        traceability_paths = [
            Path(workdir) / "traceability.yaml",
            Path(workdir) / "docs" / "traceability.yaml",
        ]
        for tp in traceability_paths:
            if tp.exists():
                try:
                    artifacts["traceability"] = _load_yaml_config(str(tp))
                    break
                except Exception:
                    pass

        # Run all gates
        verdict = scheduler.run_all(artifacts, workdir)
        verdict.cycle_id = cycle_id
        verdict.iteration = iteration

        # Generate passport if all passed
        if verdict.verdict == "ALL_PASSED":
            verdict.passport = generate_passport(verdict.to_dict(), workdir)

        # Record to history DB
        try:
            record_run(verdict.to_dict())
        except Exception as e:
            if json_mode:
                print(f"  ⚠ History DB write failed: {e}", file=sys.stderr)

        # Output
        if json_mode:
            print(json.dumps(verdict.to_dict(), indent=2, ensure_ascii=False))
        else:
            _print_human_report(verdict)

        sys.exit(0 if verdict.verdict == "ALL_PASSED" else 1)

    except Exception as e:
        error_verdict = {
            "verdict": "GATE_RUNNER_CRASHED",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "workdir": workdir,
            "cycle_id": cycle_id,
            "error": str(e),
            "traceback": traceback.format_exc()[-1000:],
            "action": {
                "fix_phase": 0,
                "fix_agent": "orchestrator",
                "diagnostic": f"Gate runner crashed: {e}. Check logs.",
            },
        }
        if json_mode:
            print(json.dumps(error_verdict, indent=2, ensure_ascii=False))
        else:
            print(f"\n🔥 GATE RUNNER CRASHED: {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        sys.exit(2)


def _print_human_report(verdict):
    """Print human-readable report."""
    from gates.base import GateVerdict

    print()
    print("=" * 60)
    print("  QUALITY GATE REPORT")
    print("=" * 60)
    print(f"  Verdict: {verdict.verdict}")
    print(f"  Workdir: {verdict.workdir}")
    print(f"  Cycle:   {verdict.cycle_id}")
    print(f"  Gates:   {verdict.passed_gates}/{verdict.total_gates} passed")
    print("-" * 60)

    for gate_result in verdict.gates:
        status = "✅" if gate_result.passed else "❌"
        print(f"\n  {status} {gate_result.gate_name} "
              f"(score: {gate_result.score:.0%}, "
              f"threshold: {gate_result.threshold:.0%}, "
              f"{gate_result.duration_ms}ms)")

        if gate_result.error:
            print(f"     ⚠ Gate error: {gate_result.error[:200]}")

        for check in gate_result.failed_checks[:5]:  # Show first 5 failures
            print(f"     ✗ {check.check_id}: {check.description}")
            print(f"       Actual:   {check.actual[:120]}")
            print(f"       Expected: {check.expected[:120]}")
            if check.diagnostic:
                print(f"       Fix:      {check.diagnostic[:200]}")

        if len(gate_result.failed_checks) > 5:
            print(f"     ... and {len(gate_result.failed_checks) - 5} more failures")

    print()
    print("-" * 60)
    if verdict.verdict == "ALL_PASSED":
        print("  VERDICT: ALL CHECKS PASSED ✅")
        if verdict.passport:
            from gates.passport import format_passport_string
            print(f"  Passport: {format_passport_string(verdict.passport)}")
    else:
        print(f"  VERDICT: {verdict.failed_gates} GATE(S) FAILED ❌")
        if hasattr(verdict, '_build_action') or hasattr(verdict, 'to_dict'):
            action = verdict.to_dict().get("action", {})
            if action:
                print(f"  Fix phase: {action.get('fix_phase', '?')}")
                print(f"  Fix agent: {action.get('fix_agent', '?')}")
                print(f"  Diagnostic: {action.get('diagnostic', '')[:200]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
