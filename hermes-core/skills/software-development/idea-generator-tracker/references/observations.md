# Idea Generator — Phase Observations
> Project: <SESSION_ID> | Task: capability self-model for plan2
> Last updated: Phase 0 (bootstrap)

---
## PHASE 0 — Project Bootstrap (2026-06-25)

### 1. UNHEARD IDEAS (идеи не услышаны)
| # | Idea | Source | Why ignored | Potential value |
|---|------|--------|-------------|-----------------|
| 1 | **Capability Partitioning (LLM + deterministic)** | IEEE Software 2025 paper (from recent BA deep research) | Not surfaced in current cycle planning | Could prevent "solution-jumping" in Phase 1 Requirements Agent |
| 2 | **Requirements Interviewer agent** — already exists at `~/.hermes/agents/requirements-interviewer.md` with 6-phase SPIN/5Whys/SMART protocol | Created 2026-06-23 in session 20260623_220108 | plan2 still references "Requirements Analyst #1" not "Requirements Interviewer" | Huge improvement over basic Requirements Analyst — structured elicitation with SMART-ification, persona-driven, interview log |
| 3 | **15+ plan2 improvements from orchestrator research** — Triple Guard, Jidoka, Recursive Ownership, GoT DAG, etc. | Session 20260624_230951 (deep research on orchestrator agents) | Not yet integrated into plan2.md | Critical safety improvements (Triple Guard prevents $47K loops) |
| 4 | **Deep Plan Research v3 (S10-S15)** — Structured Output, Context Overflow Protection, Retry Budget, Provenance Chain, Auto-Ingest Education Graph, Self-Review | `/home/user/dev/codemes/deep-plan-research/improvement-plan-v3.md` | Not yet implemented; 8.5 days of work identified | Fixes all 3 MAST failure categories (FC1/FC2/FC3) |
| 5 | **Search backend audit completed** — Crossref/OpenAlex work, SearxNG = garbage, English Wikipedia works but rate-limited | Session 20260623_220108 | Not formally documented as system knowledge | Should be a skill or AGENTS.md reference so future research phases don't waste time on SearxNG |
| 6 | **Model Router with Complexity-Based Selection** — ~80% calls don't need frontier models | Session 20260624_230951 | Not in routing table | Could reduce API costs 3-5x |
| 7 | **Fragment Trait System** (from Codex) — 30+ bounded context fragments, no unbounded items | Session 20260624_230951 | Not in context engineering | Would prevent context overflow at source |

