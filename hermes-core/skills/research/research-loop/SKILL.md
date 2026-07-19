---
name: research-loop
description: "v3.0: Classify → Plan → Multi-Language Paraphrased Search → Evaluate → Loop → Synthesize. Structured JSON output, context overflow protection, provenance chain, self-review, skill library."
version: 3.0.0
tags: [research, subagent, searchbox, pipeline, agentic-search, multi-language, paraphrasing, structured-output]
---

# Research Loop Subagent

You are a **research subagent**. Your ONLY job: receive a research question, follow
the mandatory pipeline, and return a structured findings report. Do NOT do anything else.

## Mandatory Pipeline (NEVER skip steps)

```
CLASSIFY → PLAN → SEARCH → EVALUATE → [LOOP back to PLAN] → DONE → SYNTHESIZE
```

Every iteration: PLAN → SEARCH → EVALUATE. Max iterations by mode. Stop ONLY via DONE signal or max iterations.

## Step 1: CLASSIFY

Determine the research mode and strategy:

| Signal | Mode | Max iterations | Engines | Strategy |
|--------|------|---------------|---------|----------|
| Simple fact, definition, single answer | **quick** | 2 | searxng, wikipedia | One search → verify → done |
| Multi-facet topic, comparison, how-to | **standard** | 6 | searxng, wikipedia, arxiv, github | 2–3 searches from different angles |
| Deep research, literature review, unknown domain | **deep** | 12 | ALL (searxng, wikipedia, arxiv, github, crossref, openalex, hackernews, stackexchange) | Multi-angle, cross-reference, follow citations |

Output (in your thinking, not to user):
```
MODE: <quick|standard|deep>
DEPTH: <justification>
SOURCES: <selected engines>
```

## Step 2: PLAN

Formulate 2–4 specific search queries. Rules:
- Be specific, not generic
- Each query targets a different angle
- Use technical terms when appropriate
- For code/package research: include language/framework

Output format (keep in working memory):
```
QUERIES:
  1. "<query 1>" → engines: [e1, e2]
  2. "<query 2>" → engines: [e3, e4]
  ...
```

## Step 3: SEARCH

Use the searchbox MCP server at `http://127.0.0.1:8024/mcp`.

### Session setup (first call only)
```bash
SESSION=$(curl -s -D - 'http://127.0.0.1:8024/mcp' -X POST \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"research-subagent","version":"1.0"}}}' \
  | grep -i 'mcp-session-id:' | awk '{print $2}' | tr -d '\r')
```

### Search call (reuse session)
```bash
curl -s "http://127.0.0.1:8024/mcp" -X POST \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search","arguments":{"query":"<query>","max_results":5,"engines":["searxng","wikipedia"]}}}'
```

Parse the SSE response: find `data: ` line → JSON-decode → `result.content[0].text` → JSON-decode again → `results` array.

### Available engines
Always use `search` (fan-out) tool unless you need a specific engine.
- **Free (always available):** searxng, duckduckgo, wikipedia, wikidata, arxiv, github, hackernews, stackexchange, crossref, openalex, pypi, npm
- **Premium (may fail):** brave, google, tavily

### Rate limits
- Max 3 queries per iteration
- Max 5 results per query
- Wait 1s between calls

## Step 4: EVALUATE

After receiving search results, evaluate:

1. **Sufficiency check:** Do I have enough to answer comprehensively?
   - Quick mode: 1 solid source = sufficient
   - Standard mode: 2–3 sources from different angles = sufficient
   - Deep mode: 5+ sources, multi-angle, cross-referenced = sufficient

2. **Gap analysis:** What's still missing?
   - Contradictory information? → search for resolution
   - Missing perspective? → add query from that angle
   - Outdated info? → search for recent/release date

3. **Decision:** CONTINUE (more iterations needed) or DONE

## Step 5: LOOP

If CONTINUE: go back to PLAN with new queries informed by gaps.
Track iteration: `Iteration N of M`.

## Step 6: DONE → SYNTHESIZE

When DONE, produce this exact output:

```markdown
## Research Report: [Topic]

**Mode:** [quick|standard|deep]
**Iterations used:** [N] of [M]
**Engines used:** [list]

### Key Findings

1. **[Finding title]**
   - Source: [url]
   - Summary: [2-3 sentences]

2. ...

### Sources

| # | Title | URL | Engine |
|---|-------|-----|--------|

### Gaps / Uncertainties

- [Any remaining questions or low-confidence findings]
```

## <mistakes_to_avoid>

1. **Skipping CLASSIFY** — always determine mode before searching
2. **One-search-and-done in deep mode** — deep mode requires MULTIPLE angles
3. **Generic queries** — "what is X" is worse than "X architecture comparison with Y"
4. **Ignoring contradictions** — if two sources disagree, search for resolution
5. **Calling DONE too early** — use your full iteration budget in deep mode
6. **Not using fan-out** — `search` tool without `engines` parameter fans out to ALL available engines
7. **Over-fetching** — max 5 results per call, max 3 queries per iteration
8. **Not tracking iterations** — always know N of M

## Deep Plan Research (plan2 Phase 3)

When acting inside plan2 or as standalone deep research, follow the 4-subphase pipeline with mandatory gates. Full architecture reference: [`references/deep-plan-research-architecture.md`](references/deep-plan-research-architecture.md).

