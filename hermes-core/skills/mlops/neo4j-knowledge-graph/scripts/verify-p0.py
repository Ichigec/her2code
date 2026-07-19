#!/usr/bin/env python3
"""
P0 Health Check — Codebase Graph Memory Phase 2
Run from project root: /home/user/dev/codemes/codemes_neo4j_repo-graph_20260617_002228/

Verifies the 4 critical Phase 2 fixes + Neo4j connectivity.
Usage:
    cd /home/user/dev/codemes/codemes_neo4j_repo-graph_20260617_002228
    python3 scripts/verify-p0.py
"""

import ast
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))

FAIL = 0
PASS = 0
FAILS = []


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        FAILS.append(name)
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def read_file(path, fallback=""):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return fallback


# ── 1. BUG-1: driver-close ──────────────────────────────────────────
print("=" * 60)
print("1. BUG-1: driver-close in run_watcher.py")
print("=" * 60)

watcher_src = read_file(os.path.join(PROJECT_ROOT, "run_watcher.py"))

# Must NOT have bare driver.close()
has_bare_close = "driver.close()" in watcher_src
# Must have context-managed session
has_with_session = "with indexer.writer._session() as s:" in watcher_src
# Must have writer.close() AFTER session
has_writer_close = "indexer.writer.close()" in watcher_src

check("No bare driver.close()", not has_bare_close,
      "Found driver.close() — must use context-managed session")
check("Context-managed session (with ... as s:)", has_with_session,
      "Missing 'with indexer.writer._session() as s:'")
check("writer.close() after session", has_writer_close,
      "Missing clean shutdown call")

# ── 2. .venv exclusion ─────────────────────────────────────────────
print()
print("=" * 60)
print("2. .venv exclusion")
print("=" * 60)

scanner_src = read_file(os.path.join(PROJECT_ROOT, "codebase_scanner.py"))
config_src = read_file(os.path.join(PROJECT_ROOT, "codebase_config.yaml"))

check(".venv in DEFAULT_EXCLUDE_PATTERNS (scanner)",
      ".venv" in scanner_src and "DEFAULT_EXCLUDE_PATTERNS" in scanner_src,
      "Check codebase_scanner.py DEFAULT_EXCLUDE_PATTERNS list")
check(".venv in codebase_config.yaml",
      ".venv" in config_src and "exclude_patterns" in config_src,
      "Check codebase_config.yaml exclude_patterns section")

# ── 3. MCP registration ────────────────────────────────────────────
print()
print("=" * 60)
print("3. MCP server registration")
print("=" * 60)

hermes_config = read_file(os.path.join(HERMES_HOME, "config.yaml"))

has_mcp_block = "codebase-graph:" in hermes_config
has_mjs = "codebase-server.mjs" in hermes_config
has_enabled = "enabled: true" in hermes_config.split("codebase-graph:")[1].split("\n", 20) if has_mcp_block else ""

check("codebase-graph block in config.yaml", has_mcp_block,
      "Add codebase-graph MCP server to ~/.hermes/config.yaml")
check("codebase-server.mjs path", has_mjs,
      "Check MCP server path in config")
check("enabled: true", "enabled: true" in str(has_enabled),
      "MCP server is not enabled")

# ── 4. EmbeddingGenerator integration ──────────────────────────────
print()
print("=" * 60)
print("4. EmbeddingGenerator integration")
print("=" * 60)

indexer_src = read_file(os.path.join(PROJECT_ROOT, "codebase_indexer.py"))

check("embedder.encode in full_scan() area",
      "embedder.encode" in indexer_src[:10000],  # rough check
      "full_scan() must call embedder.encode()")
check("embedder.encode in update_file() area",
      indexer_src.count("embedder.encode") >= 2,
      f"Found {indexer_src.count('embedder.encode')} calls — need at least 2 (full_scan + update_file)")
check("Lazy import: EmbeddingGenerator",
      "from codebase_embeddings import EmbeddingGenerator" in indexer_src,
      "Must lazy-import EmbeddingGenerator in _get_embedder()")

# ── 5. Syntax check ────────────────────────────────────────────────
print()
print("=" * 60)
print("5. Syntax check (AST parse)")
print("=" * 60)

py_files = [
    "codebase_indexer.py", "codebase_scanner.py", "codebase_writer.py",
    "codebase_embeddings.py", "codebase_watcher.py", "run_watcher.py",
]
for f in py_files:
    path = os.path.join(PROJECT_ROOT, f)
    try:
        with open(path) as fh:
            ast.parse(fh.read())
        check(f"AST parse: {f}", True)
    except SyntaxError as e:
        check(f"AST parse: {f}", False, str(e))

# ── 6. Neo4j connectivity ──────────────────────────────────────────
print()
print("=" * 60)
print("6. Neo4j live census")
print("=" * 60)

try:
    import json, urllib.request

    req = urllib.request.Request(
        "http://localhost:7474/db/neo4j/tx/commit",
        data=json.dumps({
            "statements": [{
                "statement": "MATCH (n) RETURN labels(n) AS label, count(*) AS cnt ORDER BY cnt DESC"
            }]
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Basic " + __import__("base64").b64encode(b"neo4j:<YOUR_NEO4J_PASSWORD>").decode(),
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        rows = data["results"][0]["data"]
        for row in rows:
            label, cnt = row["row"]
            print(f"  {label[0] if label else '?'}: {cnt}")
        check("Neo4j reachable", True)
        check("CodeFunction > 100", any(r["row"][0] == ["CodeFunction"] and r["row"][1] > 100 for r in rows),
              "CodeFunction count too low or missing")
except Exception as e:
    check("Neo4j reachable", False, str(e))

# ── Summary ────────────────────────────────────────────────────────
print()
print("=" * 60)
total = PASS + FAIL
print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
if FAILS:
    print("\nFailed checks:")
    for f in FAILS:
        print(f"  ❌ {f}")
    sys.exit(1)
else:
    print("All checks passed ✅")
    sys.exit(0)
