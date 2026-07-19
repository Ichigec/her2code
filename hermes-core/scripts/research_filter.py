#!/usr/bin/env python3
"""
research_filter.py — EXIT-style relevance filtering for Tech Lead.

Reads research JSON + StandardWork keywords → outputs filtered findings for SW.

Usage:
    python3 research_filter.py --research docs/research/<slug>.json --sw-keywords "parser,recursive-descent,ParsedDocument,ParseError" --output /tmp/sw3_findings.json

ACON feedback: reads ~/.hermes/plans/<cycle>-filter-rules.json for evolved rules.
"""

import argparse
import json
import sys
from pathlib import Path

# ─── Filtering Rules (ACON-evolvable) ───────────────────────────

DEFAULT_RULES = {
    "must_see_always_include": True,
    "tag_match_threshold": 1,           # min tag matches to include
    "high_confidence_threshold": 0.85,  # auto-include actionable above this
    "dependency_include": True,         # include findings whose parents are included
    "preserve_categories": ["security", "pitfall"],  # always include these
    "max_findings_per_sw": 15,          # hard cap to prevent context bloat
    "sort_by": "confidence_desc"        # confidence_desc | relevance_desc
}


def load_rules(cycle_id):
    """Load ACON-evolved rules, fall back to defaults."""
    rules_path = Path.home() / ".hermes" / "plans" / f"{cycle_id}-filter-rules.json"
    if rules_path.exists():
        with open(rules_path) as f:
            rules = json.load(f)
            # Merge with defaults (rules override)
            return {**DEFAULT_RULES, **rules}
    return DEFAULT_RULES.copy()


def save_rules(cycle_id, rules):
    """Save updated rules (ACON feedback)."""
    rules_path = Path.home() / ".hermes" / "plans" / f"{cycle_id}-filter-rules.json"
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rules_path, 'w') as f:
        json.dump(rules, f, indent=2)


def extract_keywords(sw_contract_path):
    """Extract keywords from StandardWork JSON or markdown."""
    path = Path(sw_contract_path)
    if not path.exists():
        return []

    text = path.read_text()

    # Try JSON first
    try:
        contract = json.loads(text)
        keywords = set()
        # From files
        for f in contract.get("files", []):
            keywords.add(Path(f).stem)  # "parser" from "plugins/foo/parser.py"
        # From title
        if "title" in contract:
            keywords.update(contract["title"].lower().split())
        # From acceptance criteria
        for ac in contract.get("acceptance_criteria", []):
            if isinstance(ac, dict):
                keywords.update(ac.get("criterion", "").lower().split())
        # From tags if present
        keywords.update(contract.get("tags", []))
        return [k for k in keywords if len(k) > 2]
    except json.JSONDecodeError:
        # Markdown: extract from headers and code references
        keywords = set()
        for line in text.split('\n'):
            if line.startswith('#'):
                keywords.update(line.lower().replace('#', '').split())
            if '`' in line:
                # Extract code references
                import re
                refs = re.findall(r'`(\w+)`', line)
                keywords.update(refs)
        return [k for k in keywords if len(k) > 2]


def compute_relevance(finding, sw_keywords):
    """EXIT-style: compute relevance score between finding and SW keywords."""
    finding_tags = set(t.lower() for t in finding.get("tags", []))
    sw_kw_set = set(k.lower() for k in sw_keywords)

    # Direct tag matches
    direct_matches = finding_tags & sw_kw_set

    # Partial matches (substring)
    partial_matches = set()
    for tag in finding_tags:
        for kw in sw_kw_set:
            if tag in kw or kw in tag:
                partial_matches.add(tag)

    # Finding text keyword matches
    finding_text = finding.get("finding", "").lower()
    text_matches = sum(1 for kw in sw_kw_set if kw in finding_text)

    # Relevance score: weighted combination
    score = len(direct_matches) * 1.0 + len(partial_matches) * 0.5 + text_matches * 0.3
    return score


