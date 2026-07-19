#!/usr/bin/env python3
"""
Paper Deep Reader — Extracts entities, relationships, code examples from
scientific papers using local Qwen LLM and ingests into Neo4j Knowledge Graph.

Usage:
    python3 paper-deep-read.py [--date 2026-07-01] [--top 5] [--dry-run]
    python3 paper-deep-read.py --arxiv-id 2402.03300

Requires:
    - Qwen 3.6 35B (llama.cpp :8092)
    - Neo4j (:7474)
    - pdftotext (poppler-utils)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

# ── Path resolution ──


def _resolve_real_home() -> Path:
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        p = Path(hermes_home)
        return p.parent if p.name == ".hermes" else p
    try:
        expanded = Path(os.path.expanduser("~"))
        if (expanded / "dev" / "codemes").exists():
            return expanded
    except Exception:
        pass
    user = os.environ.get("USER", "pavel")
    candidate = Path(f"/home/{user}")
    return candidate if candidate.exists() else Path("/home/user")


_REAL_HOME = _resolve_real_home()
_REAL_HERMES = _REAL_HOME / ".hermes"
QUEUE_DIR = _REAL_HERMES / "paper_queue"
TEMP_DIR = Path("/tmp/paper-deep-read")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ── API ──

LLAMA_URL = os.environ.get("LLAMA_URL", "http://127.0.0.1:8092/v1")
NEO4J_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"
_N4J_USER = "neo4j"
_N4J_PASS = os.environ.get("NEO4J_PASS", "changeme")
NEO4J_AUTH = HTTPBasicAuth(_N4J_USER, _N4J_PASS)

# ── Entity types (14+) ──

ENTITY_TYPES = [
    "Paper",              # scientific paper
    "Algorithm",          # named algorithm or method
    "Framework",          # software framework or library
    "Model",              # AI/ML model
    "Pattern",            # design pattern, architecture pattern
    "Concept",            # abstract concept, technique
    "CodeExample",        # code snippet demonstrating algorithm/pattern
    "Dataset",            # named dataset or benchmark
    "Metric",             # evaluation metric or KPI
    "Tool",               # software tool or utility
    "Organization",       # company, lab, institution
    "Author",             # researcher or contributor
    "ProgrammingLanguage",# language used
    "Benchmark",          # evaluation benchmark
]

# ── Enhanced extraction prompt ──

EXTRACTION_PROMPT = """Extract structured knowledge from this research paper as JSON.

Return a JSON object with these keys:

1. "paper_meta": { "title", "year", "venue", "arxiv_id", "abstract_short" }
2. "entities": [{ "name", "type": one of """ + ", ".join(ENTITY_TYPES) + """, "description": "1-2 sentence summary", "confidence": 0.0-1.0 }]
3. "relationships": [{ "source": "entity name", "predicate": "IMPLEMENTS|IMPROVES_ON|USES|DESCRIBES|DERIVED_FROM|EVALUATED_ON|OUTPERFORMS|EXTENDS|COMPARES_TO|TRAINED_ON|BUILT_WITH", "target": "entity name", "confidence": 0.0-1.0 }]
4. "code_examples": [{ "language": "python|bash|etc", "description": "what this code does", "demonstrates": "entity name", "code": "// first 500 chars of code", "loc": 42 }]
5. "citations": ["arxiv_id of cited paper", ...]

Rules:
- Extract 8-15 entities max. Focus on the most important ones.
- All entity names MUST be unique within this paper.
- For Paper type: include the paper itself as an entity.
- For CodeExample: extract code blocks from the paper, note language and what they demonstrate.
- For relationships: connect entities within this paper. Use the SOURCE name → predicate → TARGET name format.
- Confidence: 0.9+ for explicitly stated facts, 0.7-0.9 for clearly implied, <0.7 for speculative.
- Citations: list arxiv IDs of cited papers (e.g. "2402.03300").
- Only JSON, no other text. No markdown fences.

