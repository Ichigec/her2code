"""
Hybrid searcher: BM25 (Neo4j fulltext) + Cosine similarity (vector) via RRF.

Architecture (arXiv:2407.21783 — Hybrid Search RRF):
  Query → BM25 top-50 + Cosine top-50
        → Reciprocal Rank Fusion (k=60)
        → Graph enrichment (1-hop neighbors)
        → Re-rank by connectivity

Usage:
  python -m graph_tool.python.hybrid_searcher "how to search the web"
  python -m graph_tool.python.hybrid_searcher --json "find docker tools" | jq
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from neo4j import GraphDatabase, Driver


@dataclass
class Neo4jConfig:
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))


class HybridSearcher:
    """BM25 + Cosine + RRF search over Neo4j tool catalog."""

    def __init__(self, config: Neo4jConfig | None = None):
        self.config = config or Neo4jConfig()
        self._driver: Driver | None = None
        self._encoder = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
                max_connection_pool_size=20,
            )
        return self._driver

    @property
    def encoder(self):
        """Lazy-load SentenceTransformer to avoid import cost when not needed."""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._encoder

    def encode(self, text: str) -> list[float]:
        return self.encoder.encode(text).tolist()

    def bm25_search(self, query: str, k: int = 50) -> list[dict]:
        """BM25 fulltext search via Neo4j toolSearch index."""
        q = query if " " in query else f"{query}*"
        with self.driver.session(database=self.config.database) as session:
            result = session.run(
                """CALL db.index.fulltext.queryNodes('toolSearch', $q)
                   YIELD node, score
                   WHERE coalesce(node.status, 'active') <> 'pruned'
                   RETURN node.id AS id, node.name AS name, node.type AS type,
                          node.description AS description, score
                   ORDER BY score DESC LIMIT $k""",
                q=q, k=k,
            )
            return [dict(r) for r in result]

    def cosine_search(self, embedding: list[float], k: int = 50) -> list[dict]:
        """Cosine similarity via Neo4j vector index. Falls back gracefully."""
        try:
            with self.driver.session(database=self.config.database) as session:
                result = session.run(
                    """CALL db.index.vector.queryNodes('toolEmbeddings', $k, $embedding)
                       YIELD node, score
                       WHERE coalesce(node.status, 'active') <> 'pruned'
                       RETURN node.id AS id, node.name AS name, node.type AS type,
                              node.description AS description, score
                       ORDER BY score DESC LIMIT $k""",
                    k=k, embedding=embedding,
                )
                return [dict(r) for r in result]
        except Exception:
            return []

    def rrf_fuse(
        self,
        bm25_results: list[dict],
        cosine_results: list[dict],
        top_k: int = 20,
        bm25_weight: float = 0.3,
    ) -> list[tuple[str, float]]:
        """Reciprocal Rank Fusion (k=60)."""
        K = 60
        cosine_weight = 1.0 - bm25_weight
        scores: dict[str, float] = {}

        for rank, item in enumerate(bm25_results):
            tid = item["id"]
            scores[tid] = scores.get(tid, 0.0) + bm25_weight / (K + rank)
        for rank, item in enumerate(cosine_results):
            tid = item["id"]
            scores[tid] = scores.get(tid, 0.0) + cosine_weight / (K + rank)

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    def enrich_with_graph(self, tool_ids: list[str]) -> dict[str, dict]:
        """Add graph context: dependencies, co-occurrences, evidence."""
        if not tool_ids:
            return {}
        with self.driver.session(database=self.config.database) as session:
            result = session.run(
                """UNWIND $ids AS tid
                   MATCH (t:Tool {id: tid})
                   OPTIONAL MATCH (t)-[:DEPENDS_ON]->(dep:Tool)
                   OPTIONAL MATCH (t)-[:CO_OCCURS_WITH]-(co:Tool)
                   OPTIONAL MATCH (t)-[:DUPLICATE_OF]->(dup:Tool)
                   OPTIONAL MATCH (t)<-[:EVIDENCED_BY]-(ev:Evidence)
                   RETURN t.id AS id, t.name AS name, t.type AS type,
                          t.description AS description, t.target AS target,
                          t.confirmations AS confirmations, t.status AS status,
                          collect(DISTINCT dep.id) AS depends_on,
                          collect(DISTINCT co.id) AS co_occurs_with,
                          collect(DISTINCT dup.id) AS duplicate_of,
                          collect(DISTINCT ev.anchor) AS evidence""",
                ids=tool_ids,
            )
            return {
                r["id"]: {k: v for k, v in r.items() if k != "id"}
                for r in result
            }

    def search(
        self,
        query: str,
        top_k: int = 20,
        bm25_weight: float = 0.3,
        use_embedding: bool = True,
        enrich: bool = True,
    ) -> list[dict]:
        """Main entry: hybrid search with optional graph enrichment."""
        bm25_results = self.bm25_search(query, k=50)
        cosine_results = (
            self.cosine_search(self.encode(query), k=50) if use_embedding else []
        )
        fused = self.rrf_fuse(bm25_results, cosine_results, top_k, bm25_weight)

        bm25_map = {r["id"]: r for r in bm25_results}
        cosine_map = {r["id"]: r for r in cosine_results}

        if not enrich:
            return [
                {
                    "id": tid,
                    "rrf_score": round(score, 4),
                    "bm25_score": round(bm25_map.get(tid, {}).get("score", 0), 4),
                    "cosine_score": round(cosine_map.get(tid, {}).get("score", 0), 4),
                    "name": bm25_map.get(tid, {}).get("name", tid),
                    "type": bm25_map.get(tid, {}).get("type", ""),
                }
                for tid, score in fused
            ]

        tool_map = self.enrich_with_graph([tid for tid, _ in fused])
        results = []
        for tid, rrf_score in fused:
            tool = tool_map.get(tid, {})
            graph_score = self._connectivity_score(tool)
            results.append({
                "id": tid,
                "rrf_score": round(rrf_score, 4),
                "graph_score": round(graph_score, 4),
                "combined_score": round(rrf_score * 0.7 + min(graph_score / 10, 1.0) * 0.3, 4),
                "name": tool.get("name", tid),
                "type": tool.get("type", ""),
                "description": tool.get("description", ""),
                "target": tool.get("target", ""),
                "confirmations": tool.get("confirmations", 0),
                "depends_on": tool.get("depends_on", []),
                "co_occurs_with": tool.get("co_occurs_with", []),
                "duplicate_of": tool.get("duplicate_of", []),
                "evidence": tool.get("evidence", []),
            })
        return results

    @staticmethod
    def _connectivity_score(tool: dict) -> float:
        score = 0.0
        score += min(len(tool.get("depends_on", [])), 10) * 1.0
        score += min(len(tool.get("co_occurs_with", [])), 10) * 0.5
        score += tool.get("confirmations", 0) or 0 * 0.3
        score += len(tool.get("evidence", [])) * 0.2
        return score

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None


def main():
    parser = argparse.ArgumentParser(description="Hybrid BM25+Cosine search over Neo4j tools")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--bm25-weight", type=float, default=0.3, help="BM25 weight in RRF")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--no-embedding", action="store_true", help="Skip cosine/vector search")
    parser.add_argument("--no-enrich", action="store_true", help="Skip graph enrichment")
    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(1)

    searcher = HybridSearcher()
    try:
        results = searcher.search(
            args.query,
            top_k=args.limit,
            bm25_weight=args.bm25_weight,
            use_embedding=not args.no_embedding,
            enrich=not args.no_enrich,
        )
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for i, r in enumerate(results):
                print(f"{i+1}. [{r['type']}] {r['name']} (score={r['combined_score']:.3f})")
                if r.get("description"):
                    print(f"   {r['description'][:120]}")
                if r.get("depends_on"):
                    print(f"   depends_on: {', '.join(r['depends_on'][:5])}")
                print()
    finally:
        searcher.close()


if __name__ == "__main__":
    main()
