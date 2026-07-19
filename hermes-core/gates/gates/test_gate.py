"""
TestGate — run test suite, all tests must pass.
"""

import json
import time
from pathlib import Path

from gates.base import GatePlugin, GateResult, CheckResult
from ..utils.terminal import run


class TestGate(GatePlugin):
    """Verify all tests pass. Supports pytest, Gradle, Jest."""

    name = "test-gate"
    description = "All tests must pass with 0 failures"
    timeout = 600
    threshold = 1.0

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        workdir_path = Path(workdir)
        incremental_scope = artifacts.get("incremental_scope", [])

        # Detect test framework
        if (workdir_path / "pyproject.toml").exists() or (workdir_path / "pytest.ini").exists():
            return self._check_pytest(workdir, incremental_scope)
        elif (workdir_path / "build.gradle.kts").exists() or (workdir_path / "build.gradle").exists():
            return self._check_gradle(workdir)
        elif (workdir_path / "package.json").exists():
            return self._check_jest(workdir)
        elif list(workdir_path.rglob("test_*.py")) or list(workdir_path.rglob("*_test.py")):
            return self._check_pytest(workdir, incremental_scope)
        else:
            return GateResult(
                gate_name=self.name,
                passed=True,
                score=1.0,
                threshold=self.threshold,
                checks=[
                    CheckResult(
                        check_id="TEST-NO-FRAMEWORK",
                        passed=True,
                        description="No test framework detected — gate skipped",
                        actual="No tests found",
                        expected="Tests exist",
                    )
                ],
                duration_ms=0,
            )

    def _check_pytest(self, workdir: str, incremental_scope: list[str]) -> GateResult:
        start = time.monotonic()

        if incremental_scope:
            return self._check_pytest_incremental(workdir, incremental_scope, start)

        # Full pytest run with JSON report
        result = run(
            [
                "python3", "-m", "pytest",
                "-x", "-q",
                "--tb=short",
                "--json-report",
                "--json-report-file=/tmp/gate-test-report.json",
            ],
            workdir=workdir,
            timeout=self.timeout,
        )

        duration_ms = int((time.monotonic() - start) * 1000)

        if result.exit_code == 0:
            return GateResult(
                gate_name=self.name,
                passed=True,
                score=1.0,
                threshold=self.threshold,
                checks=[
                    CheckResult(
                        check_id="TEST-ALL-PASS",
                        passed=True,
                        description="All tests passed",
                        actual=result.stdout.split("\n")[-3] if result.stdout else "PASS",
                        expected="All tests PASS",
                        evidence=result.stdout[-500:],
                    )
                ],
                duration_ms=duration_ms,
            )

        # Parse failures
        checks = []
        try:
            with open("/tmp/gate-test-report.json") as f:
                report = json.load(f)

            for test in report.get("tests", []):
                if test.get("outcome") != "passed":
                    checks.append(
                        CheckResult(
                            check_id=f"TEST-{test.get('nodeid', 'unknown')}",
                            passed=False,
                            description=test.get("nodeid", "Unknown test"),
                            actual=test.get("outcome", "failed"),
                            expected="passed",
                            fix_phase=6,
                            fix_agent="developer",
                            code_path=test.get("nodeid", "").split("::")[0],
                            diagnostic=self._format_test_diagnostic(test),
                            evidence=test.get("call", {}).get("longrepr", "")[:500],
                        )
                    )
        except (FileNotFoundError, json.JSONDecodeError):
            checks.append(
                CheckResult(
                    check_id="TEST-PARSE-ERROR",
                    passed=False,
                    description="Failed to parse test results",
                    actual=f"Exit code {result.exit_code}",
                    expected="All tests pass (exit code 0)",
                    fix_phase=6,
                    fix_agent="developer",
                    evidence=result.stderr[:500] or result.stdout[:500],
                    diagnostic=result.stderr[:400] or result.stdout[:400],
                )
            )

        return GateResult(
            gate_name=self.name,
            passed=False,
            score=sum(1 for c in checks if c.passed) / max(len(checks), 1),
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )

    def _check_pytest_incremental(
        self, workdir: str, incremental_scope: list[str], start: float
    ) -> GateResult:
        """Run tests only for files affected by incremental scope."""
        # Find test files for changed source files
        from ..utils.project_detection import get_test_file_for_source

        test_files = []
        for file_path in incremental_scope:
            if file_path.endswith(".py") and not file_path.startswith("test"):
                test_file = get_test_file_for_source(file_path, workdir)
                if test_file:
                    test_files.append(test_file)

        if not test_files:
            return GateResult(
                gate_name=self.name,
                passed=True,
                score=1.0,
                threshold=self.threshold,
                checks=[
                    CheckResult(
                        check_id="TEST-INC-NO-TESTS",
                        passed=True,
                        description="No test files matched incremental scope",
                        actual=f"Changed files: {incremental_scope[:5]}",
                        expected="Tests for changed modules",
                    )
                ],
                duration_ms=0,
            )

        result = run(
            [
                "python3", "-m", "pytest",
                "-x", "-q",
                "--tb=short",
                "--json-report",
                "--json-report-file=/tmp/gate-test-report.json",
            ]
            + test_files,
            workdir=workdir,
            timeout=self.timeout,
        )

        duration_ms = int((time.monotonic() - start) * 1000)

        checks = [
            CheckResult(
                check_id="TEST-INC-001",
                passed=result.exit_code == 0,
                description=f"Incremental: {', '.join(test_files[:3])}",
                actual=f"Exit code {result.exit_code}",
                expected="All tests pass",
                fix_phase=6,
                fix_agent="developer",
                evidence=result.stderr[:500] or result.stdout[:500],
                diagnostic=result.stderr[:400] or result.stdout[:400],
            )
        ]

        return GateResult(
            gate_name=self.name,
            passed=result.exit_code == 0,
            score=1.0 if result.exit_code == 0 else 0.0,
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )

    def _check_gradle(self, workdir: str) -> GateResult:
        start = time.monotonic()
        result = run("./gradlew test 2>&1", workdir=workdir, timeout=self.timeout)
        duration_ms = int((time.monotonic() - start) * 1000)

        passed = result.exit_code == 0
        if not passed:
            passed = "BUILD SUCCESSFUL" in result.stdout and "FAILED" not in result.stdout

        return GateResult(
            gate_name=self.name,
            passed=passed,
            score=1.0 if passed else 0.0,
            threshold=self.threshold,
            checks=[
                CheckResult(
                    check_id="TEST-GRADLE-001",
                    passed=passed,
                    description="Gradle test",
                    actual=f"Exit code {result.exit_code}",
                    expected="BUILD SUCCESSFUL, 0 test failures",
                    fix_phase=6,
                    fix_agent="developer",
                    evidence=result.stdout[-500:],
                    diagnostic=result.stderr[:400] if not passed else "",
                )
            ],
            duration_ms=duration_ms,
        )

    def _check_jest(self, workdir: str) -> GateResult:
        start = time.monotonic()
        result = run("npx jest --passWithNoTests 2>&1", workdir=workdir, timeout=self.timeout)
        duration_ms = int((time.monotonic() - start) * 1000)

        return GateResult(
            gate_name=self.name,
            passed=result.exit_code == 0,
            score=1.0 if result.exit_code == 0 else 0.0,
            threshold=self.threshold,
            checks=[
                CheckResult(
                    check_id="TEST-JEST-001",
                    passed=result.exit_code == 0,
                    description="Jest tests",
                    actual=f"Exit code {result.exit_code}",
                    expected="Exit code 0",
                    fix_phase=6,
                    fix_agent="developer",
                    evidence=result.stdout[-500:],
                    diagnostic=result.stderr[:400] if result.exit_code != 0 else "",
                )
            ],
            duration_ms=duration_ms,
        )

    @staticmethod
    def _format_test_diagnostic(test: dict) -> str:
        """Extract useful diagnostic from a failed test."""
        nodeid = test.get("nodeid", "unknown")
        outcome = test.get("outcome", "unknown")
        call = test.get("call", {})
        longrepr = call.get("longrepr", "")

        # Try to extract assertion error
        if longrepr:
            lines = longrepr.split("\n")
            for line in lines:
                line = line.strip()
                if "AssertionError" in line or "assert" in line:
                    return f"Test {nodeid} failed ({outcome}): {line[:300]}"
            # Return last meaningful line
            for line in reversed(lines):
                line = line.strip()
                if line and not line.startswith("=") and not line.startswith("_"):
                    return f"Test {nodeid} failed: {line[:300]}"

        return f"Test {nodeid} failed ({outcome}). Run with -v for details."
