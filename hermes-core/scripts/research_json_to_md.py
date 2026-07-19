#!/usr/bin/env python3
"""
research_json_to_md.py — Auto-generate readable markdown from structured research JSON.

Single source of truth = JSON. Markdown = view for humans (Architect, System Analyst, audit).

Usage:
    python3 research_json_to_md.py --input docs/research/<slug>.json --output docs/research/<slug>.md
    python3 research_json_to_md.py --input docs/research/<slug>.json  # stdout
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


def generate_markdown(research):
    """Convert structured research JSON to readable markdown."""

    md = f"# Research: {research.get('cycle_id', 'unknown')}\n\n"
    md += f"**Generated:** {research.get('generated_at', 'N/A')}\n"
    md += f"**Mode:** {research.get('research_mode', 'N/A')}\n"
    md += f"**Schema:** {research.get('schema_version', 'unknown')}\n\n"

    # ─── Narrative Summary ──────────────────────────────────
    if research.get("narrative_summary"):
        md += "## Summary\n\n"
        md += f"{research['narrative_summary']}\n\n"

    # ─── Research Questions ─────────────────────────────────
    rqs = research.get("research_questions", [])
    if rqs:
        md += "## Research Questions\n\n"
        for rq in rqs:
            conf_bar = "█" * int(rq.get("confidence", 0) * 10) + "░" * (10 - int(rq.get("confidence", 0) * 10))
            md += f"### {rq['id']}: {rq['question']}\n\n"
            md += f"**Answer:** {rq.get('answer', 'N/A')}\n\n"
            md += f"**Confidence:** {rq.get('confidence', 0):.0%} `{conf_bar}`\n\n"
            if rq.get("sources"):
                md += f"**Sources:** {', '.join(rq['sources'])}\n\n"

    # ─── Findings ───────────────────────────────────────────
    findings = research.get("findings", [])
    if findings:
        md += "## Findings\n\n"

        # Group by category
        categories = {}
        for f in findings:
            cat = f.get("category", "other")
            categories.setdefault(cat, []).append(f)

        # Category display order
        cat_order = ["best_practice", "pitfall", "benchmark", "alternative",
                     "code_pattern", "api_reference", "security", "performance",
                     "compatibility", "other"]

        for cat in cat_order:
            if cat not in categories:
                continue

            cat_findings = categories[cat]
            cat_title = cat.replace("_", " ").title()
            md += f"### {cat_title}\n\n"

            for f in cat_findings:
                must_see = " ⚠️ **MUST-SEE**" if f.get("must_see") else ""
                severity = f" [{f.get('severity', '').upper()}]" if f.get("severity") else ""

                md += f"#### {f['id']}: {f.get('finding', '')}{must_see}{severity}\n\n"

                # Properties table
                md += "| Property | Value |\n"
                md += "|----------|-------|\n"
                md += f"| **Confidence** | {f.get('confidence', 0):.0%} |\n"
                md += f"| **Actionable** | {'✅' if f.get('actionable') else '❌'} |\n"
                md += f"| **Category** | {f.get('category', '')} |\n"
                if f.get("subcategory"):
                    md += f"| **Subcategory** | {f.get('subcategory')} |\n"
                if f.get("severity"):
                    md += f"| **Severity** | {f.get('severity')} |\n"
                if f.get("routing_target"):
                    md += f"| **Route to** | {f.get('routing_target')} |\n"
                if f.get("tags"):
                    md += f"| **Tags** | {', '.join(f['tags'])} |\n"
                if f.get("relates_to"):
                    md += f"| **Related** | {', '.join(f['relates_to'])} |\n"
                if f.get("depends_on"):
                    md += f"| **Depends on** | {', '.join(f['depends_on'])} |\n"
                md += "\n"

                # Recommended action
                if f.get("recommended_action"):
                    md += f"**→ Action:** {f['recommended_action']}\n\n"

                # Evidence
                if f.get("evidence"):
                    md += "**Evidence:**\n\n"
                    for ev in f["evidence"]:
                        src = f" ({ev.get('source', '')})" if ev.get("source") else ""
                        md += f"- [{ev['type']}] {ev['desc']}{src}\n"
                    md += "\n"

    # ─── Pitfalls (if separate from findings) ───────────────
    pitfalls = research.get("pitfalls", [])
    if pitfalls:
        md += "## Pitfalls\n\n"
        for p in pitfalls:
            severity = p.get("severity", "medium").upper()
            md += f"### {p['id']}: {p.get('finding', '')} [{severity}]\n\n"
            md += f"- **Confidence:** {p.get('confidence', 0):.0%}\n"
            md += f"- **Category:** {p.get('category', 'general')}\n"
            if p.get("tags"):
                md += f"- **Tags:** {', '.join(p['tags'])}\n"
            md += "\n"

    # ─── Benchmarks ─────────────────────────────────────────
    benchmarks = research.get("benchmarks", [])
    if benchmarks:
        md += "## Benchmarks\n\n"
        md += "| ID | Metric | Option A | Option B | Value A | Value B | Winner |\n"
        md += "|----|--------|----------|----------|---------|---------|--------|\n"
        for b in benchmarks:
            md += f"| {b.get('id', '')} | {b.get('metric', '')} | {b.get('option_a', '')} | {b.get('option_b', '')} | {b.get('value_a', '')} | {b.get('value_b', '')} | {b.get('winner', '')} |\n"
        md += "\n"

    # ─── Alternatives Comparison ────────────────────────────
    alternatives = research.get("alternatives_comparison", [])
    if alternatives:
        md += "## Alternatives Comparison\n\n"
        for a in alternatives:
            md += f"### {a.get('id', '')}: {a.get('criterion', '')}\n\n"
            md += "| Option | Score | Notes |\n"
            md += "|--------|-------|-------|\n"
            for opt in a.get("options", []):
                md += f"| {opt.get('name', '')} | {opt.get('score', '')} | {opt.get('notes', '')} |\n"
            md += f"\n**Winner:** {a.get('winner', 'N/A')}\n\n"
            md += f"**Rationale:** {a.get('rationale', 'N/A')}\n\n"

    # ─── Source Quality Matrix ──────────────────────────────
    sources = research.get("source_quality_matrix", [])
    if sources:
        md += "## Source Quality Matrix\n\n"
        md += "| ID | Type | Title | Quality | Verified |\n"
        md += "|----|------|-------|:-------:|:--------:|\n"
        for s in sources:
            quality = "⭐⭐" if s.get("quality_score") == 2 else "⭐" if s.get("quality_score") == 1 else "—"
            verified = "✅" if s.get("verified") else "❌"
            title = s.get("title", s.get("url", ""))[:60]
            md += f"| {s['id']} | {s.get('type', '')} | {title} | {quality} | {verified} |\n"
        md += "\n"

    # ─── Unstructured Notes ─────────────────────────────────
    if research.get("unstructured_notes"):
        md += "## Notes\n\n"
        md += f"{research['unstructured_notes']}\n\n"

    # ─── Compression Metadata ───────────────────────────────
    meta = research.get("compression_metadata", {})
    if meta:
        md += "## Metadata\n\n"
        md += f"- **Total findings:** {meta.get('total_findings', len(findings))}\n"
        md += f"- **Must-see findings:** {meta.get('must_see_count', sum(1 for f in findings if f.get('must_see')))}\n"
        md += f"- **Average confidence:** {meta.get('avg_confidence', 0):.0%}\n"
        if meta.get("categories_used"):
            md += f"- **Categories used:** {', '.join(meta['categories_used'])}\n"

    return md


def main():
    parser = argparse.ArgumentParser(description="Convert research JSON to markdown")
    parser.add_argument("--input", required=True, help="Path to research JSON")
    parser.add_argument("--output", help="Output markdown path (default: stdout)")
    args = parser.parse_args()

    with open(args.input) as f:
        research = json.load(f)

    markdown = generate_markdown(research)

    if args.output:
        Path(args.output).write_text(markdown)
        print(f"Markdown written to {args.output} ({len(markdown)} chars)")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
