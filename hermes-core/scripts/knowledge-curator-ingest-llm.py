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
LLAMA_MAX_TOKENS = int(os.environ.get("LLAMA_MAX_TOKENS", "1200"))
def _resolve_real_home() -> Path:
    """Resolve real home directory robustly across all execution contexts.

    Under Hermes Agent, HOME is redirected to a session-isolated directory
    (~/.hermes/home/) and Path.home() returns the wrong path. Additionally,
    HERMES_HOME may be set to an empty string (which Path('') interprets as
    '.') rather than absent entirely.

    Resolution order:
      1. HERMES_HOME env (if non-empty) → derive home from .hermes dir
      2. os.path.expanduser("~")          → standard home resolution
      3. /home/$USER                      → fallback by username
      4. /home/user                      → hardcoded last resort
    """
    # 1. HERMES_HOME with empty-string guard
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        p = Path(hermes_home)
        if p.name == ".hermes":
            return p.parent
        return p

    # 2. expanduser (may be redirected under Hermes Agent)
    try:
        expanded = Path(os.path.expanduser("~"))
        # Sanity: the real home has dev/codemes/ — session-isolated homes don't.
        # Under Hermes Agent, HOME is ~/.hermes/home/ which contains .hermes/
        # but NOT dev/codemes/. Reject session-isolated paths.
        if (expanded / "dev" / "codemes").exists():
            return expanded
    except Exception:
        pass

    # 3. /home/$USER
    user = os.environ.get("USER", "pavel")
    candidate = Path(f"/home/{user}")
    if candidate.exists():
        return candidate

    # 4. Hardcoded fallback
    return Path("/home/user")

_REAL_HOME = _resolve_real_home()
_REAL_HERMES = _REAL_HOME / ".hermes"

CURATOR_STATE = _REAL_HERMES / "skills" / ".curator_state"
SCAN_ROOTS = [
    _REAL_HOME / "dev" / "codemes",
    _REAL_HOME / "docs" / "research",
]

# Validate scan roots — warn if missing (catches resolution failures early)
for _root in SCAN_ROOTS:
    if not _root.exists():
        print(f"WARNING: scan root does not exist: {_root}", file=sys.stderr)

