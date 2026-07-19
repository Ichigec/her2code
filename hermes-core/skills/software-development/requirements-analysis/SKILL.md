---
name: requirements-analysis
description: "Gather and refine business requirements, use cases, NFRs, and constraints — output docs/requirements/<slug>.md."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [requirements, analysis, use-cases, nfr, scoping, bduf]
    related_skills: [build-engineering-standards, architecture-design, plan]
---

# Requirements Analysis

Phase 1 of the build lifecycle. Transform a user request into a clear,
testable requirements document **before** architecture or implementation.

**Core principle:** ambiguous requirements produce rework. Ask early, document
assumptions explicitly.

## When to Use

- Start of any non-trivial build task (mandatory in build agent lifecycle).
- When scope, actors, or acceptance criteria are unclear.
- When the user says "build X" without specifying constraints.

**Compress but do not skip** for trivial tasks — a short requirements note is
still required.

## Discovery Questions

Ask the user (via `clarify` or direct questions) until you can write the doc:

### Business
- What problem does this solve? Who benefits?
- What does "done" look like? Acceptance criteria?
- What is **out of scope**?

### Actors & Use Cases
- Who are the actors (users, systems, agents)?
- Primary user journey — happy path and key alternates?

### Non-Functional Requirements (NFRs)
- **Performance:** latency, throughput, data volume?
- **Security:** auth, data classification, compliance?
- **Availability:** uptime, disaster recovery?
- **Scalability:** expected growth, multi-tenant?

### Constraints
- Budget, timeline, team skills?
- Required tech stack or forbidden technologies?
- Compliance (GDPR, SOC2, internal policies)?
- Integration with existing systems?

## Scoping with KISS / YAGNI

- Propose the **minimum viable scope** that meets the stated goal.
- List deferred features explicitly under "Future / Out of Scope".
- Challenge requirements that add complexity without clear value.

## Output

Save to: `docs/requirements/<slug>.md`

Create `docs/requirements/` if it does not exist. Use a short kebab-case slug
derived from the feature name.

## Template

```markdown
# Requirements: [Feature Name]

**Status:** draft | approved
**Date:** YYYY-MM-DD
**Author:** build agent (+ user input)

## Problem Statement

[1-3 sentences: what problem, for whom, why now]

## Goals

- [ ] Goal 1
- [ ] Goal 2

## Out of Scope

- [Explicitly excluded item]
- [Deferred to future iteration]

## Actors

| Actor | Description |
|-------|-------------|
| [User type] | [Role and needs] |
| [System] | [Integration role] |

## Use Cases

### UC-1: [Name]

- **Actor:** [who]
- **Preconditions:** [state before]
- **Main flow:**
  1. [Step]
  2. [Step]
- **Postconditions:** [state after]
- **Alternates / errors:** [if relevant]

### UC-2: [Name]

[Repeat as needed]

## Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | [The system shall ...] | must |
| FR-2 | [...] | should |

## Non-Functional Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Performance | [e.g. p95 latency] | [< 200ms] |
| Security | [e.g. auth method] | [OAuth2 / mTLS] |
| Availability | [e.g. uptime] | [99.9%] |
| Scalability | [e.g. concurrent users] | [N] |

## Constraints

- **Timeline:** [if known]
- **Tech stack:** [required / forbidden]
- **Compliance:** [if any]
- **Budget:** [if relevant]

## Assumptions

- [Assumption 1 — validate with user if unconfirmed]
- [Assumption 2]

## Open Questions

- [ ] [Question needing user answer]

## Acceptance Criteria

- [ ] [Testable criterion 1]
- [ ] [Testable criterion 2]
```

## Quality Gates for Requirements

Three layers of gates validate requirements across the build lifecycle:

### Layer 1: Artifact Completeness (Orchestrator, post-Phase 1)
After the Requirements Agent produces `docs/requirements/<slug>.md`, the orchestrator verifies:
- `## SMART Goal` section present
- `## Actors` section present
- `## Acceptance Criteria` with measurable thresholds
- `## Constraints` section present
- `## NFRs` section present
- `## Out of Scope` section present

Missing sections → artifact rejected → agent re-does the phase.

### Layer 2: System Analyst Verification (Phase 6.5)
After implementation, the System Analyst (`~/.hermes/agents/system-analyst.md`) checks:
1. **Spec conformance** — does the code match the requirements spec?
2. **Goal tree alignment** — are sub-goals achieved? No YAGNI creep?
3. **Root cause resolved** — was the root cause fixed, or only the symptom?
4. **Correct abstraction level** — was the fix at the right layer?

