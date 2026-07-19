# Business Analysis Knowledge Bank

Condensed from a 5-angle parallel fan-out research (2026-06-24).
Full research files at `/home/user/BA_COMPREHENSIVE_RESEARCH.md` and 5 angle reports.

## BABOK v3 — 6 Knowledge Areas (IIBA, 2015)

1. **Business Analysis Planning & Monitoring** — approach, governance, metrics
2. **Elicitation & Collaboration** — interviews, workshops, observation, surveys
3. **Requirements Life Cycle Management** — traceability, prioritization, change control
4. **Strategy Analysis** — current/future state analysis, risk assessment
5. **Requirements Analysis & Design Definition** — modeling, verification, specification
6. **Solution Evaluation** — KPI, ROI, value assessment

## BACCM — 6 Core Concepts

Change → Need → Solution → Stakeholder → Value → Context

## BA Lifecycle — 7 Stages

1. Initiation (SWOT, PESTLE, MOST) → Business Case
2. Elicitation (interviews, workshops) → Raw requirements
3. Analysis (BPMN, UML, MoSCoW) → Requirements models
4. Specification (BRD, SRS, User Stories) → Requirements doc
5. Validation (review, prototyping) → Confirmed requirements
6. Management (Change Control, RTM) → Traceable requirements
7. Evaluation (KPI, ROI) → Value assessment

## AI BA Agent Landscape (2025-2026)

Key OSS projects:
- **4D-ARE** (181★) — Attribution-Driven Agent RE, MCP-compatible
- **Agile V Skills** (47★) — REQ→ART→TC traceability, ISO 9001/27001
- **spec2ship** (30★) — 12-agent spec-driven development, arc42/ISO 25010
- **C-LEIA** — LLM stakeholder simulation for requirements training
- **agentic-system-architect** (IEEE SW 2025) — Five Whys + Capability Partitioning

Architectural patterns:
- **Multi-Agent Collaboration** (CrewAI, LangGraph, AutoGen)
- **Persona-Driven Stakeholder Simulation** (C-LEIA, WorkplaceSim)
- **Capability Partitioning** — LLM for dialogue, deterministic system for traceability
- **MCP integrations** — elm-mcp (IBM DOORS), 4D-ARE

Key paper: "Agentic Architecture Mediation for LLM Assistants" (IEEE Software 2025) —
Capability Partitioning prevents solution-jumping and hallucinations.

## Interview Mechanisms for AI Agents

6 AI interviewer design patterns:
1. **Persona Design** — adopt stakeholder role (User Advocate, Developer, Security Officer, PO)
2. **Adaptive Questioning** — SPIN funnel: Situation → Problem → Implication → Need-Payoff
3. **Comprehension Verification** — paraphrase every answer, confirm understanding
4. **Context Management** — maintain full dialogue history, detect contradictions
5. **Multimodality** — support text + voice + diagrams
6. **Escalation/Handoff** — detect when AI reaches its limit, escalate to human

Conversational RE Protocol (6-phase dialogue flow):
```
Opening → Context Gathering → As-Is Analysis → Problem Deep-Dive → To-Be Vision → Closing
```

## Pre-hoc Requirements Quality Evaluation

For evaluating requirements quality BEFORE development: standards cross-reference (ISO 29148, IEEE 830, BABOK, IREB, INCOSE), requirements smells word dictionaries (vagueness, optionality, subjectivity, weakness, incompleteness), structural checks (passive voice, compounds, pronouns), and the 5-level hybrid checking architecture. See `references/requirements-quality-evaluation.md`.

## Our System's Requirements Infrastructure

Agents:
- `requirements-agent.md` — basic requirements collector (5 mandatory question areas)
- `requirements-interviewer.md` — structured interviewer (SPIN, 5 Whys, SMART, personas)
- `system-analyst.md` — goal keeper, Verification Gate (Phase 6.5)

Gates:
- Structural validation (orchestrator, post-Phase 1) — artifact section completeness
- Pre-Flight Gate (`orchestrator_gate.py`, Phase 5.5) — 7 checks including research
- System Analyst Verification (Phase 6.5) — 4 checks (spec, goals, root cause, abstraction)
- **BusinessAnalysisGate** (ROOT MANDATORY, Phase 7+) — code + test + security + acceptance per REQ
- Deep Research gates: B (Source Quality), C (Completeness), D (Citations)

## Key References

- BABOK v3: iiba.org
- CBAP Study Guide: doi:10.1201/9781315367347
- Palomares et al. (2021): arXiv:2102.11556
- IEEE RE 2021: Typology of Questions for RE Interviews
- IEEE RE 2024: GPT-Powered Elicitation Interview Script Generator
- IEEE Software 2025: Agentic Architecture Mediation
- Scheinholtz & Wilmont (2011): Interview Patterns for RE
- 4D-ARE: arXiv:2601.04556, github.com/ybeven/4D-ARE