PROMPT = """Extract structured knowledge from this research artifact as JSON.

Entity types (choose the BEST fit):
- Paper: scientific paper (include year, venue, arxiv_id if known)
- Algorithm: named algorithm or method (e.g. DRPO, PPO, GRPO)
- Framework: software framework or library (e.g. TRL, PyTorch, LangChain)
- Model: AI/ML model (e.g. Llama-4, Qwen-3, StableDiffusion)
- Pattern: design pattern, architecture pattern, recurring solution
- Concept: abstract concept, technique, methodology
- CodeExample: code snippet demonstrating an algorithm/pattern (include language + code)
- Dataset: named dataset or benchmark corpus
- Metric: evaluation metric or KPI
- Tool: software tool or utility
- Organization: company, lab, institution
- Author: researcher or contributor
- ProgrammingLanguage: language used in code examples
- Benchmark: evaluation benchmark (e.g. MMLU, HumanEval)
- Gap: identified knowledge gap or missing capability
- BestPractice: recommended approach or guideline

If the artifact contains code blocks, extract them as CodeExample entities with language and description.

JSON format:
{{
  "entities": [
    {{"n":"name","t":"Paper|Algorithm|...","d":"1-line description","c":0.9}}
  ],
  "relations": [
    {{"s":"source entity","p":"IMPLEMENTS|IMPROVES_ON|USES|DESCRIBES|DERIVED_FROM|EXTENDS","o":"target entity"}}
  ]
}}

Limit: 12 entities, 6 relations max. Confidence: 0.9+ for explicit, 0.7-0.9 for implied.
Only JSON, no other text. No markdown fences.

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


def call_llm(artifact_path: str, content: str) -> dict | None:
    """Call local LLM to extract knowledge entities and relations.

    Returns dict with 'entities' and 'relations' keys, or None on failure.
    """
    prompt = PROMPT.format(path=artifact_path, content=content[:3500])
    try:
        resp = requests.post(
            f"{LLAMA_URL}/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": LLAMA_MAX_TOKENS,
            },
            timeout=180,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"  LLM error: {exc}")
        return None

    # Parse JSON — handle both array format (legacy) and object format (new)
    clean = re.sub(r'```(?:json)?\s*', '', raw).strip()
    
    # Try new format: {"entities": [...], "relations": [...]}
    try:
        start = clean.find('{')
        end = clean.rfind('}')
        if start >= 0 and end >= 0:
            data = json.loads(clean[start:end + 1])
            if isinstance(data, dict) and "entities" in data:
                return data
    except json.JSONDecodeError:
        pass

    # Fallback: legacy array format [{...}, {...}]
    close_pos = clean.rfind(']')
    if close_pos < 0:
        print(f"  No valid JSON in response ({len(raw)} chars)")
        return None

    js = clean[:close_pos + 1]
    js = re.sub(r',\s*]', ']', js)
    js = re.sub(r',(\s*})', r'\1', js)
    try:
        entities = json.loads(js)
    except json.JSONDecodeError:
        objs = re.findall(r'\{[^}]+\}', js)
        entities = []
        for o in objs:
            try:
                entities.append(json.loads(re.sub(r',\s*}', '}', o)))
            except json.JSONDecodeError:
                pass
        if not entities:
            print(f"  Bad JSON ({len(js)} chars): {js[:100]}...")
            return None

    return {"entities": entities, "relations": []}


def ingest_entities(extraction: dict, path: Path) -> tuple[int, int]:
    """MERGE entities and relations into Neo4j.

    Returns (entities_ingested, relations_ingested).
    """
    entities = extraction.get("entities", [])
    relations = extraction.get("relations", [])

    if not entities:
        return (0, 0)

    # Normalize entity field names (n→name, t→type, d→description, c→confidence)
    normalized = []
    for e in entities:
        if isinstance(e, dict) and e.get("n"):
            # Safe confidence parse — LLM can return strings, HTML, or garbage
            raw_c = e.get("c", 0.8)
            try:
                confidence = float(raw_c)
                # Clamp to [0, 1]
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                confidence = 0.8
            normalized.append({
                "name": str(e["n"])[:80],
                "type": str(e.get("t", "Concept"))[:30],
                "description": str(e.get("d", ""))[:300],
                "confidence": confidence,
            })
    entities = normalized
    if not entities:
        return (0, 0)

    # 1. MERGE entities
    statements: list[dict] = []
    for ent in entities:
        statements.append({
            "statement": (
                "MERGE (ke:KnowledgeEntity {name: $name}) "
                "ON CREATE SET ke.created_at = timestamp() "
                "SET ke.type = $type, "
                "ke.description = $desc, "
                "ke.confidence = $conf, "
                "ke.source = $source, "
                "ke.updated_at = timestamp()"
            ),
            "parameters": {
                "name": ent["name"],
                "type": ent["type"],
                "desc": ent["description"],
                "conf": ent["confidence"],
                "source": str(path),
            },
        })

    ingested = 0
    try:
        requests.post(
            f"{NEO4J_URL}/db/neo4j/tx/commit",
            json={"statements": statements},
            auth=NEO4J_AUTH,
            timeout=30,
        ).raise_for_status()
        ingested = len(entities)
    except Exception as exc:
        print(f"  Neo4j entity error: {exc}")
        return (0, 0)

    # 2. MERGE relations
    rel_ingested = 0
    for rel in relations:
        s = str(rel.get("s", ""))[:80]
        p = str(rel.get("p", "RELATES_TO"))[:30]
        o = str(rel.get("o", ""))[:80]
        if not s or not o:
            continue

        try:
            requests.post(
                f"{NEO4J_URL}/db/neo4j/tx/commit",
                json={"statements": [{
                    "statement": (
                        "MATCH (a:KnowledgeEntity {name: $s}) "
                        "MATCH (b:KnowledgeEntity {name: $o}) "
                        "MERGE (a)-[r:RELATES_TO {predicate: $p}]->(b) "
                        "SET r.source = $source"
                    ),
                    "parameters": {"s": s, "o": o, "p": p, "source": str(path)},
                }]},
                auth=NEO4J_AUTH,
                timeout=10,
            ).raise_for_status()
            rel_ingested += 1
        except Exception as exc:
            print(f"  Neo4j relation error ({s}→{o}): {exc}")

    return (ingested, rel_ingested)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv

    # Ensure unbuffered output for cron/log visibility
    sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

    state = load_state()
    artifacts = find_artifacts()
    processed = 0
    total_entities = 0
    total_relations = 0

    for path in artifacts:
        pstr = str(path)
        h = state_hash(path)

        if not force and state.get(pstr) == h:
            continue

        content = path.read_text()

        if dry_run:
            print(f"[dry-run] {path.name} ({len(content)} chars)")
            state[pstr] = h
            processed += 1
        else:
            extraction = call_llm(path.name, content)
            if extraction is None:
                # Transient LLM failure — retry next run
                print(f"{path.name}: LLM extraction failed, will retry")
                continue
            elif extraction:
                entities = extraction.get("entities", [])
                n_ent, n_rel = ingest_entities(extraction, path)
                total_entities += n_ent
                total_relations += n_rel
                # Use normalized key 'n' (raw format from LLM) for display
                names = ", ".join(str(e.get("n", e.get("name", "?")))[:30] for e in entities[:3])
                print(f"{path.name}: {len(entities)} entities → "
                      f"{n_ent} ingested, {n_rel} relations ({names}...)" if names else
                      f"{path.name}: {n_ent} entities, {n_rel} relations")
            else:
                print(f"{path.name}: no entities extracted")
            state[pstr] = h
            processed += 1
        # Checkpoint state after every 10 files
        if not dry_run and processed % 10 == 0:
            save_state(state)

    if not dry_run:
        save_state(state)

    print(f"\nDone: {processed} files processed, "
          f"{total_entities} entities, {total_relations} relations ingested.")

if __name__ == "__main__":
    main()
