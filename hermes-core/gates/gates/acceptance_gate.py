"""
AcceptanceGate — run acceptance tests against deployed service.

Tests are defined in traceability.yaml as acceptance_test_ids with curl commands.
"""

import json
import time
from pathlib import Path

from gates.base import GatePlugin, GateResult, CheckResult
from ..utils.terminal import run


class AcceptanceGate(GatePlugin):
    """Run HTTP acceptance tests against deployed service."""

    name = "acceptance-gate"
    description = "All acceptance criteria must pass against deployed service"
    threshold = 1.0
    timeout = 120

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        # Get deployment URL
        base_url = artifacts.get("deployment_url", "")
        if not base_url:
            base_url = self._find_base_url(artifacts, workdir)

        if not base_url:
            return GateResult(
                gate_name=self.name,
                passed=False,
                score=0.0,
                threshold=self.threshold,
                checks=[CheckResult(
                    check_id="AC-NO-BASE-URL",
                    passed=False,
                    description="No deployment URL configured",
                    actual="No base_url in artifacts or config",
                    expected="Deployment URL (e.g. http://localhost:8000)",
                    fix_phase=8,
                    fix_agent="deployment",
                    diagnostic="Set deployment_url in artifacts or base_url in config.yaml.",
                )],
                duration_ms=0,
            )

        # Load traceability for acceptance tests
        traceability = artifacts.get("traceability")
        if not traceability:
            return GateResult(
                gate_name=self.name,
                passed=False,
                score=0.0,
                threshold=self.threshold,
                checks=[CheckResult(
                    check_id="AC-NO-TRACEABILITY",
                    passed=False,
                    description="No traceability matrix",
                    actual="traceability not in artifacts",
                    expected="Traceability matrix with acceptance_test_ids",
                    fix_phase=1,
                    fix_agent="requirements",
                    diagnostic="Generate traceability matrix first.",
                )],
                duration_ms=0,
            )

        start = time.monotonic()
        checks = []
        requirements = traceability.get("requirements", [])

        for req in requirements:
            req_id = req.get("id", "unknown")
            for ac_test in req.get("acceptance_test_ids", []):
                # Skip disabled tests
                if not ac_test.get("enabled", True):
                    continue

                test_id = ac_test.get("id", f"AC-{req_id}")
                command = ac_test.get("command", "")
                expected_status = ac_test.get("expected_status", 0)
                expected_body = ac_test.get("expected_body_contains", "")

                if not command:
                    checks.append(CheckResult(
                        check_id=f"AC-NO-CMD-{test_id}",
                        requirement_id=req_id,
                        passed=False,
                        description=f"Acceptance test {test_id}: no command",
                        actual="Empty command",
                        expected="Valid curl command",
                        fix_phase=8,
                        fix_agent="tester",
                        diagnostic=f"Acceptance test {test_id} for {req_id} has no command.",
                    ))
                    continue

                # Substitute {{base_url}} in command
                command = command.replace("{{base_url}}", base_url)

                result = run(command, workdir=workdir, timeout=10)

                # Check status
                status_pass = result.exit_code == expected_status

                # Check body contains
                body_pass = True
                if expected_body and status_pass:
                    body_pass = expected_body in result.stdout

                passed = status_pass and body_pass

                checks.append(CheckResult(
                    check_id=f"AC-{test_id}",
                    requirement_id=req_id,
                    passed=passed,
                    description=f"Acceptance test: {command[:100]}",
                    actual=(
                        f"Exit {result.exit_code}" +
                        (f", body contains '{expected_body}'" if expected_body else "")
                    ),
                    expected=(
                        f"Exit {expected_status}" +
                        (f", body contains '{expected_body}'" if expected_body else "")
                    ),
                    fix_phase=6 if not status_pass else 8,
                    fix_agent="developer" if not status_pass else "tester",
                    diagnostic=(
                        f"Acceptance test {test_id} failed. "
                        f"Command: {command[:150]}. "
                        f"Exit code: {result.exit_code} (expected {expected_status})."
                    )[:400],
                    evidence=result.stdout[:500] or result.stderr[:500],
                ))

        duration_ms = int((time.monotonic() - start) * 1000)

        if not checks:
            checks.append(CheckResult(
                check_id="AC-NO-TESTS-DEFINED",
                passed=True,
                description="No acceptance tests defined",
                actual="0 acceptance_test_ids across all requirements",
                expected="Acceptance tests defined",
            ))

        return GateResult(
            gate_name=self.name,
            passed=all(c.passed for c in checks),
            score=sum(1 for c in checks if c.passed) / max(len(checks), 1),
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )

    def _find_base_url(self, artifacts: dict, workdir: str) -> str:
        """Try to find deployment URL from various sources."""
        # Check deployment artifacts
        deployment = artifacts.get("deployment", {})
        if deployment.get("url"):
            return deployment["url"]

        # Check env
        import os
        for env_var in ["DEPLOY_URL", "SERVICE_URL", "APP_URL", "BASE_URL"]:
            url = os.environ.get(env_var)
            if url:
                return url

        # Default localhost
        return "http://localhost:8000"