FAIL → deviation routing: scope mismatch → Phase 2, architecture → Architect, implementation → Developer, acceptance → Tester.

### Layer 3: BusinessAnalysisGate (ROOT MANDATORY, Phase 7+)
`~/.hermes/gates/gates/business_analysis_gate.py` — runs inside `quality_gate_runner.py`. Cannot be disabled. Threshold = 1.0. For EVERY requirement in `traceability.yaml`, verifies:
- `BA-CODE` — `code_paths` non-empty (implementation exists)
- `BA-TEST` — `test_ids` non-empty (tests exist)
- `BA-SEC` — `security_checks` non-empty (security reviewed)
- `BA-AC` — `acceptance_criteria` → `acceptance_test_ids` non-empty (acceptance tests)

Any single requirement failing any check → **entire cycle BLOCKED**. Fix agent auto-assigned: developer (code/test), security (SEC), tester (acceptance).

Pre-Phase-6 gating: `orchestrator_gate.py` (`~/.hermes/scripts/`) checks 7 conditions including `research` (>500-byte artifact) and `research_deep` (GATES B/C/D) — FAIL blocks Implementation.

## Structured Interviewing (Requirements Interviewer)

For complex requirements, prefer **Requirements Interviewer** (`~/.hermes/agents/requirements-interviewer.md`) over the basic Requirements Agent. It uses a 6-phase interview methodology:

```
CLASSIFY → ELICIT → PROBE → CLARIFY → SMART-IFY → CONSOLIDATE
```

Key techniques available: **SPIN** (Situation→Problem→Implication→Need-Payoff), **5 Whys** (root cause), **Socratic questioning** (contradictions), **GROW** (Goal→Reality→Options→Will). Rules: max 2 questions per turn, always paraphrase before next question, never accept «да» without clarification, 5 Whys capped at 5 iterations.

See `references/question-catalog.md` for ~40 template questions across 6 categories (Context, As-Is, Problems, To-Be, Constraints, Stakeholders).

## Pre-hoc Requirements Quality Evaluation (PHASE 1 GATE)

**Critical gap identified (2026-06-25):** our system has 3 layers of post-hoc gates but NO pre-hoc gate that verifies requirements quality BEFORE they enter development. Requirements with vague words («быстро», «удобно», «много») pass Phase 1 and fail only at Phase 6.5 or 7, wasting the entire cycle. The gate below closes this gap.

### Quality Criteria (ISO 29148:2018 — 9 characteristics)

Every individual requirement must pass all 9. The most automatable:

| # | Criterion | FAIL if... | Automated? |
|---|----------|-----------|:----------:|
| 3 | **Unambiguous** | Vague/optional/subjective words present; multiple interpretations possible | ✅ Full |
| 4 | **Complete** | TBD/TBA/etc. markers; missing subject/object | ✅ Partial |
| 5 | **Singular** | Multiple `shall`/`must` in one sentence; compound with `and`/`or` | ✅ Full |
| 7 | **Verifiable** | No measurement + threshold; «удобно»/«быстро»/«надёжно» without numbers | ✅ Full |
| 9 | **Conforming** | Violates org template/style/terminology standards | ✅ Full |
| 1 | **Necessary** | Not traced to a business goal | ⚠️ Human |
| 2 | **Appropriate** | Describes HOW not WHAT (implementation detail) | ⚠️ Human |
| 6 | **Feasible** | Technically impossible | ⚠️ Human |
| 8 | **Correct** | Doesn't match real stakeholder need | ⚠️ Human |

### Requirements Smells — Instant-Automatable Word Dictionaries

These are the QuARS/NASA/INCOSE dictionaries. Every word in the requirement that matches = FAIL or WARN depending on context.

**VAGUENESS (must FAIL):** `about`, `almost`, `approximately`, `generally`, `in general`, `large`, `mostly`, `near`, `nearly`, `normally`, `quite`, `relatively`, `roughly`, `several`, `small`, `typically`, `usually`, `very`, `virtually`

**OPTIONALITY (must FAIL):** `if possible`, `if needed`, `if necessary`, `where possible`, `can`, `may`, `might`, `optionally`, `perhaps`, `either...or`

**SUBJECTIVITY (must FAIL):** `adequate`, `easy`, `efficient`, `fast`, `flexible`, `good`, `intuitive`, `reliable`, `robust`, `seamless`, `simple`, `user-friendly`, `sufficient`, `suitable`, `appropriate`, `proper`, `reasonable`, `satisfactory`, `scalable`, `extensible`, `maintainable`, `portable`, `secure`, `usable`, `well`, `bad`, `poor`, `excellent`, `nice`

