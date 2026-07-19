#!/usr/bin/env python3
"""Execute her2code-phase-knowledge.cypher against Neo4j Education Graph.

Uses the HTTP API to avoid credential-tuple shell masking issues.
Run from any environment with requests installed:

    python3 /home/user/.hermes/skills/mlops/neo4j-knowledge-graph/references/her2code-knowledge-ingest.py

If requests is not available, use the bundled jupyterlab venv:

    /home/user/jupyterlab/.venv/bin/python /home/user/.hermes/skills/mlops/neo4j-knowledge-graph/references/her2code-knowledge-ingest.py
"""
import json
import os
import sys
from pathlib import Path

from requests.auth import HTTPBasicAuth

NEO4J_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"
NEO4J_USER = "neo4j"
NEO4J_PASS = "changeme"

CYPHER_FILE = Path(__file__).with_suffix(".cypher")

def run_statement(session, statement):
    payload = {"statements": [{"statement": statement}]}
    r = session.post(NEO4J_URL, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"Neo4j error: {data['errors']}")
    return data

def main():
    try:
        import requests
    except ImportError as exc:
        print("ERROR: 'requests' is not installed. Use the jupyterlab venv or install it.", file=sys.stderr)
        raise SystemExit(1) from exc

    if not CYPHER_FILE.exists():
        print(f"ERROR: Cypher file not found: {CYPHER_FILE}", file=sys.stderr)
        raise SystemExit(1)

    raw = CYPHER_FILE.read_text(encoding="utf-8")
    # Split on semicolons, keeping comments and blank lines is fine because
    # Neo4j HTTP API ignores them, but we strip purely cosmetic blank statements.
    statements = [s.strip() for s in raw.split(";") if s.strip()]

    print(f"Loaded {len(statements)} statement(s) from {CYPHER_FILE}")

    auth = HTTPBasicAuth(NEO4J_USER, NEO4J_PASS)
    with requests.Session() as session:
        session.auth = auth
        session.headers["Content-Type"] = "application/json"

        # Verify connectivity
        run_statement(session, "RETURN 1")
        print("Neo4j connection OK")

        for idx, stmt in enumerate(statements, start=1):
            try:
                run_statement(session, stmt)
                print(f"  [{idx}/{len(statements)}] OK")
            except Exception as exc:
                print(f"  [{idx}/{len(statements)}] FAILED: {exc}", file=sys.stderr)
                print(f"  Statement preview: {stmt[:200]}...", file=sys.stderr)
                raise SystemExit(1)

    print("Ingestion complete.")

if __name__ == "__main__":
    main()
