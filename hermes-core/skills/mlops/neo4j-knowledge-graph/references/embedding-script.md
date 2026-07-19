# Embedding Generation Script

Generates 384-dim embeddings (all-MiniLM-L6-v2) for all active Tool nodes and creates the `toolEmbeddings` vector index.

Location: `/tmp/generate_embeddings.py` (can be re-run after tool catalog grows)

```python
#!/usr/bin/env python3
"""Generate embeddings for all Tool nodes and create vector index in Neo4j."""
import sys, os

sys.path.insert(0, '/home/user/cursor/first/graph_tool/python')

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD="chan...BASE = "neo4j"
MODEL_NAME = "all-MiniLM-L6-v2"

def main():
    print(f"Loading model: {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)
    print(f"Model loaded. Embedding dim: {model.get_sentence_embedding_dimension()}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # 1. Fetch all Tool nodes
    with driver.session(database=DATABASE) as session:
        result = session.run(
            "MATCH (t:Tool) WHERE coalesce(t.status, 'active') <> 'pruned' "
            "RETURN t.id AS id, t.name AS name, t.type AS type, t.description AS description"
        )
        tools = [(r["id"], r["name"], r["type"], r["description"] or "") for r in result]
    
    print(f"Found {len(tools)} active tools")
    
    # 2. Generate embeddings (batch)
    texts = [f"{t[0]} {t[1]} {t[2]} {t[3]}" for t in tools]
    print(f"Generating embeddings for {len(texts)} tools ...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    print(f"Done. Shape: {embeddings.shape}")
    
    # 3. Write back
    print("Writing embeddings to Neo4j ...")
    with driver.session(database=DATABASE) as session:
        for i, (tool_id, _, _, _) in enumerate(tools):
            emb = embeddings[i].tolist()
            session.run(
                "MATCH (t:Tool {id: $id}) SET t.embedding = $embedding",
                id=tool_id, embedding=emb
            )
    print(f"Written {len(tools)} embeddings")
    
    # 4. Create vector index
    dim = embeddings.shape[1]
    print(f"Creating vector index 'toolEmbeddings' (dim={dim}) ...")
    with driver.session(database=DATABASE) as session:
        try:
            session.run(f"""
                CREATE VECTOR INDEX toolEmbeddings IF NOT EXISTS
                FOR (t:Tool) ON (t.embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {dim},
                        `vector.similarity_function`: 'COSINE'
                    }}
                }}
            """)
            print("Vector index created.")
        except Exception as e:
            print(f"Index may already exist: {e}")
    
    # 5. Verify
    print("\n=== VERIFICATION ===")
    with driver.session(database=DATABASE) as session:
        r = session.run(
            "MATCH (t:Tool) WHERE t.embedding IS NOT NULL RETURN count(t) AS cnt"
        )
        print(f"Tools with embeddings: {r.single()['cnt']}")
        
        q_emb = model.encode("docker container management").tolist()
        r = session.run(
            "CALL db.index.vector.queryNodes('toolEmbeddings', 5, $embedding) "
            "YIELD node, score "
            "RETURN node.name AS name, node.type AS type, score "
            "ORDER BY score DESC",
            embedding=q_emb
        )
        print("\nTest query: 'docker container management'")
        for row in r:
            print(f"  [{row['type']}] {row['name']} (score={row['score']:.4f})")
    
    driver.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
```

Run with:
```bash
/home/user/jupyterlab/.venv/bin/python /tmp/generate_embeddings.py
```
