# PDF → Education Graph Ingestion Recipe

## Session context (2026-06-11)

Ingested "Agentic Design Patterns" (Antonio Gulli, 482pp, 20MB) from Google Drive into Neo4j education graph.

## Pipeline

### 1. Download
```bash
curl -L -o /tmp/doc.pdf "https://drive.google.com/uc?export=download&id=FILE_ID"
file /tmp/doc.pdf  # verify: "PDF document, version 1.7, N page(s)"
```

### 2. Extract text (pymupdf)
```python
import pymupdf
doc = pymupdf.open("/tmp/doc.pdf")
all_text = []
for i in range(len(doc)):
    text = doc[i].get_text()
    if text.strip():
        all_text.append(f"--- PAGE {i+1} ---\n{text}")
full = "\n".join(all_text)
# Save for later full-text reference
with open("/path/to/docs/doc.txt", "w") as f:
    f.write(full)
doc.close()
```

### 3. Analyze & tag

Read first 3 pages + TOC (`doc.get_toc()`) to determine:
- **Primary tag:** domain/book name, hyphenated (e.g., `agentic-design-patterns`)
- **Secondary tags:** chapter topics, concepts, frameworks (e.g., `multi-agent`, `mcp-protocol`, `tool-use`, `rag`)
- **Entity type:** `book` for the whole document, `concept` for chapters/sections

**Tag strategy for later retrieval:** Each chapter entity gets `tags: ['PRIMARY_TAG', 'chapter-slug']`. This enables both broad (`WHERE 'agentic-design-patterns' IN ke.tags`) and precise (`WHERE 'mcp-protocol' IN ke.tags`) queries.

### 4. Create entities in Neo4j

```python
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase

model = SentenceTransformer('all-MiniLM-L6-v2')
driver = GraphDatabase.driver('bolt://127.0.0.1:7687', auth=('neo4j', password))

# Book entity
book_name = "primary-tag-book"
book_emb = model.encode(book_name + " " + book_description).tolist()
session.run("""
    MERGE (ke:KnowledgeEntity {name: $name})
    SET ke.type = 'book', ke.description = $desc, ke.embedding = $emb,
        ke.tags = $tags, ke.source = $source, ke.confidence = 1.0,
        ke.created_at = datetime(), ke.updated_at = datetime()
""", name=book_name, desc=book_desc, emb=book_emb,
     tags=all_tags, source=pdf_url)

# Chapter entities (loop)
for slug, title, desc in chapters:
    name = f"primary-tag-{slug}"
    emb = model.encode(f"{title}: {desc}").tolist()
    session.run("""MERGE (ke:KnowledgeEntity {name: $name}) SET ...""", ...)
    
    # Link both directions
    session.run("""MATCH (ch {name: $ch}), (bk {name: $bk})
                   MERGE (ch)-[:RELATES_TO {predicate: 'is_part_of'}]->(bk)""", ...)
    session.run("""MATCH (bk {name: $bk}), (ch {name: $ch})
                   MERGE (bk)-[:RELATES_TO {predicate: 'contains'}]->(ch)""", ...)

# LearningSource
session.run("""
    MERGE (ls:LearningSource {id: $id})
    SET ls.type = 'book', ls.path = $path, ls.ingested_at = datetime(),
        ls.triple_count = $count
""", id=book_name, path=pdf_url, count=len(chapters))
```

### 5. Verify search

```python
# Via Python EducationAgent
from education.education_agent import EducationAgent
agent = EducationAgent()
results = await agent.search_knowledge("multi-agent coordination", top_k=5)
# Should return chapter entities ranked by RRF score
```

### Pitfalls

- **Neo4j Community Edition:** no `CREATE DATABASE`. All labels in `neo4j` DB.  
- **Python Bolt auth:** may fail even with correct password. Use HTTP API (`curl ... /db/neo4j/tx/commit`) as fallback.  
- **Large PDFs (400+ pp):** extraction takes 10-30s. Use background process.  
- **`graph_tool` package not pip-installed:** use `PYTHONPATH` or `sys.path.insert(0, ...)`.  
- **`sentence-transformers` install timeout:** use existing venv with torch (e.g., `jupyterlab/.venv`).  