**Trigger phrases for this mode:** "deep research", "deep plan research", "исследование с гейтами", "research plan", "developer query research", "citation enforcement".

## <response_protocol>

- NEVER output free-form text before the final SYNTHESIS
- Each iteration: silently execute PLAN → SEARCH → EVALUATE
- Output ONLY the final Markdown report
- If max iterations reached without DONE, synthesize what you have and note gaps

## Engine Reliability Notes

For academic/paper research, **prioritize arxiv** — it has the cleanest results. SearxNG is noisy for niche academic queries (may return irrelevant web results). Always include both arxiv and at least one web engine.

For code/implementation searches: **github** + **pypi**/npm are reliable. Hackernews is useful for community sentiment but not for finding papers.

See [`references/anthropic-multi-agent-research.md`](references/anthropic-multi-agent-research.md) for the Anthropic multi-agent research blueprint — architecture, prompt engineering, production reliability, and 8 design decisions.

See [`references/planning-orchestrator-agents-research.md`](references/planning-orchestrator-agents-research.md) for the planning/orchestrator agent research knowledge bank — 15 academic papers, 14 reasoning patterns (ReAct, ToT, GoT, ReWOO, Reflexion, LLMCompiler, etc.), and 22 production best practices, condensed from a 5-subagent parallel research session.

See [`references/deep-research-landscape.md`](references/deep-research-landscape.md) for the competitive landscape — OpenAI vs Google vs Perplexity with concrete numbers.

See [`references/meta-agent-design-papers.md`](references/meta-agent-design-papers.md) for the ADAS and AFlow papers (both ICLR 2025) — automated agent design via evolutionary search and MCTS, with concrete application patterns for plan2 orchestrator improvement.

See [`references/meta-agent-papers-2025-2026.md`](references/meta-agent-papers-2025-2026.md) for condensed knowledge on three landmark 2025–2026 papers (ADAS, AFlow, SDB Architecture) — use as bootstrap context when researching agent orchestration, workflow optimization, or plan2 improvement.

See [`references/llm-iterative-code-improvement.md`](references/llm-iterative-code-improvement.md) for the LLM iterative code improvement knowledge bank — 8 papers (2023–2026), decision matrix (when self-repair works vs fails), DDI decay framework, rise-then-collapse mechanics, and practical deployment recipe. Load as bootstrap context when researching whether LLMs (especially weaker ones) can iteratively clean/improve code.

## Model Comparison Research

When the research task involves comparing models for local deployment, quantization quality is a first-class variable. See `references/quantization-quality.md` for the quick-reference rules and `references/apex-quant-deep-dive.md` for MoE-specific adaptive quantization (APEX-Quant), the ACL 2025 paper findings, and model-specific quantization availability data. Key principle: **big model + bad quant < smaller model + good quant.** Always normalize comparisons to equivalent quantization levels, or explicitly call out the quantization gap.

## Education Graph Parallelism

The main agent should query the education graph BEFORE dispatching this subagent and pass the results as bootstrap context. This prevents the subagent from wasting iterations rediscovering known facts.

Expected context shape:
```
EDUCATION GRAPH BOOTSTRAP:
- Known entities: [list with type + description]
- Known relationships: [entity → predicate → entity]
- Known facts: [subject → predicate → object]
```

## Main-Agent Research (alternative to subagent)

When you are the MAIN agent (not a subagent) and need to research:

```
PARALLEL web_search queries (3–5 angles) → curl extract full articles → synthesize → present
```

**curl extraction (when web_extract fails):**
```bash
curl -sL --max-time 15 -H 'User-Agent: Mozilla/5.0' '<URL>' | python3 -c "
import sys, re
html = sys.stdin.read()
text = re.sub(r'<[^>]+>', ' ', html)
text = re.sub(r'&[a-z]+;', ' ', text)
text = re.sub(r'\s+', ' ', text)
print(text[:5000])
"
```

Use this when the user asks deep research questions that need full article text, not just search snippets. Do NOT use execute_code for curl extraction — it adds consent-prompt latency.

**PDF paper extraction (when curl to arxiv abstract page is not enough):**
```bash
# Download PDF → pdftotext → read sections
curl -sL --max-time 20 -o /tmp/paper.pdf -H 'User-Agent: Mozilla/5.0' 'https://arxiv.org/pdf/XXXX.XXXXX' && \
pdftotext /tmp/paper.pdf /tmp/paper.txt && \
head -400 /tmp/paper.txt
```

Then paginate: `sed -n '200,450p' /tmp/paper.txt` to extract specific sections (algorithm, results, architecture).
This is the MOST RELIABLE method for paper deep-dives — web_extract fails with DuckDuckGo backend, and arxiv HTML pages have JS-loaded content that doesn't extract well. PDF → pdftotext gives clean, paginated, searchable text.
Check `pdftotext` availability first: `which pdftotext` (part of poppler-utils). If missing: `sudo apt install poppler-utils`.

