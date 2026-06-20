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
