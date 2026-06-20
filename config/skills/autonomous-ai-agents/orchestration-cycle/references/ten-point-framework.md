# 10-Point Code Agent Improvement Framework

> Full catalog of improvements implemented across Hermes agent files.
> Design docs: `/home/user/dev/global_changes/`
> Agent files: `~/.hermes/agents/*.md`

## Implementation Summary

| # | Improvement | Source | Files Changed | Key Change |
|---|------------|--------|---------------|------------|
| 1 | AGENTS.md migration | Claude Code | NEW: `~/.hermes/AGENTS.md`, 10 agent files trimmed | Single source of truth for project conventions. Auditor auto-applies safe changes. |
| 2 | Repository Map (Phase 0) | Aider | `plan.md`, `developer-agent.md` | Isolation dir at `/home/user/dev/codemes/{pid}/`. structure.md auto-gen. |
| 3 | Edit→Lint→Test cycle | Aider, SWE-Agent | `developer-agent.md` §1 | 5-step cycle with lint BEFORE tests. |
| 4 | Git safety net | Claude Code, Aider | `developer-agent.md` §0 | Pre-edit snapshot. Rollback: `git checkout -- .` |
| 5 | Self-correction 3 attempts | Aider | `developer-agent.md` | 3 attempts max, change approach each time. |
| 6 | Reality check | Aider, Claude Code | `plan.md` oversight table | Orchestrator verifies subagent claims via `terminal`. |
| 7 | Module Contracts | Aider | `architect-agent.md`, `developer-agent.md` | §Module Contracts table in every architecture doc. |
| 8 | Artifact validation | OpenCode+ | `plan.md` | Grep-check required sections before accepting artifacts. |
| 9 | READ/WRITE-ONLY split | OpenCode+ | `researcher.md`, `developer-agent.md` | Researcher: never write code. Developer: never search externally. |
| 10 | Curated skills catalog | Codex CLI | NEW: `skills/.curated/index.json` | 15 skills indexed with categories and descriptions. |

## Design Docs Catalog

All in `/home/user/dev/global_changes/`:

| File | Lines | Contains |
|------|:-----:|----------|
| `hermes-md-migration.md` | ~600 | Full AGENTS.md spec, Auditor Evolution Driver, EvoAgentX patterns |
| `repository.md` | 425 | Phase 0 bootstrap, structure.md format, worktree isolation |
| `edit-lint-test-cycle.md` | ~50 | 5-step cycle spec with lint integration |
| `git-safety-net.md` | ~200 | Pre-edit snapshot, worktree merge protocol, rollback |
| `self-correction-loops.md` | ~50 | 3-attempt loop with approach variation |
| `orchestrator-reality-check.md` | ~50 | Post-delegate verification rules |
| `architect-editor-contracts.md` | ~50 | Module Contracts table format |
| `artifact-validation.md` | ~50 | Required sections per artifact type |
| `stateless-stateful-separation.md` | ~50 | READ-ONLY and WRITE-ONLY rules |
| `curated-skills.md` | ~50 | Skills catalog format |

## Agent File State

After all 10 improvements, agent files contain ONLY role-specific instructions.
Project conventions → `~/.hermes/AGENTS.md` (loaded at Phase 0).

Backup: `~/.hermes/agents.backup-20260613_210841/`

## New Files Created

| File | Purpose |
|------|---------|
| `~/.hermes/AGENTS.md` | Project conventions (build, env, pitfalls, conventions) |
| `~/.hermes/auditor_memory.md` | Cross-cycle auditor memory (append-only) |
| `~/.hermes/skills/.curated/index.json` | 15 skills catalog |
| `/home/user/dev/global_changes/*.md` | 10 design docs |
