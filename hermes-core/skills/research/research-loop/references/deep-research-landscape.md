# Deep Research Landscape — OpenAI vs Google vs Perplexity

> Compiled: 2026-06-23 from multiple sources (PromptLayer, Google AI, Perplexity Research, Waylandz AI Agent Book)

## Comparison Table (Concrete Numbers)

| Parameter | OpenAI Deep Research | Google Gemini Deep Research Max | Perplexity Deep Research |
|----------|---------------------|--------------------------------|-------------------------|
| **Launch date** | Feb 2, 2025 | Dec 2024 (Max: Apr 2026) | Feb 14, 2025 |
| **Base model** | o3 (specialized version) | Gemini 3.1 Pro | Undisclosed (multi-model) |
| **Architecture** | Single-agent + strong RL reasoning | Multi-phase pipeline + collaborative planning | RAG-pipeline + iterative search |
| **Max duration** | 20–30 min | Background (hours) | 1–5 min |
| **Max search queries** | 30–60 | Up to 160 | ~30–50 (estimate) |
| **Max pages fetched** | 120–150 | Not explicitly limited | 100+ sources |
| **Max reasoning iterations** | 150–200 | Extended test-time compute | Pipeline (no ReAct loop) |
| **Code execution** | Python (5–10 calls) | Yes (Code Execution tool) | No (text only) |
| **Input formats** | Text, PDF, images | Text, PDF, CSV, audio, video, images | Text, PDF |
| **Visualizations** | Generated via Python | Native charts + infographics | None |
| **Data integration** | Internet only | MCP + Google Workspace + files | Internet only |
| **Plan before execution** | Implicit (internal CoT) | Explicit (user edits plan) | None |
| **Progress streaming** | No (final report only) | Yes (live thought summaries) | No (but shows steps) |
| **Price** | $200/mo (100 queries) | API: pay-per-use | Free (Pro: $20/mo) |
| **Speed** | 10–30 min | Fast: ~1 min / Max: 5–30 min | 1–3 min |

## Architectural Spectrum

```
DEPTH OF REASONING (deeper →)
  OpenAI (o3 + end-to-end RL trained research behaviour)
  Google Max (extended test-time compute)
  Google (base, collaborative planning)
  Perplexity (RAG-pipeline, minimal reasoning)

SPEED (faster →)
  Perplexity (1–3 min)
  Google base (1–5 min)
  Google Max (5–30 min)
  OpenAI (10–30 min)
```

## OpenAI Deep Research — Architecture Details

**Philosophy:** Single agent + strong reasoning. RL-trained, not programmed.

**5 phases:**
1. Clarify — ask follow-up questions to user
2. Plan — decompose query into sub-questions, build strategy
3. Search — iterative search with progressive query refinement
4. Analyze — read pages, PDFs, images, execute Python
5. Synthesize — structured report with inline citations

**Key mechanism:** End-to-end reinforcement learning — model trained in simulated research environments with tool access. Learned planning, backtracking, and strategy pivoting autonomously.

**2-tier stopping mechanism:**
- **Coverage-based:** 2+ independent sources per sub-question, novelty exhausted, contradictions resolved
- **Budget-driven:** 20-30 min wall-clock, 30-60 searches, 120-150 pages, 150-200 iterations, 5-10 Python calls

**Real results:**
- 15,000-word building code checklist from 21 sources (6-8 human hours saved)
- 8,000-word legal memo at junior attorney quality (15-20 hours saved)

## Google Gemini Deep Research — Architecture Details

**Philosophy:** Collaborative planning + enterprise data integration via MCP.

**Two tiers (Apr 2026):**
- **Deep Research:** speed + interactivity, streamed to client UI
- **Deep Research Max:** maximum comprehensiveness, background/async, extended test-time compute

**4 phases:**
1. Plan — agent proposes research plan → user reviews and edits
2. Search — autonomous search across web + Google Workspace + MCP sources
3. Reason — multi-step reasoning, cross-referencing, conflict resolution
4. Report — structured report + native charts + audio summary

**Key differentiators:**
- **MCP support:** Connect to FactSet, S&P Global, PitchBook, custom data
- **Can disable web** and search only private data
- **Collaborative planning:** user edits plan before execution
- **Native visualizations:** HTML/Nano Banana charts inline
- **Multi-modal input:** PDF, CSV, audio, video, images
- **Background execution:** `background=true`, poll for results
- **Up to 160 web searches** (Deep Research Max)
- **Audio summaries** (NotebookLM-style)
- **Interactive dashboards** and quizzes

**Powers:** Gemini App, NotebookLM, Google Search, Google Finance

## Perplexity Deep Research — Architecture Details

**Philosophy:** Answer engine, not research engine. Citation-first UX, speed optimized.

**Architecture:** RAG-pipeline with iterative search
1. Search across multiple sources
2. Rank relevance
3. Synthesize with citations
4. If complex topic — additional search round

**Key differentiators:**
- **Free** Deep Research available
- **500M+ queries/month** (Q1 2026)
- **100+ sources** per query
- **1-3 minute** speed (fastest)
- **DRACO Benchmark:** 100 curated tasks across 10 domains (Academic, Finance, Law, Medicine, Technology, General Knowledge, UX Design, Personalized Assistant, Shopping, Needle in a Haystack)
- **Valuation:** $14B+ (mid-2025)

## When to Use Which

| Scenario | Best choice | Why |
|----------|------------|-----|
| Academic research | OpenAI | Deepest reasoning, PDF analysis, Python for statistics |
| Business analytics (with corp data) | Google Max | MCP + Workspace + charts + background mode |
| Fast fact-checking with citations | Perplexity | Speed 1-3 min, citation-first UX |
| Due diligence / compliance | Google Max | Many sources, MCP to financial data, background |
| Long-form report writing | OpenAI | 15,000+ words, structured, professional |
| Collaborative research | Google | Collaborative planning: stakeholder edits plan |
| Free deep research | Perplexity | Only one with free tier |
| Custom data (not web) | Google | Only one with MCP + Workspace + file upload |

## Primary Sources

1. PromptLayer, "How OpenAI's Deep Research Works" (Oct 2025) — https://blog.promptlayer.com/how-deep-research-works/
2. Google AI, "Deep Research Max: a step change for autonomous research agents" (Apr 2026) — https://blog.google/
3. Google AI, "Gemini Deep Research Agent API docs" (2026) — https://ai.google.dev/gemini-api/docs/interactions/deep-research
4. Perplexity Research, "DRACO Benchmark" (Feb 2026) — https://research.perplexity.ai/articles/evaluating-deep-research-performance-in-the-wild-with-the-draco-benchmark
5. Waylandz, "AI Agent Architecture — Chapter 27: Deep Research" (2026) — https://waylandz.com/ai-agent-book-en/chapter-27-deep-research/
6. OpenAI, "Introducing deep research" (Feb 2025) — https://openai.com/index/introducing-deep-research/