def filter_findings(research, sw_keywords, rules):
    """
    Main filtering function.
    
    Rules (in priority order):
    1. must_see → ALWAYS include (hard constraint)
    2. preserve_categories → always include (security, pitfall)
    3. tag/relevance match → include if above threshold
    4. dependency → include if parent finding is included
    5. high confidence + actionable → include (broad relevance)
    """
    all_findings = research.get("findings", [])
    pitfalls = research.get("pitfalls", [])

    # Merge pitfalls into findings for unified filtering
    for p in pitfalls:
        p["category"] = "pitfall"
        p.setdefault("must_see", True)
        p.setdefault("actionable", True)
        all_findings.append(p)

    included = []
    included_ids = set()
    remaining = list(all_findings)

    # Pass 1: must_see (hard constraint)
    if rules["must_see_always_include"]:
        for f in remaining[:]:
            if f.get("must_see", False):
                included.append(f)
                included_ids.add(f["id"])
                remaining.remove(f)

    # Pass 2: preserve_categories
    for f in remaining[:]:
        if f.get("category") in rules["preserve_categories"]:
            included.append(f)
            included_ids.add(f["id"])
            remaining.remove(f)

    # Pass 3: tag/relevance match
    scored = []
    for f in remaining:
        score = compute_relevance(f, sw_keywords)
        if score >= rules["tag_match_threshold"]:
            scored.append((score, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    for score, f in scored:
        if f["id"] not in included_ids:
            f["_relevance_score"] = round(score, 2)
            included.append(f)
            included_ids.add(f["id"])

    # Pass 4: dependency inclusion
    if rules["dependency_include"]:
        changed = True
        while changed:
            changed = False
            for f in list(remaining):
                if f["id"] in included_ids:
                    continue
                deps = f.get("depends_on", [])
                if any(dep in included_ids for dep in deps):
                    included.append(f)
                    included_ids.add(f["id"])
                    remaining.remove(f) if f in remaining else None
                    changed = True

    # Pass 5: high confidence + actionable + MINIMAL relevance
    # (not just high confidence — must have SOME connection to SW)
    min_relevance = rules.get("min_relevance_for_confidence_pass", 0.3)
    for f in remaining:
        if f["id"] in included_ids:
            continue
        if (f.get("confidence", 0) >= rules["high_confidence_threshold"]
                and f.get("actionable", False)):
            score = compute_relevance(f, sw_keywords)
            if score >= min_relevance:
                f["_relevance_score"] = round(score, 2)
                included.append(f)
                included_ids.add(f["id"])

    # Sort
    if rules["sort_by"] == "confidence_desc":
        included.sort(key=lambda f: f.get("confidence", 0), reverse=True)
    elif rules["sort_by"] == "relevance_desc":
        included.sort(key=lambda f: f.get("_relevance_score", 0), reverse=True)

    # Hard cap
    if len(included) > rules["max_findings_per_sw"]:
        # Always keep must_see, then top by score
        must_see = [f for f in included if f.get("must_see")]
        others = [f for f in included if not f.get("must_see")]
        included = must_see + others[:rules["max_findings_per_sw"] - len(must_see)]

    return included


def update_rules_from_feedback(cycle_id, sw_result, filtered_ids, research):
    """
    ACON: if developer failed and needed findings that were filtered out,
    update rules to be less aggressive.
    """
    rules = load_rules(cycle_id)

    if sw_result.get("verdict") == "FAIL":
        requested = sw_result.get("developer_requested_findings", [])
        for fid in requested:
            if fid not in filtered_ids:
                # Finding was filtered out but developer needed it
                finding = next((f for f in research["findings"] if f["id"] == fid), None)
                if finding:
                    # Lower threshold or add tag to keywords
                    tags = finding.get("tags", [])
                    if tags:
                        rules.setdefault("forced_keywords", [])
                        rules["forced_keywords"].extend(tags)
                        # Deduplicate
                        rules["forced_keywords"] = list(set(rules["forced_keywords"]))

                    # If confidence was high, lower threshold
                    if finding.get("confidence", 0) > 0.7:
                        rules["high_confidence_threshold"] = max(0.7,
                            rules["high_confidence_threshold"] - 0.05)

    save_rules(cycle_id, rules)
    return rules


def main():
    parser = argparse.ArgumentParser(description="Filter research findings for StandardWork")
    parser.add_argument("--research", required=True, help="Path to research JSON")
    parser.add_argument("--sw-keywords", required=True, help="Comma-separated keywords for SW")
    parser.add_argument("--sw-contract", help="Path to StandardWork JSON (alternative to --sw-keywords)")
    parser.add_argument("--cycle-id", default="default", help="Cycle ID for ACON rules")
    parser.add_argument("--output", help="Output path (default: stdout)")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")

    args = parser.parse_args()

    # Load research
    with open(args.research) as f:
        research = json.load(f)

    # Get keywords
    if args.sw_contract:
        keywords = extract_keywords(args.sw_contract)
    else:
        keywords = [k.strip() for k in args.sw_keywords.split(",")]

    # Load rules
    rules = load_rules(args.cycle_id)

    # Filter
    filtered = filter_findings(research, keywords, rules)

    # Output
    result = {
        "sw_keywords": keywords,
        "total_findings_in_research": len(research.get("findings", [])),
        "findings_after_filter": len(filtered),
        "filter_rules_used": {k: v for k, v in rules.items() if k != "forced_keywords"},
        "findings": filtered
    }

    if args.format == "markdown":
        print(format_as_markdown(result))
    else:
        output = json.dumps(result, indent=2, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(output)
            print(f"Filtered findings written to {args.output}")
            print(f"  {len(filtered)} findings (from {len(research.get('findings', []))} total)")
        else:
            print(output)


def format_as_markdown(result):
    """Format filtered findings as markdown for human reading."""
    md = f"# Filtered Research Findings\n\n"
    md += f"**Keywords:** {', '.join(result['sw_keywords'])}\n"
    md += f"**Findings:** {result['findings_after_filter']} / {result['total_findings_in_research']}\n\n"
    for f in result["findings"]:
        must_see = " ⚠️ MUST-SEE" if f.get("must_see") else ""
        md += f"## {f['id']}: {f.get('finding', '')}{must_see}\n"
        md += f"- **Category:** {f.get('category', 'unknown')}\n"
        md += f"- **Confidence:** {f.get('confidence', 0)}\n"
        if f.get("recommended_action"):
            md += f"- **Action:** {f['recommended_action']}\n"
        if f.get("tags"):
            md += f"- **Tags:** {', '.join(f['tags'])}\n"
        if f.get("evidence"):
            for ev in f["evidence"]:
                md += f"- **Evidence ({ev['type']}):** {ev['desc']}\n"
        md += "\n"
    return md


if __name__ == "__main__":
    main()