**Paper deep-dive workflow (MAIN agent, for user asks «расскажи про X paper»):**
1. `web_search` for paper title + venue + year → find arxiv ID and GitHub
2. `curl arxiv abstract page` → get abstract, authors, status
3. `curl PDF → pdftotext` → extract algorithm details, results, architecture sections
4. `curl GitHub README` → get code structure, installation, operators
5. `curl Neo4j` → check if paper is already in education graph
6. Synthesize → structured deep-dive with: (a) what it is, (b) architecture, (c) algorithm, (d) results, (e) how to apply to plan2, (f) comparison with related papers
7. Present in Russian with dense tables and code blocks — user prefers this format

**GitHub repository source analysis (when researching a library/framework):**

For deep-diving a GitHub-hosted library, fetch raw files directly — no browser, no web_extract, no HTML stripping needed. `browser_navigate` times out on github.com (JS-heavy pages), and `web_extract` fails with DuckDuckGo backend. Raw content URLs return clean text/markdown/source instantly:

```bash
# 1. Fetch README (raw markdown — clean text, no HTML to strip)
curl -sL --max-time 30 "https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"

# 2. List directory structure with file sizes (GitHub Contents API)
curl -sL --max-time 30 "https://api.github.com/repos/{owner}/{repo}/contents/{path}" | \
  python3 -c "import sys,json; data=json.load(sys.stdin); [print(f\"{x['name']} ({x['type']}, {x.get('size','?')}b)\") for x in data]"

# 3. Read individual source files (docstrings, class defs, function signatures)
curl -sL --max-time 30 "https://raw.githubusercontent.com/{owner}/{repo}/main/{path/to/file.py}"
```

**Workflow for library deep-dive (MAIN agent, for user asks «расскажи про библиотеку X»):**
1. `web_search` for library name → confirm GitHub URL, get overview from search snippets
2. `curl raw README.md` → understand what the library does, installation, quickstart, features
3. `curl Contents API` on root → see top-level directory structure, identify key modules
4. `curl Contents API` on subdirectories → drill into relevant modules (e.g. `mixle/task/`, `mixle/models/`)
5. `curl raw` on 3-5 key source files → read implementation details (docstrings reveal design philosophy, class relationships, API surface)
6. Check companion projects / sibling repos (linked in README) → often where the gateway/serving/deployment layer lives
7. Synthesize → structured analysis with comparison tables, code excerpts, architecture summary — present in Russian with dense tables

**Why this works better than browser/web_extract for GitHub:**
- `raw.githubusercontent.com` serves plain text — no JS, no HTML, no rendering needed
- GitHub Contents API returns JSON with file names, types, and sizes — instant directory tree
- File sizes in the API response help prioritize which files to read (larger = more logic)
- Can fetch multiple files in parallel terminal calls — 5 source files in ~5 seconds total
- No rate limit issues for public repos (unauthenticated GitHub API allows 60 req/hr, raw content has no limit)

**Presentation:** when the user says «покажи всё», «все данные», present raw research data FIRST (search snippets, extracted texts, structured findings), then synthesis. Never skip the data and go straight to conclusions — the user wants to see the evidence.

**Competitive / Market Analysis Research (MAIN agent, for «сравни платформы», «deep research на тему X vs Y»):**

When the user asks for a competitive or market analysis (companies, platforms, pricing, build-vs-buy), the research has a distinct multi-dimension structure. Each dimension needs its OWN search round — don't try to find everything in one query:

| Round | Dimension | Sources | Query pattern |
|-------|-----------|---------|---------------|
| 1 | Market size & CAGR | Precedence Research, Grand View, Roots | `"{domain}" market size 2025 forecast CAGR billion` |
| 2 | Company financials | Tracxn, Crunchbase, PitchBook, Pulse2 | `"{company}" funding valuation 2024 2025` |
| 3 | Adoption metrics | GitHub, releasealert.dev, tech blogs | `"{project}" GitHub stars users 2025 2026` |
| 4 | Build-vs-buy TCO | DextraLabs, AISera, ServicesGround | `"build vs buy" AI agent cost TCO 2025` |
| 5 | Analyst verdicts | Gartner, McKinsey, HBR | `Gartner AI agent prediction {year}` |
| 6 | Pricing | Vendor pages, SaaStr, costbench | `"{platform}" pricing per seat cost 2025` |

**Key insight:** `web_extract` will fail (DuckDuckGo backend). Accept search **snippets as first-pass data** — they carry enough signal (funding amounts, valuations, star counts) for a competitive overview. Only `curl`-extract for deep dives on 1-2 key companies.

**Output structure** (presentation-ready):
1. Market size (triangulate 2-3 sources) → 2. Platform categorization → 3. Company financials table → 4. OSS champions deep-dive → 5. Build cost breakdown → 6. Buy pricing comparison → 7. TCO matrix → 8. Decision matrix → 9. Analyst reality check → 10. Conclusions

Present in Russian with dense comparison tables.

**Market Localization Adaptation (MAIN agent, for «переведи на российский рынок», «adapt for {country} market»):**

When the user asks to adapt a global market/competitive analysis to a specific national market (most commonly Russia), recalculate ALL of these dimensions — don't just translate currency:

