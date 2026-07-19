# AGENTS.md Pattern — Project Context Extraction

## Problem

Agent files (~/.hermes/agents/*.md) historically contained a **mix** of role instructions and project conventions:

- Build commands repeated across 4+ agents
- Code style (TDD, KISS, DRY) duplicated in 3+ agents
- Environment facts (Jetson, ADB, Python version) in persona + 3+ agents
- Pitfalls (ADB reverse, Gradle cache) in memory only — not in agent files
- SAST commands in security-agent + developer-agent + general/build
- Project structure in 6+ agents

**Result:** changing any project convention requires editing N files. The orchestrator doesn't know the project when entering — agents repeat conventions in every file.

## Solution: AGENTS.md

One file (`~/.hermes/AGENTS.md` or `~/project/AGENTS.md`) is the **single source of truth** for all project-level conventions. Modeled after Claude Code's CLAUDE.md.

### Extraction Principle

| Criterion | → AGENTS.md | → Agent file |
|-----------|:----------:|:-----------:|
| Applies to **any** agent in the project | ✅ | |
| Specific to a **single role** | | ✅ |
| Changes when project/stack/environment changes | ✅ | |
| Stable regardless of project | | ✅ |
| Commands (build, test, lint) | ✅ | |
| Methodology (TDD, RED-GREEN-REFACTOR) | ✅ | |
| Agent personality ("you are architect") | | ✅ |
| Phase-specific logic (Verification Gate) | | ✅ |
| Tool restrictions (no clarify for devs) | | ✅ |
| Escalation chains | ✅ | |
| Artifact formats | ✅ | |
| Environment pitfalls | ✅ | |

### AGENTS.md Structure

```markdown
# AGENTS.md — <Project Name>

## Build & Test Commands
## Code Conventions
## Project Structure
## Documentation Conventions
## Development Lifecycle
## Testing Conventions
## Security Gate
## Architecture Conventions
## Knowledge Sources
## Environment
## Known Pitfalls
```

### Orchestrator Loading (in plan.md)

```
### Project context loading (MANDATORY)

Before Phase 1, read:
1. read_file("~/.hermes/AGENTS.md") — project conventions
2. read_file("~/.hermes/auditor_memory.md") — cross-cycle patterns

When delegating to ANY sub-agent: include relevant AGENTS.md excerpts
in the context field. Minimum: §Known Pitfalls + §Environment.
```

### What Happens to Agent Files

Agents become **thinner and more role-focused**. Each agent keeps:
- Role definition and personality
- Unique methodology (Vane pipeline, 9 stages, etc.)
- Phase-specific responsibilities
- Interaction protocols with other agents
- Prohibitions and tool restrictions

Everything reusable moves to AGENTS.md.

### Agent File Shrinkage Reference

For a 12-agent project: ~115 KB → ~36 KB agent files (-69%), +5 KB AGENTS.md.

Key: methodology IS role-specific and stays in agent files. Only TRULY shared conventions move.

### Pitfall: Don't Over-Extract

Methodology (like Researcher's Vane pipeline, System Analyst's 9 stages) is **role-specific** — it belongs in the agent file, not AGENTS.md. If only one agent uses it, it stays.

Extract only what **≥2 agents** would otherwise duplicate.
