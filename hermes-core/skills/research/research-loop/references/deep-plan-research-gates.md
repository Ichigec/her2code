# Deep Plan Research — Gate Script Catalog

> Created: 2026-06-24 | S1–S5 implementation | 5 gates (0 + A–D)

## Script Inventory

| Gate | Script | Exit Code |
|------|--------|-----------|
| B: Source Quality | `~/.hermes/scripts/research_quality_gate.py` | 0=PASS, 1=FAIL |
| C: Completeness | `~/.hermes/scripts/research_completeness_gate.py` | 0=PASS, 1=FAIL |
| D: Citation Enforcement | `~/.hermes/scripts/citation_enforcement_gate.py` | 0=PASS, 1=FAIL |
| All (B+C+D) | `~/.hermes/scripts/orchestrator_gate.py` — `research_deep` check | orchestrated |

## GATE B: Source Quality (`research_quality_gate.py`)

5 Anthropic-style criteria scored 0.0–1.0 each, average ≥ 0.6 to pass:

```
factual_accuracy  — avg source matrix score normalized to 0-1
citation_accuracy — citation density × 0.7 + URL presence × 0.3
completeness      — required sections % minus TBD penalty
source_quality    — avg(authority scores)/2 × 0.6 + avg(recency scores)/2 × 0.4
tool_efficiency   — domain diversity × 0.4 + source type diversity × 0.6
```

Usage: `python3 research_quality_gate.py --artifact <path> [--json] [--threshold 0.6]`

## GATE C: Completeness (`research_completeness_gate.py`)

5 structural checks:

1. **RQ Coverage** — every RQ has an answer (no TBD/unknown)
2. **Citation Mapping** — ≥80% paragraphs in `## RQ Answers` section have `[N]` citations
3. **Artifact Structure** — required sections present (RQ Answers, Source Quality Matrix, heading)
4. **Source Diversity** — ≥3 source types OR ≥5 unique domains
5. **Artifact Size** — >2000 bytes AND >300 words

Usage: `python3 research_completeness_gate.py --artifact <path> [--json]`

## GATE D: Citation Enforcement (`citation_enforcement_gate.py`)

Checks:
1. ≥90% claims have `[N]` citations
2. ≥90% citations valid (random 20% sample curl-verified)
3. ≤10% ungrouped sequential same-source blocks
4. Groups consecutive same-source facts → single `[N]` at end

Usage: `python3 citation_enforcement_gate.py --artifact <path> [--verify-sample 20] [--json]`

## Orchestrator Integration

`orchestrator_gate.py` runs all three as the 7th check (`research_deep`):

```python
def check_research_deep(self):
    # Finds latest docs/research/*.md
    # Runs research_quality_gate.py --json
    # Runs research_completeness_gate.py --json
    # Runs citation_enforcement_gate.py --verify-sample 20 --json
    # Reports PASS only if all three pass
```

Pre-Flight Gate now has 7 checks (was 6): contracts, ports, env_vars, isolation, observers, research, research_deep.

## Bug Fix History (S5)

### Bug 1: RQ Coverage false positive (GATE C, check 1)

**Symptom:** Script matched "RQ" substring in table header rows, counting them as RQ identifiers.

**Fix:** Added `in_rq_table` state machine — only counts RQs inside `Research Questions` table body rows (lines starting with `|` that contain digits, excluding header/separator rows).

```python
# Before: line.startswith("|") and "RQ" in line → false match on table headers
# After: in_rq_table flag set only when "Research Questions" heading found,
#        then only rows with digits counted as RQ ids
```

### Bug 2: Citation Mapping counting wrong sections (GATE C, check 2)

**Symptom:** Script counted all substantive paragraphs after `## RQ Answers` — including `### Source Quality Matrix`, `### Debate Resolution`, `### Cross-References`, `### Developer Handoff` paragraphs that don't need citations.

**Fix:** Stop paragraph collection at section boundaries. Detect `### Source Quality Matrix` and `### Debate` as RQ Answers section end markers.

```python
# Before: elif in_answers and line.startswith("## ") and "RQ Answers" not in line: break
# After:  elif in_answers and (line.startswith("## ")
#             or line.startswith("### Source Quality Matrix")
#             or line.startswith("### Debate")) and "RQ Answers" not in line: break
```

### Bug 3: Paragraph-level citation detection (GATE C, check 2)

**Symptom:** Line-by-line citation check counted short fragments as paragraphs.

**Fix:** Buffer lines into paragraph groups (delimited by blank lines). Only count as a paragraph if accumulated text >80 chars. Check for `[N]` pattern at paragraph level, not line level.

## Agent Files Created (S1–S4)

| File | Role | Src |
|------|------|-----|
| `~/.hermes/agents/deep-plan-researcher.md` | Primary agent: plan2 Phase 3 + standalone | S1 |
| `~/.hermes/agents/research/citation-agent.md` | GATE D: citation verification | S1 |
| `~/.hermes/agents/research/codebase-analyzer.md` | Optional: Neo4j codebase graph | S3 |
| `~/.hermes/agents/research/education-graph-analyzer.md` | Optional: Neo4j Education Graph | S3 |
| `~/.hermes/agents/research/debate-agent.md` | Debate mode: alternative RQ perspective | S3 |
| `~/.hermes/agents/researcher_old.md` | Renamed from researcher.md (deprecated) | — |

## Registry

`~/.hermes/agents/registry.json` — 37 agents. Auto-regenerated via `python3 ~/.hermes/scripts/agent_registry.py`.