| Dimension | What to research | RU-specific sources |
|-----------|-----------------|---------------------|
| Currency & TCO | Convert all $ figures; recalculate with local salaries | hh.ru, Habr Career for salaries |
| API/inference pricing | Local LLM API pricing per tokens | GigaChat, YandexGPT developer docs |
| Labor costs | Local ML/DevOps/MLOps salaries (median + senior) | IT Institute, Practicum, RBC |
| Regulatory constraints | Data residency laws, import substitution rules | 152-FZ, software registry, FSTEK |
| Platform landscape | Local proprietary platforms + imported OSS | Tadviser, tproger.ru, Habr |
| Adoption cases | Local company case studies with effect figures | TASS, Kommersant, RBC, company press |

Critical for Russia: **foreign SaaS (Salesforce, MS Copilot) is blocked** for gov/finance by 152-FZ + software registry. This is a hard constraint that reshapes the build-vs-buy recommendation. Also: Russian LLM APIs are **15-40x cheaper** than GPT-4o — this flips the inference cost calculus.

See [`references/russian-ai-market-2026.md`](references/russian-ai-market-2026.md) for the full Russian AI market knowledge bank — GigaChat/YandexGPT API pricing (RUB per 1K tokens), Russian IT labor costs by role, 152-FZ and software registry regulatory constraints, Sber/Yandex/Rosatom adoption cases with RUB effect figures, and the 6-dimension localization adaptation pattern. Load when the user asks to «переведи на российский рынок», adapt analysis for Russia, or needs Russian API pricing or salary data.

## Parallel Fan-Out Research (Orchestrator Pattern) — v2.0

When the orchestrator needs DEEP research on a complex topic, use **parallel fan-out**
instead of a single sequential research subagent. This cuts research time by 2-3× and
produces richer cross-referenced findings.

For research on agent orchestration, workflow optimization, and self-evolving systems,
load the paper reference bank: `skill_view(name="research-loop", file_path="references/orchestration-papers.md")`
— covers ADAS, AFlow, SDB Architecture, FoT, and GoT with key insights for plan2 design.

### When to use parallel fan-out

| Signal | Single subagent ok | Fan-out (3+ subagents) |
|--------|:------------------:|:----------------------:|
| Simple fact, definition | ✅ | ❌ overhead |
| Multi-facet comparison | ⚠️ ok | ✅ better |
| Unknown domain exploration | ❌ insufficient | ✅ **required** |
| Architecture/design research | ❌ biased | ✅ multiple perspectives |
| User says «глубокое исследование» | ❌ | ✅ |

### Pattern

```
MAIN AGENT (orchestrator):
  delegate_task(tasks=[
    {goal: "Research angle A — academic papers", toolsets: [terminal, web]},
    {goal: "Research angle B — code/implementations", toolsets: [terminal, web]},
    {goal: "Research angle C — community/best practices", toolsets: [terminal, web]},
  ])
  → Collect 3 structured reports
  → Cross-reference claims
  → Synthesize into unified research artifact
```

### Choosing research angles

Every topic has multiple facets. Split by SOURCE TYPE, not by subtopic:

| Angle | Sources | Best for |
|-------|---------|----------|
| **Academic** | arxiv, crossref, openalex, semanticscholar | Papers, algorithms, theory |
| **Code** | github, pypi, npm | Implementations, libraries, real code |
| **Community** | hackernews, stackexchange, reddit | Discussions, gotchas, best practices |
| **Vendor docs** | Direct curl of official docs | API specs, requirements, limits |
| **Claw+Codebase** | Neo4j claw graph + codebase graph | What the system ALREADY knows |

### Model selection for fan-out

- **3 subagents, different models** → broader perspective (e.g., deepseek-v4-pro + kimi-k2.7-code + gpt-4.1)
- **5 subagents, same model** → deeper coverage (Research Orchestra with 5 specialized agents)
- **model=deepseek-v4-pro, provider=deepseek** for each — cheapest, 1M context, proven for subagent research

### Pitfalls

1. **DeepSeek connection error after successful writes** — subagent writes files then final API call drops. Check `tool_trace` for `write_file` calls BEFORE re-spawning. If `write_file` present with reasonable size → files are on disk, do NOT re-spawn. Verify with `wc -l <path>`.

2. **Batch cap** — `delegation.max_concurrent_children` limits parallel tasks. Default is 3. Split into multiple `delegate_task` calls if needed (3 + 2 or 3 + 3).

3. **Same-model bias** — 5 subagents on the same model may produce correlated findings. Mix models when budget allows for genuine multi-perspective research.

4. **Synthesizer must cross-reference** — don't just concatenate 5 reports. The synthesizer MUST: dedup by URL, flag contradictions between agents, assign confidence scores, and produce a unified artifact.

### Real example (2026-06-20)

Researching "best patterns from Claude Code, Cursor, and Vane for agent orchestration":

```
delegate_task(tasks=[
  {goal: "Claude Code agent architecture patterns", toolsets: [web, terminal]},
  {goal: "Cursor IDE multi-agent architecture", toolsets: [web, terminal]},
  {goal: "Vane deep research orchestration", toolsets: [web, terminal]},
])
→ 3 reports in 255s (parallel) vs ~600s (sequential)
→ Cross-referenced: Claude Code fan-out pattern confirmed by Cursor's recursive nesting
→ Synthesized into 7-point orchestrator transformation plan
```

Fan-out research agents are defined in `~/.hermes/agents/research/`: academic, code, community, vendor-docs, claw-analyzer, synthesizer.

## Pitfalls

