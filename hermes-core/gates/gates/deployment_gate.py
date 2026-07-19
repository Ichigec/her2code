"""
DeploymentGate — verify deployed service responds to health check.
"""

import time

from gates.base import GatePlugin, GateResult, CheckResult
from ..utils.terminal import run


class DeploymentGate(GatePlugin):
    """Verify deployed service is alive and responding."""

    name = "deployment-gate"
    description = "Deployed service must respond to health check"
    threshold = 1.0
    timeout = 30

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        base_url = artifacts.get("deployment_url", "")
        if not base_url:
            base_url = self._find_base_url(artifacts)

        if not base_url:
            return GateResult(
                gate_name=self.name,
                passed=False,
                score=0.0,
                threshold=self.threshold,
                checks=[CheckResult(
                    check_id="DEP-NO-URL",
                    passed=False,
                    description="No deployment URL",
                    actual="No deployment_url or deploy URL found",
                    expected="Deployment URL configured",
                    fix_phase=8,
                    fix_agent="deployment",
                    diagnostic="Set deployment_url in artifacts or DEPLOY_URL in env.",
                )],
                duration_ms=0,
            )

        health_endpoint = artifacts.get("health_endpoint", "/health")
        health_url = f"{base_url.rstrip('/')}{health_endpoint}"

        start = time.monotonic()
        result = run(
            ["curl", "-sf", "--max-time", "10", health_url],
            workdir=workdir,
            timeout=15,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        passed = result.exit_code == 0

        checks = [CheckResult(
            check_id="DEP-HEALTH",
            passed=passed,
            description=f"Health check: {health_url}",
            actual=f"HTTP {result.exit_code}" + (f": {result.stdout[:100]}" if passed else ""),
            expected="HTTP 200 OK",
            fix_phase=8,
            fix_agent="deployment",
            evidence=result.stdout[:200] if passed else result.stderr[:200],
            diagnostic=(
                f"Health check to {health_url} failed. "
                f"Exit code: {result.exit_code}. {result.stderr[:200]}"
            ) if not passed else "",
        )]

        # Also check process/port if local deployment
        if "localhost" in base_url or "127.0.0.1" in base_url:
            port = self._extract_port(base_url)
            if port:
                port_result = run(
                    ["ss", "-tlnp"],
                    workdir=workdir,
                    timeout=5,
                )
                port_listening = f":{port}" in port_result.stdout
                checks.append(CheckResult(
                    check_id="DEP-PORT",
                    passed=port_listening,
                    description=f"Port {port} listening",
                    actual=f"Port {port} {'is' if port_listening else 'is NOT'} listening",
                    expected=f"Port {port} bound and listening",
                    fix_phase=8,
                    fix_agent="deployment",
                    evidence=port_result.stdout[:300],
                    diagnostic=(
                        f"Port {port} is not listening. Service may not have started." if not port_listening else ""
                    ),
                ))

        return GateResult(
            gate_name=self.name,
            passed=all(c.passed for c in checks),
            score=sum(1 for c in checks if c.passed) / max(len(checks), 1),
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _find_base_url(artifacts: dict) -> str:
        deployment = artifacts.get("deployment", {})
        if deployment.get("url"):
            return deployment["url"]

        import os
        for env_var in ["DEPLOY_URL", "SERVICE_URL", "APP_URL"]:
            url = os.environ.get(env_var)
            if url:
                return url

        return ""

    @staticmethod
    def _extract_port(url: str) -> str:
        """Extract port from URL like http://localhost:8000."""
        if ":" in url.split("//")[-1]:
            return url.rsplit(":", 1)[-1].split("/")[0]
        return ""
