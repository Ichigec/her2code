"""
Quality Gate Plugin — abstract base class and data models.

Every gate MUST implement GatePlugin.check(artifacts, workdir) → GateResult.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    """Single atomic check within a gate."""

    check_id: str
    requirement_id: str = ""
    description: str = ""
    passed: bool = False
    actual: str = ""
    expected: str = ""
    fix_phase: int = 6
    fix_agent: str = "developer"
    code_path: str = ""
    diagnostic: str = ""
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "requirement_id": self.requirement_id,
            "description": self.description,
            "passed": self.passed,
            "actual": self.actual,
            "expected": self.expected,
            "fix_phase": self.fix_phase,
            "fix_agent": self.fix_agent,
            "code_path": self.code_path,
            "diagnostic": self.diagnostic,
            "evidence": self.evidence[:500],
        }


@dataclass
class GateResult:
    """Result of a single gate check."""

    gate_name: str
    passed: bool
    score: float = 0.0
    threshold: float = 1.0
    checks: list[CheckResult] = field(default_factory=list)
    duration_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "gate_name": self.gate_name,
            "passed": self.passed,
            "score": round(self.score, 3),
            "threshold": self.threshold,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "checks": [c.to_dict() for c in self.checks],
        }

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    @property
    def first_failure(self) -> Optional[CheckResult]:
        for c in self.checks:
            if not c.passed:
                return c
        return None


@dataclass
class GateVerdict:
    """Aggregated result from all gates."""

    verdict: str  # ALL_PASSED | FAILED | GATE_RUNNER_CRASHED
    timestamp: str = ""
    workdir: str = ""
    cycle_id: str = ""
    iteration: int = 0
    total_gates: int = 0
    passed_gates: int = 0
    failed_gates: int = 0
    gates: list[GateResult] = field(default_factory=list)
    error: Optional[str] = None
    passport: Optional[dict] = None

    def to_dict(self) -> dict:
        d = {
            "verdict": self.verdict,
            "timestamp": self.timestamp,
            "workdir": self.workdir,
            "cycle_id": self.cycle_id,
            "iteration": self.iteration,
            "total_gates": self.total_gates,
            "passed_gates": self.passed_gates,
            "failed_gates": self.failed_gates,
            "gates": [g.to_dict() for g in self.gates],
        }
        if self.error:
            d["error"] = self.error
        if self.passport:
            d["passport"] = self.passport
        if self.verdict == "FAILED":
            d["action"] = self._build_action()
        return d

    def _build_action(self) -> dict:
        """Extract fix_phase/fix_agent/diagnostic from first failed gate."""
        for gate in self.gates:
            if not gate.passed:
                ff = gate.first_failure
                if ff:
                    return {
                        "fix_phase": ff.fix_phase,
                        "fix_agent": ff.fix_agent,
                        "diagnostic": ff.diagnostic[:400],
                        "code_paths": [ff.code_path] if ff.code_path else [],
                        "gate_name": gate.gate_name,
                        "check_id": ff.check_id,
                    }
        # Fallback: gate failed but no checks (error case)
        for gate in self.gates:
            if not gate.passed:
                return {
                    "fix_phase": 0,
                    "fix_agent": "orchestrator",
                    "diagnostic": f"Gate '{gate.gate_name}' failed: {gate.error or 'unknown'}",
                    "code_paths": [],
                    "gate_name": gate.gate_name,
                }
        return {
            "fix_phase": 0,
            "fix_agent": "orchestrator",
            "diagnostic": "Unknown failure in gate runner",
            "code_paths": [],
        }


# ── Gate Plugin ABC ────────────────────────────────────────────────────────

class GatePlugin(ABC):
    """Base class for all quality gates."""

    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    mandatory: bool = False  # True = cannot be disabled
    threshold: float = 1.0   # Override in subclass or config.yaml
    timeout: int = 120        # Override in subclass or config.yaml

    # Dependencies: names of gates that must pass before this one
    depends_on: list[str] = []

    @abstractmethod
    def check(self, artifacts: dict, workdir: str) -> GateResult:
        """
        Execute all checks for this gate.

        Args:
            artifacts: dict with keys like 'requirements', 'code', 'traceability',
                       'incremental_scope', 'changed_files', 'deployment_url', etc.
            workdir: absolute path to project root.

        Returns:
            GateResult with passed=True only if ALL checks passed.
        """
        ...
