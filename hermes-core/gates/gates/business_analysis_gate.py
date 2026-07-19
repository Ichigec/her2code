"""
BusinessAnalysisGate — ROOT mandatory gate.

Verifies EVERY business requirement has: code → test → security → acceptance.
Cannot be disabled. Cannot be bypassed. Threshold = 1.0 always.
"""

import time
from pathlib import Path

from gates.base import GatePlugin, GateResult, CheckResult

# Try importing yaml (may not be available)
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class BusinessAnalysisGate(GatePlugin):
    """
    ROOT GATE. Mandatory. Cannot be disabled.

    Checks that for EVERY REQ in traceability.yaml:
    1. code_paths is non-empty (implementation exists)
    2. test_ids is non-empty (tests exist)
    3. security_checks is non-empty (security reviewed)
    4. If acceptance_criteria non-empty → acceptance_test_ids non-empty
    """

    name = "business-analysis-gate"
    description = "Every business requirement must have code + test + security + acceptance"
    mandatory = True
    threshold = 1.0
    timeout = 5

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        matrix = self._load_traceability(workdir, artifacts)

        if matrix is None:
            return GateResult(
                gate_name=self.name,
                passed=False,
                score=0.0,
                threshold=self.threshold,
                checks=[CheckResult(
                    check_id="BA-NO-MATRIX",
                    passed=False,
                    description="No traceability matrix found",
                    actual="traceability.yaml not found",
                    expected="Traceability matrix generated from requirements",
                    fix_phase=1,
                    fix_agent="requirements",
                    diagnostic=(
                        "No traceability.yaml found. Run generate_traceability.py "
                        "from the requirements document."
                    ),
                )],
                duration_ms=0,
            )

        requirements = matrix.get("requirements", [])
        if not requirements:
            return GateResult(
                gate_name=self.name,
                passed=False,
                score=0.0,
                threshold=self.threshold,
                checks=[CheckResult(
                    check_id="BA-NO-REQS",
                    passed=False,
                    description="No requirements defined",
                    actual="0 requirements in traceability.yaml",
                    expected="Requirements extracted from docs",
                    fix_phase=1,
                    fix_agent="requirements",
                    diagnostic="Traceability matrix has no requirements. Check requirements doc.",
                )],
                duration_ms=0,
            )

        checks = []

        for req in requirements:
            req_id = req.get("id", "unknown")
            desc = req.get("description", "")[:80]

            # 1. CODE: implementation must exist
            code_paths = req.get("code_paths", [])
            if not code_paths:
                checks.append(CheckResult(
                    check_id=f"BA-CODE-{req_id}",
                    requirement_id=req_id,
                    passed=False,
                    description=f"REQ {req_id}: No implementation",
                    actual="No code_paths",
                    expected=f"Code implementing {req_id}",
                    fix_phase=6,
                    fix_agent="developer",
                    diagnostic=f"Requirement {req_id} ('{desc}') has no code_paths. Implement the feature.",
                ))

            # 2. TEST: tests must exist
            test_ids = req.get("test_ids", [])
            if not test_ids:
                checks.append(CheckResult(
                    check_id=f"BA-TEST-{req_id}",
                    requirement_id=req_id,
                    passed=False,
                    description=f"REQ {req_id}: No tests",
                    actual="No test_ids",
                    expected=f"Tests covering {req_id}",
                    fix_phase=6,
                    fix_agent="developer",
                    diagnostic=f"Requirement {req_id} ('{desc}') has no test_ids. Write tests.",
                ))

            # 3. SECURITY: security checks must exist
            security_checks = req.get("security_checks", [])
            if not security_checks:
                checks.append(CheckResult(
                    check_id=f"BA-SEC-{req_id}",
                    requirement_id=req_id,
                    passed=False,
                    description=f"REQ {req_id}: No security review",
                    actual="No security_checks",
                    expected=f"Security checks for {req_id}",
                    fix_phase=7,
                    fix_agent="security",
                    diagnostic=f"Requirement {req_id} ('{desc}') has no security_checks. Run SecurityGate.",
                ))

            # 4. ACCEPTANCE: acceptance criteria → acceptance tests
            acceptance_criteria = req.get("acceptance_criteria", [])
            acceptance_test_ids = req.get("acceptance_test_ids", [])
            if acceptance_criteria and not acceptance_test_ids:
                checks.append(CheckResult(
                    check_id=f"BA-AC-{req_id}",
                    requirement_id=req_id,
                    passed=False,
                    description=f"REQ {req_id}: No acceptance tests",
                    actual=f"0 acceptance tests for {len(acceptance_criteria)} criteria",
                    expected=f"Acceptance tests covering {len(acceptance_criteria)} criteria",
                    fix_phase=8,
                    fix_agent="tester",
                    diagnostic=(
                        f"Requirement {req_id} has {len(acceptance_criteria)} acceptance "
                        f"criteria but 0 acceptance_test_ids."
                    ),
                ))

        if not checks:
            checks.append(CheckResult(
                check_id="BA-ALL-COVERED",
                passed=True,
                description=f"All {len(requirements)} requirements fully covered",
                actual=f"{len(requirements)} requirements covered",
                expected="All requirements covered",
            ))

        passed = all(c.passed for c in checks)
        score = sum(1 for c in checks if c.passed) / max(len(checks), 1)

        return GateResult(
            gate_name=self.name,
            passed=passed,
            score=score,
            threshold=self.threshold,
            checks=checks,
            duration_ms=0,
        )

    def _load_traceability(self, workdir: str, artifacts: dict) -> dict | None:
        """Load traceability matrix from disk or artifacts."""
        # Check artifacts first (passed in-memory by orchestrator)
        matrix = artifacts.get("traceability")
        if matrix:
            return matrix

        # Try traceability.yaml in workdir
        paths = [
            Path(workdir) / "traceability.yaml",
            Path(workdir) / "docs" / "traceability.yaml",
            Path(workdir) / ".hermes" / "traceability.yaml",
        ]

        for path in paths:
            if path.exists():
                try:
                    if HAS_YAML:
                        with open(path) as f:
                            return yaml.safe_load(f)
                    else:
                        # Fallback: try reading as JSON
                        import json
                        with open(path) as f:
                            content = f.read()
                            if content.strip().startswith("{"):
                                return json.loads(content)
                            # Basic YAML parsing for simple structure
                            return _parse_simple_yaml(content)
                except Exception:
                    pass

        return None


def _parse_simple_yaml(content: str) -> dict | None:
    """Minimal YAML parser for traceability format (no pyyaml dependency)."""
    result = {"requirements": []}
    current_req = None

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue

        if stripped.startswith("- id:"):
            if current_req:
                result["requirements"].append(current_req)
            req_id = stripped.replace("- id:", "").strip().strip('"').strip("'")
            current_req = {"id": req_id}
        elif current_req is not None:
            if ":" in stripped and not stripped.startswith("  "):
                pass  # skip non-indented keys
            elif stripped.startswith("code_paths:"):
                current_req["code_paths"] = ["placeholder"]
            elif stripped.startswith("test_ids:"):
                current_req["test_ids"] = ["placeholder"]
            elif stripped.startswith("security_checks:"):
                current_req["security_checks"] = ["placeholder"]
            elif stripped.startswith("acceptance_test_ids:"):
                current_req["acceptance_test_ids"] = ["placeholder"]
            elif stripped.startswith("description:"):
                current_req["description"] = stripped.replace("description:", "").strip()

    if current_req:
        result["requirements"].append(current_req)

    return result if result["requirements"] else None
