#!/usr/bin/env python3
"""
Paper Collector — Automated discovery and scoring of scientific papers.

Fetches new papers from arXiv, enriches with Semantic Scholar + OpenAlex,
scores by composite quality metric, and queues top-K for deep reading.

Usage:
    python3 paper-collector.py [--days 1] [--top 20] [--dry-run]
    python3 paper-collector.py --categories cs.AI,cs.CL,cs.LG,cs.MA

Requires:
    - Internet access (arXiv, Semantic Scholar, OpenAlex APIs are free)
    - Hermes env (HOME, HERMES_HOME for path resolution)
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

# ── Path resolution (same robust logic as knowledge-curator-ingest-llm.py) ──


def _resolve_real_home() -> Path:
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        p = Path(hermes_home)
        return p.parent if p.name == ".hermes" else p
    try:
        expanded = Path(os.path.expanduser("~"))
        if (expanded / "dev" / "codemes").exists():
            return expanded
    except Exception:
        pass
    user = os.environ.get("USER", "pavel")
    candidate = Path(f"/home/{user}")
    return candidate if candidate.exists() else Path("/home/user")


_REAL_HOME = _resolve_real_home()
QUEUE_DIR = _REAL_HOME / ".hermes" / "paper_queue"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

# ── API endpoints ──

ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1"
OPENALEX = "https://api.openalex.org"

# ── Configuration ──

DEFAULT_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.MA"]
DEFAULT_TOP_K = 20
ARXIV_DELAY = 3.0  # seconds between API calls (politeness)
SEMANTIC_SCHOLAR_DELAY = 1.0
OPENALEX_DELAY = 0.5

# Composite score weights
WEIGHTS = {
    "citations": 0.25,   # log10(citations + 1)
    "venue": 0.20,       # venue tier (NeurIPS=1.0, arXiv-only=0.2)
    "author_h": 0.15,    # max/mean author h-index
    "recency": 0.25,     # exponential decay by days old
    "relevance": 0.15,   # LLM-based relevance (placeholder for Qwen)
}

# Venue tier mapping
VENUE_TIERS = {
    # Tier 1 (1.0): top ML/AI conferences
    "neurips": 1.0, "icml": 1.0, "iclr": 1.0,
    # Tier 2 (0.85): strong conferences
    "acl": 0.85, "emnlp": 0.85, "naacl": 0.85,
    "cvpr": 0.85, "iccv": 0.85, "eccv": 0.85,
    "aaai": 0.85, "ijcai": 0.85,
    "www": 0.85, "sigir": 0.85, "wsdm": 0.85, "kdd": 0.85,
    "sosp": 0.85, "osdi": 0.85, "nsdi": 0.85,
    # Tier 3 (0.70): solid conferences/workshops
    "coling": 0.70, "eacl": 0.70, "conll": 0.70,
    "recsys": 0.70, "cikm": 0.70,
    "icra": 0.70, "iros": 0.70,
    # Tier 4 (0.40): workshops
    "workshop": 0.40,
    # Default (0.20): arXiv-only / unknown
}


def parse_arxiv_xml(xml_text: str) -> list[dict]:
    """Parse arXiv Atom XML response into paper dicts."""
    import xml.etree.ElementTree as ET

    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(xml_text)
    papers = []

    for entry in root.findall("a:entry", ns):
        title_el = entry.find("a:title", ns)
        title = title_el.text.strip().replace("\n", " ") if title_el is not None else ""

        id_el = entry.find("a:id", ns)
        arxiv_id = ""
        if id_el is not None:
            arxiv_id = id_el.text.strip().split("/abs/")[-1]
            # Strip version suffix for canonical ID
            if "v" in arxiv_id:
                arxiv_id = arxiv_id.rsplit("v", 1)[0]

        published_el = entry.find("a:published", ns)
        published = published_el.text[:10] if published_el is not None else ""

        summary_el = entry.find("a:summary", ns)
        abstract = summary_el.text.strip()[:2000] if summary_el is not None else ""

        authors = []
        for author_el in entry.findall("a:author", ns):
            name_el = author_el.find("a:name", ns)
            if name_el is not None:
                authors.append(name_el.text.strip())

        categories = []
        for cat_el in entry.findall("a:category", ns):
            term = cat_el.get("term", "")
            if term:
                categories.append(term)

        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "published": published,
            "abstract": abstract[:500],
            "categories": categories,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "abs_url": f"https://arxiv.org/abs/{arxiv_id}",
        })

    return papers


def fetch_arxiv_papers(
    categories: list[str],
    days_back: int = 1,
    max_results: int = 200,
) -> list[dict]:
    """Fetch recent papers from arXiv for given categories."""
    all_papers: list[dict] = []

    for cat in categories:
        query = f"cat:{cat}"
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": min(max_results, 100),
        }
        url = f"{ARXIV_API}?{'&'.join(f'{k}={quote(str(v))}' for k, v in params.items())}"

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            papers = parse_arxiv_xml(resp.text)
            all_papers.extend(papers)
            print(f"  arXiv {cat}: {len(papers)} papers")
        except Exception as exc:
            print(f"  arXiv {cat}: ERROR — {exc}", file=sys.stderr)

        time.sleep(ARXIV_DELAY)

    # Deduplicate by arxiv_id
    seen: set[str] = set()
    unique = []
    for p in all_papers:
        if p["arxiv_id"] not in seen:
            seen.add(p["arxiv_id"])
            unique.append(p)

    return unique


def fetch_semantic_scholar(arxiv_id: str) -> dict | None:
    """Fetch citation count and author metadata from Semantic Scholar."""
    try:
        resp = requests.get(
            f"{SEMANTIC_SCHOLAR}/paper/arXiv:{arxiv_id}",
            params={
                "fields": "citationCount,influentialCitationCount,authors,"
                          "year,venue,publicationVenue,title"
            },
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_openalex(arxiv_id: str) -> dict | None:
    """Fetch venue info and citation counts from OpenAlex."""
    try:
        # OpenAlex indexes by DOI or by title search
        resp = requests.get(
            f"{OPENALEX}/works",
            params={"filter": f"primary_location.source_id:null", "search": arxiv_id, "per_page": 1},
            timeout=15,
        )
        # Fallback: try by arXiv ID directly
        if resp.status_code != 200 or not resp.json().get("results"):
            resp = requests.get(
                f"{OPENALEX}/works/arxiv:{arxiv_id}",
                timeout=15,
            )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "id" in data:
            return data
        return None
    except Exception:
        return None


def venue_tier(venue_name: str | None) -> float:
    """Determine venue tier from name."""
    if not venue_name:
        return 0.20  # arXiv-only
    name_lower = venue_name.lower()
    for key, tier in VENUE_TIERS.items():
        if key in name_lower:
            return tier
    return 0.20


def compute_composite_score(paper: dict, now: datetime | None = None) -> float:
    """
    Compute composite quality score.
    
    score = w1·log10(cit+1) + w2·venue_tier + w3·h_score + w4·recency_decay + w5·relevance
    """
    now = now or datetime.now(timezone.utc)
    score = 0.0

    # 1. Citation impact
    citations = paper.get("citations", 0)
    import math
    cit_score = math.log10(citations + 1) / math.log10(1001)  # normalize to [0,1]
    score += WEIGHTS["citations"] * cit_score

    # 2. Venue tier
    venue_score = venue_tier(paper.get("venue"))
    score += WEIGHTS["venue"] * venue_score

    # 3. Author h-index (normalized: h/100)
    h_index = paper.get("max_h_index", 0)
    h_score = min(h_index / 100.0, 1.0) if h_index else 0.2  # unknown = 0.2
    score += WEIGHTS["author_h"] * h_score

    # 4. Recency (exponential decay: e^(-λ·days), λ=0.05 → half-life ~14 days)
    published_str = paper.get("published", "")
    try:
        pub_date = datetime.fromisoformat(published_str).replace(tzinfo=timezone.utc)
        days_old = (now - pub_date).days
        recency_score = 2.71828 ** (-0.05 * max(days_old, 0))
    except (ValueError, TypeError):
        recency_score = 0.5  # unknown = neutral
    score += WEIGHTS["recency"] * recency_score

    # 5. LLM relevance (placeholder — will be replaced by Qwen scoring)
    relevance = paper.get("llm_relevance", 0.5)
    score += WEIGHTS["relevance"] * relevance

    return round(score, 4)


def enrich_papers(papers: list[dict]) -> list[dict]:
    """Enrich papers with Semantic Scholar and OpenAlex metadata."""
    enriched = []
    for i, paper in enumerate(papers):
        arxiv_id = paper["arxiv_id"]
        print(f"  [{i+1}/{len(papers)}] {arxiv_id} ...", end=" ")

        # Semantic Scholar
        ss_data = fetch_semantic_scholar(arxiv_id)
        if ss_data:
            paper["citations"] = ss_data.get("citationCount", 0)
            paper["influential_citations"] = ss_data.get("influentialCitationCount", 0)
            paper["venue"] = (
                ss_data.get("publicationVenue") or {}
            ).get("name") or ss_data.get("venue", "")

            # Extract max h-index from authors
            author_hs = []
            for author in ss_data.get("authors", []):
                h = author.get("hIndex") or 0
                author_hs.append(h)
            paper["max_h_index"] = max(author_hs) if author_hs else 0
            paper["mean_h_index"] = sum(author_hs) / len(author_hs) if author_hs else 0
            paper["author_count"] = len(author_hs)

            print(f"cit={paper['citations']}, venue={paper.get('venue','?')}, "
                  f"max_h={paper['max_h_index']}")
        else:
            paper["citations"] = 0
            paper["venue"] = None
            paper["max_h_index"] = 0
            print("no Semantic Scholar data")

        enriched.append(paper)
        time.sleep(SEMANTIC_SCHOLAR_DELAY)

    return enriched


def score_and_rank(papers: list[dict], top_k: int = 20) -> list[dict]:
    """Score papers and return top-K."""
    for paper in papers:
        paper["composite_score"] = compute_composite_score(paper)

    papers.sort(key=lambda p: p["composite_score"], reverse=True)
    return papers[:top_k]


def save_queue(papers: list[dict], date_str: str) -> Path:
    """Save paper queue to disk."""
    date_dir = QUEUE_DIR / date_str
    date_dir.mkdir(parents=True, exist_ok=True)

    queue_file = date_dir / "papers.json"
    with open(queue_file, "w") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False, default=str)

    # Also save a human-readable summary
    summary_file = date_dir / "summary.md"
    with open(summary_file, "w") as f:
        f.write(f"# Paper Queue — {date_str}\n\n")
        f.write(f"Total collected: {len(papers)}\n\n")
        f.write("| # | Score | Citations | Title |\n")
        f.write("|---|-------|-----------|-------|\n")
        for i, p in enumerate(papers, 1):
            title = p["title"][:80]
            score = p["composite_score"]
            cit = p.get("citations", 0)
            f.write(f"| {i} | {score:.4f} | {cit} | [{title}]({p['abs_url']}) |\n")

    return queue_file


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    days_back = 1
    top_k = DEFAULT_TOP_K

    # Parse --days
    for arg in sys.argv:
        if arg.startswith("--days="):
            days_back = int(arg.split("=")[1])
        elif arg.startswith("--top="):
            top_k = int(arg.split("=")[1])

    categories = DEFAULT_CATEGORIES
    for arg in sys.argv:
        if arg.startswith("--categories="):
            categories = arg.split("=")[1].split(",")

    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"=== Paper Collector === {date_str} (last {days_back}d, top {top_k})")
    print(f"Categories: {categories}")

    # Step 1: Fetch from arXiv
    print("\n── Step 1: arXiv fetch ──")
    papers = fetch_arxiv_papers(categories, days_back=days_back)
    print(f"Total unique: {len(papers)}")

    if dry_run:
        print("[dry-run] Would enrich and score these papers:")
        for p in papers[:10]:
            print(f"  {p['arxiv_id']}: {p['title'][:80]}")
        print(f"  ... and {len(papers) - 10} more")
        return

    # Step 2: Enrich with Semantic Scholar
    print(f"\n── Step 2: Semantic Scholar enrichment ──")
    papers = enrich_papers(papers)

    # Step 3: Score and rank
    print(f"\n── Step 3: Scoring ──")
    ranked = score_and_rank(papers, top_k=top_k)

    print(f"\nTop {top_k} papers:")
    for i, p in enumerate(ranked, 1):
        print(f"  {i:2d}. [{p['composite_score']:.4f}] {p['title'][:70]}...")

    # Step 4: Save queue
    print(f"\n── Step 4: Save ──")
    queue_file = save_queue(ranked, date_str)
    print(f"Queue saved: {queue_file}")

    print(f"\n── Done ──")
    print(f"Collected: {len(papers)}, Ranked: {len(ranked)}, "
          f"Top score: {ranked[0]['composite_score'] if ranked else 'N/A'}")


if __name__ == "__main__":
    main()
