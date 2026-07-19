# Knowledge Extraction Workflow — Codebase + Architecture Docs → Neo4j

Systematic methodology for Knowledge Curator to extract entities from a
codebase + architecture documentation for ingestion into the Education
Knowledge Graph (KnowledgeEntity nodes).

## Trigger

"Knowledge Curator: extract entities from X for Knowledge Graph" or
any instruction to analyze a codebase for graph-ready knowledge.

## Step-by-step workflow

### 1. Read architecture docs FIRST
Load the architecture documentation (usually in `docs/architecture/`)
to understand the topology, component map, contracts, and data flows
BEFORE diving into code. This gives you the big picture and prevents
misinterpretation of implementation details.

### 2. Read ALL code files
Read every source file in the target directory tree. Compare against
the architecture spec — note what's implemented vs what's only specified.
Use `list` to discover files, then `read_file` for each one.

### 3. Query live Neo4j for existing entities
Before proposing new entities, check what already exists:
```bash
# Check all node labels and counts
curl -s -u neo4j:PASS -d '{"statements":[{"statement":"MATCH (n) RETURN labels(n) AS label, count(*) AS cnt ORDER BY cnt DESC"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# Check for domain-specific entities
curl -s -u neo4j:PASS -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) WHERE ke.name CONTAINS \"keyword\" RETURN ke.name, ke.type ORDER BY ke.name LIMIT 50"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```
This prevents duplicates and identifies what's genuinely new.

### 4. Categorize entities into 4 types
Every entity must fit one of these KnowledgeEntity types:

| Type | Definition | Example |
|------|-----------|---------|
| **Concept** | Core abstraction in the system | GatePlugin, GateVerdict, TraceabilityMatrix |
| **Pattern** | Reusable design template | FAST FAIL, Plugin Self-Registration, Tamper-Evident Certificate |
| **Framework** | System of components working together | QualityGateRunner, GateEnforcementFramework |
| **Algorithm** | Specific computational method | TopologicalGateSort, HMAC-SHA256 Passport |

### 5. Extract relationships
Map how entities connect. Use natural language predicates:
- `X IMPLEMENTS Y`
- `X DEPENDS_ON Y`
- `X CONTAINS Y`
- `X ENFORCES Y`
- `X QUERIES Y`
- `X SECURED_BY Y`

These become `RELATES_TO` edges with `predicate` property in Neo4j.

### 6. Identify knowledge gaps
Compare the architecture specification against the actual implementation:
- What's specified but not coded?
- What's coded but missing critical dependencies?
- What's designed but never tested with real data?
- What files are referenced but don't exist?

Classify by severity: High (system can't function) / Medium (feature incomplete) / Low (nice-to-have).

### 7. Output structured extraction
Format the response with clear sections:
1. **New Entities** — table with Entity name, Category, Value (concise description), Tags
2. **Relationships** — numbered list of connections
3. **Knowledge Gaps** — table with #, Gap, Severity, Why it matters
4. **What to Save** — priority-ranked Cypher snippets

## Entity template for Neo4j

```cypher
MERGE (ke:KnowledgeEntity {name: $name})
SET ke.type = $type,            -- 'Concept' | 'Pattern' | 'Framework' | 'Algorithm'
    ke.description = $desc,     -- 1-2 sentence explanation
    ke.confidence = 0.95,       -- from architecture docs: 0.9-1.0; from code inspection: 0.8-0.95
    ke.tags = $tags,            -- ['domain-tag', 'subdomain', 'technology']
    ke.source = 'codebase-extraction',
    ke.created_at = datetime()
```

### Tag strategy
- Primary tag: domain/project name (e.g., 'quality-gates')
- Secondary tags: technology, pattern name, enforcement mechanism
- Use tags for filtering: `WHERE 'quality-gates' IN ke.tags`

## Pitfalls

- **Don't trust documented counts.** Neo4j grows autonomously. Always query live before citing numbers.
- **CONTAINS in Cypher needs string literals.** `WHERE ke.name CONTAINS "word"` not bare `word`.
- **Community Edition = single database.** Use labels to separate concerns, not `CREATE DATABASE`.
- **Prefer HTTP API over Bolt Python driver** when auth issues arise with the Python driver.
