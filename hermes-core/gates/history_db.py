"""
Gate History DB — SQLite storage for gate run history.

Used for: regression detection, stuck detection, cross-cycle Auditor analysis.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional


DB_PATH = Path.home() / ".hermes" / "gate_history.db"


def _get_db() -> sqlite3.Connection:
    """Get or create the gate history SQLite database."""
    db_path = DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS gate_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id TEXT NOT NULL,
            iteration INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            verdict TEXT NOT NULL,
            total_gates INTEGER NOT NULL DEFAULT 0,
            passed_gates INTEGER NOT NULL DEFAULT 0,
            failed_gates INTEGER NOT NULL DEFAULT 0,
            total_checks INTEGER NOT NULL DEFAULT 0,
            passed_checks INTEGER NOT NULL DEFAULT 0,
            failed_checks INTEGER NOT NULL DEFAULT 0,
            first_failure_gate TEXT,
            first_failure_check_id TEXT,
            first_failure_diagnostic TEXT,
            first_failure_fix_phase INTEGER,
            first_failure_fix_agent TEXT,
            first_failure_code_path TEXT,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            workdir TEXT NOT NULL DEFAULT '',
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS gate_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES gate_runs(id),
            gate_name TEXT NOT NULL,
            check_id TEXT NOT NULL,
            requirement_id TEXT DEFAULT '',
            passed INTEGER NOT NULL DEFAULT 0,
            actual TEXT DEFAULT '',
            expected TEXT DEFAULT '',
            fix_phase INTEGER,
            fix_agent TEXT,
            code_path TEXT DEFAULT '',
            diagnostic TEXT DEFAULT '',
            evidence TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_gate_runs_cycle
            ON gate_runs(cycle_id, iteration);
        CREATE INDEX IF NOT EXISTS idx_gate_runs_verdict
            ON gate_runs(verdict);
        CREATE INDEX IF NOT EXISTS idx_gate_checks_run
            ON gate_checks(run_id);
        CREATE INDEX IF NOT EXISTS idx_gate_checks_passed
            ON gate_checks(passed);
        CREATE INDEX IF NOT EXISTS idx_gate_checks_requirement
            ON gate_checks(requirement_id);
    """)


def record_run(verdict_dict: dict) -> int:
    """
    Record a gate run verdict to the history DB.

    Returns the run_id (row ID).
    """
    conn = _get_db()

    gates = verdict_dict.get("gates", [])
    total_checks = sum(len(g.get("checks", [])) for g in gates)
    passed_checks = sum(
        sum(1 for c in g.get("checks", []) if c.get("passed"))
        for g in gates
    )

    # Find first failure
    first_failure_gate = None
    first_failure_check = None
    for gate in gates:
        if not gate.get("passed"):
            first_failure_gate = gate.get("gate_name")
            for check in gate.get("checks", []):
                if not check.get("passed"):
                    first_failure_check = check
                    break
            break

    cursor = conn.execute(
        """INSERT INTO gate_runs (
            cycle_id, iteration, verdict, total_gates, passed_gates,
            failed_gates, total_checks, passed_checks, failed_checks,
            first_failure_gate, first_failure_check_id,
            first_failure_diagnostic, first_failure_fix_phase,
            first_failure_fix_agent, first_failure_code_path,
            duration_ms, workdir, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            verdict_dict.get("cycle_id", "unknown"),
            verdict_dict.get("iteration", 0),
            verdict_dict.get("verdict", "FAILED"),
            verdict_dict.get("total_gates", 0),
            verdict_dict.get("passed_gates", 0),
            verdict_dict.get("failed_gates", 0),
            total_checks,
            passed_checks,
            total_checks - passed_checks,
            first_failure_gate,
            first_failure_check.get("check_id") if first_failure_check else None,
            first_failure_check.get("diagnostic", "")[:400] if first_failure_check else None,
            first_failure_check.get("fix_phase") if first_failure_check else None,
            first_failure_check.get("fix_agent") if first_failure_check else None,
            first_failure_check.get("code_path") if first_failure_check else None,
            sum(g.get("duration_ms", 0) for g in gates),
            verdict_dict.get("workdir", ""),
            json.dumps(verdict_dict),
        ),
    )
    run_id = cursor.lastrowid

    # Record individual checks
    for gate in gates:
        gate_name = gate.get("gate_name", "unknown")
        for check in gate.get("checks", []):
            conn.execute(
                """INSERT INTO gate_checks (
                    run_id, gate_name, check_id, requirement_id,
                    passed, actual, expected, fix_phase, fix_agent,
                    code_path, diagnostic, evidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    gate_name,
                    check.get("check_id", "unknown"),
                    check.get("requirement_id", ""),
                    1 if check.get("passed") else 0,
                    check.get("actual", ""),
                    check.get("expected", ""),
                    check.get("fix_phase"),
                    check.get("fix_agent"),
                    check.get("code_path", ""),
                    check.get("diagnostic", "")[:400],
                    check.get("evidence", "")[:500],
                ),
            )

    conn.commit()
    conn.close()
    return run_id


