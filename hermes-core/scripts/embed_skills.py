#!/usr/bin/env python3
"""Embed skills into Neo4j for semantic search. Run: python3 embed_skills.py"""
import json, os, sys, urllib.request
from pathlib import Path
from neo4j import GraphDatabase

LITELLM = "http://localhost:4000/v1/embeddings"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
SKILLS_DIR = Path.home() / ".hermes" / "skills"

def get_embedding(text: str) -> list:
    """Get embedding from LiteLLM."""
    import urllib.request, json
    req = urllib.request.Request(LITELLM,
        data=json.dumps({"model": EMBED_MODEL, "input": text[:8000]}).encode(),
        headers={"Authorization": "Bearer sk-local", "Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    return data["data"][0]["embedding"]

def main():
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "changeme"))

    # Create vector index
    with driver.session() as s:
        try:
            s.run("""
                CREATE VECTOR INDEX skill_embeddings IF NOT EXISTS
                FOR (n:Skill) ON (n.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 768,
                    `vector.similarity_function`: 'cosine'
                }}
            """)
            print("Vector index created")
        except Exception as e:
            print(f"Index (may exist): {e}")

    # Process all skills
    skills = list(SKILLS_DIR.rglob("SKILL.md"))
    print(f"Found {len(skills)} skills")

    for i, skill_path in enumerate(skills):
        name = skill_path.parent.name
        content = skill_path.read_text()

        # Skip if already embedded in last 7 days
        with driver.session() as s:
            existing = s.run(
                "MATCH (sk:Skill {path: $path}) WHERE sk.embedded_at > datetime() - duration('P7D') RETURN sk",
                path=str(skill_path)
            ).single()
            if existing:
                print(f"[{i+1}/{len(skills)}] SKIP {name} (recent)")
                continue

        try:
            embedding = get_embedding(content[:8000])

            with driver.session() as s:
                s.run("""
                    MERGE (sk:Skill {path: $path})
                    SET sk.name = $name,
                        sk.embedding = $embedding,
                        sk.content = $content,
                        sk.embedded_at = datetime()
                """, path=str(skill_path), name=name,
                     embedding=embedding, content=content[:5000])

            print(f"[{i+1}/{len(skills)}] EMBED {name} ({len(embedding)}d)")
        except Exception as e:
            print(f"[{i+1}/{len(skills)}] FAIL {name}: {e}")

    driver.close()
    print("Done")

if __name__ == "__main__":
    main()
