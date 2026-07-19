# Tiered Schema for Structured Research Output — Implementation

> **Date:** 2026-07-03
> **Session:** Context compression implementation — structured research output + Tech Lead filtering

## Problem

Research agent output was free-form markdown (5000 words, ~8KB). Tech Lead read all of it. Developer got "use research findings" — no actionable data. Context noise ~42% for developer.

## Solution: Tiered Schema (3 Layers + Cross-cutting Flag)

### Why Rigid Schemas Break Research

A rigid JSON schema with fixed enum categories forces the research agent to:
- **Force-fit** nuanced findings into wrong categories (loss of nuance)
- **Drop** findings that don't match any category (loss of information)
- **Fabricate** categories (schema violation)

Example: "PEG parsers give better error messages but are slower — consensus is DX > performance for small grammars" — not a `best_practice`, not a `pitfall`, not a `benchmark`. It's **meta-reasoning** connecting multiple findings.

### 3-Layer Design

**Layer 1 — Structured Core (mandatory):**
Fields that ALWAYS exist in any research output. They describe the *structure* of knowledge, not the *content*:
- `research_questions[]` — id, question, answer, confidence, sources
- `findings[]` — id, category (enum), finding (free text), confidence, tags, actionable, recommended_action, routing_target
- `source_quality_matrix[]` — id, type, quality_score, verified
- `narrative_summary` — one-paragraph for Architect/System Analyst who prefer prose

Key insight: `category` is enum (for routing), but `finding` is free text (for content). This preserves research freedom while enabling machine routing.

**Layer 2 — Conditional (optional, when applicable):**
Fields that appear only when relevant:
- `pitfalls[]` — when research found risks (auto `must_see: true`)
- `benchmarks[]` — when research compared performance
- `alternatives_comparison[]` — when research evaluated ≥2 options
- `code_patterns[]`, `api_reference[]`, `security_notes[]`

Research agent decides which to include. Schema permits absence.

**Layer 3 — Unstructured Notes (escape hatch):**
Single free-form string field `unstructured_notes`. Catches:
- Meta-reasoning connecting findings
- Debate context (why consensus emerged)
- Caveats and conditions
- Serendipitous observations

**Who reads it:** Architect + System Analyst (always). Tech Lead (during filtering, may promote to findings). Developer: NEVER (filtered out for noise reduction).

**Cross-cutting — `must_see` flag:**
Per-finding boolean. Hard constraint on Tech Lead: MUST include in StandardWork regardless of tag/relevance matching. Prevents false negatives in filtering.

Auto-set when:
- `category: "pitfall"` AND `severity: "high"`
- `category: "security"`
- `confidence > 0.9`
- Tags contain platform constraints (`ARM64`, `Jetson`, `CUDA`, `aarch64`)
- Research agent explicitly marks

### Schema File

`~/.hermes/schemas/research-output-v1.json` — JSON Schema draft-07, 10 category enum values, versioned for forward compatibility.

## Tech Lead Filtering Protocol (Step 4.3)

After creating DAG + StandardWork, BEFORE delivering to developer:

```bash
python3 ~/.hermes/scripts/research_filter.py \
  --research docs/research/<slug>.json \
  --sw-keywords "parser,recursive-descent,ParsedDocument" \
  --cycle-id <pid> \
  --output /tmp/sw<N>_findings.json
```

### 5-Pass Filtering (priority order)

1. **must_see: true** → ALWAYS include (hard constraint)
2. **category in ["security", "pitfall"]** → ALWAYS include
3. **Tag match** → include if finding tags intersect with SW keywords (EXIT-style)
4. **Dependency** → include if finding `depends_on` an already-included finding
5. **High confidence + actionable + minimal relevance** → safety net (confidence ≥ 0.85 AND relevance ≥ 0.3)

### ACON Feedback Loop

After each StandardWork completion (PASS or FAIL):
- If developer requested a finding that was filtered out → filter was too aggressive
- Update `~/.hermes/plans/<cycle>-filter-rules.json`:
  - Lower `high_confidence_threshold` by 0.05
  - Add finding tags to `forced_keywords`
- Next cycle: less aggressive filtering for similar tasks

### Validation Results (test case)

| Test | Input | Output | Correct? |
|------|-------|--------|----------|
| SW#3 (parser) | 6 findings | 5 (F1-F4, P1) | ✅ F5 (AST visitor) correctly excluded |
| SW#5 (AST visitor) | 6 findings | 4 (F5, F2 must_see, P1 must_see, F1 dep) | ✅ F3,F4 correctly excluded |

## plan3.md — 8 Synchronized Changes (2026-07-03)

After initial implementation (deep-plan-researcher.md + techlead-agent.md), plan3.md was updated with 8 changes to synchronize the full pipeline:

| # | Location | Change |
|---|----------|--------|
| 1 | Phase 3 header | Added "Structured output" block + "Who reads what" table (Architect→.md, TechLead→.json, Developer→filtered, Observers→.md) |
| 2 | Phase 3.0-3.3 | All GATE B/C/D references changed from `.md` → `.json`; Phase 3.2 goal updated to "structured, PRIMARY" + auto-gen .md command |
| 3 | Phase 3.2 GATE C | Added 7 structured completeness checks (schema, must_see flags, narrative_summary, source_quality_matrix, unstructured_notes) |
| 4 | Phase 4 Architect Trio | Added "Research input" column — Architect gets .md (prose) + .json findings (full); Enterprise Architect gets .json unstructured_notes |
| 5 | Phase 5.5 Pre-Flight Gate | Research check updated: verifies `.json` exists + `schema_version = "research-output-v1"` + valid JSON |
| 6 | Phase 6 Progressive Dev | Added "Research delivery to developers" block — must_see always included, unstructured_notes never to developer, escape hatch, ACON feedback |
| 7 | Checkpoint table | Phase 3.2/3.3 artifact paths updated to `.json (structured, PRIMARY)` + schema compliance focus |
| 8 | Routing table | Replaced prompt-based routing instructions with data-driven auto-routing via `routing_target` field. Each finding routes by metadata, not orchestrator interpretation. |

