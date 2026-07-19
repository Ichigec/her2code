"""
CoverageGate — verify code coverage meets threshold.
"""

import json
import time
from pathlib import Path

from gates.base import GatePlugin, GateResult, CheckResult
from ..utils.terminal import run


class CoverageGate(GatePlugin):
    """Verify line coverage ≥ threshold (default 80%)."""

    name = "coverage-gate"
    description = "Code coverage must meet threshold (default ≥80%)"
    threshold = 0.80
    timeout = 600

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        start = time.monotonic()
        check_changed_only = artifacts.get("check_changed_only", False)
        changed_files = artifacts.get("changed_files", [])

        # Build pytest-cov command
        cmd = [
            "python3", "-m", "pytest",
            "--cov=.",
            "--cov-report=json:/tmp/coverage.json",
            "--cov-report=term",
            "-x", "-q",
        ]

        if check_changed_only and changed_files:
            from ..utils.project_detection import get_test_file_for_source
            test_files = []
            for f in changed_files:
                tf = get_test_file_for_source(f, workdir)
                if tf:
                    test_files.append(tf)
            if test_files:
                cmd.extend(test_files)

        result = run(cmd, workdir=workdir, timeout=self.timeout)
        duration_ms = int((time.monotonic() - start) * 1000)

        if result.exit_code != 0 and "no tests ran" in (result.stdout + result.stderr).lower():
            return GateResult(
                gate_name=self.name,
                passed=True,
                score=1.0,
                threshold=self.threshold,
                checks=[CheckResult(
                    check_id="COV-NO-TESTS",
                    passed=True,
                    description="No tests to measure coverage",
                    actual="No tests ran",
                    expected="Coverage from test run",
                )],
                duration_ms=duration_ms,
            )

        # Parse coverage JSON
        try:
            with open("/tmp/coverage.json") as f:
                cov_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return GateResult(
                gate_name=self.name,
                passed=False,
                score=0.0,
                threshold=self.threshold,
                checks=[CheckResult(
                    check_id="COV-PARSE-ERROR",
                    passed=False,
                    description="Failed to parse coverage data",
                    actual="coverage.json not found or invalid",
                    expected=f"Coverage report with line rate ≥ {self.threshold:.0%}",
                    fix_phase=6,
                    fix_agent="developer",
                    diagnostic="pytest-cov did not produce coverage.json. Install pytest-cov.",
                    evidence=result.stderr[:500],
                )],
                duration_ms=duration_ms,
            )

        total_rate = cov_data.get("totals", {}).get("percent_covered", 0) / 100.0
        checks = []

        # Overall coverage check
        passed = total_rate >= self.threshold
        checks.append(CheckResult(
            check_id="COV-OVERALL",
            passed=passed,
            description=f"Overall line coverage ({total_rate:.1%})",
            actual=f"{total_rate:.1%}",
            expected=f"≥ {self.threshold:.0%}",
            fix_phase=6,
            fix_agent="developer",
            diagnostic="" if passed else (
                f"Coverage {total_rate:.1%} below threshold {self.threshold:.0%}. "
                f"Add tests to uncovered files."
            ),
            evidence=f"Line rate: {total_rate:.1%}, "
                     f"Covered lines: {cov_data.get('totals', {}).get('covered_lines', '?')}, "
                     f"Total lines: {cov_data.get('totals', {}).get('num_statements', '?')}",
        ))

        # Per-file checks (for quality mode)
        per_file_threshold = artifacts.get("per_file_threshold", 0.0)
        if per_file_threshold > 0:
            for file_path, file_data in cov_data.get("files", {}).items():
                file_rate = file_data.get("summary", {}).get("percent_covered", 0) / 100.0
                if file_rate < per_file_threshold:
                    checks.append(CheckResult(
                        check_id=f"COV-FILE-{Path(file_path).name}",
                        passed=False,
                        description=f"Coverage of {file_path}: {file_rate:.1%}",
                        actual=f"{file_rate:.1%}",
                        expected=f"≥ {per_file_threshold:.0%} per file",
                        fix_phase=6,
                        fix_agent="developer",
                        code_path=file_path,
                        diagnostic=f"File {file_path} coverage {file_rate:.1%} below per-file threshold {per_file_threshold:.0%}.",
                    ))

        return GateResult(
            gate_name=self.name,
            passed=all(c.passed for c in checks),
            score=sum(1 for c in checks if c.passed) / max(len(checks), 1),
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )
