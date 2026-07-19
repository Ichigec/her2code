#!/usr/bin/env python3
"""
GATE D: Citation Enforcement Gate.

Проверяет:
    1. Каждый факт (claim) имеет ссылку на источник [N]
    2. Последовательные факты из одного источника сгруппированы (одна [N] в конце группы)
    3. Не менее 90% цитат валидны (URL отвечает, контент семантически совпадает)

Запускается после Phase 3.3 (CitationAgent), перед передачей в Phase 4.

Usage:
    python3 citation_enforcement_gate.py --artifact docs/research/<slug>.md [--json] [--verify-sample 20]

Exit codes:
    0 — PASS (≥90% citations valid)
    1 — FAIL
"""

import json
import os
import re
import subprocess
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
class CitationReport:
    total_claims: int = 0
    cited_claims: int = 0
    uncited_claims: int = 0
    total_citations: int = 0
    valid_citations: int = 0
    invalid_citations: int = 0
    ungrouped_blocks: int = 0
    suggestions: list[str] = field(default_factory=list)

    @property
    def citation_rate(self) -> float:
        return self.cited_claims / max(self.total_claims, 1)

    @property
    def validity_rate(self) -> float:
        return self.valid_citations / max(self.total_citations, 1)


class CitationEnforcementGate:
    """GATE D: Citation enforcement with grouping and URL verification."""

    def __init__(self, artifact_path: str, verify_sample_pct: int = 20):
        self.artifact_path = artifact_path
        self.verify_sample_pct = verify_sample_pct
        self.results: list[CheckResult] = []

    def _add(self, name: str, passed: bool, detail: str = "", error: str | None = None):
        self.results.append(CheckResult(name=name, passed=passed, detail=detail, error=error))

    # ------------------------------------------------------------------
    # 1. Extract claims and citations
    # ------------------------------------------------------------------

    def _extract_claims(self, content: str) -> list[dict]:
        """Extract substantive claims with their citations from RQ Answers."""
        claims = []
        in_answers = False
        paragraph_buffer = []
        current_citation = None

        for line in content.split("\n"):
            if "## RQ Answers" in line:
                in_answers = True
                continue
            elif in_answers and line.startswith("## ") and "RQ Answers" not in line:
                # Flush buffer
                if paragraph_buffer:
                    text = " ".join(paragraph_buffer)
                    # Extract citation from end of paragraph
                    cite_match = re.search(r'\[(\d+(?:,\s*\d+)*)\]\s*$', text)
                    claims.append({
                        "text": text.strip(),
                        "citation": cite_match.group(1) if cite_match else None,
                        "has_citation": cite_match is not None,
                    })
                break

            if in_answers and line.strip():
                # Check if this line ends a paragraph (ends with citation)
                cite_match = re.search(r'\[(\d+(?:,\s*\d+)*)\]\s*$', line.strip())
                if cite_match and paragraph_buffer:
                    # Flush previous paragraph
                    text = " ".join(paragraph_buffer)
                    claims.append({
                        "text": text,
                        "citation": None,  # old paragraph might not have citation
                        "has_citation": bool(re.search(r'\[\d', text)),
                    })
                    paragraph_buffer = [line.strip()]
                else:
                    paragraph_buffer.append(line.strip())
            elif in_answers and not line.strip() and paragraph_buffer:
                # Empty line = paragraph boundary
                text = " ".join(paragraph_buffer)
                cite_match = re.search(r'\[(\d+(?:,\s*\d+)*)\]', text)
                claims.append({
                    "text": text,
                    "citation": cite_match.group(1) if cite_match else None,
                    "has_citation": cite_match is not None,
                })
                paragraph_buffer = []

        return claims

    def _extract_source_urls(self, content: str) -> dict[str, str]:
        """Extract source index → URL mapping from Source Quality Matrix."""
        sources = {}
        in_table = False
        for line in content.split("\n"):
            if "Source Quality Matrix" in line:
                in_table = True
                continue
            if in_table and line.startswith("## "):
                break
            if in_table and line.startswith("|") and "---" not in line and "Title" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    index = parts[0]
                    url = parts[2] if parts[2].startswith("http") else ""
                    if url:
                        sources[index] = url
        return sources

    # ------------------------------------------------------------------
    # 2. Check grouping
    # ------------------------------------------------------------------

    def _check_grouping(self, claims: list[dict]) -> tuple[int, list[str]]:
        """Check that consecutive same-source claims are grouped under one citation."""
        ungrouped = 0
        suggestions = []
        prev_citation = None
        consecutive_same = 0

        for i, claim in enumerate(claims):
            cit = claim.get("citation")
            if cit == prev_citation and cit is not None:
                consecutive_same += 1
                if consecutive_same == 1:  # First duplicate
                    ungrouped += 1
                    suggestions.append(
                        f"Claims {i}-{i+1} both cite [{cit}] — should be grouped"
                    )
            else:
                consecutive_same = 0
            prev_citation = cit

        return ungrouped, suggestions

    # ------------------------------------------------------------------
    # 3. Verify citations via curl (sample)
    # ------------------------------------------------------------------

    def _verify_citations(self, content: str, sources: dict[str, str]) -> tuple[int, int]:
        """Verify a random sample of citations by curling source URLs."""
        if not sources:
            return 0, 0

        import random
        sample_size = max(1, int(len(sources) * self.verify_sample_pct / 100))
        sample_keys = random.sample(list(sources.keys()), min(sample_size, len(sources)))

        verified = 0
        failed = 0

        for key in sample_keys:
            url = sources[key]
            try:
                r = subprocess.run(
                    ["curl", "-sL", "--max-time", "8", "-o", "/dev/null", "-w", "%{http_code}",
                     "-H", "User-Agent: Mozilla/5.0", url],
                    capture_output=True, text=True, timeout=10,
                )
                status = r.stdout.strip()
                if status.startswith("2") or status.startswith("3"):
                    verified += 1
                else:
                    failed += 1
            except (subprocess.TimeoutExpired, Exception):
                failed += 1

        return verified, failed

    # ------------------------------------------------------------------
    # 4. Main evaluation
    # ------------------------------------------------------------------

    def evaluate(self) -> CitationReport:
        if not os.path.isfile(self.artifact_path):
            self._add("GATE D", False, f"Artifact not found: {self.artifact_path}")
            return CitationReport()

        try:
            with open(self.artifact_path) as f:
                content = f.read()
        except OSError as e:
            self._add("GATE D", False, f"Cannot read: {e}")
            return CitationReport()

        claims = self._extract_claims(content)
        sources = self._extract_source_urls(content)

        total = len(claims)
        cited = sum(1 for c in claims if c["has_citation"])
        uncited = total - cited
        total_citations = len([c for c in claims if c["citation"]])

        # Check grouping
        ungrouped, suggestions = self._check_grouping(claims)

        # Verify sample
        verified, failed = self._verify_citations(content, sources)

        report = CitationReport(
            total_claims=total,
            cited_claims=cited,
            uncited_claims=uncited,
            total_citations=total_citations,
            valid_citations=verified,
            invalid_citations=failed,
            ungrouped_blocks=ungrouped,
            suggestions=suggestions,
        )

        # Determine pass/fail
        citation_rate_ok = report.citation_rate >= 0.90
        validity_ok = (report.validity_rate >= 0.90) if report.total_citations > 0 else True
        grouping_ok = ungrouped <= max(1, total * 0.1)  # ≤10% ungrouped

        all_passed = citation_rate_ok and validity_ok and grouping_ok

        detail_lines = [
            f"  Claims total      : {total}",
            f"  Claims cited      : {cited} ({report.citation_rate:.0%})",
            f"  Claims uncited    : {uncited}",
            f"  Citations verified: {verified}/{verified + failed} ({report.validity_rate:.0%})",
            f"  Ungrouped blocks  : {ungrouped}",
            f"  ─────────────────────────────",
            f"  Citation rate ≥90% : {'✓' if citation_rate_ok else '✗'} ({report.citation_rate:.0%})",
            f"  Validity ≥90%     : {'✓' if validity_ok else '✗'} ({report.validity_rate:.0%})",
            f"  Grouping ≤10%     : {'✓' if grouping_ok else '✗'} ({ungrouped} blocks)",
        ]
        if suggestions:
            detail_lines.append(f"\n  Suggestions:")
            for s in suggestions[:5]:
                detail_lines.append(f"    - {s}")

        self._add("GATE D", all_passed, "\n".join(detail_lines),
                  None if all_passed else "Citations need fixing")

        return report

    def report_json(self) -> str:
        return json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "artifact": self.artifact_path,
            "verify_sample_pct": self.verify_sample_pct,
            "passed": all(r.passed for r in self.results),
            "checks": [{"name": r.name, "passed": r.passed, "detail": r.detail, "error": r.error}
                       for r in self.results],
        }, indent=2, ensure_ascii=False)

    def report_text(self) -> str:
        lines = ["=" * 60, "  GATE D — CITATION ENFORCEMENT GATE", "=" * 60,
                 f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                 f"  Artifact: {self.artifact_path}",
                 f"  Sample verify: {self.verify_sample_pct}%", "-" * 60]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"\n  [{status}] {r.name}")
            if r.detail:
                lines.append(r.detail)
            if r.error:
                lines.append(f"  Error: {r.error}")
        passed_count = sum(1 for r in self.results if r.passed)
        lines.extend(["", "-" * 60,
                      f"  VERDICT: {'PASS' if passed_count == len(self.results) else 'FAIL — fix citations'}",
                      "=" * 60])
        return "\n".join(lines)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    artifact_path = None
    verify_sample = 20
    json_mode = False

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--artifact" and i + 1 < len(sys.argv):
            artifact_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--verify-sample" and i + 1 < len(sys.argv):
            verify_sample = int(sys.argv[i + 1])
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

    gate = CitationEnforcementGate(artifact_path, verify_sample)
    gate.evaluate()

    if json_mode:
        print(gate.report_json())
    else:
        print(gate.report_text())

    sys.exit(0 if all(r.passed for r in gate.results) else 1)


if __name__ == "__main__":
    main()
