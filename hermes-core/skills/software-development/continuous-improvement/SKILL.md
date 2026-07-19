---
name: continuous-improvement
description: "Post-delivery metrics, retrospectives, tech debt backlog, and principle compliance — output docs/retrospectives/<date>-<slug>.md."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [retrospective, metrics, improvement, tech-debt, iteration]
    related_skills: [build-engineering-standards, deployment-operations, requesting-code-review]
---

# Continuous Improvement

Phase 7 of the build lifecycle. Close the loop: capture what happened,
measure outcomes, and feed lessons into the next cycle.

**Core principle:** without retrospection, the same mistakes repeat. Every
delivery cycle should leave the codebase and process slightly better.

## When to Use

- After Deployment phase completes (mandatory in build lifecycle).
- After incidents, failed deploys, or significant rework.
- At natural milestones (sprint end, feature ship, PR merge).

## Metrics to Capture

Collect what is available — do not block on missing tooling.

| Metric | Source | Why |
|--------|--------|-----|
| Test count / coverage trend | `pytest --cov`, CI artifacts | Quality signal |
| CI duration | GitHub Actions timing | DevEx / APO |
| Security findings (new vs baseline) | `sast-audit` output | Security trend |
| Review findings count | Code review notes | Process quality |
| Incident count | User report / monitoring | Reliability |
| Lines changed / files touched | `git diff --stat` | Scope calibration |
| Principle violations noted | Self-audit | Standards drift |

Snapshot numbers at retro time; trends matter more than absolutes.

## Retrospective Format

### What Worked
- Practices, tools, or decisions that helped.

### What Didn't Work
- Friction, surprises, rework, missed requirements.

### Action Items
- Concrete, owned, time-bound improvements for next cycle.
- Tech debt items → backlog with priority.

### Principle Compliance

Review against `build-engineering-standards` matrix:

| Principle | This cycle | Drift? | Action |
|-----------|------------|--------|--------|
| KISS | [assessment] | yes/no | [if drift] |
| DRY | ... | ... | ... |
| YAGNI | ... | ... | ... |
| BDUF | ... | ... | ... |
| SOLID | ... | ... | ... |
| APO | ... | ... | ... |
| Versioning | ... | ... | ... |

## Tech Debt Backlog

Add items discovered during implementation or review:

```markdown
| ID | Item | Priority | Effort | Source |
|----|------|----------|--------|--------|
| TD-1 | [description] | high/med/low | S/M/L | [retro date / PR] |
```

Do not fix all debt in the same cycle — prioritize for next Requirements phase.

## Output

Save to: `docs/retrospectives/YYYY-MM-DD-<slug>.md`

## Template

```markdown
# Retrospective: [Feature Name]

**Date:** YYYY-MM-DD
**Cycle:** [requirements → deploy summary]
**Links:**
- Requirements: docs/requirements/<slug>.md
- Architecture: docs/architecture/<slug>.md
- Plan: .hermes/plans/<ts>-<slug>.md
- Deployment: docs/deployment/<slug>.md

## Metrics Snapshot

| Metric | Value | Notes |
|--------|-------|-------|
| Tests | [N passing] | |
| Coverage | [%] | |
| CI duration | [Xm Ys] | |
| Security findings (new) | [N] | |
| Files changed | [N] | |

## What Worked

- [Item]

## What Didn't Work

- [Item]

## Action Items

| # | Action | Owner | Target |
|---|--------|-------|--------|
| 1 | [concrete step] | [agent/user] | [next cycle / date] |

## Tech Debt Added / Resolved

| ID | Item | Status |
|----|------|--------|
| TD-1 | [item] | open / resolved |

## Principle Compliance

[Table or narrative — see format above]

## Next Cycle Inputs

- [Requirement to refine]
- [Architecture decision to revisit]
- [Metric to watch]
```

## Gate Checklist (end of lifecycle)

- [ ] Metrics captured (or N/A documented)
- [ ] Retro written with worked / didn't / actions
- [ ] Tech debt items logged
- [ ] Principle drift assessed
- [ ] Document saved at `docs/retrospectives/<date>-<slug>.md`
- [ ] Ready to start next cycle at Requirements if continuing

## Feeding Forward

Action items from the retro become inputs to the **next** Requirements phase:
- Refine scope based on what was over/under-built.
- Update architecture if boundaries proved wrong.
- Add CI or monitoring tasks if deploy phase exposed gaps.
