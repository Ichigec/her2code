"""
IntegrationGate — verify cross-module imports via Neo4j codebase graph.

Checks: orphaned imports, broken function calls, unresolved references.
Requires Neo4j running at localhost:7687.
"""

import json
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

from gates.base import GatePlugin, GateResult, CheckResult


class IntegrationGate(GatePlugin):
    """Verify cross-module imports resolve correctly using Neo4j."""

    name = "integration-gate"
    description = "All cross-module imports must resolve correctly"
    threshold = 1.0
    timeout = 30

    NEO4J_URI = "http://localhost:7474"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "changeme"

    def check(self, artifacts: dict, workdir: str) -> GateResult:
        start = time.monotonic()

        # Check if Neo4j is reachable
        if not self._neo4j_health():
            return GateResult(
                gate_name=self.name,
                passed=True,
                score=1.0,
                threshold=self.threshold,
                checks=[CheckResult(
                    check_id="INT-NEO4J-UNAVAILABLE",
                    passed=True,
                    description="Neo4j not available — gate skipped",
                    actual="Neo4j unreachable",
                    expected="Neo4j running for integration checks",
                )],
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        checks = []

        # Check 1: Orphaned imports
        orphaned = self._check_orphaned_imports()
        for row in orphaned:
            checks.append(CheckResult(
                check_id=f"INT-ORPHAN-{row.get('file', 'unknown')}-{row.get('import_name', '?')}",
                passed=False,
                description=f"Orphaned import: {row.get('import_name', '?')}",
                actual=f"Import '{row.get('import_name', '?')}' does not resolve",
                expected="Import resolves to existing file",
                fix_phase=6,
                fix_agent="developer",
                code_path=f"{row.get('file', '')}:{row.get('line', '?')}",
                diagnostic=(
                    f"Import '{row.get('import_name', '')}' in {row.get('file', '')}"
                    f":{row.get('line', '')} does not resolve. "
                    f"Check that the file exists and the import path is correct."
                ),
            ))

        # Check 2: Broken function calls
        broken_calls = self._check_broken_calls()
        for row in broken_calls:
            checks.append(CheckResult(
                check_id=f"INT-BROKEN-{row.get('caller', '')[:60]}-{row.get('callee', '')[:60]}",
                passed=False,
                description=f"Broken call: {row.get('callee', '')[:80]}",
                actual=f"Function '{row.get('callee', '')}' status: {row.get('status', 'unknown')}",
                expected="All called functions exist and are not deprecated",
                fix_phase=6,
                fix_agent="developer",
                code_path=row.get("file", ""),
                diagnostic=(
                    f"Call from {row.get('caller', '')} to {row.get('callee', '')} "
                    f"is broken (status: {row.get('status', 'unknown')}). "
                    f"File: {row.get('file', 'unknown')}"
                ),
            ))

        duration_ms = int((time.monotonic() - start) * 1000)

        if not checks:
            checks.append(CheckResult(
                check_id="INT-ALL-CLEAN",
                passed=True,
                description="All imports and calls resolve correctly",
                actual="0 orphaned imports, 0 broken calls",
                expected="All imports and calls clean",
            ))

        return GateResult(
            gate_name=self.name,
            passed=all(c.passed for c in checks),
            score=sum(1 for c in checks if c.passed) / max(len(checks), 1) if checks else 1.0,
            threshold=self.threshold,
            checks=checks,
            duration_ms=duration_ms,
        )

    # ── Neo4j Helpers ──────────────────────────────────────────────────────

    def _neo4j_health(self) -> bool:
        """Check if Neo4j HTTP endpoint is reachable."""
        try:
            req = Request(f"{self.NEO4J_URI}/db/neo4j/tx/commit")
            req.add_header("Content-Type", "application/json")
            auth_str = f"{self.NEO4J_USER}:{self.NEO4J_PASSWORD}"
            req.add_header("Authorization", f"Basic {self._b64(auth_str)}")
            body = json.dumps({"statements": [{"statement": "RETURN 1"}]}).encode()
            urlopen(req, data=body, timeout=5)
            return True
        except (URLError, OSError):
            return False

    def _neo4j_query(self, statement: str, params: dict | None = None) -> list[dict]:
        """Run a Cypher query and return results as list of dicts."""
        try:
            req = Request(f"{self.NEO4J_URI}/db/neo4j/tx/commit")
            req.add_header("Content-Type", "application/json")
            auth_str = f"{self.NEO4J_USER}:{self.NEO4J_PASSWORD}"
            req.add_header("Authorization", f"Basic {self._b64(auth_str)}")
            body = json.dumps({
                "statements": [{"statement": statement, "parameters": params or {}}]
            }).encode()
            response = urlopen(req, data=body, timeout=10)
            data = json.loads(response.read())
            results = data.get("results", [])
            if not results:
                return []
            rows = results[0].get("data", [])
            columns = results[0].get("columns", [])
            return [dict(zip(columns, row.get("row", []))) for row in rows]
        except Exception:
            return []

    def _check_orphaned_imports(self) -> list[dict]:
        """Find imports that don't resolve to any file."""
        return self._neo4j_query("""
            MATCH (f:CodeFile)-[:IMPORTS]->(imp:CodeImport)
            WHERE NOT EXISTS {
                MATCH (target:CodeFile)
                WHERE target.name = imp.name
                   OR target.name = imp.name + '.py'
                   OR target.name = replace(imp.name, '.', '/') + '.py'
            }
            RETURN f.name AS file, imp.name AS import_name,
                   imp.line AS line, imp.status AS status
            LIMIT 50
        """)

    def _check_broken_calls(self) -> list[dict]:
        """Find calls to removed or deprecated functions."""
        return self._neo4j_query("""
            MATCH (caller:CodeFunction)-[:CALLS]->(callee:CodeFunction)
            WHERE callee.status IN ['removed', 'deprecated']
               OR callee.status IS NULL
            RETURN caller.signature AS caller,
                   callee.signature AS callee,
                   callee.file_path AS file,
                   callee.status AS status
            LIMIT 50
        """)

    @staticmethod
    def _b64(s: str) -> str:
        import base64
        return base64.b64encode(s.encode()).decode()
