# Requirements Quality Evaluation — Full Research Reference

> Condensed from 3 parallel research agents (2026-06-25): criteria, automated tools, practical gates.
> Full files: `/home/user/requirements_quality_criteria_research.md` (570 lines),
> `/home/user/automated_requirements_checking_research.md` (639 lines),
> `/home/user/practical_requirements_quality_gates_research.md` (429 lines).

## Standards Cross-Reference

### ISO/IEC/IEEE 29148:2018 — Individual Requirement (9 criteria)
1. Necessary, 2. Appropriate (implementation-free), 3. Unambiguous, 4. Complete,
5. Singular, 6. Feasible, 7. Verifiable, 8. Correct, 9. Conforming

### IEEE 830-1998 — SRS Quality (8 characteristics)
Correct, Unambiguous, Complete, Consistent, Ranked, Verifiable, Modifiable, Traceable

### BABOK v3 — Requirements & Designs Quality (9 characteristics)
Atomic, Complete, Consistent, Concise, Feasible, Unambiguous, Testable, Prioritized, Understandable

### IREB/CPRE v3.1 — (10 criteria)
Agreed, Unambiguous, Necessary, Verifiable, Complete, Consistent, Traceable, Feasible, Comprehensible, Rated

### INCOSE GtWR v4 — 42 Rules
3 quality levels, 42 writing rules grouped by characteristic, vague-word dictionaries with examples.

## Requirements Smells Catalog (Femmer et al., 2017, arXiv:1611.08847)

9 smell types mapped to ISO 29148:
1. Subjective language → Unambiguous violation
2. Ambiguous adverbs → Unambiguous violation
3. Loopholes → Complete violation
4. Unverifiable terms → Verifiable violation
5. Superlatives/comparatives → Unambiguous violation
6. Negative statements → Unambiguous violation
7. Indefinite pronouns → Unambiguous violation
8. Incomplete references → Complete violation
9. Compound requirements → Singular violation

## Automated Checking Tools

| Tool | Type | Key Feature | Accuracy |
|------|------|-------------|----------|
| **QuARS** (ISTI-CNR, 2001) | Dictionary + NLP | 7 indicators: optionality, subjectivity, vagueness, weakness, implicity, underspec, multiplicity | — |
| **NASA ARM** (SATC) | Metrics | Imperative form, completeness, weak phrases, size, terminology consistency, continuance | — |
| **Paska** (U. Luxembourg, 2023) | NLP + CNL | Tregex tree patterns, Rimay template recommendations | Precision 89% |
| **SREE** (U. Waterloo) | Dictionary | Recall-prioritized (100%), dangerous terms + Ambiguity Handbook | — |
| **IBM RQA** (Watson) | LLM + INCOSE | Commercial, NLP pipeline + Watson AI | — |
| **ARTA** (M. Zakeri) | ML + Ontology | Testability measurement, domain polysemy detection (10 domains) | — |
| **TAPHSIR** | BERT | Anaphoric ambiguity via coreference resolution | — |
| **LMAdetect** (2026) | Hybrid LLM | Traditional methods + LLM for ambiguity detection | — |

## Automated vs. Human Judgment

**Fully automatable (high precision + recall):**
- Vague, optional, subjective, weak words (dictionary)
- TBD/TBA/etc. incompleteness markers
- Passive voice without actor
- Compound requirements (>1 shall per sentence)
- Missing imperative (no shall/must)
- Pronouns without antecedent

**Partially automatable (needs validation):**
- Anaphoric ambiguity (TAPHSIR)
- Domain polysemy (ARTA)
- Terminology consistency (GUITAR)
- Testability scoring (ARTA)

**Human-only:**
- Correctness (matches real need)
- Coverage completeness (all needs covered)
- Prioritization (business value)
- Feasibility (technical, budget, timeline)
- Business value alignment

## Practical Checklists (from Industry)

### NASA SEH Appendix C — "How to Write a Good Requirement"
Binary pass/fail per characteristic: Necessary? Appropriate? Unambiguous? Complete? Singular? Feasible? Verifiable? Correct? Conforming?

### Fagan Inspection Checklist — 12 Categories
Completeness, Consistency, Correctness, Feasibility, Modifiability, Traceability, Understandability, Maintainability, Verifiability, Clarity, Functionality, Reliability — each with pass/fail questions.

### DO-178C (Avionics) — QRA Corp Best Practices
10 must-follow practices including: atomic requirements, no design in requirements, measurable acceptance criteria, bidirectional traceability.

### IEC 62304 (Medical Devices)
Safety-classification-driven requirements quality: each safety-related requirement must have risk control measure, verifiable by test, traceable to hazard.

## Recommended Implementation for Hermes

```python
# Level 1-2 checks (deterministic, <3s total)
# Run as: python3 ~/.hermes/scripts/requirements_quality_gate.py docs/requirements/<slug>.md

CHECKS = {
    "RQ-VAGUE":    "No vague words (about, almost, approximately, generally, ...)",
    "RQ-OPT":      "No optionality words (if possible, can, may, might, perhaps, ...)",
    "RQ-SUBJ":     "No subjectivity words (easy, fast, reliable, user-friendly, ...)",
    "RQ-INCOMPL":  "No incompleteness markers (TBD, TBA, etc., to be defined)",
    "RQ-SHALL":    "Every requirement contains shall/must",
    "RQ-COMPOUND": "No compound requirements (>1 shall per sentence)",
    "RQ-PASSIVE":  "No passive voice without actor",
    "RQ-SMART":    "Acceptance Criteria contain measurement + threshold",
    "RQ-ACTORS":   "Actors section non-empty",
    "RQ-SCOPE":    "Out of Scope explicitly defined",
    "RQ-NFR":      "NFRs contain numbers (not 'fast' but '<200ms p95')",
    "RQ-LOG":      "Interview Log exists with ≥3 questions",
    "RQ-WHYS":     "5 Whys trace present (≥3 depth levels)",
}
```

Threshold: 1.0 (all checks must pass). FAIL on any → return to Interviewer with specific diagnostic.
