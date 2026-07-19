"""
Capability Gate Plugin — pre-phase capability check for plan2 orchestrator.

Integrates with existing gate system (base.py, runner.py, registry.py).
Executed before Phase 0 (bootstrap) to verify all required capabilities.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from gates.base import GatePlugin, GateResult, CheckResult


class CapabilityGatePlugin(GatePlugin):
    """Pre-phase gate: verifies agent capabilities before any phase starts."""

    name: str = "capability-gate"
    version: str = "1.0.0"
    description: str = "Verifies agent capabilities (static + dynamic + inferred) before phase entry"
    mandatory: bool = True  # Cannot be disabled
    threshold: float = 0.8  # 80% of checks must pass
    timeout: int = 30       # Capability check should be fast

    depends_on: list[str] = []  # No dependencies — runs first

    # Known capability gaps (static)
    KNOWN_GAPS = {
        "vision": "Cannot see/analyze images. Workaround: imagemagick identify + user confirmation.",
        "browser_gui": "Cannot open GUI browser. Workaround: curl + headless checks.",
        "web_fetch": "Cannot fetch web pages. Workaround: curl -sL for text extraction.",
        "web_search": "No web_search tool. Workaround: searchbox MCP.",
        "audio_play": "Cannot play audio. Workaround: write file, user plays manually.",
    }

    # Live probes for dynamic capabilities
    LIVE_PROBES = {
        "cuda": "python3 -c 'import ctranslate2; print(ctranslate2.get_cuda_device_count())' 2>/dev/null || echo 0",
        "docker": "docker info >/dev/null 2>&1 && echo 1 || echo 0",
        "adb": "test -x /home/user/Android/Sdk/platform-tools/adb && echo 1 || echo 0",
        "neo4j": "curl -s -o /dev/null -w '%{http_code}' -u neo4j:<YOUR_NEO4J_PASSWORD> http://localhost:7474 2>/dev/null | grep -q 200 && echo 1 || echo 0",
        "searchbox": "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8024/mcp 2>/dev/null | grep -q 200 && echo 1 || echo 0",
        "git": "git rev-parse --git-dir 2>/dev/null && echo 1 || echo 0",
    }

    # Core tools that MUST be available
    CORE_TOOLS = ["python3", "curl", "bash"]

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        """
        Execute all capability checks.

        artifacts may contain:
          - 'task': task description string
          - 'task_description': alternative key
        """
        start = time.monotonic()
        checks: list[CheckResult] = []
        workdir_path = Path(workdir) if workdir else Path.cwd()

        # 1. Core tools check
        checks.extend(self._check_core_tools())

        # 2. Static capability gaps
        checks.extend(self._check_static_gaps())

        # 3. Live probes for dynamic capabilities
        checks.extend(self._check_live_probes())

        # 4. Task-based capability inference (if task provided)
        task = artifacts.get("task") or artifacts.get("task_description", "")
        if task:
            checks.extend(self._check_task_capabilities(task))

        # 5. Workdir writability
        checks.append(self._check_workdir(workdir_path))

        # 6. Inventory file existence
        checks.append(self._check_inventory())

        # Aggregate
        passed = all(c.passed for c in checks)
        score = sum(1 for c in checks if c.passed) / max(len(checks), 1)
        duration_ms = int((time.monotonic() - start) * 1000)

        return GateResult(
            gate_name=self.name,
            passed=(score >= self.threshold),
            score=score,
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )

    def _check_core_tools(self) -> list[CheckResult]:
        """Verify core tools are available."""
        results = []
        for tool in self.CORE_TOOLS:
            try:
                subprocess.run(
                    ["which", tool],
                    capture_output=True, text=True, timeout=5,
                )
                results.append(CheckResult(
                    check_id=f"CAP-TOOL-{tool.upper()}",
                    requirement_id="CAP-001",
                    description=f"Core tool '{tool}' available",
                    passed=True,
                    expected=tool,
                    actual=tool,
                    fix_phase=0,
                    fix_agent="orchestrator",
                    diagnostic=f"Tool '{tool}' found",
                ))
            except Exception:
                results.append(CheckResult(
                    check_id=f"CAP-TOOL-{tool.upper()}",
                    requirement_id="CAP-001",
                    description=f"Core tool '{tool}' available",
                    passed=False,
                    expected=tool,
                    actual="MISSING",
                    fix_phase=0,
                    fix_agent="orchestrator",
                    diagnostic=f"Core tool '{tool}' not found. Install: apt install {tool}",
                ))
        return results

    def _check_static_gaps(self) -> list[CheckResult]:
        """Report known static capability gaps."""
        results = []
        for gap_name, description in self.KNOWN_GAPS.items():
            results.append(CheckResult(
                check_id=f"CAP-GAP-{gap_name.upper()}",
                requirement_id="CAP-002",
                description=f"Capability '{gap_name}' availability",
                passed=False,  # These are known gaps — always report
                expected="Available",
                actual=f"UNAVAILABLE: {description}",
                fix_phase=0,
                fix_agent="orchestrator",
                diagnostic=f"Static gap: {gap_name} is not available. {description}",
            ))
        return results

    def _check_live_probes(self) -> list[CheckResult]:
        """Execute live probes for dynamic capabilities."""
        results = []
        for cap_name, check_cmd in self.LIVE_PROBES.items():
            diagnostic = ""
            passed = False
            actual = "UNKNOWN"

            try:
                proc = subprocess.run(
                    check_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                output = proc.stdout.strip()
                actual = output

                # Check semantics:
                # "command || echo 0" → success if output is non-zero and not "0"
                # "command && echo 1 || echo 0" → success if output is "1"
                if check_cmd.endswith("|| echo 0"):
                    passed = output not in ("0", "")
                elif check_cmd.endswith("|| echo 0"):
                    passed = output == "1"
                elif "grep -q" in check_cmd:
                    passed = proc.returncode == 0
                elif ">/dev/null" in check_cmd:
                    passed = proc.returncode == 0
                else:
                    passed = proc.returncode == 0

                diagnostic = f"Live probe: {cap_name} → {'AVAILABLE' if passed else 'UNAVAILABLE'} (output: {output[:100]})"

            except subprocess.TimeoutExpired:
                actual = "TIMEOUT"
                diagnostic = f"Live probe timeout (10s): {cap_name}"
            except Exception as e:
                actual = f"ERROR: {e}"
                diagnostic = f"Live probe error: {cap_name} → {e}"

            results.append(CheckResult(
                check_id=f"CAP-PROBE-{cap_name.upper()}",
                requirement_id="CAP-003",
                description=f"Live probe for '{cap_name}'",
                passed=passed,
                expected="AVAILABLE",
                actual=actual[:200],
                fix_phase=0,
                fix_agent="orchestrator",
                diagnostic=diagnostic[:400],
            ))

        return results

    def _check_task_capabilities(self, task: str) -> list[CheckResult]:
        """Infer required capabilities from task description."""
        results = []
        task_lower = task.lower()

        # Keyword-based inference (L1, ~60% accuracy)
        keyword_map = {
            "vision": ["картинк", "изображен", "скриншот", "screenshot", "image", "picture", "photo", "фото"],
            "adb": ["телефон", "phone", "android", "adb", "мобильн", "mobile"],
            "browser_gui": ["браузер", "browser", "gui", "интерфейс", "сайт", "web"],
            "ffmpeg": ["аудио", "audio", "видео", "video", "звук", "sound", "голос", "voice"],
            "docker": ["docker", "контейнер", "container"],
            "cuda": ["gpu", "cuda", "ml", "обучен", "train"],
            "neo4j": ["neo4j", "граф", "graph", "база данных", "database"],
            "searchbox_mcp": ["поиск", "search", "research", "исследова"],
        }

        for cap_name, keywords in keyword_map.items():
            if any(kw in task_lower for kw in keywords):
                gap_known = cap_name in self.KNOWN_GAPS
                results.append(CheckResult(
                    check_id=f"CAP-INFER-{cap_name.upper()}",
                    requirement_id="CAP-004",
                    description=f"Task requires '{cap_name}' (keyword match)",
                    passed=not gap_known,  # Pass if capability IS available (not a known gap)
                    expected="AVAILABLE" if not gap_known else "WORKAROUND",
                    actual=f"UNAVAILABLE: {self.KNOWN_GAPS.get(cap_name, 'Capability missing from inventory')}" if gap_known else "AVAILABLE",
                    fix_phase=0,
                    fix_agent="orchestrator",
                    diagnostic=f"Task keyword match: '{cap_name}' {'is UNAVAILABLE (known gap)' if gap_known else 'appears available'}. Keywords matched: {[k for k in keywords if k in task_lower]}",
                ))

        return results

    def _check_workdir(self, workdir: Path) -> CheckResult:
        """Verify workspace directory is writable."""
        writable = workdir.exists() and os.access(workdir, os.W_OK) if workdir else False
        return CheckResult(
            check_id="CAP-WORKDIR",
            requirement_id="CAP-005",
            description="Workspace directory writable",
            passed=writable,
            expected="Writable",
            actual=str(workdir) if writable else f"NOT WRITABLE: {workdir}",
            fix_phase=0,
            fix_agent="orchestrator",
            diagnostic=f"Workspace {workdir} {'is writable' if writable else 'is NOT writable'}" if workdir else "No workspace specified",
        )

    def _check_inventory(self) -> CheckResult:
        """Verify capability inventory file exists."""
        inventory_path = Path("/home/user/.hermes/agents/capability_inventory.yaml")
        exists = inventory_path.exists()
        return CheckResult(
            check_id="CAP-INVENTORY",
            requirement_id="CAP-006",
            description="Capability inventory exists",
            passed=exists,
            expected=str(inventory_path),
            actual=str(inventory_path) if exists else "MISSING",
            fix_phase=0,
            fix_agent="orchestrator",
            diagnostic=f"Capability inventory {'found' if exists else 'NOT FOUND at ' + str(inventory_path)}",
        )