1. **Subagents cannot use MCP tools directly** — searchbox, education-graph, and other MCP tools are NOT available as function calls inside subagents. Use raw `curl` commands to the MCP HTTP endpoint instead (see SEARCH step above for exact commands).

2. **SSE response parsing** — searchbox returns `text/event-stream`. Parse by: (a) capture `mcp-session-id` from HTTP response header of initialize call; (b) find `data: ` line in SSE body; (c) JSON-decode that line; (d) access `result.content[0].text`; (e) JSON-decode again for the actual results.

3. **SearxNG noise for academic queries** — when searching for niche academic terms (paper titles, author names), SearxNG frequently returns irrelevant web results. For academic topics, always include `arxiv` in the engine list and consider it the primary signal.

4. **Tool output size** — searchbox fan-out across 15 engines can return 2,000+ lines of SSE. Use `max_results=3` for initial queries, increase only if results are insufficient.

5. **curl variable persistence** — the `$SESSION` variable set in the initialize call persists within a single terminal session but NOT across separate `terminal()` calls in subagents. Set it once per research round and reuse within the same command chain.

6. **web_extract fails with DuckDuckGo backend** — `web_extract` using DuckDuckGo (ddgs) is search-only and CANNOT extract URL content. Error: `DuckDuckGo (ddgs) is a search-only backend and cannot extract URL content. Set web.extract_backend to firecrawl, tavily, exa, or parallel.` Workaround: use `curl` with User-Agent header + Python HTML-stripping (see Main-Agent Research section above).

7. **web_search burst failures** — if web_search fails 3+ times consecutively with different errors (TLS handshake, http2 module errors), it's likely a transient searchbox container or network issue. Do NOT retry the same query — switch to a different approach (different engine, direct curl to known URLs, or query the education/Neo4j graph).

8. **SearxNG useless for Russian-language vendor docs** — when researching Yandex, 1C, or other Russian-platform official documentation, SearxNG returns Yandex portal pages (ya.ru, music.yandex.ru) rather than the actual documentation. Do NOT use search engines for Russian vendor docs. Instead: find the documentation URL path from memory or a quick guess (`yandex.ru/support/<product>/ru/...`), then use `curl -sL --max-time 15 'URL' | python3 -c "..."` to extract text directly. This is faster and more reliable than any search engine for this class of content.

9. **Vendor documentation > search engines** — go directly to official docs.

10. **GATE C: RQ Coverage false positives** — table headers containing "RQ" are filtered by checking for "Priority" and "---" markers. Ensure RQ tables follow the format: header→separator→data rows.

11. **GATE C: Citation scope** — citation mapping only counts paragraphs inside the `## RQ Answers` section. Paragraphs in `### Source Quality Matrix` and `### Debate Resolution` are intentionally excluded. Boundary detection uses `### Source Quality Matrix` or h2 headings (other than RQ Answers).

12. **GATE D: Mock URL handling** — on test data with fake URLs, GATE D fails because the 20% spot-check uses real curl. Expected. Real artifacts with live URLs pass. Accept GATE D failure on mock data as a correct signal.

10. **GATE C section boundary detection** — the Citation Mapping check must stop at `### Source Quality Matrix` or `### Debate` sections. The script uses section-header detection to avoid counting non-RQ-answer paragraphs as uncited. If adding new sections after RQ Answers, update the boundary list in `research_completeness_gate.py` or the check will produce false failures.

11. **GATE C RQ Coverage table parsing** — the RQ Coverage check uses a state machine to avoid false matches on "RQ" in table headers. If the Research Plan table format changes, verify the parser still correctly identifies RQ rows (lines with digits in the first column, inside a table body).

See [`references/dgx-spark-model-comparison-2026-07.md`](references/dgx-spark-model-comparison-2026-07.md) for DGX Spark (128GB) model comparison — covers BOTH quantized (GGUF) and non-quantized (BF16/FP16) models: Nex-N2-Pro/mini, Qwen-AgentWorld, Qwen3.6-35B-A3B, Nemotron-Super-49B, Huihui4, ALIA-40B, QwQ-56B-Ghost; GGUF availability + BF16 safetensors sizes, llama.cpp-dgx fork (SM12.1/CUDA 13.1), MoE tok/s estimates, memory budget for non-quantized inference, abliteration quality impact data. Use as bootstrap context for local-model research on Grace Blackwell hardware.

See [`references/test-results.md`](references/test-results.md) for a real execution trace with metrics, engine reliability data, and the education graph bootstrap pattern.

See [`references/search-engine-reliability.md`](references/search-engine-reliability.md) for search engine reliability ratings — **critical: SearxNG is unusable for technical queries**, use source-specific APIs (crossref, arxiv, GitHub) instead.

See [`references/searchbox-api.md`](references/searchbox-api.md) for the full searchbox MCP API reference — all 18 tools, engine descriptions, session setup, Python client, response format, and engine reliability ratings.

Run `scripts/integration-test.py` to validate all Deep Plan Research components (agents, gates, registry). Requires `HERMES_HOME` env var. Default: `/home/user/.hermes`.

See [`references/deep-research-landscape.md`](references/deep-research-landscape.md) for the competitive landscape of major deep research products (OpenAI Deep Research vs Google Gemini Deep Research Max vs Perplexity Deep Research) — architecture, concrete numbers, pricing, and when-to-use-which guidance.