def detect_stuck(cycle_id: str, threshold: int = 3) -> Optional[dict]:
    """Detect if the same failure diagnostic has appeared threshold times in a row."""
    conn = _get_db()

    row = conn.execute(
        """SELECT first_failure_diagnostic, COUNT(*) as cnt,
                  MIN(iteration) as started_at, MAX(iteration) as last_at
           FROM (
               SELECT *,
                   LAG(first_failure_diagnostic) OVER (
                       PARTITION BY cycle_id ORDER BY iteration
                   ) as prev_diag
               FROM gate_runs
               WHERE cycle_id = ? AND verdict = 'FAILED'
           )
           WHERE first_failure_diagnostic = prev_diag
              AND first_failure_diagnostic IS NOT NULL
           GROUP BY first_failure_diagnostic
           HAVING COUNT(*) >= ?""",
        (cycle_id, threshold),
    ).fetchone()

    conn.close()

    if row:
        return {
            "stuck": True,
            "diagnostic": row["first_failure_diagnostic"],
            "consecutive_count": row["cnt"],
            "started_iteration": row["started_at"],
            "last_iteration": row["last_at"],
        }
    return None


def detect_regression(cycle_id: str) -> Optional[dict]:
    """Detect if the latest run has fewer passed checks than the previous one."""
    conn = _get_db()

    rows = conn.execute(
        """SELECT iteration, passed_checks FROM gate_runs
           WHERE cycle_id = ? ORDER BY iteration DESC LIMIT 2""",
        (cycle_id,),
    ).fetchall()

    conn.close()

    if len(rows) == 2 and rows[0]["passed_checks"] < rows[1]["passed_checks"]:
        return {
            "regression": True,
            "current_iteration": rows[0]["iteration"],
            "current_passed": rows[0]["passed_checks"],
            "previous_iteration": rows[1]["iteration"],
            "previous_passed": rows[1]["passed_checks"],
            "delta": rows[0]["passed_checks"] - rows[1]["passed_checks"],
        }
    return None


def get_cycle_metrics(cycle_id: str) -> dict:
    """Get aggregate metrics for a cycle."""
    conn = _get_db()

    row = conn.execute(
        """SELECT COUNT(*) as total_iterations,
                  SUM(CASE WHEN verdict = 'ALL_PASSED' THEN 1 ELSE 0 END) as final_pass,
                  AVG(passed_checks * 1.0 / CASE WHEN total_checks > 0 THEN total_checks ELSE 1 END) as avg_score,
                  MIN(timestamp) as started_at,
                  MAX(timestamp) as finished_at,
                  SUM(duration_ms) as total_duration_ms
           FROM gate_runs
           WHERE cycle_id = ?""",
        (cycle_id,),
    ).fetchone()

    conn.close()

    if row:
        return {
            "cycle_id": cycle_id,
            "total_iterations": row["total_iterations"],
            "final_pass": bool(row["final_pass"]),
            "avg_score": round(row["avg_score"] or 0, 3),
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "total_duration_ms": row["total_duration_ms"] or 0,
        }
    return {}
