"""
SecurityGate — SAST analysis. 0 Critical/High findings required.

Tools: bandit, semgrep, gitleaks, pip-audit.
"""

import json
import time
from pathlib import Path

from gates.base import GatePlugin, GateResult, CheckResult
from ..utils.terminal import run


class SecurityGate(GatePlugin):
    """Verify 0 Critical/High security findings."""

    name = "security-gate"
    description = "0 Critical/High security findings across SAST tools"
    threshold = 1.0
    timeout = 300

    TOOLS = [
        ("bandit", ["bandit", "-r", ".", "--severity-level", "high", "-f", "json"]),
        ("semgrep", ["semgrep", "--config=auto", "--error", "--json"]),
        ("gitleaks", ["gitleaks", "detect", "--no-git", "-v", "-f", "json"]),
        ("pip-audit", ["pip-audit", "--format", "json"]),
    ]

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        start = time.monotonic()
        tools_config = self._get_tools_config(artifacts)
        checks = []
        total_duration = 0

        for tool_name, cmd in self.TOOLS:
            if not tools_config.get(tool_name, True):
                continue

            tool_start = time.monotonic()
            result = run(cmd, workdir=workdir, timeout=self.timeout // len(self.TOOLS))
            tool_ms = int((time.monotonic() - tool_start) * 1000)
            total_duration += tool_ms

            findings = self._parse_findings(tool_name, result)

            if not findings:
                checks.append(
                    CheckResult(
                        check_id=f"SEC-{tool_name}-CLEAN",
                        passed=True,
                        description=f"{tool_name}: 0 Critical/High findings",
                        actual="0 findings",
                        expected="0 Critical/High findings",
                    )
                )
                continue

            for finding in findings:
                checks.append(
                    CheckResult(
                        check_id=f"SEC-{tool_name}-{finding.get('id', 'unknown')}",
                        passed=False,
                        description=f"{tool_name}: {finding.get('description', 'Security finding')}",
                        actual=f"{finding.get('severity', 'unknown')}: {finding.get('description', '')}",
                        expected="No Critical/High findings",
                        fix_phase=6 if finding.get("file") else 5,
                        fix_agent="developer" if finding.get("file") else "techlead",
                        code_path=finding.get("file", ""),
                        diagnostic=(
                            f"{tool_name}: {finding.get('description', 'Security issue')}. "
                            f"File: {finding.get('file', 'unknown')}:{finding.get('line', '?')}. "
                            f"Fix: {finding.get('fix', 'manual review needed')}"
                        )[:400],
                        evidence=json.dumps(finding)[:500],
                    )
                )

        duration_ms = int((time.monotonic() - start) * 1000)

        return GateResult(
            gate_name=self.name,
            passed=all(c.passed for c in checks),
            score=sum(1 for c in checks if c.passed) / max(len(checks), 1) if checks else 1.0,
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )

    def _get_tools_config(self, artifacts: dict) -> dict:
        """Read which SAST tools to run from artifacts config."""
        return artifacts.get("security_tools", {
            "bandit": True,
            "semgrep": True,
            "gitleaks": True,
            "pip_audit": True,
        })

    # ── Result Parsers ──────────────────────────────────────────────────────

    def _parse_findings(self, tool_name: str, result) -> list[dict]:
        if result.exit_code == -1 or result.exit_code == -3:
            return [{
                "id": "tool-error",
                "severity": "High",
                "description": f"{tool_name} execution failed: {result.stderr[:200]}",
                "file": "",
                "line": 0,
                "fix": f"Ensure {tool_name} is installed and working.",
            }]

        if result.exit_code == -2:
            return [{
                "id": "not-installed",
                "severity": "High",
                "description": f"{tool_name} is not installed",
                "file": "",
                "line": 0,
                "fix": f"Install {tool_name} or disable it in config.",
            }]

        parser = getattr(self, f"_parse_{tool_name.replace('-', '_')}", None)
        if parser:
            return parser(result)
        return []

    def _parse_bandit(self, result) -> list[dict]:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        findings = []
        for issue in data.get("results", []):
            severity = issue.get("issue_severity", "unknown")
            if severity in ("HIGH", "MEDIUM"):
                findings.append({
                    "id": f"{issue.get('test_id', 'unknown')}:{issue.get('line_number', 0)}",
                    "severity": severity,
                    "description": issue.get("issue_text", ""),
                    "file": issue.get("filename", ""),
                    "line": issue.get("line_number", 0),
                    "fix": issue.get("more_info", ""),
                })
        return findings

    def _parse_semgrep(self, result) -> list[dict]:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        findings = []
        for finding in data.get("results", []):
            severity = finding.get("extra", {}).get("severity", "unknown")
            if severity in ("ERROR", "WARNING"):
                findings.append({
                    "id": finding.get("check_id", "unknown"),
                    "severity": "High" if severity == "ERROR" else "Medium",
                    "description": finding.get("extra", {}).get("message", ""),
                    "file": finding.get("path", ""),
                    "line": finding.get("start", {}).get("line", 0),
                    "fix": finding.get("extra", {}).get("fix", ""),
                })
        return findings

    def _parse_gitleaks(self, result) -> list[dict]:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        findings = []
        for finding in data if isinstance(data, list) else []:
            findings.append({
                "id": finding.get("ruleID", "unknown"),
                "severity": "High",
                "description": finding.get("Description", "Secret detected"),
                "file": finding.get("File", ""),
                "line": finding.get("StartLine", 0),
                "fix": finding.get("Match", "")[:80] + " — remove hardcoded secret",
            })
        return findings

    def _parse_pip_audit(self, result) -> list[dict]:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        findings = []
        for vuln_list in data.get("dependencies", []):
            for vuln in vuln_list.get("vulns", []):
                findings.append({
                    "id": vuln.get("id", "unknown"),
                    "severity": "High",
                    "description": f"{vuln_list.get('name', '?')}: {vuln.get('id', '?')}",
                    "file": "requirements.txt / pyproject.toml",
                    "line": 0,
                    "fix": f"Update {vuln_list.get('name', '?')} to patched version.",
                })
        return findings