See [`references/anthropic-multi-agent-research.md`](references/anthropic-multi-agent-research.md) for the complete Anthropic multi-agent research blueprint — architecture, prompt engineering principles, production reliability, token economics, and 8 critical design decisions derived from their June 2025 engineering post-mortem.

## Deep Plan Research (plan2 integration) — v2.0

When the research-loop skill is used within `/agent plan2` orchestration, the enhanced **Deep Plan Research** pipeline applies. This is a **four-subphase** enhancement to plan2's Phase 3 with **five gates** (0 + A–D):

```
3.0 PLAN      → 3–7 Research Questions, source strategy, depth mode
                 ↓ GATE 0: Cost Gate — single vs multi-agent choice
                 ↓ GATE A: User Approval Gate — user approves via clarify
3.1 EXECUTE   → 5–7 subagents in parallel (incl. Claw + Debate pairs)
                 ↓ Adaptive RQ discovery: subagents can propose new RQs
                 ↓ GATE B: Source Quality Gate (LLM-as-judge: 5 criteria)
3.2 SYNTHESIS → unified artifact + citation mapping (claim → source[index])
                 ↓ GATE C: Research Completeness Gate (5 checks)
3.3 CITATIONS → CitationAgent: independent citation verification
                 ↓ GATE D: Citation Enforcement — ≥90% citations valid
                 ↓ Sequential same-source facts grouped → one [N] at end
```

### Five Gates (full set)

| Gate | When | What | FAIL → |
|------|------|------|--------|
| **GATE 0: Cost Gate** | After 3.0, before spawning | Single-agent (≤2 simple RQs) vs multi-agent (≥3 complex RQs). Prevents overkill — Anthropic: multi-agent uses 15× more tokens. Princeton: single-agent wins 64% of tasks. | N/A (auto-decision) |
| **GATE A: User Approval** | After Cost Gate, before 3.1 | User sees and edits research plan via clarify | Re-edit plan |
| **GATE B: Source Quality** | After 3.1, before 3.2 | LLM-as-judge: factual accuracy, citation accuracy, completeness, source quality, tool efficiency. ≥70% sources score ≥4/8. | Re-search low-quality RQs |
| **GATE C: Completeness** | After 3.2, before 3.3 | All RQs answered, citations mapped, structure valid, source diversity ≥3 types, artifact >2000 bytes | Return to Synthesizer |
| **GATE D: Citation Enforcement** | After 3.3, before Phase 4 | Separate CitationAgent verifies ≥90% citations. Groups sequential same-source facts → single [N] reference. Samples 20% for URL validity. | Fix invalid citations |

### Cost Gate Logic

Not every research task needs 7 subagents. Cost gate prevents overkill:

```
RQs ≤ 2 AND all fact/single-source type     → SINGLE  (1 agent, ~3K tokens, 15s)
  Example: "What's the latest FastAPI version?"
RQs = 2–4 AND different domains             → BALANCED (3–5 agents)
  Example: "Compare FastAPI vs Litestar latency and ecosystem"
RQs ≥ 5 OR HIGH-priority OR lit.review       → QUALITY (5–7 + debate mode)
  Example: "Voice pipeline for Android: STT, TTS, latency, formats, libraries"
```

**Complexity criteria:**
| Criterion | LOW (→ single) | HIGH (→ quality) |
|-----------|---------------|-----------------|
| Domains | 1 | 3+ |
| Info type | Fact (version, date) | Analysis (comparison, trends) |
| Source diversity needed | No (docs only) | Yes (arxiv + github + community) |

### Debate Mode

For HIGH-priority RQs, spawn 2 agents with different models on the same RQ:

```python
delegate_task(tasks=[
  {goal: "RQ1: ...", model: "deepseek-v4-pro", provider: "deepseek"},
  {goal: "RQ1 — alternative view: ...", model: "kimi-k2.7-code", provider: "custom:kimi"},
])
# Synthesizer receives both results, compares, resolves conflicts
# Reduces hallucinations — agents catch each other's mistakes
# Source: Beam.ai (2026) production pattern
```

### Adaptive RQ Discovery

Subagents may discover unexpected connections. Each can return:

```json
{
  "findings": [...],
  "new_rq_suggested": "Discovered unexpected link to X. Propose RQ7: How does X affect Y?",
  "confidence": "MEDIUM"
}
```

Orchestrator decides whether to add the new RQ and re-spawn (within iteration budget).

### CitationAgent — Separate Verification Pass

Anthropic's key insight: citation verification is a **separate pass**, not part of synthesis.

**Agent:** `~/.hermes/agents/research/citation-agent.md` (kimi-k2.7-code, toolsets: [terminal, web, file_ro])

**Algorithm:**
1. Read `docs/research/<slug>.md`
2. Extract all `[N]` citation references
3. For each — find source in Source Quality Matrix
4. For random 20% sample — curl source URL, verify semantic match
5. Group sequential same-source facts → single `[N]` at end of group
6. Flag claims without citations
7. Return: `{valid: N, invalid: M, ungrouped: K, suggestions: [...]}`

