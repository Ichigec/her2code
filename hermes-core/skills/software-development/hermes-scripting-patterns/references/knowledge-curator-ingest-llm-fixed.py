#!/usr/bin/env python3
"""Knowledge Curator — LLM-powered ingest into Neo4j Education Graph.

Uses local LLM (llama.cpp :8092, Qwen 3.6 35B) to extract typed entities
from markdown research artifacts.

Usage:
    python3 knowledge-curator-ingest-llm.py [--dry-run] [--force]

Requires:
    - llama.cpp server with Qwen 3.6 35B at :8092
    - Neo4j at :7474
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

LLAMA_URL = os.environ.get("LLAMA_URL", "http://127.0.0.1:8092/v1")
NEO4J_URL = os.environ.get("NEO4J_URL", "http://127.0.0.1:7474")
NEO4J_AUTH = ("neo4j", os.environ.get("NEO4J_PASS", "changeme"))

# Use HERMES_HOME (always points to real ~/.hermes) to derive the true
# user home, because under Hermes Agent HOME is redirected to a session-
# isolated directory and Path.home() would return the wrong path.
_REAL_HERMES = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
_REAL_HOME = _REAL_HERMES.parent if _REAL_HERMES.name == ".hermes" else _REAL_HERMES

CURATOR_STATE = _REAL_HERMES / "skills" / ".curator_state"
SCAN_ROOTS = [
    _REAL_HOME / "dev" / "codemes",
    _REAL_HOME / "docs" / "research",
]

PROMPT = """Extract key concepts/patterns/gaps/papers from this research as JSON:

Return: [{"n":"name","t":"Paper|Pattern|Gap|Trend|BestPractice|Concept","d":"1-line description"}]

Limit: 8 entities max. Only the JSON array, no other text.

Artifact: {path}

{content}"""


def state_hash(path: Path) -> str:
    try:
        stat = path.stat()
        return hashlib.sha256(
            f"{path}:{stat.st_mtime}:{stat.st_size}".encode()
        ).hexdigest()[:16]
    except OSError:
        return ""


def load_state() -> dict[str, str]:
    if CURATOR_STATE.exists():
        try:
            return json.loads(CURATOR_STATE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def save_state(state: dict[str, str]) -> None:
    CURATOR_STATE.parent.mkdir(parents=True, exist_ok=True)
    CURATOR_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def find_artifacts() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for md in root.rglob("*.md"):
            s = str(md)
            if "/.git/" in s or "/node_modules/" in s:
                continue
            files.append(md)
    return sorted(files)


def call_llm(artifact_path: str, content: str) -> list[dict] | None:
    """Call local LLM to extract knowledge entities."""
    prompt = PROMPT.format(path=artifact_path, content=content[:3500])
    try:
        resp = requests.post(
            f"{LLAMA_URL}/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 600,
            },
            timeout=180,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"  LLM error: {exc}")
        return None

    # Parse JSON array — handle truncated responses
    clean = re.sub(r'```(?:json)?\s*', '', raw).strip()
    close_pos = clean.rfind(']')
    if close_pos < 0:
        print(f"  No ']' in response ({len(raw)} chars)")
        return None

    js = clean[:close_pos + 1]
    js = re.sub(r',\s*]', ']', js)       # trailing comma
    js = re.sub(r',(\s*})', r'\1', js)   # trailing comma in object
    try:
        entities = json.loads(js)
    except json.JSONDecodeError:
        # Fallback: extract individual objects
        objs = re.findall(r'\{[^}]+\}', js)
        entities = []
        for o in objs:
            try:
                o = re.sub(r',\s*}', '}', o)
                entities.append(json.loads(o))
            except json.JSONDecodeError:
                pass
        if not entities:
            print(f"  Bad JSON ({len(js)} chars): {js[:100]}...")
            return None

    # Normalize field names (n→name, t→type, d→description)
    result = []
    for e in entities:
        if isinstance(e, dict) and e.get("n"):
            result.append({
                "name": str(e["n"])[:80],
                "type": str(e.get("t", "Concept"))[:30],
                "description": str(e.get("d", ""))[:300],
            })
    return result or None


def ingest_entities(entities: list[dict], path: Path) -> int:
    """MERGE entities into Neo4j KnowledgeEntity nodes."""
    if not entities:
        return 0

    statements: list[dict] = []
    for ent in entities:
        statements.append({
            "statement": (
                "MERGE (ke:KnowledgeEntity {name: $name}) "
                "ON CREATE SET ke.created_at = timestamp() "
                "SET ke.type = $type, "
                "ke.description = $desc, "
                "ke.source = $source, "
                "ke.updated_at = timestamp()"
            ),
            "parameters": {
                "name": ent["name"],
                "type": ent["type"],
                "desc": ent["description"],
                "source": str(path),
            },
        })

    try:
        requests.post(
            f"{NEO4J_URL}/db/neo4j/tx/commit",
            json={"statements": statements},
            auth=NEO4J_AUTH,
            timeout=30,
        ).raise_for_status()
        return len(entities)
    except Exception as exc:
        print(f"  Neo4j error: {exc}")
        return 0


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv

    # Ensure unbuffered output for cron/log visibility
    sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

    state = load_state()
    artifacts = find_artifacts()
    processed = 0
    total_ingested = 0

    for path in artifacts:
        pstr = str(path)
        h = state_hash(path)

        if not force and state.get(pstr) == h:
            continue

        content = path.read_text()

        if dry_run:
            print(f"[dry-run] {path.name} ({len(content)} chars)")
        else:
            entities = call_llm(path.name, content)
            if entities:
                n = ingest_entities(entities, path)
                total_ingested += n
                names = ", ".join(e["name"][:30] for e in entities[:3])
                print(f"{path.name}: {len(entities)} entities → {n} ingested ({names}...)")
            else:
                print(f"{path.name}: no entities extracted")

        state[pstr] = h
        processed += 1
        # Checkpoint state after every 10 files to survive timeouts
        if not dry_run and processed % 10 == 0:
            save_state(state)

    if not dry_run:
        save_state(state)

    print(f"\nDone: {processed} files processed, {total_ingested} entities ingested.")


if __name__ == "__main__":
    main()
