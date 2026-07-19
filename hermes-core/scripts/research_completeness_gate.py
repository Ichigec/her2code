#!/usr/bin/env python3
"""
GATE C: Research Completeness Gate — 5 structural checks.

Проверяет, что research-артефакт полный и готов к передаче в Phase 4.
Запускается после Phase 3.2 (Synthesis), перед 3.3 (Citation Verification).

5 проверок:
    1. RQ Coverage  — каждый RQ имеет ответ (не TBD/unknown)
    2. Citation Mapping — каждый claim ссылается на source
    3. Artifact Structure — все обязательные секции присутствуют
    4. Source Diversity — ≥3 разных типа источников
    5. Artifact Size — >2000 байт

Usage:
    python3 research_completeness_gate.py --artifact docs/research/<slug>.md [--json]

Exit codes:
    0 — PASS (все 5 проверок)
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


class CompletenessGate:
    """GATE C: 5 structural completeness checks."""

    def __init__(self, artifact_path: str):
        self.artifact_path = artifact_path
        self.results: list[CheckResult] = []

    def _add(self, name: str, passed: bool, detail: str = "", error: str | None = None):
        self.results.append(CheckResult(name=name, passed=passed, detail=detail, error=error))

    # ------------------------------------------------------------------
    # Check 1: RQ Coverage
    # ------------------------------------------------------------------

    def check_rq_coverage(self, content: str):
        """Every RQ in the plan section has an answer (not TBD/unknown/empty)."""
        # Find RQ definitions in the table
        rq_ids = set()
        in_rq_table = False
        for line in content.split("\n"):
            if "Research Questions" in line and "|" in content[content.find(line):content.find(line)+200]:
                in_rq_table = True
                continue
            if in_rq_table and line.startswith("|") and "---" not in line and "RQ" not in line and "Priority" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if parts and len(parts) >= 3:
                    # First column is RQ id if it contains digits
                    if any(c.isdigit() for c in parts[0]):
                        rq_ids.add(parts[0])
            if in_rq_table and not line.startswith("|"):
                in_rq_table = False

        # Find answered RQs (sections with content)
        answered = set()
        current_rq = None
        has_content = False
        for line in content.split("\n"):
            if line.startswith("#### RQ") or line.startswith("### RQ"):
                if current_rq and has_content:
                    answered.add(current_rq)
                current_rq = line.strip("# ").split(":")[0].strip()
                has_content = False
            elif current_rq and line.strip() and not line.startswith("#"):
                if len(line.strip()) > 20:  # substantive content
                    has_content = True
        if current_rq and has_content:
            answered.add(current_rq)

        # Check for unresolved markers
        unresolved = len(re.findall(r'\b(TBD|TODO|unknown|неизвестно)\b',
                                    content, re.IGNORECASE))

        missing = rq_ids - answered
        all_covered = len(missing) == 0 and unresolved == 0

        detail_lines = [
            f"  RQs defined: {len(rq_ids)}",
            f"  RQs answered: {len(answered)}",
            f"  Missing RQs: {', '.join(sorted(missing)) if missing else 'none'}",
            f"  Unresolved markers (TBD/etc): {unresolved}",
        ]
        self._add("1. RQ Coverage", all_covered, "\n".join(detail_lines),
                  None if all_covered else f"Missing: {missing}, Unresolved: {unresolved}")

    # ------------------------------------------------------------------
    # Check 2: Citation Mapping
    # ------------------------------------------------------------------

    def check_citation_mapping(self, content: str):
        """Every substantive paragraph in RQ Answers has a [N] citation."""
        in_answers = False
        substantive_paragraphs = 0
        cited_paragraphs = 0
        buffer = []
        
        for line in content.split("\n"):
            if "## RQ Answers" in line:
                in_answers = True
                continue
            elif in_answers and (line.startswith("## ") or line.startswith("### Source Quality Matrix") or line.startswith("### Debate")) and "RQ Answers" not in line:
                # End of RQ Answers — flush buffer
                if buffer:
                    text = " ".join(buffer)
                    if len(text) > 80:
                        substantive_paragraphs += 1
                        if re.search(r'\[\d+(?:,\s*\d+)*\]', text):
                            cited_paragraphs += 1
                break
            
            if in_answers:
                if not line.strip() and buffer:
                    # Paragraph boundary
                    text = " ".join(buffer)
                    if len(text) > 80:
                        substantive_paragraphs += 1
                        if re.search(r'\[\d+(?:,\s*\d+)*\]', text):
                            cited_paragraphs += 1
                    buffer = []
                elif line.strip() and not line.startswith("#"):
                    buffer.append(line.strip())

        ratio = cited_paragraphs / max(substantive_paragraphs, 1)
        passed = ratio >= 0.8

        self._add("2. Citation Mapping", passed,
                  f"  Cited paragraphs: {cited_paragraphs}/{substantive_paragraphs} ({ratio:.0%})\n"
                  f"  Threshold: 80%",
                  None if passed else f"Only {ratio:.0%} cited (need ≥80%)")

    # ------------------------------------------------------------------
    # Check 3: Artifact Structure
    # ------------------------------------------------------------------

    def check_artifact_structure(self, content: str):
        """All mandatory sections present."""
        required = [
            ("## RQ Answers", "RQ Answers section"),
            ("Source Quality Matrix", "Source Quality Matrix"),
            ("#", "Title (any heading)"),
        ]
        recommended = [
            ("Developer Handoff", "Developer Handoff section"),
            ("Recommendations for Architect", "Architect recommendations"),
            ("Cross-References", "Cross-references section"),
        ]

        missing_required = []
        for pattern, name in required:
            if pattern not in content:
                missing_required.append(name)

        missing_recommended = []
        for pattern, name in recommended:
            if pattern not in content:
                missing_recommended.append(name)

        all_required_present = len(missing_required) == 0

        detail = [f"  Required sections present: {len(required) - len(missing_required)}/{len(required)}"]
        if missing_required:
            detail.append(f"  MISSING (required): {', '.join(missing_required)}")
        if missing_recommended:
            detail.append(f"  Missing (recommended): {', '.join(missing_recommended)}")

        self._add("3. Artifact Structure", all_required_present, "\n".join(detail),
                  None if all_required_present else f"Missing: {missing_required}")

    # ------------------------------------------------------------------
    # Check 4: Source Diversity
    # ------------------------------------------------------------------

    def check_source_diversity(self, content: str):
        """At least 3 different source types used."""
        source_types = set()
        type_markers = {
            "arxiv": "arxiv.org",
            "github": "github.com",
            "wikipedia": "wikipedia.org",
            "docs": "docs.",
            "stack": "stackoverflow.com",
            "reddit": "reddit.com",
            "hn": "news.ycombinator.com",
            "medium": "medium.com",
            "acm": "acm.org",
            "ieee": "ieee.org",
            "semanticscholar": "semanticscholar.org",
        }

        for type_name, marker in type_markers.items():
            if marker in content.lower():
                source_types.add(type_name)

        # Also count unique domains in Source Quality Matrix
        urls = re.findall(r'https?://[^\s)\]]+', content)
        domains = set()
        for url in urls:
            try:
                domain = url.split("://")[1].split("/")[0].replace("www.", "")
                domains.add(domain)
            except IndexError:
                pass

        unique_types = len(source_types) + (1 if len(domains) >= 3 else 0)
        passed = len(source_types) >= 3 or len(domains) >= 5

        self._add("4. Source Diversity", passed,
                  f"  Source types: {len(source_types)} ({', '.join(sorted(source_types)) if source_types else 'none'})\n"
                  f"  Unique domains: {len(domains)}\n"
                  f"  Threshold: ≥3 types OR ≥5 domains",
                  None if passed else f"Only {len(source_types)} types, {len(domains)} domains")

    # ------------------------------------------------------------------
    # Check 5: Artifact Size
    # ------------------------------------------------------------------

    def check_artifact_size(self, content: str):
        """Artifact >2000 bytes (substantive content)."""
        size = len(content.encode("utf-8"))
        word_count = len(content.split())
        passed = size > 2000 and word_count > 300

        self._add("5. Artifact Size", passed,
                  f"  Size: {size} bytes, {word_count} words\n"
                  f"  Threshold: >2000 bytes AND >300 words",
                  None if passed else f"Too small: {size}B, {word_count} words")

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def evaluate(self) -> bool:
        if not os.path.isfile(self.artifact_path):
            self._add("GATE C", False, f"Artifact not found: {self.artifact_path}")
            return False

        try:
            with open(self.artifact_path) as f:
                content = f.read()
        except OSError as e:
            self._add("GATE C", False, f"Cannot read: {e}")
            return False

        self.check_rq_coverage(content)
        self.check_citation_mapping(content)
        self.check_artifact_structure(content)
        self.check_source_diversity(content)
        self.check_artifact_size(content)

        return all(r.passed for r in self.results)

    def report_json(self) -> str:
        return json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "artifact": self.artifact_path,
            "passed": sum(1 for r in self.results if r.passed),
            "total": len(self.results),
            "checks": [{"name": r.name, "passed": r.passed, "detail": r.detail, "error": r.error}
                       for r in self.results],
        }, indent=2, ensure_ascii=False)

    def report_text(self) -> str:
        lines = ["=" * 60, "  GATE C — COMPLETENESS GATE", "=" * 60,
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
        total = len(self.results)
        lines.extend(["", "-" * 60,
                      f"  Result: {passed_count}/{total} checks passed",
                      f"  VERDICT: {'ALL PASSED' if passed_count == total else 'FAIL — fix and re-run'}",
                      "=" * 60])
        return "\n".join(lines)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    artifact_path = None
    json_mode = False

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--artifact" and i + 1 < len(sys.argv):
            artifact_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--json":
            json_mode = True
            i += 1
        else:
            i += 1

    if not artifact_path:
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

    gate = CompletenessGate(artifact_path)
    all_passed = gate.evaluate()

    if json_mode:
        print(gate.report_json())
    else:
        print(gate.report_text())

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
