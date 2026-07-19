"""
GateScheduler — topological sort and parallel execution of gates.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from gates.base import GatePlugin, GateResult, GateVerdict
from gates.registry import get_enabled_gates


class GateScheduler:
    """
    Schedules gates respecting their dependency DAG.

    Gates at the same topological level run in parallel.
    On first failure, remaining gates are cancelled (FAST FAIL).
    """

    def __init__(self, config: dict, mode: str = "balanced"):
        self.config = config
        self.mode = mode

    def run_all(self, artifacts: dict, workdir: str) -> GateVerdict:
        """
        Execute all enabled gates respecting dependencies.

        Returns GateVerdict with ALL_PASSED or FAILED.
        """
        start = time.time()

        # Discover and instantiate gates
        all_gates = get_enabled_gates(self.config, self.mode)

        if not all_gates:
            return GateVerdict(
                verdict="ALL_PASSED",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                workdir=workdir,
                total_gates=0,
                passed_gates=0,
                failed_gates=0,
                gates=[],
            )

        # Build dependency graph
        gate_map = {g.name: g for g in all_gates}
        levels = self._topological_sort(all_gates)

        # Inject mode-specific config into artifacts
        mode_config = self.config.get("modes", {}).get(self.mode, {})
        if "security-gate" in mode_config:
            tools_override = mode_config["security-gate"].get("tools", {})
            if "security_tools" not in artifacts:
                artifacts["security_tools"] = tools_override

        results: list[GateResult] = []
        total_duration = 0

        for level_idx, level in enumerate(levels):
            # Run level in parallel
            if len(level) == 1:
                gate = level[0]
                result = self._run_single(gate, artifacts, workdir)
                results.append(result)
                total_duration += result.duration_ms

                # FAST FAIL
                if not result.passed:
                    # Cancel remaining levels
                    return self._build_verdict(
                        results=results,
                        remaining_gates=sum(len(l) for l in levels[level_idx + 1:]),
                        workdir=workdir,
                        start=start,
                    )
            else:
                with ThreadPoolExecutor(max_workers=len(level)) as executor:
                    futures = {
                        executor.submit(self._run_single, gate, artifacts, workdir): gate
                        for gate in level
                    }

                    for future in as_completed(futures):
                        result = future.result()
                        results.append(result)
                        total_duration += result.duration_ms

                        # FAST FAIL: if any gate fails, collect completed results, cancel rest
                        if not result.passed:
                            # Collect results from already-completed futures
                            for f in list(futures.keys()):
                                if f.done() and f != future:
                                    try:
                                        r = f.result()
                                        results.append(r)
                                        total_duration += r.duration_ms
                                    except Exception:
                                        pass
                            # Cancel remaining
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            return self._build_verdict(
                                results=results,
                                remaining_gates=(
                                    sum(len(l) for l in levels[level_idx + 1:]) +
                                    sum(1 for f in futures if not f.done())
                                ),
                                workdir=workdir,
                                start=start,
                            )

        return self._build_verdict(
            results=results,
            remaining_gates=0,
            workdir=workdir,
            start=start,
        )

    def _run_single(self, gate: GatePlugin, artifacts: dict, workdir: str) -> GateResult:
        """Run a single gate with error handling."""
        try:
            return gate.check(artifacts, workdir)
        except Exception as e:
            import traceback
            return GateResult(
                gate_name=gate.name,
                passed=False,
                score=0.0,
                threshold=gate.threshold,
                checks=[],
                duration_ms=0,
                error=f"Gate '{gate.name}' crashed: {e}\n{traceback.format_exc()[-500:]}",
            )

    def _topological_sort(self, gates: list[GatePlugin]) -> list[list[GatePlugin]]:
        """
        Sort gates into levels based on their depends_on declarations.

        Returns list of levels, where each level is a list of gates
        that can run in parallel.

        MANDATORY gates (business-analysis-gate) always run in their own
        dedicated level before any other gates, to ensure fast feedback
        on traceability issues.
        """
        gate_map = {g.name: g for g in gates}
        dag = {g.name: set(g.depends_on) & set(gate_map.keys()) for g in gates}

        levels = []
        completed: set[str] = set()

        # Mandatory gates run first, alone in their own level
        mandatory_names = {g.name for g in gates if g.mandatory}
        if mandatory_names:
            mandatory_level = [gate_map[name] for name in mandatory_names if name in gate_map]
            if mandatory_level:
                levels.append(mandatory_level)
                completed.update(mandatory_names)

        remaining = set(dag.keys()) - completed

        while remaining:
            # Gates whose dependencies are all completed
            ready = {
                name for name in remaining
                if dag[name].issubset(completed)
            }

            if not ready:
                # Circular dependency or missing dependency
                ready = remaining.copy()

            level = [gate_map[name] for name in ready]
            levels.append(level)
            completed.update(ready)
            remaining -= ready

        return levels

    def _build_verdict(
        self,
        results: list[GateResult],
        remaining_gates: int,
        workdir: str,
        start: float,
    ) -> GateVerdict:
        """Build final GateVerdict from gate results."""
        passed_gates = sum(1 for r in results if r.passed)
        total_gates = len(results) + remaining_gates

        verdict = GateVerdict(
            verdict="ALL_PASSED" if all(r.passed for r in results) and remaining_gates == 0 else "FAILED",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            workdir=workdir,
            cycle_id=results[0].gate_name if results else "unknown",
            total_gates=total_gates,
            passed_gates=passed_gates,
            failed_gates=total_gates - passed_gates,
            gates=results,
        )

        if remaining_gates > 0:
            verdict.error = f"{remaining_gates} gate(s) were not executed (fast-fail)"

        return verdict