**Grouping example:**
```markdown
FastAPI processes 25,000 req/s on one worker. Litestar reaches 31,000 req/s
under the same conditions. Both use uvloop, but Litestar avoids monkey-patching. [3]

FastAPI has a more mature ecosystem: 70,000+ GitHub stars, 200+ middleware,
OpenAPI 3.1 integration out of the box. [5]
```

### Developer Query Interface

Developer agents (Phase 6) can query Deep Research mid-implementation:

```python
delegate_task(
  goal="Research query from Developer: ...",
  context="""
    ## Developer Research Query
    ### Что уже исследовано (from Phase 3)
    - RQ1: ... (confidence HIGH) [sources: 1,3]
    ### Что хочется найти
    - [specific developer question]
    ### Что не хватает
    - [gaps]
    ### Что мешает
    - [blockers]
    ### Бюджет: max 5 min, max 3 sub-agents
  """,
  agent="standalone-deep-researcher",
  model="deepseek-v4-pro", provider="deepseek"
)
# Returns mini-report (500-2000 words, with citations) in 3-5 minutes
```

Full implementation plan: `/home/user/dev/codemes/deep-plan-research/implementation-plan-v2.md` (32 KB).

### Key Differences from Standalone research-loop

- **Collaborative planning** (Google-style): user sees and edits the research plan before execution
- **Five gates** (0, A, B, C, D) instead of one (>500 bytes check)
- **Cost awareness**: single-agent for simple, multi-agent for complex — prevents 15× token waste
- **Debate mode**: 2 agents on HIGH-priority RQs reduce hallucinations
- **Adaptive RQ discovery**: subagents can propose new research directions
- **CitationAgent**: separate verification pass (Anthropic pattern)
- **Citation grouping**: sequential same-source facts → one `[N]` at end of group
- **Developer query interface**: structured protocol for developers to ask research questions mid-cycle
- **Claw Orchestrator integration**: direct Neo4j curl (fast) or full claw-analyzer subagent (deep)
- **`#research-needed` tags**: Claw can flag infrastructure patterns for future research cycles
- **Per-RQ subagent assignment**: each subagent gets specific questions, not a generic topic
- **Cross-graph analysis**: Codebase graph + Claw graph + Education graph consulted before spawning

When acting as a research subagent within plan2, expect to receive specific RQs (not a general topic) and return findings keyed to those RQs. You may suggest new RQs if you discover unexpected connections. The orchestrator and Deep Plan Researcher handle planning and gating; your job is execution against assigned RQs.

## v3.0 — Structured Output, Context Budget, Provenance, Self-Review

### Structured Output (JSON Schemas)

All 5 research sub-agents return typed JSON instead of free-form Markdown. Synthesizer receives machine-readable inputs — saves ~30% parsing tokens.

| Agent | Schema fields |
|-------|--------------|
| academic-researcher | rq_id, claim, source_url, source_title, source_type, confidence, evidence_excerpt, source_quality |
| code-researcher | rq_id, claim, source_url, language, stars, last_commit, license, confidence |
| community-researcher | rq_id, claim, source_url, platform, upvotes, date, sentiment, confidence |
| vendor-docs-researcher | rq_id, claim, source_url, version, last_updated, api_endpoint, rate_limit, confidence |
| claw-analyzer | (already JSON — relevance_score, confidence, patterns[]) |

Every schema includes `timestamp`, `search_queries[]`, `iterations`, `new_rq_suggested`, `gaps[]`.

### Context Budget Tracking

Each sub-agent receives a budget in context. Prevents silent context overflow (MAST FC1: System Design → FM-1.4 Loss of conversation history):

```yaml
context_budget:
  max_tokens: 150000
  max_iterations: 6
  max_time_seconds: 180
  max_sources: 15
  diminishing_threshold: 2  # stop after N iterations with no new info
  overflow_protocol: |
    If context > 80% max_tokens:
    1. Summarize findings so far
    2. Spawn fresh agent with summary + remaining RQs
    3. Return partial results from this agent
```

### Research Provenance Chain

Every claim in the final artifact gets a provenance block — tracks which agent found what, when, and with which search query:

```markdown
FastAPI: 25,000 req/s. Litestar: 31,000 req/s. [1]
  └─ Provenance: academic-researcher @ 2026-06-24T14:32:01, iter=3, q="fastapi benchmark req/s 2025"
  └─ Provenance: code-researcher @ 2026-06-24T14:35:18, iter=2, q="litestar performance github"
```

Addresses MAST FC3 (Verification — no/incomplete verification).

### Auto-Ingest Education Graph

After GATE C passes, structured findings are auto-ingested into Neo4j Education Graph via Knowledge Curator:

```cypher
MERGE (ke:KnowledgeEntity {name: "Litestar performance"})
SET ke.category = "Framework",
    ke.description = "31,000 req/s, p50=1.2ms, Python 3.12, msgspec serialization",
    ke.source = "research/<slug>.md",
    ke.confidence = "HIGH"
```

Prevents knowledge loss between cycles (MAST FC3).

### Self-Review Phase

After Synthesis, before GATE C — agent self-evaluates on 5 criteria (Anthropic pattern):

| Criterion | What |
|-----------|------|
| RQ coverage | Are all RQs answered? |
| Source diversity | ≥3 source types, ≥5 unique domains? |
| Citation accuracy | Every claim has valid [N]? |
| Confidence calibration | HIGH confidence backed by 2+ sources? |
| Actionable output | Clear recommendations? |

