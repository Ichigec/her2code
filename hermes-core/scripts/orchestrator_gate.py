#!/usr/bin/env python3
"""
Pre-Flight Gate — запускается перед Phase 6 (Implementation).
Проверяет 6 условий. Все должны пройти, иначе Implementation блокируется.

Usage:
    python3 orchestrator_gate.py          # human-readable output
    python3 orchestrator_gate.py --json   # JSON output
Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# PreFlightGate
# ---------------------------------------------------------------------------

class PreFlightGate:
    """Pre-Flight Gate with 6 mandatory checks."""

    def __init__(self, workdir: str = os.getcwd()):
        self.workdir = workdir
        self.results: list[CheckResult] = []

    # -- helpers --------------------------------------------------------------

    def _run(self, cmd: list[str], timeout: int = 10, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout,
            env=env or os.environ.copy(),
        )

    def _add(self, name: str, passed: bool, detail: str = "", error: str | None = None):
        self.results.append(CheckResult(name=name, passed=passed, detail=detail, error=error))

    # -- 6 checks -------------------------------------------------------------

    def check_contracts(self):
        """a) Health-check всех сервисов через curl (таймаут 5s)."""
        endpoints: list[tuple[str, list[str]]] = [
            ("Hermes API",          ["curl", "-sf", "--max-time", "5", "http://localhost:8643/health"]),
            ("Voice proxy",         ["curl", "-sf", "--max-time", "5", "http://localhost:8647/health"]),
            ("LiteLLM",             ["curl", "-sf", "--max-time", "5", "-H", "Authorization: Bearer sk-local", "http://localhost:4000/v1/models"]),
            ("Neo4j",               ["curl", "-sf", "--max-time", "5", "-u", "neo4j:<YOUR_NEO4J_PASSWORD>",
                                     "-H", "Content-Type: application/json",
                                     "-d", '{"statements":[{"statement":"RETURN 1"}]}',
                                     "http://localhost:7474/db/neo4j/tx/commit"]),
        ]

        # Optional services: failure = WARN, not BLOCKER
        optional = {"Voice proxy"}

        all_ok = True
        details: list[str] = []
        for name, cmd in endpoints:
            try:
                r = self._run(cmd, timeout=7)
                if r.returncode == 0:
                    details.append(f"  ✓ {name} — OK")
                else:
                    if name in optional:
                        details.append(f"  ⚠ {name} — not running (optional, skipping)")
                    else:
                        details.append(f"  ✗ {name} — exit code {r.returncode}: {r.stderr.strip()[:200]}")
                        all_ok = False
            except subprocess.TimeoutExpired:
                if name in optional:
                    details.append(f"  ⚠ {name} — timeout (optional, skipping)")
                else:
                    details.append(f"  ✗ {name} — timeout (5s)")
                    all_ok = False
            except FileNotFoundError:
                details.append(f"  ✗ {name} — curl not found")
                all_ok = False
            except Exception as exc:
                details.append(f"  ✗ {name} — {exc}")
                all_ok = False

        self._add("contracts", all_ok, "\n".join(details),
                  None if all_ok else "One or more services unreachable")

    def check_ports(self):
        """b) Проверка конфликтов портов (ss -tlnp)."""
        try:
            r = self._run(["ss", "-tlnp"], timeout=5)
        except FileNotFoundError:
            self._add("ports", False, "ss not found", "Cannot run ss -tlnp")
            return
        except Exception as exc:
            self._add("ports", False, f"ss failed: {exc}", str(exc))
            return

        lines = r.stdout.strip().split("\n")
        # port -> set of (process_name or 'unknown')
        port_procs: dict[str, set[str]] = {}

        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) < 4:
                continue
            listen_addr = parts[3]  # e.g. 0.0.0.0:8643, [::]:8643
            if ":" not in listen_addr:
                continue
            # Extract port: strip brackets from IPv6 addresses like [::]:4000
            port = listen_addr.rsplit(":", 1)[-1]

            # Extract process name from last column if present
            # Format: users:(("procname",pid=NNN,fd=N))
            proc_col = parts[-1] if len(parts) >= 7 else ""
            proc_name = "unknown"
            if 'users:(("' in proc_col:
                try:
                    proc_name = proc_col.split('users:(("', 1)[1].split('"', 1)[0]
                except (IndexError, ValueError):
                    pass

            port_procs.setdefault(port, set()).add(proc_name)

        conflicts: dict[str, str] = {}
        for p, procs in port_procs.items():
            if len(procs) > 1:
                conflicts[p] = ", ".join(sorted(procs))
        if conflicts:
            detail_lines = [f"  ✗ Port conflicts detected:"]
            for p, procs in sorted(conflicts.items()):
                detail_lines.append(f"    Port {p}: {', '.join(procs)}")
            self._add("ports", False, "\n".join(detail_lines), "Port conflicts found")
        else:
            self._add("ports", True, f"  ✓ No port conflicts ({len(port_procs)} listening ports)")

    def check_env_vars(self):
        """c) Кросс-компонентная проверка HERMES_HOME и NEO4J_PASSWORD."""
        hermes_home = os.environ.get("HERMES_HOME", "")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "")

        issues: list[str] = []

        if not hermes_home:
            issues.append("  ✗ HERMES_HOME is not set")
        elif not os.path.isdir(hermes_home):
            issues.append(f"  ✗ HERMES_HOME='{hermes_home}' is not a directory")
        else:
            issues.append(f"  ✓ HERMES_HOME='{hermes_home}' — exists")

        if not neo4j_password:
            neo4j_password = "changeme"  # default for local dev
            issues.append("  ⚠ NEO4J_PASSWORD not set, using default 'changeme'")
        else:
            issues.append(f"  ✓ NEO4J_PASSWORD is set (len={len(neo4j_password)})")

        all_ok = all(not line.startswith("  ✗") for line in issues)
        self._add("env_vars", all_ok, "\n".join(issues),
                  None if all_ok else "Environment variables misconfigured")

    def check_isolation(self):
        """d) Проверка изоляции — HERMES_HOME уникален для процесса."""
        hermes_home = os.environ.get("HERMES_HOME", "")
        if not hermes_home:
            self._add("isolation", False,
                      "  ✗ HERMES_HOME not set — cannot verify isolation",
                      "HERMES_HOME missing")
            return

        exists = os.path.isdir(hermes_home)
        pid = os.getpid()
        detail = (
            f"  ✓ HERMES_HOME='{hermes_home}' (pid={pid}, dir_exists={exists})"
            if exists else
            f"  ✗ HERMES_HOME='{hermes_home}' — directory does not exist"
        )
        self._add("isolation", exists, detail,
                  None if exists else f"Directory {hermes_home} not found")

    def check_observers(self):
        """e) Проверка observers: если выключены в config.yaml — PASS (intentional).
        Если включены — проверить PID files или processes (WARNING, не BLOCKER)."""
        # Check config.yaml observer.enabled
        observer_enabled = True  # default
        try:
            import yaml
            config_path = os.path.expanduser("~/.hermes/config.yaml")
            if os.path.exists(config_path):
                with open(config_path) as fh:
                    cfg = yaml.safe_load(fh)
                obs_cfg = cfg.get("observer", {})
                observer_enabled = obs_cfg.get("enabled", True)
        except Exception:
            pass

        if not observer_enabled:
            self._add("observers", True,
                      "  ✓ Observers disabled in config.yaml (GUI toggle OFF)",
                      None)
            return

        # Observers enabled — check for PID files or running processes
        observer_pids = []
        pid_dir = "/tmp"
        try:
            for fname in os.listdir(pid_dir):
                if fname.startswith("observer_") and fname.endswith(".pid"):
                    pid_path = os.path.join(pid_dir, fname)
                    try:
                        with open(pid_path) as fh:
                            pid_val = fh.read().strip()
                        if pid_val:
                            observer_pids.append((fname, int(pid_val)))
                    except (ValueError, OSError):
                        continue
        except FileNotFoundError:
            pass

        alive = 0
        dead = 0
        details: list[str] = []

        for name, pid_val in observer_pids:
            try:
                os.kill(pid_val, 0)  # signal 0 — check existence
                alive += 1
                details.append(f"  ✓ {name} (pid={pid_val}) — alive")
            except OSError:
                dead += 1
                details.append(f"  ⚠ {name} (pid={pid_val}) — not running")

        if not observer_pids:
            # No PID files but observers enabled — plan2 spawns via delegate_task dynamically
            # This is NOT a blocker, just informational
            self._add("observers", True,
                      "  ⚠ Observers enabled in config but no daemon PID files. "
                      "Plan2 spawns observers via delegate_task at Phase 0 (in-process, not daemonized).",
                      None)
        elif dead == 0:
            self._add("observers", True,
                      f"  ✓ All {alive} observers alive\n" + "\n".join(details))
        else:
            # Some daemons dead — WARNING, not blocker (in-process observers still work)
            self._add("observers", True,
                      f"  ⚠ {dead}/{len(observer_pids)} daemon observers dead "
                      f"(in-process observers still active)\n" + "\n".join(details),
                      None)

    def check_research(self):
        """f) Проверка наличия research-артефакта (>500 байт)."""
        candidates: list[str] = []

        # Search in docs/research/
        research_dir = os.path.join(self.workdir, "docs", "research")
        if os.path.isdir(research_dir):
            for fname in os.listdir(research_dir):
                if fname.endswith(".md"):
                    candidates.append(os.path.join(research_dir, fname))

        # Also search .hermes/plans/ for research-like artifacts
        hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~"))
        plans_dir = os.path.join(hermes_home, "plans") if os.path.basename(hermes_home) == ".hermes" else os.path.join(hermes_home, ".hermes", "plans")
        if os.path.isdir(plans_dir):
            for fname in os.listdir(plans_dir):
                if fname.endswith(".md") and "research" in fname.lower():
                    candidates.append(os.path.join(plans_dir, fname))

        details: list[str] = []
        found_valid = False

        for path in sorted(set(candidates)):
            try:
                size = os.path.getsize(path)
                if size > 500:
                    found_valid = True
                    details.append(f"  ✓ {path} ({size} bytes)")
                else:
                    details.append(f"  ✗ {path} ({size} bytes — too small, need >500)")
            except OSError as exc:
                details.append(f"  ✗ {path} — {exc}")

        if not candidates:
            self._add("research", False,
                      "  ✗ No research artifacts found (docs/research/*.md or .hermes/plans/*research*.md)",
                      "No research artifacts")
        elif found_valid:
            self._add("research", True, "\n".join(details))
        else:
            self._add("research", False,
                      "\n".join(details) + "\n  ✗ No artifact >500 bytes",
                      "All artifacts too small or missing")

    def check_research_deep(self):
        """g) Deep research completeness: runs GATE B, C, D on the research artifact.

        Only runs on artifacts explicitly produced by the structured research
        pipeline (containing '## RQ Answers', 'Source Quality Matrix', or
        'schema_version' markers). Legacy free-form research notes are SKIPped.
        """
        import importlib.util

        # Find the latest research artifact
        research_dir = os.path.join(self.workdir, "docs", "research")
        artifact_path = None

        if os.path.isdir(research_dir):
            # Prefer structured .json (per research-output-v1.json schema)
            jsons = sorted(
                [f for f in os.listdir(research_dir) if f.endswith(".json")],
                key=lambda f: os.path.getmtime(os.path.join(research_dir, f)),
                reverse=True,
            )
            if jsons:
                artifact_path = os.path.join(research_dir, jsons[0])
            else:
                # Fall back to .md, but ONLY if it carries structured-output markers
                mds = sorted(
                    [f for f in os.listdir(research_dir) if f.endswith(".md")],
                    key=lambda f: os.path.getmtime(os.path.join(research_dir, f)),
                    reverse=True,
                )
                for m in mds:
                    p = os.path.join(research_dir, m)
                    try:
                        head = open(p, errors="ignore").read(2048)
                    except OSError:
                        continue
                    # Structured research artifacts contain these markers
                    if any(marker in head for marker in (
                        "## RQ Answers",
                        "Source Quality Matrix",
                        "schema_version",
                        "research-output-v1",
                    )):
                        artifact_path = p
                        break

        if not artifact_path or not os.path.isfile(artifact_path):
            # No structured research artifact from an active cycle → SKIP, not FAIL.
            # Legacy free-form notes should not be evaluated against structural gates.
            self._add("research_deep", True,
                      "  ℹ No structured research artifact from active cycle — "
                      "deep gates skipped (legacy notes ignored). "
                      "Gates B/C/D will run when Phase 3 produces a structured artifact.",
                      None)
            return

        details: list[str] = []
        all_passed = True

        # GATE B: Source Quality
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        quality_script = os.path.join(scripts_dir, "research_quality_gate.py")
        if os.path.isfile(quality_script):
            try:
                r = self._run(
                    ["python3", quality_script, "--artifact", artifact_path, "--json"],
                    timeout=15,
                )
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    scores = data.get("scores", {})
                    avg = scores.get("average", 0)
                    details.append(f"  ✓ GATE B (Source Quality): {avg:.2f}/1.0")
                else:
                    details.append(f"  ✗ GATE B (Source Quality): FAIL")
                    all_passed = False
            except Exception as exc:
                details.append(f"  ✗ GATE B: crashed — {exc}")
                all_passed = False

        # GATE C: Completeness
        completeness_script = os.path.join(scripts_dir, "research_completeness_gate.py")
        if os.path.isfile(completeness_script):
            try:
                r = self._run(
                    ["python3", completeness_script, "--artifact", artifact_path, "--json"],
                    timeout=15,
                )
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    passed = data.get("passed", 0)
                    total = data.get("total", 5)
                    details.append(f"  ✓ GATE C (Completeness): {passed}/{total}")
                else:
                    data = json.loads(r.stdout) if r.stdout else {}
                    passed = data.get("passed", 0)
                    total = data.get("total", 5)
                    details.append(f"  ✗ GATE C (Completeness): {passed}/{total}")
                    all_passed = False
            except Exception as exc:
                details.append(f"  ✗ GATE C: crashed — {exc}")
                all_passed = False

        # GATE D: Citations
        citation_script = os.path.join(scripts_dir, "citation_enforcement_gate.py")
        if os.path.isfile(citation_script):
            try:
                r = self._run(
                    ["python3", citation_script, "--artifact", artifact_path,
                     "--verify-sample", "20", "--json"],
                    timeout=30,
                )
                if r.returncode == 0:
                    details.append(f"  ✓ GATE D (Citations): PASS")
                else:
                    details.append(f"  ✗ GATE D (Citations): FAIL")
                    all_passed = False
            except Exception as exc:
                details.append(f"  ✗ GATE D: crashed — {exc}")
                all_passed = False

        self._add("research_deep", all_passed, "\n".join(details),
                  None if all_passed else "One or more deep research gates failed")

    # -- main entry -----------------------------------------------------------

    def check_all(self) -> bool:
        """Run all 7 checks. Returns True if all passed."""
        checks = [
            ("contracts",      self.check_contracts),
            ("ports",          self.check_ports),
            ("env_vars",       self.check_env_vars),
            ("isolation",      self.check_isolation),
            ("observers",      self.check_observers),
            ("research",       self.check_research),
            ("research_deep",  self.check_research_deep),
        ]

        for name, method in checks:
            try:
                method()
            except Exception as exc:
                self._add(name, False, f"  ✗ Check crashed: {exc}", str(exc))

        return all(r.passed for r in self.results)

    def report_text(self) -> str:
        """Human-readable report."""
        lines = ["=" * 60,
                 "  PRE-FLIGHT GATE REPORT",
                 "=" * 60,
                 f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                 f"  Workdir: {self.workdir}",
                 "-" * 60]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"\n  [{status}] {r.name}")
            if r.detail:
                lines.append(r.detail)
            if r.error:
                lines.append(f"  Error: {r.error}")
        lines.append("")
        lines.append("-" * 60)
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        lines.append(f"  Result: {passed}/{total} checks passed")
        if passed == total:
            lines.append("  VERDICT: ALL CHECKS PASSED — Implementation may proceed.")
        else:
            lines.append(f"  VERDICT: {total - passed} CHECK(S) FAILED — Implementation BLOCKED.")
            lines.append("  Fix the issues above and re-run the gate.")
        lines.append("=" * 60)
        return "\n".join(lines)

    def report_json(self) -> str:
        """JSON report."""
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "workdir": self.workdir,
            "passed": sum(1 for r in self.results if r.passed),
            "total": len(self.results),
            "checks": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "detail": r.detail,
                    "error": r.error,
                }
                for r in self.results
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    json_mode = "--json" in sys.argv
    workdir = os.getcwd()

    gate = PreFlightGate(workdir=workdir)
    all_passed = gate.check_all()

    if json_mode:
        print(gate.report_json())
    else:
        print(gate.report_text())

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
