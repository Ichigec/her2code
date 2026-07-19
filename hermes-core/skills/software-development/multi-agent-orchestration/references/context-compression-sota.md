# Context Compression SOTA — Mechanisms & Implementation (2026-07-03)

> Research session: deep investigation into compression mechanisms proposed by
> scientific community and frontier companies. 8 categories identified, 13 papers/tools
> analyzed, 4-level compression stack designed for our pipeline.

## Unified Taxonomy (Survey, May 2026)

Source: "Context Compression for LLM Agents: A Survey of Methods, Failure Modes, and
Evaluation" (preprints.org, May 2026) — CASIA, SJTU, UCSD, HFUT joint.

Three dimensions:
- **Compression Target**: what is compressed (env observations, interaction history,
  tool outputs, system prompts, retrieved documents)
- **Compression Mechanism**: how it's transformed (extractive, abstractive, hybrid,
  structured)
- **Control Policy**: who decides when (threshold-based, adaptive, learned, external)

Key claim: "Agent core bottleneck shifting from 'can the model think' to 'can context
be reliably managed'."

## 8 Categories of Compression

### 1. EXTRACTIVE — "leave only what's needed"

**LLMLingua / LongLLMLingua** (Microsoft, EMNLP'23, ACL'24)
- Coarse-to-fine: Budget Controller → Iterative Token-level Compression → Alignment
- Small LM (GPT-2/LLaMA-7B) computes PPL per token; low-PPL tokens = predictable = drop
- 2-10x compression, <2% accuracy drop on QA
- LLMLingua-2 adds document-level + question-aware compression

**EXIT** (ACL 2025 Findings, arXiv:2412.12559)
- Sentence-level binary classification: relevant to query? YES/NO
- Context-aware (not just statistical like LLMLingua)
- Outperforms LLMLingua on QA at same compression ratio
- **Application**: filter research artifact sentences by relevance to specific SW

### 2. ABSTRACTIVE — "retell shorter"

**Anchored Iterative Summarization** (Factory.ai, Dec 2025)
- THE most relevant method for our pipeline
- Maintains persistent "session state" document with structured sections:
  Session Intent, Decisions Made, Files Modified, Pending Work, Errors Resolved
- **INCREMENTAL MERGE, not regenerate**: new info merged into existing anchor
- Factory.ai evaluation: 95%+ critical info preserved at 50+ steps vs 60-70% naive
- **Application**: `.hermes/plans/<ts>-<slug>-session-state.md`, updated after each SW

**Claude Compaction API** (Anthropic, Jan 2026 → Opus 4.6 Mar 2026)
- Server-side auto-compaction at configurable token threshold
- `pause_after_compaction` — client can insert preserved messages
- **Not directly applicable**: we use multiple providers (Kimi, DeepSeek, local)
- Pattern: application-level compaction needed for multi-provider

### 3. STRUCTURED — "transform to structured format"

**ContextEvolve** (arXiv:2602.02597, Feb 2026)
- Decomposes context into 3 orthogonal dimensions, each compressed by separate agent:
  - Summarizer: code → natural language abstraction
  - Navigator: distill direction from past trajectories
  - Sampler: curate informative exemplars