**WEAKNESS (must FAIL):** `as required`, `as appropriate`, `as a minimum`, `be able to`, `be capable of`, `capability of`, `should` (instead of `shall`/`must`), `provide for`, `normal`, `effective`

**INCOMPLETENESS (must FAIL):** `TBD`, `TBA`, `etc.`, `and so on`, `to be defined`, `to be determined`

### Structural Checks (Regex + NLP)

- **Passive voice without actor:** «Данные должны быть сохранены» → FAIL (who saves?)
- **Compound requirements:** >1 `shall`/`must` per sentence → FAIL (split into N requirements)
- **Pronouns without antecedent:** «их запросы», «этот процесс» → WARN
- **No imperative:** missing `shall`/`must` → FAIL (not a requirement, just a statement)
- **Long sentences:** >40 words → WARN (probably compound or unclear)

### 5-Level Hybrid Checking Architecture

```
Level 1 — Regex + Dictionaries (Python, <100ms): vagueness, optionality,
         subjectivity, weakness, incompleteness, shall/must presence
Level 2 — NLP Structural (spaCy, 1-3s): passive voice, compounds, pronouns,
         missing subjects/objects
Level 3 — ML Classification (BERT, 5-30s): context-aware smell detection
         (Bi-LSTM ~90% accuracy), domain polysemy
Level 4 — LLM Analysis (30-120s): semantic contradictions, coverage gaps,
         alternative formulation suggestions
Level 5 — Human Expert: correctness, prioritization, feasibility, business value
```

Levels 1-2 are deterministic (Python, NOT LLM) and should run as a mandatory pre-hoc gate. Levels 3-4 are advisory (suggestions, not gates).

### Integration with Hermes

The pre-hoc gate runs as a Python script (`~/.hermes/scripts/requirements_quality_gate.py`) implementing Levels 1-2. It reads `docs/requirements/<slug>.md`, runs all dictionary + structural checks, and returns pass/fail per requirement. FAIL on any check → return to Interviewer with specific diagnostic (e.g. «REQ-03: слово 'быстрой' — замени на '<200ms p95 при 1000 RPS'»).

Full research: `references/requirements-quality-evaluation.md`.

## Research Bank

For domain-specific requirements research (BABOK, elicitation techniques, BA patterns, interview frameworks, AI BA agent landscape), see `references/business-analysis-knowledge-bank.md`.

## Pitfalls

### Scope creep into future phases
- **Phase 1 requirements are for the CURRENT increment only.** If the roadmap has Phases A/B/C, the Requirements document should primarily cover Phase A. Phase B (Skill Factory Agent) and Phase C (Topology Evolution) should appear ONLY as deferred items in Out of Scope, not as full FRs/ACs with detailed acceptance criteria.
- **Do NOT copy general project constraints from AGENTS.md into the Requirements document.** Constraints like "Python 3.12.3", "SQLite WAL mode", "HMAC-SHA256" that apply to ALL Hermes projects belong in AGENTS.md. The Requirements document should contain ONLY constraints specific to this feature.
- **Thresholds in Acceptance Criteria require data, not round numbers.** Avoid: "≥5 tasks", "≥10% improvement", "≥5% degradation over 3 cycles". These are arbitrary without baseline measurements. Instead write: "Thresholds TBD based on baseline metrics collected in first 3-5 evolution cycles. Initial hypothesis: ≥5 tasks, ≥10% improvement." This prevents the Architecture/Plan phases from treating hypotheses as fixed gates.

### Duplication
- **Do NOT duplicate NFRs as FRs.** If NFR-03 says "overhead <20%", do not create FR-17 with the same content. One source of truth.
- **Do NOT close Open Questions prematurely.** Questions like "which representative tasks" and "which metrics are primary" should remain open in Requirements — they are answered in System Analysis, not Requirements.

### Research-first ordering
- When research was completed BEFORE requirements (by user request), the Requirements document MUST reference the research artifact and trace every FR back to a specific research finding. Generic traceability is not enough — use the format `FR-04 ← Research §10.1 Finding 2 (Sandbox Validation gap)`.

Before proceeding to Architecture:

- [ ] Problem statement and goals are clear
- [ ] At least one use case with acceptance criteria
- [ ] NFRs captured or explicitly marked N/A
- [ ] Out-of-scope items listed (YAGNI)
- [ ] Open questions resolved or recorded as assumptions
- [ ] Document saved at `docs/requirements/<slug>.md`
