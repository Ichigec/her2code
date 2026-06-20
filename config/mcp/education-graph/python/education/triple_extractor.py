"""
Education Agent — continuous knowledge graph enrichment from agent interactions.

Triple extraction pipeline based on NVIDIA txt2kg (dgx-spark-txt2kg).
Extracts (subject, predicate, object) triples from text chunks using an LLM.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from neo4j import GraphDatabase, Driver


TRIPLE_EXTRACTION_PROMPT = """Extract knowledge triples from the text below.
A triple has format: (subject, predicate, object, confidence).
- subject: the main entity (tool, file, concept, command, service)
- predicate: the relationship (uses, depends_on, configures, runs, exposes, requires, is_part_of, mitigates, vulnerable_to, alternative_to)
- object: the related entity
- confidence: float 0.0-1.0 (how certain you are)

Rules:
- Extract ONLY factual, verifiable relationships
- Skip opinions, speculation, or uncertain claims
- If a triple describes a security vulnerability, mark predicate as "vulnerable_to", "exposes_cve", or "mitigates"
- Max 10 triples per chunk
- Output JSON array only, no other text

Text:
{text}

Output (JSON array of triples):"""


@dataclass
class ExtractedTriple:
    subject: str
    predicate: str
    obj: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.obj,
            "confidence": self.confidence,
        }


class TripleExtractor:
    """Extracts knowledge triples from text using LLM or rule-based fallback."""

    VALID_PREDICATES = {
        "uses", "depends_on", "configures", "runs", "exposes",
        "requires", "is_part_of", "mitigates", "vulnerable_to",
        "alternative_to", "implements", "provides", "manages",
        "connects_to", "writes_to", "reads_from", "executes",
        "installs", "removes", "starts", "stops", "monitors",
        "exposes_cve", "contains", "owns",
    }

    def __init__(self, llm_callable=None):
        """
        Args:
            llm_callable: async function(text, prompt) -> str
                          If None, uses rule-based fallback only.
        """
        self._llm = llm_callable

    async def extract(self, text: str, chunk_size: int = 512) -> list[ExtractedTriple]:
        """Extract triples from text, chunking if needed."""
        if len(text) <= chunk_size:
            return await self._extract_chunk(text)

        # Chunk with sliding window
        chunks = []
        for i in range(0, len(text), chunk_size - 64):
            chunks.append(text[i:i + chunk_size])
            if len(chunks) >= 20:  # safety cap
                break

        all_triples = []
        for chunk in chunks:
            triples = await self._extract_chunk(chunk)
            all_triples.extend(triples)

        return self._deduplicate(all_triples)

    async def _extract_chunk(self, text: str) -> list[ExtractedTriple]:
        if self._llm:
            try:
                prompt = TRIPLE_EXTRACTION_PROMPT.format(text=text[:2000])
                response = await self._llm(text, prompt)
                return self._parse_llm_response(response)
            except Exception:
                pass
        return self._rule_based_extract(text)

    def _parse_llm_response(self, response: str) -> list[ExtractedTriple]:
        """Parse LLM JSON response into triples."""
        try:
            # Extract JSON array from response (may contain extra text)
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []
            data = json.loads(json_match.group())
            triples = []
            for item in data:
                if isinstance(item, dict) and all(k in item for k in ("subject", "predicate", "object", "confidence")):
                    pred = item["predicate"].lower().replace(" ", "_")
                    if pred in self.VALID_PREDICATES:
                        triples.append(ExtractedTriple(
                            subject=item["subject"].strip().lower(),
                            predicate=pred,
                            obj=item["object"].strip().lower(),
                            confidence=float(item["confidence"]),
                        ))
            return triples
        except (json.JSONDecodeError, ValueError, KeyError):
            return []

    def _rule_based_extract(self, text: str) -> list[ExtractedTriple]:
        """Rule-based triple extraction fallback (no LLM)."""
        triples = []
        text_lower = text.lower()

        # Pattern: "uses X"
        for match in re.finditer(r'(?:using|uses?|with)\s+`?([a-zA-Z0-9_\-/.]+)`?', text_lower):
            tool = match.group(1)
            triples.append(ExtractedTriple("unknown", "uses", tool, 0.5))

        # Pattern: "runs on X" / "deployed on X"
        for match in re.finditer(r'(?:runs?\s+on|deployed\s+on|hosted\s+on)\s+`?([a-zA-Z0-9_\-/.]+)`?', text_lower):
            target = match.group(1)
            triples.append(ExtractedTriple("unknown", "runs", target, 0.5))

        # Pattern: file paths
        for match in re.finditer(r'([/~][a-zA-Z0-9_\-/.]+)', text):
            path = match.group(1)
            triples.append(ExtractedTriple("unknown", "contains", path, 0.6))

        # Pattern: "depends on X"
        for match in re.finditer(r'depends?\s+on\s+`?([a-zA-Z0-9_\-/.]+)`?', text_lower):
            dep = match.group(1)
            triples.append(ExtractedTriple("unknown", "depends_on", dep, 0.6))

        return self._deduplicate(triples)

    @staticmethod
    def _deduplicate(triples: list[ExtractedTriple]) -> list[ExtractedTriple]:
        seen = set()
        result = []
        for t in triples:
            key = (t.subject, t.predicate, t.obj)
            if key not in seen:
                seen.add(key)
                result.append(t)
        return result
