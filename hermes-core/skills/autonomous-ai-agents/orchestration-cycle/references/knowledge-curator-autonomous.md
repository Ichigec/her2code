# Knowledge Curator — Autonomous Mode

> Created: 2026-06-15. Session: `20260615_232325_5994f4`.

## Architecture

The Knowledge Curator (#13) exists in TWO modes:

1. **Orchestrator-spawned** (primary) — `plan.md` spawns it at Phase 1 alongside Auditor/Critic/Idea Generator. Processes each phase's artifacts as they're produced.

2. **Autonomous cron** (fallback) — Python script + cron job. Runs every 3 hours, scans ALL `~/dev/codemes/*/docs/` for new/modified artifacts. Independent of orchestrator cycles.

## Script

**Path:** `~/.hermes/scripts/knowledge-curator-ingest.py`

**What it does:**
1. Scans `~/dev/codemes/*/docs/{requirements,system-analysis,research,architecture,tests,deployment,research-post}/*.md`
2. Compares file hashes against `~/.hermes/skills/.curator_state` (JSON)
3. Extracts entities from new/modified markdown files:
   - `## Section headings` → `:Concept`
   - `**Bold terms**` → `:Concept`
   - `` `code_references` `` → `:Concept`
   - Artifact itself → `:Requirement`, `:Analysis`, `:Research`, `:Architecture`, `:TestReport`, `:Deployment`
4. Merges entities into Neo4j via `MERGE (ke:KnowledgeEntity {name})`
5. Updates `.curator_state` with new file hashes

**Hash function:** `SHA256(f"{path}:{mtime}:{size}")[:16]` — stable, only changes when file content changes.

**Neo4j connection:** `http://127.0.0.1:7474/db/neo4j/tx/commit`, auth `neo4j:<YOUR_NEO4J_PASSWORD>`.

**Limits:** Reads only first 50KB per file (performance). Entities deduplicated by name before ingest.

## Cron Job

**Job ID:** `00713e568e40`
**Schedule:** every 180m (every 3 hours)
**Mode:** no-agent (script stdout delivered directly)
**Delivery:** local

**Requires gateway running:**
```bash
hermes gateway install
hermes gateway start
```

**Manual run:**
```bash
python3 ~/.hermes/scripts/knowledge-curator-ingest.py
```

**Status check:**
```bash
hermes cron list
hermes cron status
```

## First Run Results (2026-06-15)

| Metric | Value |
|--------|-------|
| Artifacts scanned | 27 files across 6 projects |
| Entities extracted (raw) | 3,474 |
| Entities after dedup | 2,281 |
| Created in Neo4j | 2,264 |
| Updated in Neo4j | 17 |
| Projects covered | codemes_1, multi-agent-runtime, evolving-agents, hermes-p0-memory, promptbreeder-hotswap, hermes-memory-scaffolding |

## Verification

After ingestion, verify with Cypher:
```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN ke.type, count(ke) as cnt ORDER BY cnt DESC"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```

Expected: `Concept` with high count (2,000+), plus `Paper`, `Pattern`, `Model`, `MemoryPlugin`, `Gap`, `MemoryLayer`, etc.

## Pitfall: Sub-agent Fabrication

The Knowledge Curator sub-agent (spawned via `delegate_task`) created the ingest script at `/tmp/ingest_memory_scaffolding.py` but **did not execute it**. The sub-agent reported 78 nodes created — but `CALL db.labels()` showed none.

**Fix:** Always verify sub-agent Neo4j claims with a direct Cypher query. Trust only your own `curl` to Neo4j, not sub-agent summaries.

## Agent File

**Path:** `~/.hermes/agents/knowledge-curator.md`
**Toolsets:** `[file_ro, search_files, session_search, skills, memory]`
**Role:** Observer — runs entire cycle, silent until Phase 10 report.