### 2. MISSING CONNECTIONS (кого с кем связать)
| # | Agent A | Agent B | Why | What would change |
|---|---------|---------|-----|-------------------|
| 1 | **Requirements Analyst (#1)** should load `requirements-interviewer.md` agent instead of generic role | plan2.md still hardcodes "Requirements Analyst" | Would use structured SPIN/5Whys/SMART protocol instead of generic clarifying questions |
| 2 | **Deep Plan Researcher (#3)** should read `improvement-plan-v3.md` (S10-S15) | Researcher is unaware of known gaps in research pipeline | Would implement structured output, context overflow protection, provenance chain |
| 3 | **Knowledge Curator (#10)** should ingest findings from ALL recent deep research sessions (BA agents, orchestrator improvements, interview mechanisms) | Education Graph has 0 BA entities, 0 orchestrator-improvement entities | Cross-cycle knowledge wouldn't be lost |
| 4 | **System Analyst (#2)** should consult `BA_COMPREHENSIVE_RESEARCH.md` (455 lines of BA methodology) | System Analyst doesn't know about BABOK v3, 6 Knowledge Areas, BACCM model | Would apply industry-standard BA frameworks to system analysis |
| 5 | **Orchestrator** should load `agentic_reasoning_patterns.md` (14 patterns) before delegating | Orchestrator delegates without awareness of known reasoning patterns | Would apply proven patterns (Coordinator 4-phase, Recursive Ownership) to delegation strategy |
| 6 | **Enterprise Architect (#4b)** should query Neo4j topology graph for ALL existing services BEFORE proposing architecture | Currently may design without full topology awareness | Would prevent port conflicts, service overlaps, and integration surprises |

### 3. MISSING INFORMATION (где взять)
| # | What's missing | Where to find it | Tool/Path |
|---|---------------|------------------|-----------|
| 1 | **BA domain knowledge** — BABOK, elicitation techniques, 40+ question templates | `/home/user/BA_COMPREHENSIVE_RESEARCH.md` (455 lines) + 5 supporting files (~2400 lines total) | `read_file` |
| 2 | **Orchestrator improvement patterns** — 15+ concrete improvements with sources | `/home/user/agentic_reasoning_patterns.md` + session 20260624_230951 | `read_file` + `session_search` |
| 3 | **Search backend reliability data** — which search engines work and which don't | Session 20260623_220108 (messages 40639-40725) | `session_search(session_id="20260623_220108_8ad780", around_message_id=40725)` |
| 4 | **Deep Plan Research known gaps** — MAST taxonomy coverage, what's missing in research pipeline | `/home/user/dev/codemes/deep-plan-research/improvement-plan-v3.md` (285 lines) | `read_file` |
| 5 | **Codebase dependency graph** — what files call what, who depends on what | Neo4j codebase graph via curl or MCP tools | `curl -u neo4j:<YOUR_NEO4J_PASSWORD> -d '...' http://localhost:7474/db/neo4j/tx/commit` |
| 6 | **Education Graph knowledge gaps** — what domains have zero entities | Neo4j Education Graph | `curl -u neo4j:<YOUR_NEO4J_PASSWORD> -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN ke.category, count(*) as cnt ORDER BY cnt"}]}' http://localhost:7474/db/neo4j/tx/commit` |
| 7 | **Existing agent registry** — which agents exist, their models, toolsets | `~/.hermes/agents/registry.json` | `read_file` or `python3 ~/.hermes/scripts/agent_registry.py` |
| 8 | **Auditor memory** — cross-cycle patterns, agent performance trends | `~/.hermes/auditor_memory.md` | `read_file` (currently empty — 0 cycles observed) |

### 4. PIPELINE OPTIMISATIONS
| # | Current flow | Proposed change | Expected impact |
|---|-------------|-----------------|-----------------|
| 1 | **Phase 1:** Requirements Analyst asks generic clarifying questions | **Replace with Requirements Interviewer** (SPIN/5Whys/SMART protocol, persona-driven, interview log) | Structured requirements with measurable acceptance criteria, full traceability from start |
| 2 | **Phase 3:** Deep Plan Research uses free-form Markdown outputs | **Implement S10 Structured Output Enforcement** (JSON schemas per sub-agent type) | -30% tokens on parsing, +quality of Synthesizer output |
| 3 | **Phase 3:** No context overflow protection for sub-agents | **Implement S11 Context Overflow Protection** (budget tracking, summary at 80%, fresh spawn) | Eliminates silent RQ loss in quality mode (25 iterations) |
| 4 | **Phase 3:** No retry budget for sub-agents | **Implement S12 Retry Budget** (max_iterations, max_time, diminishing returns detection) | Prevents runaway costs, MAST FC1: unbounded loops |
| 5 | **Phase 4:** Architecture Trio runs without full topology awareness | **Add mandatory Neo4j topology query** before Architecture Trio delegation | Prevents cross-project conflicts, port collisions |
| 6 | **Phase 5:** Tech Lead plans without codebase dependency awareness | **Add mandatory codebase graph query** (what calls what) before plan generation | Prevents planning impossible changes, identifies blast radius |
| 7 | **Phase 6:** Dev agents may re-discover known patterns | **Inject Deep Plan Research findings into dev context** + auto-load relevant skills via Neo4j semantic search | Less re-discovery, faster implementation |
| 8 | **All phases:** Knowledge Curator runs only at end | **Run Knowledge Curator after EACH phase** (fire-and-forget) to continuously ingest entities | Less knowledge loss between cycles, incremental graph building |
| 9 | **Pre-Flight Gate:** 6 mandatory checks but no model routing validation | **Add check #7: model routing validation** — verify each agent's assigned model is available and responding | Prevents mid-cycle model failures |
| 10 | **Observer mechanism:** Observers are stateless and "forget" between checkpoints | **Add observer_state file** — each observer writes incrementally to `~/.hermes/reports/observer-<name>-<pid>.md` at each checkpoint | Enables true accumulation; current fire-and-forget means observers lose context between phases |

---
## SYSTEM-LEVEL OBSERVATIONS

### Capability Gaps (from capability_inventory.yaml):
- **No vision** — cannot see/analyze images (workaround: imagemagick identify)
- **No browser GUI** — no $DISPLAY (workaround: curl, headless)
- **No web_fetch** — cannot fetch arbitrary web pages (workaround: curl -sL)
- **No web_search** — no web_search tool (workaround: searchbox MCP at :8024)
- **No audio_play** — cannot play audio (workaround: write to file)

### Architecture Debt Identified:
1. plan2.md references old "Requirements Analyst" but `requirements-interviewer.md` exists and is superior
2. Deep Plan Research v3 improvements (S10-S15) designed but not implemented (8.5 days)
3. 15+ plan2 orchestrator improvements identified but not integrated
4. Search backend reliability not codified as system knowledge
5. Education Graph has zero entities in BA domain despite recent deep research
6. Auditor memory is empty (0 cycles) — no cross-cycle learning
7. Agent registry may be stale (last updated: varies)

### Pre-existing Context That Should Flow Into This Cycle:
- The user ("Pavel") speaks Russian, prefers technical depth
- Current research interests: meta-agents (ADAS, AFlow), self-evolving agents, Vane patterns, agentic RL
- All research should be ingested into Education Neo4j graph
- User values fast action — read_file/search_files > execute_code
- TEST before claiming success
- ONE agent > two identical ones
- Legacy files → _old, never delete
- Telegram channel: @raicomml (chat_id: <YOUR_TELEGRAM_CHAT_ID>)
