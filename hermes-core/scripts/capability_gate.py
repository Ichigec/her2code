#!/usr/bin/env python3
"""
Capability Gate — Phase 0 bootstrap engine for plan2 orchestrator.

Usage:
    python3 capability_gate.py --task "make app with pictures" --json
    python3 capability_gate.py --task "test phone" --workspace /path --json
    python3 capability_gate.py --validate

Architecture:
    G0: CapabilityGate   — entry point, orchestrator calls capability_check()
    G1: CapabilityLoader — loads static inventory from YAML
    G2: CapabilityProber — live probes for dynamic capabilities
    G3: TaskInterviewer  — BACCM interview, keyword matching, inference
    G4: CompositionEngine— compositional reasoning (A+B→C, A_missing→derived)
    G5: GapResolver      — for each GAP: what-can / what-missing / what-hard
    G6: FabricationGuard — scans plan for impossible verification steps (post-Phase 5)
    G7: ReportBuilder    — pre-flight report ≤50 lines
    G8: CapabilityLearner— persists user additions to Neo4j (post-cycle)
"""

import argparse
import json
import subprocess
import sys
import time
import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# DATA TYPES
# ═══════════════════════════════════════════════════════════════

class Severity(Enum):
    BLOCKER = "BLOCKER"
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    WARN = "WARN"

class Verdict(Enum):
    GO = "Go"
    KILL = "Kill"
    HOLD = "Hold"
    RECYCLE = "Recycle"


class _CapabilityEncoder(json.JSONEncoder):
    """Custom JSON encoder that serializes Enum values and other non-serializable types."""
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        return str(obj)

class GapDetectionMethod(Enum):
    STATIC_INVENTORY = "M1_static_inventory"
    KEYWORD_MATCH = "M2_keyword_match"
    BACCM_INFERENCE = "M3_baccm_inference"
    COMPOSITIONAL = "M4_compositional"
    LIVE_PROBE = "M5_live_probe"
    CIRCUIT_BREAKER = "M6_circuit_breaker"

@dataclass
class CapabilityRecord:
    name: str
    available: bool
    source: str
    description: str = ""
    severity: Severity = Severity.MEDIUM
    workaround: str = ""
    resolution_strategy: str = ""
    check_command: str = ""
    path: str = ""
    confidence: float = 1.0
    detection_method: GapDetectionMethod = GapDetectionMethod.STATIC_INVENTORY
    probe_output: str = ""
    probe_exit_code: int = 0

@dataclass
class CapabilityRequirement:
    """A capability needed for the task, with why and how we know."""
    capability_name: str
    required: bool
    confidence: float
    reasoning: str
    detection_method: GapDetectionMethod
    baccm_dimension: str = ""

@dataclass
class CapabilityGap:
    capability_name: str
    severity: Severity
    confidence: float
    detection_method: GapDetectionMethod
    what_can_be_done: str
    what_is_missing: str
    what_is_hard: str
    resolution_strategy: str
    resolution_action: str

@dataclass
class CheckResult:
    check_id: str
    passed: bool
    severity: Severity
    detail: str
    resolution: str = ""

@dataclass
class GateVerdict:
    verdict: Verdict
    passed: int
    total: int
    blockers: list[CheckResult] = field(default_factory=list)
    warnings: list[CheckResult] = field(default_factory=list)
    gaps: list[CapabilityGap] = field(default_factory=list)
    capability_report: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# G1: CAPABILITY LOADER
# ═══════════════════════════════════════════════════════════════

class CapabilityLoader:
    """Loads static capability inventory from YAML."""

    DEFAULT_INVENTORY_PATH = Path("/home/user/.hermes/agents/capability_inventory.yaml")

    def __init__(self, inventory_path: Optional[Path] = None):
        self.inventory_path = inventory_path or self.DEFAULT_INVENTORY_PATH

    def load(self) -> dict[str, CapabilityRecord]:
        """Load and parse capability inventory YAML → dict of CapabilityRecord."""
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"Capability inventory not found: {self.inventory_path}")

        with open(self.inventory_path) as f:
            raw = yaml.safe_load(f)

        records: dict[str, CapabilityRecord] = {}

        # Load static capabilities
        for name, data in raw.get("static", {}).items():
            records[name] = CapabilityRecord(
                name=name,
                available=data.get("available", False),
                source=data.get("source", "unknown"),
                description=data.get("description", ""),
                severity=Severity(data.get("severity", "MEDIUM")),
                workaround=data.get("workaround", ""),
                resolution_strategy=data.get("resolution_strategy", "ask_user"),
                check_command=data.get("check", ""),
                path=data.get("path", ""),
            )

        # Load dynamic capabilities (available=False until probed)
        for name, data in raw.get("dynamic", {}).items():
            records[name] = CapabilityRecord(
                name=name,
                available=False,  # Unknown until probed
                source="runtime",
                description=data.get("description", ""),
                severity=Severity(data.get("severity", "MEDIUM")),
                workaround=data.get("workaround", ""),
                resolution_strategy="retry_with_backoff",
                check_command=data.get("check", ""),
            )

        self.raw = raw  # Keep for keyword_mapping, composition_rules, baccm_template
        return records


