"""
BuildGate — verify project compiles/builds successfully.

Supports: Python (compileall), Gradle (Kotlin/Java), TypeScript (tsc).
"""

from pathlib import Path

from gates.base import GatePlugin, GateResult, CheckResult
from ..utils.terminal import run
from ..utils.project_detection import detect_project_type


class BuildGate(GatePlugin):
    """Verify project compiles without errors."""

    name = "build-gate"
    description = "Project must compile/build successfully with 0 errors"

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        project_type = detect_project_type(workdir)
        incremental_scope = artifacts.get("incremental_scope", [])

        if project_type in ("python", "python-simple"):
            return self._check_python(workdir, incremental_scope)
        elif project_type == "kotlin":
            return self._check_gradle(workdir)
        elif project_type == "typescript":
            return self._check_typescript(workdir)
        elif project_type == "make":
            return self._check_make(workdir)
        else:
            return GateResult(
                gate_name=self.name,
                passed=True,
                score=1.0,
                threshold=self.threshold,
                checks=[
                    CheckResult(
                        check_id="BUILD-UNKNOWN",
                        passed=True,
                        description="No build system detected — gate skipped",
                        actual=f"Project type: {project_type}",
                        expected="Build system detected",
                    )
                ],
                duration_ms=0,
            )

    def _check_python(self, workdir: str, incremental_scope: list[str]) -> GateResult:
        start = __import__("time").monotonic()

        if incremental_scope:
            py_files = [f for f in incremental_scope if f.endswith(".py")]
            if not py_files:
                return GateResult(
                    gate_name=self.name,
                    passed=True,
                    score=1.0,
                    threshold=self.threshold,
                    checks=[
                        CheckResult(
                            check_id="BUILD-PY-INC",
                            passed=True,
                            description="No Python files in incremental scope",
                            actual="0 .py files changed",
                            expected="Compilation check",
                        )
                    ],
                    duration_ms=0,
                )
            files_arg = " ".join(py_files)
            result = run(f"python3 -m py_compile {files_arg}", workdir=workdir)
        else:
            result = run("python3 -m compileall -q . 2>&1", workdir=workdir, timeout=self.timeout)

        duration_ms = int((__import__("time").monotonic() - start) * 1000)

        checks = [
            CheckResult(
                check_id="BUILD-PY-001",
                passed=result.exit_code == 0,
                description="Python compilation check (compileall)",
                actual=f"Exit code {result.exit_code}",
                expected="Exit code 0",
                fix_phase=6,
                fix_agent="developer",
                evidence=result.stderr[:500] if result.exit_code != 0 else result.stdout[:500],
                diagnostic=self._extract_python_diagnostic(result),
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
        start = __import__("time").monotonic()
        result = run("./gradlew assembleDebug 2>&1", workdir=workdir, timeout=self.timeout)
        duration_ms = int((__import__("time").monotonic() - start) * 1000)

        passed = result.exit_code == 0
        if not passed:
            # Check for BUILD SUCCESSFUL even if exit code weird
            passed = "BUILD SUCCESSFUL" in result.stdout

        checks = [
            CheckResult(
                check_id="BUILD-GRADLE-001",
                passed=passed,
                description="Gradle assembleDebug",
                actual=f"Exit code {result.exit_code}",
                expected="BUILD SUCCESSFUL",
                fix_phase=6,
                fix_agent="developer",
                evidence=result.stdout[-500:],
                diagnostic=self._extract_gradle_diagnostic(result),
            )
        ]

        return GateResult(
            gate_name=self.name,
            passed=passed,
            score=1.0 if passed else 0.0,
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )

    def _check_typescript(self, workdir: str) -> GateResult:
        start = __import__("time").monotonic()
        result = run("npx tsc --noEmit 2>&1", workdir=workdir, timeout=self.timeout)
        duration_ms = int((__import__("time").monotonic() - start) * 1000)

        checks = [
            CheckResult(
                check_id="BUILD-TS-001",
                passed=result.exit_code == 0,
                description="TypeScript compilation (tsc --noEmit)",
                actual=f"Exit code {result.exit_code}",
                expected="Exit code 0",
                fix_phase=6,
                fix_agent="developer",
                evidence=result.stderr[:500],
                diagnostic=result.stderr[:400] if result.exit_code != 0 else "",
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

    def _check_make(self, workdir: str) -> GateResult:
        start = __import__("time").monotonic()
        result = run("make -j$(nproc) 2>&1", workdir=workdir, timeout=self.timeout)
        duration_ms = int((__import__("time").monotonic() - start) * 1000)

        checks = [
            CheckResult(
                check_id="BUILD-MAKE-001",
                passed=result.exit_code == 0,
                description="Make build",
                actual=f"Exit code {result.exit_code}",
                expected="Exit code 0",
                fix_phase=6,
                fix_agent="developer",
                evidence=result.stderr[:500],
                diagnostic=result.stderr[:400] if result.exit_code != 0 else "",
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

    @staticmethod
    def _extract_python_diagnostic(result) -> str:
        """Extract meaningful error from compileall output."""
        if result.exit_code == 0:
            return ""
        lines = result.stderr.strip().split("\n") if result.stderr else []
        errors = [l for l in lines if "Error" in l or "SyntaxError" in l or "error" in l.lower()]
        if errors:
            return f"Compilation errors: {errors[0][:300]}"
        return result.stderr[:300]

    @staticmethod
    def _extract_gradle_diagnostic(result) -> str:
        """Extract meaningful error from Gradle output."""
        if "BUILD SUCCESSFUL" in result.stdout:
            return ""
        lines = (result.stdout + result.stderr).split("\n")
        errors = [
            l.strip()
            for l in lines
            if "FAILURE" in l or "error:" in l.lower() or "Error:" in l
        ]
        if errors:
            return f"Gradle failure: {errors[0][:300]}"
        return result.stdout[-300:]
