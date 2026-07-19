# AI Agent Platform Landscape — Competitive Analysis (July 2026)

Condensed knowledge bank from a deep research session on custom AI agents vs
ready-made platforms. Includes market data, company financials, pricing models,
and build-vs-buy TCO. **Data has a half-life of ~6 months** — verify before citing.

## Research Methodology — Source Mapping

| Data needed | Best sources | Query pattern |
|-------------|-------------|---------------|
| Market size & CAGR | Precedence Research, Grand View Research, Roots Analysis | `"{domain}" market size 2025 2026 forecast billion CAGR` |
| Company funding/valuation | Tracxn, Crunchbase, PitchBook, Pulse2 | `"{company}" funding valuation 2024 2025` |
| GitHub stars/users | GitHub repo, releasealert.dev, awesome agents blogs | `"{project}" GitHub stars users 2025 2026` |
| Analyst reports (failure/forecast) | Gartner press releases, McKinsey State of AI, HBR | `Gartner AI agent prediction {year}` / `McKinsey AI survey {year}` |
| Pricing (per seat/consumption) | Vendor pricing pages, SaaStr, costbench | `"{platform}" pricing per seat cost 2025 2026` |
| Build-vs-buy TCO | DextraLabs, AISera, ServicesGround, Contus | `"build vs buy" AI agent cost TCO 2025 2026` |

Key insight: **web_extract fails** (DuckDuckGo backend). Accept search snippets as
first-pass data — they carry enough signal (funding amounts, valuations, star counts)
for a competitive overview. Only curl-extract for deep dives on specific companies.

## Market Size (consensus range)

| Source | 2025 | Forecast | CAGR |
|--------|------|----------|------|
| Precedence (Agentic AI) | $7.55B | $199B by 2034 | 43.8% |
| Precedence (AI Agents) | $7.92B | $295B by 2035 | 43.6% |
| Grand View Research | $7.7B | — | 39.5% |
| Roots Analysis | $15B | $221B by 2035 | — |

## Company Financials Snapshot

| Company | Funding | Valuation | Stars/Users | Model |
|---------|---------|-----------|-------------|-------|
| Cognition (Devin) | $400M+ | $10.2B | — | SaaS |
| Cursor (Anysphere) | ~$2.3B+ | $29-60B | millions | SaaS |
| LangChain | $135M | $1.1B | — | OSS+Cloud |
| Nous Research (Hermes) | $70M | $1B | 43.7K stars/2mo | OSS |
| CrewAI | $12-18M | — | 63% F500 | OSS+Cloud |
| OpenCode (SST) | — | — | 182K stars, 8M MAU | OSS |
| OpenWebUI | $0 (bootstrap) | — | 140K stars | OSS |
| AutoGPT | — | — | 183K stars | OSS |

## Cursor ARR Trajectory (commercial benchmark)

$100M (Jan 2025) → $500M (Jun 2025) → $1B (Nov 2025) → $2B (Feb 2026) → ~$4B (Jun 2026)

## Build vs Buy — 3-Year TCO

| | BUILD | BUY |
|---|-------|-----|
| Upfront | $50K-$500K | $0-$50K |
| Monthly | $2K-$15K | $500-$10K |
| 3yr TCO | $200K-$1M+ | $300K-$2M+ |
| Time-to-value | 6-18 months | 2-8 weeks |

## Pricing Models (per platform)

| Model | Examples | Cost |
|-------|----------|------|
| Per-seat | MS Copilot ($30), GitHub ($10-39), Cursor ($20-40), Perplexity ($271) | $10-$271/mo/seat |
| Per-consumption | Salesforce ($2/convo, $0.10/action), OpenAI API | usage-based |
| Self-hosted free | OpenWebUI, Hermes, OpenCode | $0 + infra |

## Analyst Verdicts

- **Gartner (Jun 2025):** 40%+ agentic AI projects canceled by end 2027 (cost, unclear ROI, weak risk controls)
- **McKinsey (Nov 2025):** 88% adoption, only 23% scaled enterprise-wide, only 5.5% report >5% EBIT impact
- **HBR (Oct 2025):** "The market will not reward those who pursue agentic AI for its own sake"

## Open-Core Dominance Pattern

Most modern agent platforms use open-core: free OSS core + paid cloud/enterprise tier.
LangChain (MIT + LangSmith SaaS), CrewAI (MIT + Enterprise Cloud), OpenWebUI (BSD-3 +
Enterprise License), OpenCode (OSS + Zen cloud). This is the winning go-to-market for
agent infrastructure — not pure SaaS, not pure OSS.

## Presentation Structure (for similar tasks)

1. Market size + CAGR (2-3 sources for triangulation)
2. Platform landscape categorization (6 categories table)
3. Key players financial table (funding, valuation, stars, users)
4. Open-source champions deep-dive (per platform)
5. Build: frameworks + cost breakdown
6. Buy: pricing comparison
7. TCO comparison (build vs buy)
8. Decision matrix (when to build, when to buy)
9. Analyst reality check (Gartner/McKinsey statistics)
10. Conclusions + recommendations

Output in Russian with dense comparison tables — user preference.
