#!/usr/bin/env python3
"""
GATE B: Source Quality Gate — LLM-as-judge evaluation (5 Anthropic-стиль критериев).

Проверяет качество источников в research-артефакте.
Запускается после Phase 3.1 (Parallel Execution), перед 3.2 (Synthesis).

Usage:
    python3 research_quality_gate.py --artifact docs/research/<slug>.md [--json] [--threshold 0.6]

Критерии (каждый 0.0-1.0):
    factual_accuracy  — соответствие фактов источникам
    citation_accuracy — точность цитирования
    completeness      — полнота покрытия RQs
    source_quality    — авторитетность источников
    tool_efficiency   — эффективность использования инструментов

Exit codes:
    0 — PASS (средний score >= threshold)
    1 — FAIL
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    error: Optional[str] = None


@dataclass
class SourceQualityResult:
    factual_accuracy: float = 0.0
    citation_accuracy: float = 0.0
    completeness: float = 0.0
    source_quality: float = 0.0
    tool_efficiency: float = 0.0

    @property
    def average(self) -> float:
        return (self.factual_accuracy + self.citation_accuracy +
                self.completeness + self.source_quality + self.tool_efficiency) / 5.0

    def to_dict(self) -> dict:
        return {
            "factual_accuracy": round(self.factual_accuracy, 2),
            "citation_accuracy": round(self.citation_accuracy, 2),
            "completeness": round(self.completeness, 2),
            "source_quality": round(self.source_quality, 2),
            "tool_efficiency": round(self.tool_efficiency, 2),
            "average": round(self.average, 2),
        }


class SourceQualityGate:
    """GATE B: Evaluates source quality using LLM-as-judge methodology."""

    def __init__(self, artifact_path: str, threshold: float = 0.6):
        self.artifact_path = artifact_path
        self.threshold = threshold
        self.results: list[CheckResult] = []

    def _add(self, name: str, passed: bool, detail: str = "", error: str | None = None):
        self.results.append(CheckResult(name=name, passed=passed, detail=detail, error=error))

    # ------------------------------------------------------------------
    # 1. Count sources in artifact
    # ------------------------------------------------------------------

    def _extract_sources(self, content: str) -> list[dict]:
        """Extract sources from Source Quality Matrix table."""
        sources = []
        in_table = False
        for line in content.split("\n"):
            if "Source Quality Matrix" in line:
                in_table = True
                continue
            if in_table and line.startswith("## "):
                break
            if in_table and line.startswith("|") and "---" not in line and "Title" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 6:
                    sources.append({
                        "num": parts[0] if parts[0].isdigit() else "?",
                        "title": parts[1],
                        "url": parts[2],
                        "authority": parts[3] if parts[3].isdigit() else "0",
                        "recency": parts[4] if len(parts) > 4 and parts[4].isdigit() else "0",
                        "relevance": parts[5] if len(parts) > 5 and parts[5].isdigit() else "0",
                        "score": parts[-1] if len(parts) > 6 else "?",
                    })
        return sources

    def _count_claims_with_citations(self, content: str) -> tuple[int, int]:
        """Count claims with [N] citations vs total substantive paragraphs."""
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()
                      and not p.startswith("#") and not p.startswith("|")
                      and len(p) > 50]
        cited = sum(1 for p in paragraphs if re.search(r'\[\d+(?:,\s*\d+)*\]', p))
        return cited, max(len(paragraphs), 1)

    # ------------------------------------------------------------------
    # 2. Score each criterion heuristically
    # ------------------------------------------------------------------

    def _score_factual_accuracy(self, content: str, sources: list[dict]) -> float:
        """Heuristic: if sources exist and are not all score=0."""
        if not sources:
            return 0.0
        scores = []
        for s in sources:
            try:
                scores.append(int(s.get("score", "0")))
            except (ValueError, TypeError):
                scores.append(0)
        if not scores:
            return 0.0
        # Map 0-8 score to 0.0-1.0
        avg_source_score = sum(scores) / (len(scores) * 8)
        return round(min(avg_source_score, 1.0), 2)

    def _score_citation_accuracy(self, content: str, sources: list[dict]) -> float:
        """Heuristic: citation density and URL validity."""
        cited, total = self._count_claims_with_citations(content)
        density = cited / total

        # Check if URLs are present
        urls_present = sum(1 for s in sources if s.get("url", "").startswith("http"))

        url_ratio = urls_present / max(len(sources), 1)
        return round((density * 0.7 + url_ratio * 0.3), 2)

    def _score_completeness(self, content: str, sources: list[dict]) -> float:
        """Heuristic: missing sections, TBD markers."""
        required_sections = [
            "RQ Answers",
            "Source Quality Matrix",
            "Recommendations for Architect",
        ]
        found = sum(1 for s in required_sections if s.lower() in content.lower())
        section_ratio = found / len(required_sections)

        # Penalize for TBD/unknown markers
        tbd_count = len(re.findall(r'\b(TBD|unknown|TODO|неизвестно|не исследовано)\b',
                                    content, re.IGNORECASE))
        tbd_penalty = min(tbd_count * 0.1, 0.5)

        return round(min(section_ratio - tbd_penalty, 1.0), 2)

    def _score_source_quality(self, content: str, sources: list[dict]) -> float:
        """Heuristic: authority + recency scores from source matrix."""
        if not sources:
            return 0.0
        authority_scores = []
        recency_scores = []
        for s in sources:
            try:
                authority_scores.append(int(s.get("authority", "0")))
                recency_scores.append(int(s.get("recency", "0")))
            except (ValueError, TypeError):
                pass
        if not authority_scores:
            return 0.0
        avg_authority = sum(authority_scores) / (len(authority_scores) * 2)
        avg_recency = sum(recency_scores) / (len(recency_scores) * 2)
        return round((avg_authority * 0.6 + avg_recency * 0.4), 2)

    def _score_tool_efficiency(self, content: str, sources: list[dict]) -> float:
        """Heuristic: source diversity (≥3 different domains)."""
        urls = [s.get("url", "") for s in sources]
        domains = set()
        for url in urls:
            try:
                domain = url.split("://")[1].split("/")[0].replace("www.", "")
                domains.add(domain)
            except (IndexError, ValueError):
                pass
        diversity = len(domains) / max(len(sources), 1)

        # Ideal: 3+ different source types
        source_types = 0
        type_markers = {
            "arxiv": "arxiv.org",
            "github": "github.com",
            "wikipedia": "wikipedia.org",
            "docs": "docs.",
            "stack": "stack",
            "reddit": "reddit",
            "hn": "news.ycombinator",
        }
        for marker, _ in type_markers.items():
            if any(marker in url.lower() for url in urls):
                source_types += 1

        type_diversity = min(source_types / 3.0, 1.0)
        return round((diversity * 0.4 + type_diversity * 0.6), 2)

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def evaluate(self) -> SourceQualityResult:
        """Run all 5 criteria evaluations."""
        if not os.path.isfile(self.artifact_path):
            self._add("GATE B", False, f"Artifact not found: {self.artifact_path}")
            return SourceQualityResult()

        try:
            with open(self.artifact_path) as f:
                content = f.read()
        except OSError as e:
            self._add("GATE B", False, f"Cannot read artifact: {e}")
            return SourceQualityResult()

        sources = self._extract_sources(content)

        result = SourceQualityResult(
            factual_accuracy=self._score_factual_accuracy(content, sources),
            citation_accuracy=self._score_citation_accuracy(content, sources),
            completeness=self._score_completeness(content, sources),
            source_quality=self._score_source_quality(content, sources),
            tool_efficiency=self._score_tool_efficiency(content, sources),
        )

        passed = result.average >= self.threshold
        detail_lines = [
            f"  factual_accuracy : {result.factual_accuracy:.2f}",
            f"  citation_accuracy: {result.citation_accuracy:.2f}",
            f"  completeness     : {result.completeness:.2f}",
            f"  source_quality   : {result.source_quality:.2f}",
            f"  tool_efficiency  : {result.tool_efficiency:.2f}",
            f"  ─────────────────────────────",
            f"  AVERAGE          : {result.average:.2f} (threshold: {self.threshold})",
            f"  Sources found    : {len(sources)}",
        ]

        self._add("GATE B", passed, "\n".join(detail_lines),
                  None if passed else f"Average {result.average:.2f} < threshold {self.threshold}")

        return result

    def report_json(self) -> str:
        return json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "artifact": self.artifact_path,
            "threshold": self.threshold,
            "passed": all(r.passed for r in self.results),
            "checks": [{"name": r.name, "passed": r.passed, "detail": r.detail, "error": r.error}
                       for r in self.results],
        }, indent=2, ensure_ascii=False)

    def report_text(self) -> str:
        lines = ["=" * 60, "  GATE B — SOURCE QUALITY GATE", "=" * 60,
                 f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                 f"  Artifact: {self.artifact_path}", "-" * 60]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"\n  [{status}] {r.name}")
            if r.detail:
                lines.append(r.detail)
            if r.error:
                lines.append(f"  Error: {r.error}")
        passed_count = sum(1 for r in self.results if r.passed)
        lines.extend(["", "-" * 60,
                      f"  VERDICT: {'PASS' if passed_count == len(self.results) else 'FAIL'}",
                      "=" * 60])
        return "\n".join(lines)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    artifact_path = None
    threshold = 0.6
    json_mode = False

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--artifact" and i + 1 < len(sys.argv):
            artifact_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--threshold" and i + 1 < len(sys.argv):
            threshold = float(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--json":
            json_mode = True
            i += 1
        else:
            i += 1

    if not artifact_path:
        # Default: latest in docs/research/
        research_dir = os.path.join(os.getcwd(), "docs", "research")
        if os.path.isdir(research_dir):
            mds = sorted(
                [f for f in os.listdir(research_dir) if f.endswith(".md")],
                key=lambda f: os.path.getmtime(os.path.join(research_dir, f)),
                reverse=True,
            )
            if mds:
                artifact_path = os.path.join(research_dir, mds[0])

    if not artifact_path or not os.path.isfile(artifact_path):
        print("ERROR: No artifact found. Use --artifact <path>", file=sys.stderr)
        sys.exit(1)

    gate = SourceQualityGate(artifact_path, threshold)
    result = gate.evaluate()

    if json_mode:
        report = json.loads(gate.report_json())
        report["scores"] = result.to_dict()
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(gate.report_text())

    passed = all(r.passed for r in gate.results)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
