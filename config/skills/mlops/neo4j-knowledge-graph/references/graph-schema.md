# Neo4j Graph Schema

All data lives in the `neo4j` database (Community Edition, single-DB).

## Platform Graph (claw — Tool catalog)

### Node Labels
| Label | Count | Description |
|-------|-------|-------------|
| `Tool` | 78 | Tools cataloged by claw agent (id, name, type, description, embedding, status) |
| `Evidence` | 81 | Evidence for tool relationships (anchor, source) |
| `CompactionPolicy` | 6 | Context compaction rules |
| `CompactionAction` | 3 | Specific compaction actions |
| `Session` | 2 | Agent sessions |
| `RegistrySnapshot` | 1 | Registry state snapshot |
| `QAOutcome`, `Prospect`, `Trajectory`, `TurnEpisode`, `Checkpoint` | few | Housekeeping nodes |

### Tool Properties
- `id` — unique slug (e.g., `skill.code-review`, `compose.service.litellm`)
- `name` — display name
- `type` — skill, llm-model, compose-service, mcp, adapter, doc, env, script, agent, etc.
- `description` — free-text description
- `target` — installation target or URL
- `embedding` — 384-dim vector (all-MiniLM-L6-v2)
- `status` — active or pruned
- `confirmations` — count of confirmations
- `mcp_usage` — MCP usage pattern

### Relationship Types
| Type | Count | Meaning |
|------|-------|---------|
| `OBSERVED` | 156 | Tool observed in context |
| `EVIDENCED_BY` | 89 | Tool → Evidence linkage |
| `RECORDS` | 78 | Session records |
| `DEPENDS_ON` | 9 | Tool dependency |
| `TARGETS` | 4 | Tool targets something |
| `APPLIES_AXIS` | 3 | Compaction axis application |
| `PRODUCED` | 2 | Production relationships |
| `DUPLICATE_OF` | 1 | Dedup marker |

### Indexes
| Name | Type | On |
|------|------|-----|
| `toolSearch` | FULLTEXT | Tool(name, description, target, type, id) |
| `toolEmbeddings` | VECTOR (COSINE, 384-dim) | Tool(embedding) |
| `tool_id` | CONSTRAINT UNIQUE | Tool(id) |

## Education Graph (knowledge)

### Node Labels
| Label | Description |
|-------|-------------|
| `KnowledgeEntity` | Knowledge entity (name UNIQUE, type, description, embedding 384-dim, confidence) |
| `Fact` | Extracted triple (subject, predicate, object, confidence, source) |
| `LearningSource` | Source of knowledge (id UNIQUE, type: session/document/url/tool_output, path) |
| `SecurityAssessment` | Security validation result (id UNIQUE, severity, patterns, CVE refs) |

### Relationship Types
| Type | Meaning |
|------|---------|
| `(:KnowledgeEntity)-[:RELATES_TO {predicate, confidence}]->(:KnowledgeEntity)` | Entity relationship |
| `(:KnowledgeEntity)-[:EQUIVALENT_TO {confidence}]->(:KnowledgeEntity)` | Near-duplicate entities |
| `(:KnowledgeEntity)-[:SUPERSEDES {at}]->(:KnowledgeEntity)` | Replacement |
| `(:KnowledgeEntity)-[:SECURITY_RELEVANT]->(:KnowledgeEntity)` | Security-relevant link |
| `(:KnowledgeEntity)-[:HAS_ASSESSMENT]->(:SecurityAssessment)` | Security audit link |
| `(:Fact)-[:ABOUT]->(:KnowledgeEntity)` | Fact subject |
| `(:Fact)-[:ABOUT_OBJECT]->(:KnowledgeEntity)` | Fact object |
| `(:LearningSource)-[:PRODUCED]->(:Fact)` | Source produced fact |
| `(:KnowledgeEntity)-[:MENTIONS_TOOL {score}]->(:Tool)` | Cross-link to claw catalog |

### Indexes
| Name | Type | On |
|------|------|-----|
| `entitySearch` | FULLTEXT | KnowledgeEntity(name, description, type) |
| `entityEmbeddings` | VECTOR (COSINE, 384-dim) | KnowledgeEntity(embedding) |
| `knowledge_entity_name` | CONSTRAINT UNIQUE | KnowledgeEntity(name) |
| `security_assessment_id` | CONSTRAINT UNIQUE | SecurityAssessment(id) |
| `learning_source_id` | CONSTRAINT UNIQUE | LearningSource(id) |
