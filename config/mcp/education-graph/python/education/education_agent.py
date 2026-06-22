"""
Education Agent — непрерывное наполнение базы знаний.

Пайплайн:
  1. INGEST: получает сообщение / документ / вывод тула
  2. SECURITY: валидация на prompt injection + cybersecurity (ОТДЕЛЬНЫЙ ШАГ)
  3. EXTRACT: извлечение троек (subject, predicate, object) — аналог TXT2KG
  4. RESOLVE: entity resolution + дедупликация
  5. MERGE: запись в Neo4j education граф (отдельный от claw)
  6. INFER: транзитивное замыкание (фоново, при idle)

Интеграция с Hermes:
  - Как MemoryProvider (непрерывный фон)
  - Как MCP tool (по запросу агента)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from neo4j import GraphDatabase, Driver

from .triple_extractor import TripleExtractor, ExtractedTriple
from .security_validator import SecurityValidator, SecurityResult, Severity


@dataclass
class EducationConfig:
    neo4j_uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    education_database: str = field(default_factory=lambda: os.getenv("EDUCATION_DATABASE", "education"))
    entity_similarity_threshold: float = 0.85  # cosine threshold for entity merge
    embedding_model: str = "all-MiniLM-L6-v2"


class EducationAgent:
    """
    Core Education Agent — writes to `education` Neo4j database (separate from `platform`).

    Does NOT touch the claw Tool graph directly — cross-linking is done
    via GraphEnricher.cross_link_knowledge_to_tools() separately.
    """

    def __init__(
        self,
        config: EducationConfig | None = None,
        llm_callable=None,
    ):
        self.config = config or EducationConfig()
        self.llm = llm_callable
        self._driver: Driver | None = None
        self._encoder = None
        self.extractor = TripleExtractor(llm_callable=llm_callable)
        self.validator = SecurityValidator(llm_callable=llm_callable)

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password),
                max_connection_pool_size=10,
            )
        return self._driver

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.config.embedding_model)
        return self._encoder

    async def ingest(
        self,
        content: str,
        source_id: str = "",
        source_type: str = "session",
        source_path: str = "",
    ) -> dict:
        """
        Full ingestion pipeline. Returns summary dict.

        Args:
            content: Text to ingest (message, document, tool output)
            source_id: Unique source identifier (session_id, doc_path, url)
            source_type: session|document|url|tool_output
            source_path: File path or URL
        """
        result = {
            "source_id": source_id,
            "source_type": source_type,
            "status": "ok",
            "triples_extracted": 0,
            "entities_created": 0,
            "entities_updated": 0,
            "relationships_added": 0,
            "security": None,
            "blocked": False,
        }

        # === STEP 1: SECURITY VALIDATION (mandatory, separate step) ===
        security: SecurityResult = await self.validator.validate(content, source_path)
        result["security"] = security.to_dict()

        if security.blocked:
            result["status"] = "blocked"
            result["blocked"] = True
            # Still record the blocked attempt for audit
            await self._record_security_assessment(content, security, source_id)
            return result

        # Record security assessment for all non-blocked inputs
        await self._record_security_assessment(content, security, source_id)

        # === STEP 2: TRIPLE EXTRACTION ===
        triples = await self.extractor.extract(content)
        result["triples_extracted"] = len(triples)
        if not triples:
            return result

        # === STEP 3: RECORD LEARNING SOURCE ===
        await self._upsert_learning_source(source_id, source_type, source_path, len(triples))

        # === STEP 4: MERGE INTO GRAPH ===
        stats = await self._merge_triples(triples, source_id, security)
        result["entities_created"] = stats["created"]
        result["entities_updated"] = stats["updated"]
        result["relationships_added"] = stats["relationships"]

        return result

    async def _record_security_assessment(
        self, content: str, security: SecurityResult, source_id: str
    ):
        """Record security assessment in the graph for audit trail."""
        assessment_id = hashlib.sha256(
            f"{source_id}:{content[:100]}".encode()
        ).hexdigest()[:16]

        with self.driver.session(database=self.config.education_database) as session:
            session.run(
                """MERGE (sa:SecurityAssessment {id: $id})
                   SET sa.entity_name = $source_id,
                       sa.has_prompt_injection = $has_pi,
                       sa.injection_severity = $severity,
                       sa.injection_patterns = $patterns,
                       sa.cybersecurity_risk = $cyber_risk,
                       sa.cve_references = $cves,
                       sa.validated_at = datetime(),
                       sa.content_preview = $preview""",
                id=assessment_id,
                source_id=source_id,
                has_pi=security.has_prompt_injection,
                severity=security.injection_severity.value,
                patterns=security.injection_patterns,
                cyber_risk=security.cybersecurity_risk.value,
                cves=security.cve_references,
                preview=content[:200],
            )

    async def _upsert_learning_source(
        self, source_id: str, source_type: str, source_path: str, triple_count: int
    ):
        with self.driver.session(database=self.config.education_database) as session:
            session.run(
                """MERGE (ls:LearningSource {id: $id})
                   ON CREATE SET ls.type = $type, ls.path = $path,
                                 ls.ingested_at = datetime(), ls.triple_count = $count
                   ON MATCH SET ls.triple_count = coalesce(ls.triple_count, 0) + $count,
                                ls.ingested_at = datetime()""",
                id=source_id,
                type=source_type,
                path=source_path,
                count=triple_count,
            )

    async def _merge_triples(
        self, triples: list[ExtractedTriple], source_id: str, security: SecurityResult
    ) -> dict:
        """Merge extracted triples into education graph with entity resolution."""
        created = 0
        updated = 0
        relationships = 0

        with self.driver.session(database=self.config.education_database) as session:
            for triple in triples:
                # Resolve entity names (fuzzy match existing)
                subj_name = await self._resolve_entity(session, triple.subject)
                obj_name = await self._resolve_entity(session, triple.object)

                # Create/update subject
                subj_created = await self._upsert_entity(
                    session, subj_name, self._infer_type(triple.predicate, "subject"),
                    security,
                )
                if subj_created:
                    created += 1
                else:
                    updated += 1

                # Create/update object
                obj_created = await self._upsert_entity(
                    session, obj_name, self._infer_type(triple.predicate, "object"),
                    security,
                )
                if obj_created:
                    created += 1
                else:
                    updated += 1

                # Create relationship
                rel_added = await self._upsert_relationship(
                    session, subj_name, triple.predicate, obj_name,
                    triple.confidence, source_id, security,
                )
                if rel_added:
                    relationships += 1

                # If cybersecurity-relevant, mark the relationship
                if security.cybersecurity_risk.value in ("warning", "critical"):
                    await self._mark_security_relevant(session, subj_name, obj_name)

        return {"created": created, "updated": updated, "relationships": relationships}

    async def _resolve_entity(self, session, name: str) -> str:
        """Resolve entity name: find existing entity by exact match or embedding similarity."""
        # Try exact match first
        result = session.run(
            "MATCH (ke:KnowledgeEntity {name: $name}) RETURN ke.name",
            name=name,
        )
        existing = result.single()
        if existing:
            return existing["ke.name"]

        # Try embedding similarity
        try:
            embedding = self.encoder.encode(name).tolist()
            result = session.run(
                """CALL db.index.vector.queryNodes('entityEmbeddings', 1, $embedding)
                   YIELD node, score
                   WHERE score > $threshold
                   RETURN node.name AS name, score""",
                embedding=embedding,
                threshold=self.config.entity_similarity_threshold,
            )
            match = result.single()
            if match:
                return match["name"]
        except Exception:
            pass

        return name

    async def _upsert_entity(
        self, session, name: str, etype: str, security: SecurityResult
    ) -> bool:
        """Upsert entity node. Returns True if created, False if updated."""
        embedding = self.encoder.encode(name).tolist()
        result = session.run(
            """MERGE (ke:KnowledgeEntity {name: $name})
               ON CREATE SET ke.type = $type, ke.description = '',
                              ke.embedding = $embedding, ke.confidence = $confidence,
                              ke.created_at = datetime(), ke.updated_at = datetime(),
                              ke.cybersecurity_flag = $cyber_flag
               ON MATCH SET ke.updated_at = datetime(),
                            ke.confidence = (coalesce(ke.confidence, 0.5) + $confidence) / 2.0,
                            ke.cybersecurity_flag = coalesce(ke.cybersecurity_flag, false) OR $cyber_flag
               RETURN ke.created_at = ke.updated_at AS is_new""",
            name=name,
            type=etype,
            embedding=embedding,
            confidence=0.7,
            cyber_flag=security.cybersecurity_risk.value in ("warning", "critical"),
        )
        row = result.single()
        return row["is_new"] if row else True

    async def _upsert_relationship(
        self, session, subject: str, predicate: str, obj: str,
        confidence: float, source_id: str, security: SecurityResult,
    ) -> bool:
        """Create RELATES_TO relationship between entities. Returns True if new."""
        # Also create Fact node for audit trail
        session.run(
            """MERGE (f:Fact {subject: $subject, predicate: $predicate,
                              object: $object, source: $source})
               ON CREATE SET f.confidence = $confidence, f.extracted_at = datetime()
               ON MATCH SET f.confidence = (coalesce(f.confidence, 0.5) + $confidence) / 2.0
               WITH f
               MATCH (s:KnowledgeEntity {name: $subject})
               MATCH (o:KnowledgeEntity {name: $object})
               MERGE (f)-[:ABOUT]->(s)
               MERGE (f)-[:ABOUT_OBJECT]->(o)
               MERGE (ls:LearningSource {id: $source})
               MERGE (ls)-[:PRODUCED]->(f)""",
            subject=subject, predicate=predicate, object=obj,
            source=source_id, confidence=confidence,
        )

        # Create relationship between entities
        result = session.run(
            """MATCH (s:KnowledgeEntity {name: $subject})
               MATCH (o:KnowledgeEntity {name: $object})
               MERGE (s)-[r:RELATES_TO {predicate: $predicate}]->(o)
               ON CREATE SET r.confidence = $confidence, r.source = $source,
                             r.created_at = datetime()
               ON MATCH SET r.confidence = (coalesce(r.confidence, 0.5) + $confidence) / 2.0,
                            r.updated_at = datetime()
               RETURN r.created_at = r.updated_at AS is_new""",
            subject=subject, predicate=predicate, object=obj,
            source=source_id, confidence=confidence,
        )
        row = result.single()
        return row["is_new"] if row else True

    async def _mark_security_relevant(self, session, subj: str, obj: str):
        session.run(
            """MATCH (s:KnowledgeEntity {name: $subj})
               MATCH (o:KnowledgeEntity {name: $obj})
               MERGE (s)-[:SECURITY_RELEVANT]->(o)""",
            subj=subj, obj=obj,
        )

    async def transitive_inference(self) -> int:
        """Фоновая операция: вывод новых связей через транзитивное замыкание."""
        count = 0
        with self.driver.session(database=self.config.education_database) as session:
            # A → B → C ⇒ A → C (for same predicate)
            result = session.run(
                """MATCH (a:KnowledgeEntity)-[r1:RELATES_TO]->(b:KnowledgeEntity)
                         -[r2:RELATES_TO]->(c:KnowledgeEntity)
                   WHERE r1.predicate = r2.predicate
                     AND a <> c
                     AND NOT (a)-[:RELATES_TO {predicate: r1.predicate}]->(c)
                   MERGE (a)-[r3:RELATES_TO {predicate: r1.predicate}]->(c)
                   ON CREATE SET r3.confidence = r1.confidence * r2.confidence * 0.7,
                                 r3.source = 'transitive_inference',
                                 r3.inferred = true,
                                 r3.created_at = datetime()
                   RETURN count(r3) AS new_edges"""
            )
            row = result.single()
            count = row["new_edges"] if row else 0
        return count

    async def search_knowledge(
        self, query: str, top_k: int = 10
    ) -> list[dict]:
        """Search the education knowledge graph via BM25 + cosine."""
        with self.driver.session(database=self.config.education_database) as session:
            # BM25
            bm25 = session.run(
                """CALL db.index.fulltext.queryNodes('entitySearch', $q)
                   YIELD node, score
                   RETURN node.name AS name, node.type AS type,
                          node.description AS description,
                          node.confidence AS confidence, score
                   ORDER BY score DESC LIMIT 20""",
                q=query if " " in query else f"{query}*",
            )
            bm25_results = [dict(r) for r in bm25]

            # Cosine
            try:
                embedding = self.encoder.encode(query).tolist()
                cosine = session.run(
                    """CALL db.index.vector.queryNodes('entityEmbeddings', 10, $emb)
                       YIELD node, score
                       RETURN node.name AS name, node.type AS type,
                              node.description AS description,
                              node.confidence AS confidence, score
                       ORDER BY score DESC""",
                    emb=embedding,
                )
                cosine_results = [dict(r) for r in cosine]
            except Exception:
                cosine_results = []

            # RRF fuse
            K = 60
            scores: dict[str, float] = {}
            name_map: dict[str, dict] = {}

            for rank, item in enumerate(bm25_results):
                name = item["name"]
                scores[name] = scores.get(name, 0.0) + 0.3 / (K + rank)
                name_map[name] = item
            for rank, item in enumerate(cosine_results):
                name = item["name"]
                scores[name] = scores.get(name, 0.0) + 0.7 / (K + rank)
                if name not in name_map:
                    name_map[name] = item

            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            return [
                {**name_map.get(name, {"name": name}), "rrf_score": round(score, 4)}
                for name, score in ranked
            ]

    @staticmethod
    def _infer_type(predicate: str, position: str) -> str:
        """Infer KnowledgeEntity type from predicate and position."""
        if position == "subject":
            type_map = {
                "uses": "tool", "depends_on": "tool", "runs": "service",
                "exposes": "service", "configures": "tool", "provides": "service",
                "installs": "tool", "manages": "tool", "monitors": "tool",
                "vulnerable_to": "service", "mitigates": "tool",
            }
            return type_map.get(predicate, "concept")
        else:
            type_map = {
                "uses": "tool", "depends_on": "tool", "runs": "host",
                "exposes": "endpoint", "configures": "file",
                "vulnerable_to": "vulnerability", "mitigates": "vulnerability",
                "installs": "tool", "contains": "file",
            }
            return type_map.get(predicate, "concept")

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None


async def main():
    """CLI entry point for testing."""
    import argparse
    parser = argparse.ArgumentParser(description="Education Agent — knowledge graph enrichment")
    parser.add_argument("--ingest", action="store_true", help="Run ingestion on stdin")
    parser.add_argument("--infer", action="store_true", help="Run transitive inference")
    parser.add_argument("--search", type=str, help="Search knowledge graph")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = EducationAgent()
    try:
        if args.ingest:
            import sys
            content = sys.stdin.read()
            result = await agent.ingest(content, source_id=f"cli:{int(time.time())}")
            print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result)
        elif args.infer:
            n = await agent.transitive_inference()
            print(f"Inferred {n} new relationships")
        elif args.search:
            results = await agent.search_knowledge(args.search)
            print(json.dumps(results, indent=2, ensure_ascii=False) if args.json else results)
        else:
            parser.print_help()
    finally:
        agent.close()


if __name__ == "__main__":
    asyncio.run(main())
