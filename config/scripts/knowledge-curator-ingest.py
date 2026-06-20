#!/usr/bin/env python3
"""Knowledge Curator — автономный процесс для Neo4j.

Сканирует ~/dev/codemes/*/docs/ на новые артефакты фаз.
Извлекает entities в Education Graph (Neo4j).
Отслеживает обработанные файлы через state-файл.
Запускается через `hermes cron` каждые 3 часа.
"""

import hashlib, json, os, sys, time
from pathlib import Path
from collections import defaultdict

NEO4J_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"
NEO4J_AUTH = ("neo4j", "changeme")
STATE_FILE = Path.home() / ".hermes" / "skills" / ".curator_state"
ARTIFACTS_ROOT = Path.home() / "dev" / "codemes"

# Phase artifact patterns to scan
ARTIFACT_PATTERNS = [
    "docs/requirements/*.md",
    "docs/system-analysis/*.md",
    "docs/research/*.md",
    "docs/architecture/*.md",
    "docs/tests/*.md",
    "docs/deployment/*.md",
    "docs/research-post/*.md",
]

def log(msg: str):
    print(f"[knowledge-curator] {msg}", flush=True)

def load_state() -> dict:
    """Load processed files state: {file_path_hash: mtime}"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def get_file_hash(path: Path) -> str:
    """Stable hash for file path + mtime"""
    stat = path.stat()
    key = f"{path}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def scan_new_artifacts(state: dict) -> list[Path]:
    """Find artifacts that are new or modified since last processing."""
    new_files = []
    for pattern in ARTIFACT_PATTERNS:
        for f in ARTIFACTS_ROOT.rglob(pattern):
            if not f.is_file():
                continue
            fhash = get_file_hash(f)
            if state.get(str(f)) != fhash:
                new_files.append(f)
                state[str(f)] = fhash
    return new_files

def neo4j_query(query: str, params: dict = None) -> dict:
    """Execute a Cypher query via Neo4j HTTP API."""
    import requests
    payload = {"statements": [{"statement": query, "parameters": params or {}}]}
    r = requests.post(NEO4J_URL, auth=NEO4J_AUTH, json=payload, timeout=30)
    r.raise_for_status()
    result = r.json()
    if result.get("errors"):
        raise RuntimeError(f"Neo4j error: {result['errors']}")
    return result

def classify_artifact(path: Path) -> tuple[str, str]:
    """Determine phase and artifact type from path."""
    parts = path.parts
    phase_map = {
        "requirements": ("Phase 1: Requirements", "Requirement"),
        "system-analysis": ("Phase 2: System Analysis", "Analysis"),
        "research": ("Phase 3: Research", "Research"),
        "architecture": ("Phase 4: Architecture", "Architecture"),
        "tests": ("Phase 8.5: Testing", "TestReport"),
        "deployment": ("Phase 8: Deployment", "Deployment"),
        "research-post": ("Phase 9: Post-Deploy", "PostDeployResearch"),
    }
    for key, (phase, atype) in phase_map.items():
        if key in parts:
            return phase, atype
    return ("Unknown", "Artifact")

def extract_entities_from_markdown(content: str, path: Path) -> list[dict]:
    """Extract KnowledgeEntity candidates from markdown artifact.
    
    Returns list of {name, type, description} dicts.
    Uses simple heuristics — headings, bold text, code blocks.
    """
    entities = []
    phase, atype = classify_artifact(path)
    project_name = path.relative_to(ARTIFACTS_ROOT).parts[0]
    
    # Add the artifact itself as an entity
    entities.append({
        "name": f"{atype}: {path.stem} [{project_name}]",
        "type": atype,
        "description": f"Artifact from phase: {phase}. Project: {project_name}. Source: {path}"
    })
    
    # Scan for patterns like ## headings, **bold concepts**, `code references`
    lines = content.split("\n")
    current_section = ""
    
    for line in lines:
        stripped = line.strip()
        
        # ## Section headings → potential concepts
        if stripped.startswith("## "):
            current_section = stripped[3:].strip()
            if len(current_section) > 3 and len(current_section) < 80:
                entities.append({
                    "name": current_section,
                    "type": "Concept",
                    "description": f"Section heading in {path.name} ({phase}, {project_name})"
                })
        
        # **Bold terms** → potential technologies, papers, patterns
        while "**" in stripped:
            start = stripped.find("**") + 2
            end = stripped.find("**", start)
            if end == -1:
                break
            term = stripped[start:end].strip()
            if 3 < len(term) < 60 and not term.startswith("http"):
                entities.append({
                    "name": term,
                    "type": "Concept",
                    "description": f"Mentioned in {path.name} ({phase})"
                })
            stripped = stripped[end+2:]
        
        # `code_references` → tools, commands, technologies
        while "`" in stripped:
            start = stripped.find("`") + 1
            end = stripped.find("`", start)
            if end == -1:
                break
            code = stripped[start:end].strip()
            if 2 < len(code) < 40 and " " not in code and not code.startswith("/"):
                # Check if it looks like a command/tool/path
                if "." in code or "_" in code or "/" in code:
                    entities.append({
                        "name": code,
                        "type": "Concept",
                        "description": f"Code reference in {path.name}"
                    })
            stripped = stripped[end+1:]
    
    return entities

def ingest_entities(entities: list[dict]) -> dict:
    """Merge entities into Neo4j KnowledgeEntity nodes. Returns stats."""
    stats = {"created": 0, "updated": 0}
    
    for ent in entities:
        name, etype, desc = ent["name"], ent["type"], ent["description"]
        result = neo4j_query("""
            MERGE (ke:KnowledgeEntity {name: $name})
            ON CREATE SET ke.type = $type, ke.description = $desc, ke.created_at = timestamp()
            ON MATCH SET ke.type = $type, ke.description = $desc, ke.updated_at = timestamp()
            RETURN ke.name, ke.type,
                   CASE WHEN ke.created_at = ke.updated_at OR ke.updated_at IS NULL THEN 'created' ELSE 'updated' END AS action
        """, {"name": name, "type": etype, "desc": desc})
        
        for row in result['results'][0]['data']:
            action = row['row'][2]
            stats[action] = stats.get(action, 0) + 1
    
    return stats

def main():
    log("Starting scan...")
    state = load_state()
    
    new_files = scan_new_artifacts(state)
    
    if not new_files:
        log("No new artifacts found.")
        save_state(state)
        return 0
    
    log(f"Found {len(new_files)} new/modified artifact(s):")
    for f in new_files:
        log(f"  → {f}")
    
    total_entities = []
    for f in new_files:
        try:
            content = f.read_text(errors="replace")[:50000]  # First 50KB
            entities = extract_entities_from_markdown(content, f)
            total_entities.extend(entities)
            log(f"  Extracted {len(entities)} entities from {f.name}")
        except Exception as e:
            log(f"  ERROR reading {f}: {e}")
    
    if total_entities:
        # Deduplicate by name
        seen = {}
        unique = []
        for e in total_entities:
            if e["name"] not in seen:
                seen[e["name"]] = True
                unique.append(e)
        
        log(f"  Unique entities: {len(unique)} (total: {len(total_entities)})")
        stats = ingest_entities(unique)
        log(f"  Ingested: {stats.get('created', 0)} created, {stats.get('updated', 0)} updated")
    
    save_state(state)
    log("Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