Additional updates: Quality gates table (GATE B/C/D now reference `.json`), Artifact validation table (new `research (JSON)` row with Python validation command).

### Auto-Routing Replacement

The old routing table was a prompt instruction ("if finding is about architecture → deliver to Architect"). The new table is data-driven:

| `routing_target` | Delivered to | When |
|-------------------|-------------|------|
| `architect` | Architect Trio (#4) | Before Phase 4 |
| `tech_lead` | Tech Lead (#5) | Before Phase 5 (Tech Lead filters per SW) |
| `developer` | Progressive Devs (#6) | During Phase 6 (filtered by Tech Lead) |
| `security_agent` | Security Agent (#7) | Before Phase 7 |
| `tester` | Tester (#8) | Before Phase 8.5 |
| `system_analyst` | System Analyst (#2) | Before Phase 2 + 6.5 |
| `all` | All agents | N/A |
| (any) + `must_see: true` | Tech Lead MUST include in every SW | Hard constraint |

### Validation: 57/57 Checks Passed

Automated validation script checked 6 files across 57 criteria:

| File | Checks | Status |
|------|:------:|:------:|
| `schemas/research-output-v1.json` | 11 (schema structure, all fields) | ✅ |
| `scripts/research_filter.py` | 1 (exists) | ✅ |
| `scripts/research_json_to_md.py` | 1 (exists) | ✅ |
| `agents/deep-plan-researcher.md` | 13 (structured output, tiered schema, GATE C, layers 1-3) | ✅ |
| `agents/techlead-agent.md` | 9 (Step 4.3, filter script, must_see, EXIT, ACON, escape hatch, hard constraint) | ✅ |
| `agents/plan3.md` | 22 (all 8 changes + context flow + routing + quality gates + checkpoints + artifact validation) | ✅ |

Key validation insight: grep-based validation initially produced 2 false negatives because backtick-wrapped terms (`` `must_see` findings ``) didn't match plain-text search. Always use substring patterns that work regardless of markdown formatting.

## Files Created/Modified

| File | Type | Purpose |
|------|------|---------|
| `~/.hermes/schemas/research-output-v1.json` | NEW | JSON Schema — 3 layers + must_see |
| `~/.hermes/scripts/research_filter.py` | NEW | EXIT-style filtering + ACON feedback |
| `~/.hermes/scripts/research_json_to_md.py` | NEW | JSON→Markdown auto-generator (view) |
| `~/.hermes/agents/deep-plan-researcher.md` | MODIFIED | §3.2: structured output format, tiered schema rules, GATE C update |
| `~/.hermes/agents/techlead-agent.md` | MODIFIED | §Step 4.3: Research Filtering protocol |
| `~/.hermes/agents/plan3.md` | MODIFIED | 8 changes: Phase 3 structured output, GATE B/C/D .json, Phase 4 research input, Phase 5.5 schema check, Phase 6 filtered delivery, checkpoint table, auto-routing table, quality gates, artifact validation |

## Data Flow

```
Deep Plan Researcher
  ├── writes docs/research/<slug>.json  (structured, PRIMARY)
  ├── runs research_json_to_md.py
  │   └── writes docs/research/<slug>.md (auto-generated view)
  ▼
Architect / System Analyst
  └── reads .md (prose view) + .json unstructured_notes (meta-reasoning)
  ▼
Tech Lead (Phase 5)
  ├── reads .json (structured findings)
  ├── creates DAG + StandardWork
  ├── runs research_filter.py per SW (EXIT + must_see)
  │   └── embeds filtered findings into StandardWork
  ▼
Developer (Phase 6)
  ├── receives: id, finding, action, confidence (3-5 items, compressed)
  ├── does NOT receive: unstructured_notes, non-relevant, full artifact
  └── escape hatch: delegate_task(deep-plan-researcher, "Developer Query")
```

## Key Design Decisions

1. **JSON = primary, MD = view.** Single source of truth is JSON. Markdown auto-generated. Prevents drift between two formats.
2. **`category` is enum, `finding` is free text.** Routing is deterministic (enum → target agent), content is unconstrained (free text → research freedom).
3. **`must_see` is hard constraint, not soft preference.** Tech Lead system prompt explicitly instructs: "findings with must_see: true ALWAYS included, even if tags don't match."
4. **`unstructured_notes` is Layer 3, not a dump.** It has a specific purpose: meta-reasoning, debate context, caveats. Not for random observations.
5. **ACON rules are per-cycle, not global.** `~/.hermes/plans/<cycle>-filter-rules.json` — each cycle starts with defaults, evolves based on that cycle's failures. Prevents one bad cycle from poisoning all future cycles.
6. **Filter has a hard cap** (`max_findings_per_sw: 15`). Prevents context bloat even if many findings match. Must_see findings always kept first.
