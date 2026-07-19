---
name: implementation-delivery
description: "Implement modules with SRP, manage deps/lockfiles, integration tests, documentation contract, reverse engineering, and deep technical analysis."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [implementation, delivery, documentation, integration-tests, reverse-engineering, technical-analysis]
    related_skills: [test-driven-development, secure-coding, build-engineering-standards, architecture-design, plan]
---

# Implementation Delivery

Phase 4 companion skill. Guides how to implement, document, and analyze code —
not just make tests pass.

**Core principle:** the deliverable includes code **and** docs that let another
agent reproduce the solution without chat history.

## When to Use

- During Implement phase of the build lifecycle.
- When working with legacy code (reverse engineering).
- When producing a deep technical analysis of an existing system.

## Component Development

### One Module, One Responsibility

- Each file/package/module changes for **one reason**.
- Public API is minimal; internals are private.
- Cross-module communication via defined interfaces (SOLID-D).

### Dependency Management

- Add deps only when justified (YAGNI).
- Update lockfiles in the same change as manifest edits.
- Run audit tools (`pip-audit`, `npm audit`) on new deps.
- Pin versions; document why unpinned if exception.

### Integration Testing

Unit tests are necessary but not sufficient:

- Test component boundaries with real (or realistic fake) dependencies.
- Cover happy path + primary error paths across integrations.
- Name tests by behavior: `test_create_user_returns_409_when_email_exists`.

## Documentation Contract

Create **one primary doc** per feature that an agent can use to reproduce
the solution:

**Path:** `docs/<feature>/README.md` **or** `docs/adr/NNNN-<slug>.md`

### Required Sections

```markdown
# [Feature Name]

## Goal
[One paragraph: what this delivers]

## Context
[Why it exists; link to requirements and architecture docs]

## Architecture Summary
[2-5 sentences or diagram reference]

## File Map
| Path | Purpose |
|------|---------|
| `src/...` | [what it does] |

## Setup
[Prerequisites, env vars from .env.example]

## Run
[Exact commands]

## Test
[Exact commands with expected output]

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| [choice] | [why] |

## Security Notes
[Auth boundaries, secrets handling, input validation]
```

An agent reading only this doc should be able to set up, run, test, and
understand the design without the original conversation.

## Reverse Engineering (Legacy Code)

When modifying or extending code you did not write:

1. **Explore** structure: entry points, data flows, key abstractions.
2. **Document findings** in `docs/reverse-engineering/<slug>.md`.
3. Do not change behavior until you understand existing contracts.

### Reverse Engineering Template

```markdown
# Reverse Engineering: [System/Module]

**Date:** YYYY-MM-DD
**Scope:** [what was analyzed]

## Overview
[What this code does]

## Entry Points
| Entry | Type | Description |
|-------|------|-------------|
| `path/to/file` | CLI/API/cron | [purpose] |

## Component Map
[Diagram or table of modules and dependencies]

## Data Flows
1. [Input] → [Processing] → [Output]

## Hidden Assumptions
- [Undocumented behavior discovered]

## Risks
- [Fragile areas, missing tests, tech debt]

## Recommendations
- [Safe change order, what to test first]
```

## Deep Technical Analysis

Structured output when analyzing a system (audit, spike, or pre-refactor):

```markdown
# Technical Analysis: [Subject]

## Components
[Inventory with responsibilities]

## Data Flows
[Sequence or diagram]

## Dependencies
[Internal and external, with versions]

## Risks
| Risk | Severity | Evidence |
|------|----------|----------|

## Recommendations
[Prioritized, actionable]

## Open Questions
[Items needing stakeholder input]
```

## Implement Phase Checklist

- [ ] Plan task followed; TDD cycle per task
- [ ] Lockfiles updated if deps changed
- [ ] Modules respect SRP; no god objects
- [ ] Integration tests for cross-boundary behavior
- [ ] Documentation contract written or updated
- [ ] `.env.example` updated for new config
- [ ] Legacy findings documented (if applicable)
- [ ] `secure-coding` checkpoint audit clean on delta