Improvement suggestions are generated for gaps. Overall score 0-5.

### Research Skill Library

Cached search patterns by domain at `~/.hermes/skills/research/search-patterns.yaml` (8 domains: framework comparison, android latency, python async, voice chat pipeline, MCP servers, Neo4j graph patterns, deep research architecture, citation verification). Each entry: search queries, preferred sources, success rate, last-used date, notes. Loaded at 3.0 startup — matching domain → use cached queries.

### Agent Design Pitfalls

See [`references/agent-design-pitfalls.md`](references/agent-design-pitfalls.md) for lessons learned from building Deep Plan Research v2–v3: merging near-identical agents, preserving legacy agents, explaining new concepts, adapting external prompts, and testing gate scripts before integration.

### Agent Design Pitfall: One Agent, Multiple Modes

When two agents have >80% shared pipeline, merge them into ONE agent with mode switches (plan2-mode vs standalone-mode vs developer-query-mode). The `deep-plan-researcher.md` agent uses this pattern — standalone-deep-researcher was created, found to be nearly identical, and consolidated. **Rule:** before creating a new agent, ask: could the existing agent handle this with a context flag? Mode switches are cheaper than maintaining two near-identical agent files.

## Gate Script Reference

Full gate catalog with bug fix history, usage examples, and agent inventory: [`references/deep-plan-research-gates.md`](references/deep-plan-research-gates.md).

Key operational notes:
- Gate B script: `python3 ~/.hermes/scripts/research_quality_gate.py --artifact <path> [--json]`
- Gate C script: `python3 ~/.hermes/scripts/research_completeness_gate.py --artifact <path> [--json]`
- Gate D script: `python3 ~/.hermes/scripts/citation_enforcement_gate.py --artifact <path> [--verify-sample 20] [--json]`
- All three run as `research_deep` check inside `orchestrator_gate.py` (7 total checks)

## v3.0 — Multi-Language Paraphrasing & Search

### Проблема

Поиск на одном языке с одной формулировкой пропускает значительную часть релевантных результатов.
Русскоязычные источники (habr, khabr, российские форумы) не находятся через английские запросы.
Англоязычные источники (arxiv, github, HN) не находятся через русские запросы.

### Решение: перефразирование + мультиязычный fan-out

**Phase 3.0 (Plan):** для каждого RQ генерируется 4-6 поисковых запросов:
- 2-3 перефразировки на исходном языке
- 1-2 перевода + перефразировки на английском
- 1-2 перевода + перефразировки на русском

```markdown
#### RQ: Agent orchestration patterns for production 2026

| # | Query | Language | Angle |
|---|-------|----------|-------|
| 1 | agent orchestration pattern production 2026 | EN | direct |
| 2 | multi-agent coordination supervisor worker debate | EN | technical |
| 3 | "agent orchestration" production failure modes | EN | precise |
| 4 | паттерны оркестрации агентов production 2026 | RU | direct |
| 5 | многоагентная оркестрация супервизор паттерны отказы | RU | technical |
```

**Phase 3.1 (Execute):** каждый сабагент получает ВСЕ перефразировки для своих RQs и выполняет поиск по каждой из них независимо.

**Правила перефразирования:**
1. **Прямая формулировка** — оригинальный RQ как search query
2. **Техническая** — замена общих слов на domain-термины (pattern → supervisor/worker/fan-out)
3. **Точная** — ключевые слова в кавычках для exact match
4. **Перевод EN** — полный перевод с адаптацией под английскую терминологию
5. **Перевод RU** — перевод с адаптацией под русскую терминологию (включая заимствования)

### Дедупликация между языками

Synthesizer при объединении результатов:
1. Нормализовать URL (убрать www, trailing slash, query params)
2. Если один URL найден через RU и EN запросы → смержить findings, сохранить оба search query для provenance
3. Если разные URL но одинаковый контент (семантический дубликат) → оставить более свежий/авторитетный
4. Пометить язык finding'а для provenance chain

```python
# Synthesizer dedup logic:
normalized_url = url.replace("www.", "").rstrip("/").split("?")[0]
if normalized_url in seen_urls:
    merge(seen_urls[normalized_url], new_finding, query_languages=[lang1, lang2])
```

### Контекст для сабагентов

Каждый сабагент получает в context список перефразировок для своих RQs:

```yaml
# В context сабагента:
rq_id: "RQ1"
queries:
  - {text: "agent orchestration pattern production 2026", lang: "EN", angle: "direct"}
  - {text: "multi-agent coordination supervisor worker debate", lang: "EN", angle: "technical"}
  - {text: "\"agent orchestration\" production failure modes", lang: "EN", angle: "precise"}
  - {text: "паттерны оркестрации агентов production 2026", lang: "RU", angle: "direct"}
  - {text: "многоагентная оркестрация супервизор паттерны отказы", lang: "RU", angle: "technical"}
search_instructions: |
  Execute ALL queries. RU queries → search Russian sources (habr, khabr).
  EN queries → search global sources (arxiv, github). Dedup by URL before returning.
```
- Do NOT run gates on sections outside `## RQ Answers` — they use `### Source Quality Matrix` as the section boundary