- Result: 33% better performance, 29% fewer tokens
- **Application**: Research → Summarizer (findings), Navigator (what worked/didn't),
  Sampler (best examples)

**Structured Output Contracts** (CodeAgents, arXiv:2507.03254)
- Agents exchange structured JSON instead of free-form text
- 30-83% token overhead reduction for multi-agent communication
- **Application**: StandardWork handoff as JSON contract, not markdown narrative

### 4. HYBRID — "combine methods"

**ACON** (Microsoft, arXiv:2510.00615, Oct 2025)
- Compression guideline optimization in natural language space
- FAILURE-DRIVEN: analyze what was lost in compression → update guidelines
- Guidelines evolve: v1 "summarize tool outputs" → v2 "+ preserve port numbers" →
  v3 "+ preserve error messages from failures verbatim"
- Result: 26-54% peak token reduction, IMPROVED task success (noise removed)
- **Application**: Kaizen rules = ACON guidelines (already partially done)

**SARA** (arXiv:2507.05633, May 2026)
- Hybrid: natural-language snippets + semantic compression vectors
- Balances local precision and global knowledge coverage
- Complex to implement; lower priority

### 5. EVICTION — "remove unneeded"

Token budget enforcement with priority-based dropping:
1. Raw test output → summary (first to go)
2. Intermediate code drafts → keep final + diff
3. Verbose explanations → keep conclusions
4. Redundant descriptions → dedup
5. Old navigator bundles → keep key insights
- NEVER drop: StandardWork, acceptance criteria, import contracts

### 6. EXTERNALIZATION — "move outside context window"

**Tool Output Sandboxing** (context-mode MCP, github.com/mksglu/context-mode)
- Raw tool output → SQLite sandbox; agent gets summary + ref ID
- 315KB → 5.4KB (98% reduction), full output retrievable on-demand
- **Application**: Code Navigator bundle, Neo4j query results, pytest output, web_search

### 7. LINGUISTIC — "compress the language itself"

**Caveman** (github.com/JuliusBrussee/caveman, Apr 2026)
- System prompt instructs LLM to drop filler, keep technical accuracy
- ~75% output token reduction
- Example: "I've analyzed the parser and I think there might be an issue..."
  → "parser.py: empty input not handled. parse() needs guard clause."
- **Application**: all agent-to-agent communication (handoffs, Jidoka reports, reviews)

### 8. KV-CACHE SHARING (infra-level)

**TokenDance** (arXiv:2604.03143, Apr 2026)
- Multi-agent rounds: shared context blocks computed once, reused by all agents
- O(N) → O(1) for shared blocks
- **Not applicable**: requires infra-level control over inference server; we use external APIs

## 4-Level Compression Stack for Our Pipeline

```
Level 1: STRUCTURING (at creation time)
  Tech Lead creates StandardWork as JSON contract (not free-form markdown)
  Research findings → structured entries with relevance mapping
  System analysis → structured root cause + goal tree branch

Level 2: FILTERING (at delivery time)
  For each agent: filter context by relevance (EXIT-style)
  Role-based filtering: Jidoka gets AC only, not research
  Research artifact: 8KB → 1.5KB (5x), 100% relevance to specific SW

Level 3: COMPRESSION (when over budget)
  Anchored Iterative Summarization for session state
  ACON failure-driven guidelines (Kaizen rules = what to preserve)
  Caveman mode for all agent-to-agent communication

Level 4: EXTERNALIZATION (always)
  Tool outputs → SQLite sandbox + summary + ref ID (98% reduction)
  Full artifacts → disk (accessible via read_file on demand)
  Raw data → Neo4j (queryable, not in context)
```

## Per-Agent Token Budgets

| Agent | Total | Static | Dynamic | Episodic | Research/Analysis | Semantic |
|-------|:-----:|:------:|:-------:|:--------:|:-----------------:|:--------:|
| Developer | 50K | 5K | 15K | 20K | 3K (compressed) | 5K |
| Jidoka | 30K | 3K | 10K | 15K | — | 2K |
| Reviewer | 20K | 2K | 8K | 8K | — | 2K |
| Tech Lead | 100K | 10K | 40K | 30K | 10K | 10K |

## Critical Principle: COMPRESS, DON'T EXCLUDE

**Mistake made in this session**: initially proposed removing research artifact and
system analysis from developer context entirely ("Developer НЕ получает: research
artifact, system analysis").

**Why this was wrong**: In a BDUF pipeline, the developer doesn't just code — they make
micro-decisions at every step:
- Which algorithm? → Research said "recursive descent 40% faster"
- Which library? → Research compared 5 options
- How to handle edge case? → System analysis identified root cause
- Why this interface? → System analysis goal tree showed downstream dependency

Without research/analysis, developer makes these decisions blind or by intuition,
which can contradict findings.

**Correct approach**: COMPRESS + FILTER by SW relevance, don't EXCLUDE:
- Full research (8KB) → EXIT-filtered to SW-relevant findings (1.5KB)
- Full system analysis (5KB) → root cause + goal tree branch only (2KB)
- Tech Lead performs extraction at StandardWork creation time (Step 4.5)

## Implementation Priority

| Priority | Mechanism | Effort | Impact |
|:--------:|-----------|:------:|:------:|
| P1 | Caveman mode (trivial prompt change) | Trivial | -75% output tokens |
| P1 | Structured contracts (JSON StandardWork) | Low | -50% handoff tokens |
| P1 | ACON guidelines (Kaizen = compression rules) | Low | Adaptive compression |
| P1 | Anchored session state file | Low | Persistent context |
| P2 | EXIT filtering script | Medium | -80% research in dev context |
| P2 | Tool output sandboxing (SQLite) | Medium | -87% tool output tokens |
| P2 | Eviction priority queue | Low | Hard token cap |
| P3 | ContextEvolve 3-agent decomposition | High | -29% tokens, +33% quality |
| P3 | LLMLingua for long docs | Medium | -50-80% on long docs |

## References

1. "Context Compression for LLM Agents: A Survey" (preprints.org, May 2026)
2. LLMLingua (Microsoft, EMNLP'23, ACL'24) — github.com/microsoft/LLMLingua
3. EXIT (ACL 2025 Findings, arXiv:2412.12559)
4. Factory.ai "Evaluating Context Compression" (Dec 2025) — factory.ai/news/evaluating-compression
5. Anthropic Claude Compaction API (Jan 2026) — platform.claude.com/docs/en/build-with-claude/compaction
6. ContextEvolve (arXiv:2602.02597, Feb 2026)
7. SARA (arXiv:2507.05633, May 2026)
8. ACON (Microsoft, arXiv:2510.00615, Oct 2025) — github.com/microsoft/acon
9. context-mode MCP (github.com/mksglu/context-mode)
10. Caveman (github.com/JuliusBrussee/caveman, Apr 2026)
11. CodeAgents (arXiv:2507.03254, Jul 2025)
12. TokenDance (arXiv:2604.03143, Apr 2026)
13. "Cut the Crap" (arXiv:2410.02506) — token overhead in multi-agent pipelines