# ═══════════════════════════════════════════════════════════════
# G2: CAPABILITY PROBER
# ═══════════════════════════════════════════════════════════════

class CapabilityProber:
    """Executes live probes for dynamic capabilities."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def probe(self, record: CapabilityRecord) -> CapabilityRecord:
        """Run the check command for a capability and update its status."""
        if not record.check_command:
            return record

        try:
            result = subprocess.run(
                record.check_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            record.probe_output = result.stdout.strip()
            record.probe_exit_code = result.returncode

            if record.check_command.endswith("|| echo 0"):
                # Pattern: "command || echo 0" — success if output is non-zero/true
                record.available = record.probe_output not in ("0", "")
            elif "grep -q" in record.check_command:
                # Pattern: curl | grep -q 200 — success if exit 0
                record.available = (result.returncode == 0)
            elif ">/dev/null 2>&1" in record.check_command:
                record.available = (result.returncode == 0)
            else:
                record.available = (result.returncode == 0)

            record.detection_method = GapDetectionMethod.LIVE_PROBE
            record.confidence = 0.99

        except subprocess.TimeoutExpired:
            record.available = False
            record.probe_output = f"TIMEOUT ({self.timeout}s)"
            record.probe_exit_code = -1
            record.detection_method = GapDetectionMethod.LIVE_PROBE
            record.confidence = 0.85  # Might be slow network, not truly unavailable

        except Exception as e:
            record.available = False
            record.probe_output = f"ERROR: {e}"
            record.probe_exit_code = -1

        return record

    def probe_all(self, records: dict[str, CapabilityRecord]) -> dict[str, CapabilityRecord]:
        """Probe all dynamic capabilities (source='runtime')."""
        for name, record in records.items():
            if record.source == "runtime":
                records[name] = self.probe(record)
        return records

    def probe_static_with_checks(self, records: dict[str, CapabilityRecord]) -> dict[str, CapabilityRecord]:
        """Also verify static capabilities that have check commands."""
        for name, record in records.items():
            if record.check_command and record.source != "runtime":
                records[name] = self.probe(record)
        return records


# ═══════════════════════════════════════════════════════════════
# G3: TASK INTERVIEWER (L1: Keyword + L2: BACCM Inference)
# ═══════════════════════════════════════════════════════════════

class TaskInterviewer:
    """Discovers capability requirements from task description."""

    def __init__(self, raw_inventory: dict):
        self.keyword_map = raw_inventory.get("keyword_mapping", {})
        self.baccm_template = raw_inventory.get("baccm_template", {})

    def interview(self, task: str, available_caps: set[str]) -> list[CapabilityRequirement]:
        """
        Two-level interview:
          L1: Keyword matching (fast, ~60% accuracy)
          L2: BACCM inference stub (LLM would run full BACCM interview;
              here we do structural inference from task semantics)
        """
        requirements: list[CapabilityRequirement] = []

        # L1: Keyword matching
        task_lower = task.lower()
        matched_caps = set()
        for keyword, caps in self.keyword_map.items():
            if keyword.lower() in task_lower:
                for cap in caps:
                    if cap not in matched_caps:
                        matched_caps.add(cap)
                        requirements.append(CapabilityRequirement(
                            capability_name=cap,
                            required=True,
                            confidence=0.60,
                            reasoning=f"Keyword '{keyword}' found in task",
                            detection_method=GapDetectionMethod.KEYWORD_MATCH,
                        ))

        # L2: BACCM structural inference
        # (Full BACCM would use LLM. Here we do pattern-based inference.)
        baccm_reqs = self._structural_inference(task, available_caps, matched_caps)
        requirements.extend(baccm_reqs)

        # Deduplicate by capability_name, keeping highest confidence
        seen = {}
        for req in requirements:
            if req.capability_name not in seen or req.confidence > seen[req.capability_name].confidence:
                seen[req.capability_name] = req

        return list(seen.values())

    def _structural_inference(
        self, task: str, available_caps: set[str], matched_caps: set[str]
    ) -> list[CapabilityRequirement]:
        """Pattern-based structural inference (L2, ~85% accuracy)."""
        reqs = []
        task_lower = task.lower()

        # BA Context patterns
        context_patterns = [
            (["телефон", "phone", "android", "мобильн", "mobile"], "adb", "Context: mobile platform mentioned"),
            (["веб", "web", "браузер", "browser", "сайт", "url", "http"], "web_fetch", "Context: web resource mentioned"),
            (["gui", "интерфейс", "ui", "окно", "window"], "browser_gui", "Context: GUI/UI mentioned"),
            (["звук", "аудио", "audio", "голос", "voice", "музык", "music"], "ffmpeg", "Context: audio processing needed"),
            (["видео", "video", "screen record", "запись экран"], "ffmpeg", "Context: video processing needed"),
            (["граф", "graph", "neo4j", "база", "database"], "neo4j", "Context: graph/database mentioned"),
            (["поиск", "search", "research", "исследова"], "searchbox_mcp", "Context: search/research mentioned"),
            (["контейнер", "container", "docker", "образ", "image build"], "docker", "Context: containerization mentioned"),
            (["gpu", "cuda", "ml", "обучен", "train", "inference"], "cuda", "Context: ML/GPU mentioned"),
        ]

        # Stakeholder patterns (who verifies?)
        stakeholder_patterns = [
            (["проверь", "check", "verify", "test", "тест", "валидац", "validat"], "vision", 0.85,
             "Stakeholder: verification mentioned → may need vision for visual checks"),
            (["посмотри", "look", "see", "view", "посмотр", "взгля"], "vision", 0.80,
             "Stakeholder: visual inspection mentioned"),
        ]

        # Need patterns (what must the system do?)
        need_patterns = [
            (["покажи", "отобрази", "display", "show", "render", "отрендер"], "browser_gui", 0.70,
             "Need: display/render mentioned → may need GUI"),
            (["скачай", "загруз", "download", "fetch", "получ"], "web_fetch", 0.75,
             "Need: download/fetch mentioned"),
            (["установи", "install", "setup", "настрой", "configur"], "terminal_exec", 0.95,
             "Need: install/setup requires terminal"),
        ]

        all_patterns = context_patterns + stakeholder_patterns + need_patterns

        for keywords, cap, *rest in all_patterns:
            if isinstance(rest[0], str):  # context_patterns: (keywords, cap, reasoning)
                reasoning = rest[0]
                confidence = 0.85
            else:  # stakeholder/need patterns: (keywords, cap, confidence, reasoning)
                confidence = rest[0]
                reasoning = rest[1]

            if any(kw in task_lower for kw in keywords):
                if cap not in matched_caps:
                    reqs.append(CapabilityRequirement(
                        capability_name=cap,
                        required=True,
                        confidence=confidence,
                        reasoning=reasoning,
                        detection_method=GapDetectionMethod.BACCM_INFERENCE,
                        baccm_dimension="Context" if "Context" in reasoning else "Stakeholder" if "Stakeholder" in reasoning else "Need",
                    ))

        return reqs


# ═══════════════════════════════════════════════════════════════
# G4: COMPOSITION ENGINE
# ═══════════════════════════════════════════════════════════════

class CompositionEngine:
    """Derives additional capability requirements from tool combinations."""

    def __init__(self, raw_inventory: dict):
        self.rules = raw_inventory.get("composition_rules", [])

    def derive(
        self, available_caps: set[str], required_caps: set[str]
    ) -> list[CapabilityRequirement]:
        """Check composition rules: which derived capabilities are missing?"""
        requirements = []

        for rule in self.rules:
            rule_name = rule["name"]
            required = set(rule.get("required", []))
            any_of = set(rule.get("any_of", []))
            produces = rule["produces"]
            severity_str = rule.get("severity", "high")

            # Check if all required capabilities are available
            if required and not required.issubset(available_caps):
                missing = required - available_caps
                for cap in missing:
                    requirements.append(CapabilityRequirement(
                        capability_name=cap,
                        required=True,
                        confidence=0.90,
                        reasoning=f"Composition rule '{rule_name}': requires {cap} for {produces}",
                        detection_method=GapDetectionMethod.COMPOSITIONAL,
                    ))
                continue

            # Check any_of
            if any_of and not (any_of & available_caps):
                requirements.append(CapabilityRequirement(
                    capability_name=list(any_of)[0],
                    required=True,
                    confidence=0.85,
                    reasoning=f"Composition rule '{rule_name}': needs at least one of {any_of} for {produces}",
                    detection_method=GapDetectionMethod.COMPOSITIONAL,
                ))

            # If all required are available, the derived capability IS available
            if required and required.issubset(available_caps):
                requirements.append(CapabilityRequirement(
                    capability_name=produces,
                    required=False,  # Not a gap — this is available
                    confidence=0.90,
                    reasoning=f"Composition rule '{rule_name}': {produces} is available (all deps met)",
                    detection_method=GapDetectionMethod.COMPOSITIONAL,
                ))

        return requirements


# ═══════════════════════════════════════════════════════════════
# G5: GAP RESOLVER
# ═══════════════════════════════════════════════════════════════

class GapResolver:
    """Generates resolution plans for detected capability gaps."""

    def __init__(self, raw_inventory: dict):
        self.strategies = raw_inventory.get("resolution_strategies", [])
        self.strategy_map = {s["name"]: s for s in self.strategies}

    def resolve(
        self, records: dict[str, CapabilityRecord], requirements: list[CapabilityRequirement]
    ) -> list[CapabilityGap]:
        """For each required-but-unavailable capability, generate a resolution plan."""
        gaps = []
        available_names = {name for name, r in records.items() if r.available}

        for req in requirements:
            if not req.required:
                continue
            if req.capability_name in available_names:
                continue

            record = records.get(req.capability_name)
            if not record:
                # Capability not in inventory at all — unknown gap
                gaps.append(CapabilityGap(
                    capability_name=req.capability_name,
                    severity=Severity.HIGH,
                    confidence=req.confidence,
                    detection_method=req.detection_method,
                    what_can_be_done="Unknown capability — cannot assess",
                    what_is_missing=f"Capability '{req.capability_name}' not in inventory",
                    what_is_hard="Adding new capability to inventory requires manual definition",
                    resolution_strategy="ask_user",
                    resolution_action=f"Ask user: is '{req.capability_name}' available? Add to inventory if yes.",
                ))
                continue

            strategy = record.resolution_strategy or "ask_user"
            strategy_info = self.strategy_map.get(strategy, {})

            gaps.append(CapabilityGap(
                capability_name=req.capability_name,
                severity=record.severity,
                confidence=req.confidence,
                detection_method=req.detection_method,
                what_can_be_done=record.workaround or f"No workaround defined for {req.capability_name}",
                what_is_missing=record.description or f"Capability '{req.capability_name}' is not available",
                what_is_hard=f"Resolution strategy: {strategy}. {strategy_info.get('description', '')}",
                resolution_strategy=strategy,
                resolution_action=self._format_action(strategy, record, req),
            ))

        return gaps

    def _format_action(self, strategy: str, record: CapabilityRecord, req: CapabilityRequirement) -> str:
        actions = {
            "tool_workaround": f"Use workaround: {record.workaround}",
            "structural_validation": f"Validate structure instead: {record.workaround}",
            "delegate_to_user": f"Ask user to verify: {record.description}",
            "delegate_to_capable_agent": f"Route to sub-agent with {req.capability_name}",
            "replan_around_gap": f"Replan using alternative approach. Workaround: {record.workaround}",
            "accept_risk": f"Accept risk: cannot verify {req.capability_name}. Document in deviation log.",
            "retry_with_backoff": f"Retry probe in 30s. Check command: {record.check_command}",
            "ask_user": f"Ask user for guidance on {req.capability_name}",
        }
        return actions.get(strategy, f"Unknown strategy '{strategy}' for {req.capability_name}")


# ═══════════════════════════════════════════════════════════════
# G6: FABRICATION GUARD (stub — full version scans plan artifacts)
# ═══════════════════════════════════════════════════════════════

class FabricationGuard:
    """Scans plans for impossible verification steps."""

    def scan_plan(self, plan_text: str, gaps: list[CapabilityGap]) -> list[CheckResult]:
        """Check if any verification step in the plan requires an unavailable capability."""
        results = []
        gap_names = {g.capability_name for g in gaps}

        verification_keywords = ["verify", "check", "test", "validate", "провер", "тест", "валид"]

        for kw in verification_keywords:
            if kw.lower() in plan_text.lower():
                for gap_name in gap_names:
                    if gap_name == "vision" and any(
                        v in plan_text.lower() for v in ["visual", "see", "look", "визуальн", "посмотр", "глаз"]
                    ):
                        results.append(CheckResult(
                            check_id="FAB-VISION-VERIFY",
                            passed=False,
                            severity=Severity.CRITICAL,
                            detail=f"Plan contains visual verification but vision capability is unavailable",
                            resolution="Replace visual check with structural validation (imagemagick) + user confirmation",
                        ))
                    elif gap_name == "browser_gui" and any(
                        v in plan_text.lower() for v in ["browser", "gui", "ui test", "браузер", "интерфейс"]
                    ):
                        results.append(CheckResult(
                            check_id="FAB-BROWSER-VERIFY",
                            passed=False,
                            severity=Severity.HIGH,
                            detail=f"Plan contains browser/GUI verification but browser_gui is unavailable",
                            resolution="Replace with curl + DOM check, or delegate to user",
                        ))

        return results


# ═══════════════════════════════════════════════════════════════
# G7: REPORT BUILDER
# ═══════════════════════════════════════════════════════════════

class ReportBuilder:
    """Builds pre-flight capability report."""

    MAX_LINES = 50

    def build(
        self,
        records: dict[str, CapabilityRecord],
        requirements: list[CapabilityRequirement],
        gaps: list[CapabilityGap],
        fab_results: list[CheckResult],
    ) -> dict:
        """Build structured capability report."""
        available = [r for r in records.values() if r.available]
        unavailable = [r for r in records.values() if not r.available]
        critical_gaps = [g for g in gaps if g.severity in (Severity.BLOCKER, Severity.CRITICAL)]
        warning_gaps = [g for g in gaps if g.severity not in (Severity.BLOCKER, Severity.CRITICAL)]

        return {
            "summary": {
                "total_capabilities": len(records),
                "available": len(available),
                "unavailable": len(unavailable),
                "gaps_found": len(gaps),
                "critical_gaps": len(critical_gaps),
                "warning_gaps": len(warning_gaps),
                "fabrication_issues": len([r for r in fab_results if not r.passed]),
            },
            "available_capabilities": [
                {"name": r.name, "source": r.source, "description": r.description[:100]}
                for r in available
            ],
            "unavailable_capabilities": [
                {
                    "name": r.name,
                    "severity": r.severity.value,
                    "workaround": r.workaround,
                    "description": r.description[:100],
                }
                for r in unavailable
            ],
            "detected_requirements": [
                {
                    "capability": req.capability_name,
                    "required": req.required,
                    "confidence": req.confidence,
                    "reasoning": req.reasoning,
                    "method": req.detection_method.value,
                }
                for req in requirements
            ],
            "gaps": [
                {
                    "capability": g.capability_name,
                    "severity": g.severity.value,
                    "confidence": g.confidence,
                    "what_can_be_done": g.what_can_be_done,
                    "what_is_missing": g.what_is_missing,
                    "what_is_hard": g.what_is_hard,
                    "resolution_strategy": g.resolution_strategy,
                    "resolution_action": g.resolution_action,
                }
                for g in gaps
            ],
            "fabrication_issues": [
                {"check_id": r.check_id, "detail": r.detail, "resolution": r.resolution}
                for r in fab_results if not r.passed
            ],
        }

    def format_cli(self, report: dict) -> str:
        """Format report for CLI output (≤50 lines)."""
        s = report["summary"]
        lines = [
            "╔══════════════════════════════════════════════╗",
            "║     PRE-FLIGHT CAPABILITY REPORT             ║",
            "╠══════════════════════════════════════════════╣",
            f"║ Available: {s['available']:>3}  Unavailable: {s['unavailable']:>3}  Gaps: {s['gaps_found']:>3}     ║",
            f"║ Critical: {s['critical_gaps']:>3}  Warnings:  {s['warning_gaps']:>3}  Fab.Issues: {s['fabrication_issues']:>2} ║",
            "╠══════════════════════════════════════════════╣",
        ]

        if report["gaps"]:
            lines.append("║ GAPS FOUND:                                   ║")
            for g in report["gaps"][:10]:
                sev = g["severity"][:1]
                cap = g["capability"][:30]
                lines.append(f"║ [{sev}] {cap:<30} → {g['resolution_strategy']:<15} ║")

        if report["fabrication_issues"]:
            lines.append("║ FABRICATION ISSUES:                           ║")
            for f in report["fabrication_issues"][:5]:
                lines.append(f"║ ⚠ {f['check_id']:<20} {f['detail'][:30]:<30} ║")

        lines.append("╚══════════════════════════════════════════════╝")

        # Cap at MAX_LINES
        if len(lines) > self.MAX_LINES:
            lines = lines[:self.MAX_LINES - 1] + ["║ ... (truncated)                               ║", "╚══════════════════════════════════════════════╝"]

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# G0: CAPABILITY GATE — main entry point
# ═══════════════════════════════════════════════════════════════

class CapabilityGate:
    """Phase 0 bootstrap: capability check before any plan2 phase starts."""

    def __init__(
        self,
        inventory_path: Optional[Path] = None,
        probe_timeout: int = 10,
    ):
        self.loader = CapabilityLoader(inventory_path)
        self.prober = CapabilityProber(timeout=probe_timeout)
        self.interviewer = None  # Set after load
        self.composer = None
        self.resolver = None
        self.guard = FabricationGuard()
        self.builder = ReportBuilder()

    def check(self, task: str, workspace: Optional[Path] = None) -> GateVerdict:
        """
        Full capability check pipeline:
          G1: Load inventory
          G2: Probe dynamic + static-with-checks
          G3: Interview task → capability requirements
          G4: Compositional reasoning
          G5: Gap resolution
          → Return GateVerdict
        """
        # G1: Load
        try:
            records = self.loader.load()
        except FileNotFoundError as e:
            return GateVerdict(
                verdict=Verdict.KILL,
                passed=0, total=1,
                blockers=[CheckResult("G1-LOAD", False, Severity.BLOCKER, str(e), "Create capability_inventory.yaml")]
            )

        raw = self.loader.raw

        # G2: Probe
        records = self.prober.probe_all(records)
        records = self.prober.probe_static_with_checks(records)

        # G3: Interview
        available_caps = {name for name, r in records.items() if r.available}
        self.interviewer = TaskInterviewer(raw)
        requirements = self.interviewer.interview(task, available_caps)

        # G4: Composition
        required_caps = {req.capability_name for req in requirements if req.required}
        self.composer = CompositionEngine(raw)
        composition_reqs = self.composer.derive(available_caps, required_caps)
        requirements.extend(composition_reqs)

        # G5: Gap resolution
        self.resolver = GapResolver(raw)
        gaps = self.resolver.resolve(records, requirements)

        # G6: Fabrication guard (no plan yet at Phase 0 — stub)
        fab_results = []

        # Build report
        report = self.builder.build(records, requirements, gaps, fab_results)

        # Evaluate verdict
        return self._evaluate(gaps, fab_results, report)

    def check_post_plan(self, plan_text: str, gaps: list[CapabilityGap]) -> list[CheckResult]:
        """Post-Phase 5: scan plan for impossible verification steps."""
        return self.guard.scan_plan(plan_text, gaps)

    def _evaluate(self, gaps: list[CapabilityGap], fab_results: list[CheckResult], report: dict) -> GateVerdict:
        """PDP: Policy Decision Point — evaluate Go/Kill/Hold/Recycle."""
        blockers = [g for g in gaps if g.severity == Severity.BLOCKER]
        criticals = [g for g in gaps if g.severity == Severity.CRITICAL]
        fab_blockers = [r for r in fab_results if not r.passed and r.severity == Severity.BLOCKER]

        total_checks = len(gaps) + len(fab_results) + 1  # +1 for inventory load
        passed = total_checks - len(blockers) - len(fab_blockers)

        # Kill: BLOCKER gaps without resolution
        if blockers:
            has_resolution = all(
                g.resolution_strategy not in ("ask_user", "") and g.resolution_strategy != "unknown"
                for g in blockers
            )
            if not has_resolution:
                return GateVerdict(
                    verdict=Verdict.KILL,
                    passed=passed, total=total_checks,
                    blockers=[CheckResult(f"GAP-{g.capability_name}", False, Severity.BLOCKER,
                              f"{g.what_is_missing}", g.resolution_action) for g in blockers],
                    gaps=gaps,
                    capability_report=report,
                )

        # Hold: BLOCKER gaps WITH resolution → execute resolution, retry
        if blockers:
            return GateVerdict(
                verdict=Verdict.HOLD,
                passed=passed, total=total_checks,
                blockers=[CheckResult(f"GAP-{g.capability_name}", False, Severity.BLOCKER,
                          f"{g.what_is_missing} → {g.resolution_action}", g.resolution_action) for g in blockers],
                gaps=gaps,
                capability_report=report,
            )

        # Go: no blockers, possibly with warnings
        warnings = [
            CheckResult(f"GAP-{g.capability_name}", False, g.severity, g.what_is_missing, g.resolution_action)
            for g in criticals
        ]

        return GateVerdict(
            verdict=Verdict.GO,
            passed=total_checks - len(warnings), total=total_checks,
            warnings=warnings,
            gaps=gaps,
            capability_report=report,
        )


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Capability Gate — Phase 0 bootstrap for plan2")
    parser.add_argument("--task", type=str, default="", help="Task description to analyze")
    parser.add_argument("--workspace", type=str, default=".", help="Project workspace directory")
    parser.add_argument("--inventory", type=str, default=None, help="Path to capability_inventory.yaml")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    parser.add_argument("--validate", action="store_true", help="Validate inventory and exit")
    parser.add_argument("--post-plan", type=str, default=None, help="Run FabricationGuard on a plan file")
    args = parser.parse_args()

    inventory_path = Path(args.inventory) if args.inventory else None
    gate = CapabilityGate(inventory_path)

    # Validate mode
    if args.validate:
        try:
            records = gate.loader.load()
            print(f"✅ Inventory valid: {len(records)} capabilities loaded")
            for name, r in sorted(records.items()):
                status = "✅" if r.available else "❌" if r.source != "runtime" else "❓"
                print(f"   {status} {name}: {r.description[:60]}")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            sys.exit(1)

    # Post-plan fabrication scan
    if args.post_plan:
        plan_path = Path(args.post_plan)
        if not plan_path.exists():
            print(f"❌ Plan file not found: {args.post_plan}")
            sys.exit(1)
        plan_text = plan_path.read_text()
        # Load records to get gaps
        records = gate.loader.load()
        records = gate.prober.probe_all(records)
        records = gate.prober.probe_static_with_checks(records)
        available_caps = {name for name, r in records.items() if r.available}
        raw = gate.loader.raw
        gate.interviewer = TaskInterviewer(raw)
        requirements = gate.interviewer.interview(args.task or "", available_caps)
        gate.resolver = GapResolver(raw)
        gaps = gate.resolver.resolve(records, requirements)
        fab_results = gate.check_post_plan(plan_text, gaps)
        for r in fab_results:
            status = "❌" if not r.passed else "✅"
            print(f"{status} {r.check_id}: {r.detail}")
            if not r.passed:
                print(f"   Resolution: {r.resolution}")
        sys.exit(0 if all(r.passed for r in fab_results) else 1)

    # Full check
    if not args.task:
        parser.error("--task is required for capability check (or use --validate)")

    workspace = Path(args.workspace) if args.workspace else None
    verdict = gate.check(args.task, workspace)

    if args.json:
        output = {
            "verdict": verdict.verdict.value,
            "passed": verdict.passed,
            "total": verdict.total,
            "blockers": [asdict(b) for b in verdict.blockers],
            "warnings": [asdict(w) for w in verdict.warnings],
            "gaps": [asdict(g) for g in verdict.gaps],
            "capability_report": verdict.capability_report,
        }

        if args.output:
            Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False, cls=_CapabilityEncoder))
            print(f"Report written to {args.output}")
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False, cls=_CapabilityEncoder))
    else:
        print(gate.builder.format_cli(verdict.capability_report))
        print(f"\nVerdict: {verdict.verdict.value} ({verdict.passed}/{verdict.total} passed)")

        if verdict.blockers:
            print("\nBLOCKERS:")
            for b in verdict.blockers:
                print(f"  ❌ {b.check_id}: {b.detail}")

        if verdict.warnings:
            print("\nWARNINGS:")
            for w in verdict.warnings:
                print(f"  ⚠ {w.check_id}: {w.detail}")

    sys.exit(0 if verdict.verdict == Verdict.GO else 1)


if __name__ == "__main__":
    main()
