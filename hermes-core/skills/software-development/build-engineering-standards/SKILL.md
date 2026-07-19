---
name: build-engineering-standards
description: "Cross-cutting engineering principles: KISS, DRY, YAGNI, BDUF, SOLID, APO, modularity, versioning — with per-phase checklist matrix."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [engineering, principles, kiss, dry, yagni, bduf, solid, apo, modularity, versioning]
    related_skills: [plan, requirements-analysis, architecture-design, implementation-delivery, continuous-improvement]
---

# Build Engineering Standards

Cross-cutting principles for the full build lifecycle. Load this skill at the
start of non-trivial work and re-check at every phase gate.

**Reference:** [Habr/ITELMA — принципы разработки](https://habr.com/ru/companies/itelma/articles/546372/)

## Principles

### KISS (Keep It Simple, Stupid)

Choose the simplest design and implementation that satisfies requirements.
Avoid clever abstractions, premature frameworks, and speculative generality.

**Check:** Can a new team member understand this in one reading?

### DRY (Don't Repeat Yourself)

Every piece of knowledge has a single, authoritative representation. Duplicate
logic, config, and documentation drift apart and cause bugs.

**Check:** If you change a rule, how many places must you edit?

### YAGNI (You Aren't Gonna Need It)

Implement only what current requirements demand. Do not build hooks, config
knobs, or extension points for hypothetical futures.

**Check:** Is this feature in the requirements doc or an assumption?

### BDUF (Big Design Up Front — applied, not dogmatic)

Invest in Requirements, Architecture, and Plan **before** coding. The depth
scales with risk and complexity — a typo fix gets a one-line plan, a new
service gets full docs.

**Check:** Could an implementer start without asking you clarifying questions?

### SOLID

| Letter | Principle | Practice |
|--------|-----------|----------|
| **S** | Single Responsibility | One reason to change per module/class |
| **O** | Open/Closed | Extend via composition/interfaces, not editing core |
| **L** | Liskov Substitution | Subtypes honor parent contracts |
| **I** | Interface Segregation | Small, focused interfaces — no fat "god" APIs |
| **D** | Dependency Inversion | Depend on abstractions; inject concrete implementations |

**Example (SRP violation → fix):**
```python
# Bad — reports AND persists
class UserService:
    def create_user(self, data): ...
    def send_welcome_email(self, user): ...

# Good — separate responsibilities
class UserRepository: ...
class WelcomeEmailSender: ...
```

### Root Cause over Band-Aids (RCBA)

When a symptom appears, fix the **root cause**, not the presentation.
Cosmetic fixes (system prompts, client-side filters, hardcoded workarounds)
mask problems and create tech debt that compounds across sessions.

**Check:** Does this fix address WHY the problem exists, or just HOW it looks?

**Real example (16-25h wasted):**
- Symptom: LLM doesn't know it's Hermes Agent
- Band-aid (rejected): `"You are Hermes"` system prompt in ChatViewModel.kt
- Root cause: Hermes Gateway API not running (port 8643 occupied by proxy)
- Fix: Kill proxy, launch `hermes gateway run` — now Hermes IS Hermes

**Orchestrator enforcement:** when a sub-agent proposes a band-aid, escalate to
System Analysis (Phase 2) or Verification Gate (Phase 6.5). Never accept
cosmetic patches that leave the root cause unaddressed.

### APO (Avoid Premature Optimization)

Make it work, make it right, make it fast — in that order. Optimize only when
measurements show a real bottleneck.

**Check:** Do you have a profile or benchmark, or just a hunch?

### Occam's Razor

When two designs meet requirements equally, prefer the one with fewer moving
parts, fewer dependencies, and fewer concepts.

### Modularity

- Clear module boundaries with explicit public APIs.
- Minimize coupling; prefer events/interfaces over shared mutable state.
- One module = one responsibility (SRP at package level).
- Document what crosses boundaries (protocols, schemas, error contracts).

### Versioning & Reproducibility

- **Dependencies:** lockfiles (`package-lock.json`, `poetry.lock`,
  `requirements.txt` with hashes, `uv.lock`).
- **Containers:** pinned image tags or digests in compose/Dockerfile.
- **Environment:** documented `.env.example` — never commit secrets.
- **Build/run:** documented commands that work on a clean checkout.
- **APIs:** semantic versioning for published interfaces; deprecation policy.

## Principle × Phase Matrix

Use this at each gate. Mark ✅ when satisfied or N/A with justification.

| Principle | Req | Arch | Plan | Impl | Qual | Deploy | Iter |
|-----------|-----|------|------|------|------|--------|------|
| KISS | Scope minimal | Simplest viable pattern | Tasks bite-sized | No cleverness | No scope creep in review | Simplest ship path | Retro: complexity added? |
| DRY | No duplicate reqs | Single integration map | No repeated steps | Extract shared logic | No copy-paste in diff | Reuse CI templates | Debt from duplication |
| YAGNI | Out-of-scope listed | No speculative services | No future tasks | No unused code | No dead code merged | No unused infra | YAGNI violations logged |
| BDUF | Req before arch | Arch before plan | Plan before code | Follow plan | Matches spec | Matches deploy doc | Lessons → next BDUF |
| SOLID | Actors separated | Bounded contexts | Module per task | SRP in code | Interface contracts | Deploy units = modules | Modularity score |
| APO | NFRs measured not guessed | Capacity estimates | No perf micro-tasks early | Profile before optimize | Perf tests if NFR | Right-size resources | Metrics drive optimize |
| Modularity | Feature boundaries | Component diagram | File map per task | Clean imports | Coupling review | Independent deploy units | Boundary violations |
| Versioning | Stack constraints | Pinned dep policy | Lockfile tasks | Lockfiles updated | Audit clean | Image/tag pins | Dep drift tracked |

**Legend:** Req = Requirements, Arch = Architecture, Impl = Implement, Qual = Quality, Deploy = Deployment, Iter = Iterate.

## Phase-Specific Prompts

### Requirements
- What is the **smallest** scope that delivers value?
- What is explicitly **out of scope**?

### Architecture
- What is the **simplest** topology that meets NFRs?
- Where are module boundaries and integration contracts?

### Plan
- Does each task map to **one** module/responsibility?
- Are lockfile and `.env.example` updates included if deps change?

### Implement
- Am I duplicating logic that exists elsewhere?
- Does this module have **one** reason to change?

### Quality
- Does the diff introduce coupling or god objects?
- Are new deps pinned and audited?

### Deployment
- Is the deploy path the **simplest** that meets ops needs?
- Are logs structured? Correlation IDs where async?

### Iterate
- Which principles drifted this cycle?
- What tech debt items go on the backlog?

## Quick Self-Audit (before any gate)

```
[ ] Simplest solution that meets requirements (KISS + Occam)
[ ] No duplicated logic or docs (DRY)
[ ] No speculative features (YAGNI)
[ ] Design artifacts exist before code (BDUF)
[ ] Modules have single responsibility (SOLID-S)
[ ] No optimization without measurement (APO)
[ ] Lockfiles and .env.example current (Versioning)
```