Paper: {title}

Content:
{content}"""


def download_paper_text(arxiv_id: str, paper_title: str = "") -> str:
    """Download PDF from arXiv and extract text via pdftotext."""
    pdf_path = TEMP_DIR / f"{arxiv_id}.pdf"
    txt_path = TEMP_DIR / f"{arxiv_id}.txt"

    # Check cache
    if txt_path.exists():
        return txt_path.read_text()

    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    print(f"    Downloading {pdf_url}...")

    try:
        resp = requests.get(pdf_url, timeout=60, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) Hermes-Knowledge-Curator/2.0"
        })
        resp.raise_for_status()
        pdf_path.write_bytes(resp.content)
    except Exception as exc:
        print(f"    Download error: {exc}")
        return ""

    # Extract text
    try:
        subprocess.run(
            ["pdftotext", "-l", "15", str(pdf_path), str(txt_path)],
            check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("    pdftotext failed — using abstract only")
        return ""

    text = txt_path.read_text()
    # Truncate to first 8000 chars (fits Qwen context budget)
    return text[:8000]


def call_qwen(prompt: str, max_tokens: int = 2000) -> dict | None:
    """Call Qwen 3.6 35B for structured extraction."""
    try:
        resp = requests.post(
            f"{LLAMA_URL}/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": max_tokens,
            },
            timeout=300,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"    Qwen error: {exc}")
        return None

    # Parse JSON
    raw = raw.strip()
    # Remove markdown fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    # Find JSON object boundaries
    start = raw.find('{')
    end = raw.rfind('}')
    if start < 0 or end < 0:
        print(f"    No JSON in Qwen response ({len(raw)} chars)")
        return None

    js = raw[start:end + 1]
    try:
        return json.loads(js)
    except json.JSONDecodeError as exc:
        print(f"    JSON parse error: {exc}")
        # Try to salvage: find individual objects
        entities = re.findall(r'\{"name":\s*"[^"]+"[^}]*\}', js)
        if entities:
            print(f"    Salvaged {len(entities)} entity fragments")
            return {"entities": [json.loads(e) for e in entities]}
        return None


def neo4j_cypher(statements: list[dict]) -> dict:
    """Execute Cypher statements via Neo4j HTTP API."""
    payload = {"statements": statements}
    resp = requests.post(NEO4J_URL, auth=NEO4J_AUTH, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        for err in data["errors"]:
            print(f"    Neo4j error: {err.get('message', str(err))}", file=sys.stderr)
    return data


def ingest_extraction(extraction: dict, source_arxiv_id: str) -> dict:
    """Ingest extracted entities, relationships, and code into Neo4j."""
    stats = {"entities": 0, "relationships": 0, "code_examples": 0}

    paper_meta = extraction.get("paper_meta", {})
    entities = extraction.get("entities", [])
    relationships = extraction.get("relationships", [])
    code_examples = extraction.get("code_examples", [])
    citations = extraction.get("citations", [])

    if not entities:
        return stats

    # 1. Create/MERGE entities
    for ent in entities:
        name = str(ent.get("name", ""))[:80]
        etype = str(ent.get("type", "Concept"))[:30]
        desc = str(ent.get("description", ""))[:300]
        conf = float(ent.get("confidence", 0.8))

        neo4j_cypher([{
            "statement": (
                "MERGE (ke:KnowledgeEntity {name: $name}) "
                "ON CREATE SET ke.created_at = timestamp() "
                "SET ke.type = $type, "
                "ke.description = $desc, "
                "ke.confidence = $conf, "
                "ke.source = $source, "
                "ke.source_arxiv = $arxiv, "
                "ke.updated_at = timestamp()"
            ),
            "parameters": {
                "name": name,
                "type": etype,
                "desc": desc,
                "conf": conf,
                "source": f"arxiv:{source_arxiv_id}",
                "arxiv": source_arxiv_id,
            },
        }])
        stats["entities"] += 1

    # 2. Create Paper node + link to entities
    if paper_meta.get("title"):
        title = paper_meta["title"][:200]
        year = paper_meta.get("year", "")
        venue = paper_meta.get("venue", "")

        neo4j_cypher([{
            "statement": (
                "MERGE (p:Paper {arxiv_id: $arxiv}) "
                "SET p.title = $title, p.year = $year, p.venue = $venue, "
                "p.source = 'paper-collector', p.ingested_at = timestamp()"
            ),
            "parameters": {
                "arxiv": source_arxiv_id,
                "title": title,
                "year": str(year),
                "venue": venue,
            },
        }])

        # Link all extracted entities to this paper
        for ent in entities:
            name = str(ent.get("name", ""))[:80]
            neo4j_cypher([{
                "statement": (
                    "MATCH (ke:KnowledgeEntity {name: $name}) "
                    "MATCH (p:Paper {arxiv_id: $arxiv}) "
                    "MERGE (ke)-[:EXTRACTED_FROM]->(p)"
                ),
                "parameters": {"name": name, "arxiv": source_arxiv_id},
            }])

    # 3. Create relationships
    for rel in relationships:
        src = str(rel.get("source", ""))[:80]
        pred = str(rel.get("predicate", "RELATES_TO"))[:30]
        tgt = str(rel.get("target", ""))[:80]
        conf = float(rel.get("confidence", 0.8))

        if src and tgt:
            neo4j_cypher([{
                "statement": (
                    "MATCH (a:KnowledgeEntity {name: $src}) "
                    "MATCH (b:KnowledgeEntity {name: $tgt}) "
                    "MERGE (a)-[r:RELATES_TO {predicate: $pred}]->(b) "
                    "SET r.confidence = $conf, r.source_arxiv = $arxiv"
                ),
                "parameters": {
                    "src": src, "tgt": tgt, "pred": pred,
                    "conf": conf, "arxiv": source_arxiv_id,
                },
            }])
            stats["relationships"] += 1

    # 4. Create CodeExample nodes
    for ce in code_examples:
        lang = str(ce.get("language", "unknown"))[:20]
        desc = str(ce.get("description", ""))[:200]
        demonstrates = str(ce.get("demonstrates", ""))[:80]
        code = str(ce.get("code", ""))[:2000]
        loc = int(ce.get("loc", 0))

        example_name = f"code:{source_arxiv_id}:{demonstrates}"[:80]
        neo4j_cypher([{
            "statement": (
                "MERGE (ce:CodeExample {name: $name}) "
                "SET ce.language = $lang, ce.description = $desc, "
                "ce.code = $code, ce.loc = $loc, "
                "ce.source_arxiv = $arxiv, ce.updated_at = timestamp()"
            ),
            "parameters": {
                "name": example_name, "lang": lang, "desc": desc,
                "code": code, "loc": loc, "arxiv": source_arxiv_id,
            },
        }])

        # Link to entity it demonstrates
        if demonstrates:
            neo4j_cypher([{
                "statement": (
                    "MATCH (ce:CodeExample {name: $name}) "
                    "MATCH (ke:KnowledgeEntity {name: $demonstrates}) "
                    "MERGE (ce)-[:IMPLEMENTS]->(ke)"
                ),
                "parameters": {
                    "name": example_name, "demonstrates": demonstrates,
                },
            }])
        stats["code_examples"] += 1

    # 5. Citation edges
    for cited_id in citations:
        if cited_id and cited_id != source_arxiv_id:
            neo4j_cypher([{
                "statement": (
                    "MERGE (cited:Paper {arxiv_id: $cited}) "
                    "WITH cited "
                    "MATCH (citing:Paper {arxiv_id: $citing}) "
                    "MERGE (citing)-[:CITES]->(cited)"
                ),
                "parameters": {"citing": source_arxiv_id, "cited": str(cited_id)[:30]},
            }])

    return stats


def record_run(stats: dict, status: str, papers_processed: int):
    """Record CuratorRun in Neo4j."""
    neo4j_cypher([{
        "statement": (
            "CREATE (cr:CuratorRun {"
            "  timestamp: datetime(),"
            "  status: $status,"
            "  papers_processed: $papers,"
            "  entities_ingested: $entities,"
            "  relationships_created: $rels,"
            "  code_examples_ingested: $code"
            "})"
        ),
        "parameters": {
            "status": status,
            "papers": papers_processed,
            "entities": stats.get("entities", 0),
            "rels": stats.get("relationships", 0),
            "code": stats.get("code_examples", 0),
        },
    }])


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    specific_arxiv_id = None

    for arg in sys.argv:
        if arg.startswith("--arxiv-id="):
            specific_arxiv_id = arg.split("=")[1]
        elif arg.startswith("--date="):
            date_str = arg.split("=")[1]
        elif arg.startswith("--top="):
            top_k = int(arg.split("=")[1])

    # Default: latest date directory
    if not specific_arxiv_id:
        date_dirs = sorted(QUEUE_DIR.glob("????-??-??"), reverse=True)
        if not date_dirs:
            print("No paper queue found. Run paper-collector.py first.")
            return
        date_str = date_dirs[0].name
    else:
        date_str = "adhoc"

    print(f"=== Paper Deep Reader === {date_str}")

    # Load queue
    if specific_arxiv_id:
        papers = [{"arxiv_id": specific_arxiv_id, "title": specific_arxiv_id}]
    else:
        queue_file = QUEUE_DIR / date_str / "papers.json"
        if not queue_file.exists():
            print(f"No queue file: {queue_file}")
            return
        with open(queue_file) as f:
            papers = json.load(f)
        papers = papers[:top_k] if 'top_k' in dir() else papers[:5]

    print(f"Papers to deep-read: {len(papers)}")

    total_stats = {"entities": 0, "relationships": 0, "code_examples": 0}
    success_count = 0
    fail_count = 0

    for i, paper in enumerate(papers):
        arxiv_id = paper.get("arxiv_id", "")
        title = paper.get("title", arxiv_id)
        print(f"\n[{i+1}/{len(papers)}] {arxiv_id}: {title[:70]}...")

        if dry_run:
            print(f"    [dry-run] Would download and extract")
            continue

        # Step 1: Download and extract text
        text = download_paper_text(arxiv_id, title)
        if not text:
            # Fallback: use abstract from paper metadata
            text = paper.get("abstract", "")
            if not text:
                print(f"    No text available — skipping")
                fail_count += 1
                continue
            print(f"    Using abstract ({len(text)} chars)")

        print(f"    Text extracted: {len(text)} chars")

        # Step 2: Qwen extraction
        prompt = EXTRACTION_PROMPT.format(
            title=title,
            content=text,
        )
        extraction = call_qwen(prompt)
        if not extraction:
            fail_count += 1
            continue

        # Step 3: Ingest to Neo4j
        stats = ingest_extraction(extraction, arxiv_id)
        total_stats["entities"] += stats["entities"]
        total_stats["relationships"] += stats["relationships"]
        total_stats["code_examples"] += stats["code_examples"]
        success_count += 1

        print(f"    ✓ {stats['entities']} entities, "
              f"{stats['relationships']} relationships, "
              f"{stats['code_examples']} code examples")

    # Record run
    status = "healthy_active" if success_count > 0 else "degraded"
    if fail_count == len(papers):
        status = "failed"

    if not dry_run:
        record_run(total_stats, status, success_count)
        print(f"\n── Run recorded: {status} ──")

    print(f"\n── Done ──")
    print(f"Success: {success_count}, Failed: {fail_count}")
    print(f"Total: {total_stats['entities']} entities, "
          f"{total_stats['relationships']} relationships, "
          f"{total_stats['code_examples']} code examples")


if __name__ == "__main__":
    main()
