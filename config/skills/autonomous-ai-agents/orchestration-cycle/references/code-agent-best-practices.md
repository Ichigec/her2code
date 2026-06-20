# Code Agent Best Practices — Research (2026-06-13)

Research conducted across Claude Code, Aider, Codex CLI, SWE-Agent, Cursor,
and OpenCode+ to identify patterns that improve agent reliability.
Findings below are ready for adaptation into Hermes.

## Sources analyzed

| Agent | Key insight | Adaptable? |
|-------|------------|:---:|
| **Claude Code** | CLAUDE.md — per-project instructions auto-loaded | ✅ HERMES.md |
| **Aider** | Architect/Editor model split; Repomap for context; Edit→Lint→Test cycle | ✅ Already partial |
| **Codex CLI** | Skills ecosystem (YAML frontmatter + MD body) — identical format to Hermes | ✅ Already matches |
| **SWE-Agent** | Think→Act→Observe cycle; Agent-Computer Interface (structured commands) | ✅ Developer loop |
| **Cursor** | .cursorrules per-project; Apply/diff model | ✅ HERMES.md |
| **OpenCode+** | AGENTS.md runbook; Stateless writer + Stateful reader; Pipeline with hard invariants; Audit trail (log.jsonl); Schema enforcement | ✅ Already partial |

## Top 10 improvements for Hermes

### Status: 7 of 10 implemented (2026-06-13)

| # | Improvement | Status | Implemented in |
|---|-----------|:------:|---------------|
| 1 | HERMES.md auto-load | 📋 Designed | `global_changes/hermes-md-migration.md` |
| 2 | Repository Map (Phase 0) | 📋 Designed | `global_changes/repository.md` |
| 3 | Edit→Lint→Test cycle | ✅ **Active** | `developer-agent.md` §1 |
| 4 | Git safety net | 📋 Designed | `global_changes/git-safety-net.md` |
| 5 | Self-correction 3 attempts | ✅ **Active** | `developer-agent.md` |
| 6 | Orchestrator verification | ✅ **Active** | `plan.md` oversight + post-delegate verif |
| 7 | Architect/Editor contracts | ✅ **Active** | `architect-agent.md` + `developer-agent.md` |
| 8 | Artifact validation | ✅ **Active** | `plan.md` artifact validation table |
| 9 | READ/WRITE-ONLY split | ✅ **Active** | `researcher.md` + `developer-agent.md` |
| 10 | Curated skills catalog | ✅ **Active** | `skills/.curated/index.json` (15 skills) |

### 🥇 1. HERMES.md auto-load (Claude Code → Hermes)

Claude Code reads `CLAUDE.md` from project root on session start.
Hermes could read `HERMES.md` with project-specific rules, conventions,
build commands, test framework.

```
Phase 0: read_file HERMES.md → inject into orchestrator context
```

### 🥇 2. Repository Map (Aider → Hermes)

Aider builds a `--map-tokens` tree of the codebase so the model
understands structure without reading every file. Hermes orchestrator
at Phase 0 could run:

```bash
rg --files | head -200  # file inventory
pygount --format=summary .  # LOC by language
```

### 🥇 3. Edit→Lint→Test cycle (Aider/SWE-Agent → Hermes)

Every code change must pass lint + test before being committed.
Developer-agent.md should enforce:

```
edit file.py → lint file.py → test file.py → mark done
```

### 🥇 4. Git safety net (Claude Code/Aider → Hermes)

Auto-commit or stash before any agent touches files:

```bash
git stash push -m "pre-agent-snapshot-$(date +%s)"
```

### 🥈 5. Self-correction loop (Aider/SWE-Agent → Hermes)

Developer-agent.md: if test fails, read error, fix, retry. Up to 3 attempts.
NEVER give up on first failure.

### 🥈 6. Orchestrator verification (All → Hermes)

Orchestrator with `terminal` verifies key sub-agent outputs directly.
Trust but verify: 1 of 3 claims checked.

### 🥈 7. Architect/Editor split (Aider → Hermes)

Already exists in Hermes as `architect-agent.md` + `developer-agent.md`.
Needs explicit handoff protocol.

### 🥉 8. Structured outputs (OpenCode+ → Hermes)

JSON Schema for key artifacts (requirements, plan). Validation gate before
passing to next phase.

### 🥉 9. Stateless/Stateful split (OpenCode+ → Hermes)

Researcher reads (stateful), Developer writes (stateless). Prevents
reinforcement of own errors.

### 🥉 10. Curated skills list (Codex CLI → Hermes)

Codex has `openai/skills` repo with curated + experimental lists.
Hermes skills ecosystem is identical format — could have curated list.

## Known pitfalls discovered during research

1. **Subagent hallucination on DeepSeek V4 Pro** — sub-agents emit tool-call XML
   without actually executing tools. Mitigation: orchestrator verifies 1 of 3 claims.

2. **Qwen 3.5 122B-A10B Q4_K_M hallucinates at 32K+ tokens** — MoE routing noise
   compounds at low quants. Not recommended for long-context orchestration.

3. **Qwen 3.6 35B too slow on Jetson CPU** — 5+ min/turn at 116K context.
   Not usable for interactive orchestration.

4. **`toolsets: []` = ALL tools** — Python falsy semantics on empty list.
   Always use explicit list.

5. **`model:` field doesn't change provider** — agent switches model name
   but provider stays on session default. Ensure provider matches model.
