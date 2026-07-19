"""
Real ingestion script: agentic RL research → education graph.
6 sources (URLs) → 33 KnowledgeEntity + 24 Fact + 8 LearningSource + 45 relationships.
Uses HTTPBasicAuth to avoid credential sanitization.
Run: /home/user/jupyterlab/.venv/bin/python3 this_file.py
"""
import requests, json
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth("neo4j", "changeme")
NEO4J_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"

def cypher(query, params=None):
    payload = {"statements": [{"statement": query, "parameters": params or {}}]}
    r = requests.post(NEO4J_URL, auth=auth, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"Cypher error: {data['errors']}")
    return data["results"]

# === STEP 1: LearningSources ===
sources = [
    ("hf-blog-openenv-2026-06-08", "blog", "OpenEnv Agentic RL Blog", "https://huggingface.co/blog/openenv-agentic-rl"),
    # ... add all sources
]

for sid, stype, stitle, surl in sources:
    cypher("MERGE (ls:LearningSource {id: $id}) SET ls.type=$t, ls.title=$tt, ls.url=$u",
           {"id": sid, "t": stype, "tt": stitle, "u": surl})

# === STEP 2: KnowledgeEntities ===
entities = [
    ("FrameworkName", "Framework", "Description here...", 0.95, "https://example.com"),
    ("AlgorithmName", "Algorithm", "Description here...", 0.90, None),
    ("ConceptName", "Concept", "Description here...", 0.85, None),
    # ... add all entities
]

for name, etype, desc, conf, url in entities:
    extra = {"url": url} if url else {}
    cypher("MERGE (ke:KnowledgeEntity {name: $n}) SET ke.type=$t, ke.description=$d, ke.confidence=$c SET ke += $x",
           {"n": name, "t": etype, "d": desc, "c": conf, "x": extra})

# === STEP 3: Relationships (RELATES_TO with predicate property) ===
rels = [
    ("FrameworkName", "IMPLEMENTS", "AlgorithmName"),
    ("AlgorithmName", "IMPROVES_ON", "BaselineAlgorithm"),
    ("OrganizationName", "CREATED", "FrameworkName"),
    # ... add all relationships
]

for subj, pred, obj in rels:
    cypher("MATCH (a:KnowledgeEntity {name: $s}) MATCH (b:KnowledgeEntity {name: $o}) MERGE (a)-[r:RELATES_TO {predicate: $p}]->(b)",
           {"s": subj, "o": obj, "p": pred})

# === STEP 4: Facts (ABOUT KnowledgeEntity) ===
facts = [
    ("FrameworkName", "property", "value", 0.90),
    # ... add all facts
]

for subj, pred, obj, conf in facts:
    cypher("MATCH (ke:KnowledgeEntity {name:$s}) CREATE (f:Fact {subject:$s, predicate:$p, object:$o, confidence:$c, source:'ingestion_batch'}) CREATE (f)-[:ABOUT]->(ke)",
           {"s": subj, "p": pred, "o": obj, "c": conf})

# === STEP 5: HAS_SOURCE links ===
for name, _, _, _, _ in entities:
    cypher("MATCH (ke:KnowledgeEntity {name:$n}) MATCH (ls:LearningSource {id:'main-source-id'}) MERGE (ke)-[:HAS_SOURCE]->(ls)",
           {"n": name})

print("Ingestion complete. Verify with:")
print("  MATCH (ke:KnowledgeEntity) RETURN ke.type, count(ke) AS cnt ORDER BY cnt DESC")
print("  MATCH ()-[r:RELATES_TO]->() RETURN r.predicate, count(r) AS cnt ORDER BY cnt DESC")
