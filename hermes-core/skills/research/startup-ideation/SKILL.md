---
name: startup-ideation
description: "Market research → startup ideation → structured business proposal. Full pipeline from parallel web research to pitch-ready output with market data, product definition, business model, and roadmap."
version: 1.0.0
tags: [startup, market-research, ideation, business-model, pitch]
---

# Startup Ideation

When the user asks to generate or evaluate startup ideas backed by market research,
follow this pipeline end-to-end.

## Pipeline

```
PARALLEL SEARCH → EXTRACT → SYNTHESIZE GAPS → FORMULATE IDEA → STRUCTURE PROPOSAL
```

## Step 1: Parallel Web Search (5-8 queries simultaneously)

Launch multiple `web_search` calls covering different angles:

| Angle | Query template |
|-------|---------------|
| Market size & growth | `"{market}" market size 2025 2026 trends` |
| Key players | `"{market}" startups companies leaders` |
| Constraints & gaps | `"{market}" gaps problems underserved niches` |
| Technology trends | `"{market}" AI technology trends 2025` |
| Government/regulation | `"{market}" government regulation funding` |
| Investment landscape | `"{market}" investment venture capital` |
| International comparison | `"{market}" vs "comparable market" comparison` |
| Expert opinions | `"{market}" expert analysis opinion` |

Use BOTH English and Russian queries for Russian-market research.

**Accept search-result snippets as first-pass data.** Not every result needs full extraction.

## Step 2: Extract Key Articles

Use `web_extract` for the most promising URLs. If `web_extract` fails (DuckDuckGo backend limitation, 403, SSL errors), fall back to:

```bash
curl -sL --max-time 15 -H 'User-Agent: Mozilla/5.0' '<URL>' | python3 -c "
import sys, re
html = sys.stdin.read()
text = re.sub(r'<[^>]+>', ' ', html)
text = re.sub(r'\s+', ' ', text)
print(text[:4000])
"
```

## Step 3: Synthesize Market Gaps

From gathered data, extract:

1. **Market numbers** — size, growth rate, investment volume
2. **Key trends** — what's hot, what's fading
3. **Constraints** — regulation, sanctions, talent, hardware
4. **Gaps** — what's NOT being served
5. **Expert signals** — direct quotes from industry analysts

## Step 4: Formulate the Idea

Criteria for a strong startup idea:

- **Timing window** — why now, not 2 years ago or 2 years from now
- **Market pull** — existing demand, not "create the market"
- **Competitive moat** — what prevents incumbents from copying in 6 months
- **Feasibility** — buildable with available resources/talent
- **Business model** — clear path to revenue, not "monetize later"

## Step 5: Structure the Proposal

Output format:

```
1. Мarket context (numbers, sources)
2. Key trends
3. Pain points / unfilled niches
4. THE IDEA — name, one-liner, 3-layer architecture
5. Why this is powerful (table: factor → justification)
6. Competitive moat
7. Business model (pricing tiers)
8. Why now (timeline)
9. Risks & countermeasures (table)
10. Roadmap (18 months)
```

Requirements:
- **Every claim backed by data** — cite source, not opinion
- **Tables over walls of text** — comparison tables, feature matrices
- **Concrete numbers** — not "big market" but "$6.3B in 2025"
- **Direct quotes** from experts when available
- **Architecture diagrams** as ASCII/box-drawings for product ideas

## Presentation Style

- Language matching the user's (Russian for Russian-speaking users)
- Use unicode box-drawing for architecture (┌─┐│└─┘├┤)
- Use emoji sparingly as section markers
- Bold key numbers and claims
- Prefer compact, scannable sections over long paragraphs

## References

- [`references/russian-ai-market-2026.md`](references/russian-ai-market-2026.md) — Russian AI market data, trends, players, and constraints (June 2026 snapshot)
