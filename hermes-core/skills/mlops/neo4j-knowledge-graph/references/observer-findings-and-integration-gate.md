# Observer Findings — Integration Gate & Documentation Drift

> Captured from cycle 2026-06-17 through 2026-06-26.
> Three observers (Auditor, Critic, Idea Generator) run after orchestration phases.

## Observer Roles

| Observer | Agent file | Focus | Phase |
|----------|-----------|-------|-------|
| Auditor | `~/.hermes/agents/auditor-agent.md` | Integration gaps, orphan modules | Post-Implement |
| Critic | `~/.hermes/agents/critic-agent.md` | Bloat, complexity, SLOC targets | Post-Implement |
| Idea Generator | `~/.hermes/agents/idea-generator.md` | Performance forecasts, proposals | All phases |

## Instance: Cycle 2026-06-17

### Auditor Finding: 3 Orphan Modules

**Problem:** After Phase 2 implementation, `codebase_scanner.py`, `codebase_embeddings.py`, and `codebase_watcher.py` had no incoming imports from the orchestrator (`codebase_indexer.py`). They existed as files but were never wired into the pipeline.

**Fix applied:** Lazy imports added to `codebase_indexer.py`:
- `_get_ts_parser()` → `from codebase_scanner import TreeSitterParser`
- `_get_embedder()` → `from codebase_embeddings import EmbeddingGenerator`
- `start_watching()` → `from codebase_watcher import FileWatcher`

**Prevention:** DevOps Engineer (#10) role created: `~/.hermes/agents/devops-engineer.md`. Runs Integration Gate (phase 6a) after every Implement phase with 7 validation steps.

### Critic Finding: 10.8× Bloat

**Claim:** 8,400 lines → target ~780 SLOC. Delete 2,150 lines.

**Reality check (2026-06-26):** Actual Python SLOC across 6 modules = 2,300 (not 8,400). The 8,400 figure may have included non-code files or been from an earlier version. Still 2.95× above the 780 SLOC target.

**Heaviest modules:**
1. `codebase_indexer.py` — 608 SLOC (orchestrator; could split full_scan/update_file/watch into sub-modules)
2. `codebase_parser.py` — 536 SLOC (regex parser; could be replaced with tree-sitter-only path)
3. `codebase_scanner.py` — 490 SLOC (file scanning + tree-sitter; could split)

### Idea Generator: Embeddings Speed

**Forecast:** 102.8 emb/s predicted.
**Claimed actual:** 595 emb/s (5.8× faster).
**Verification status (2026-06-26):** Cannot reproduce — `sentence-transformers` not installed in current environment. EmbeddingGenerator code exists, lazy import catches `ImportError`.

## Documentation Drift — Recurring Pattern

### Problem

When infrastructure changes happen at the Hermes agent level (`~/.hermes/agents/`, `~/.hermes/config.yaml`), the project's own documentation (`AGENTS.md`, `structure.md`) is NOT automatically updated. This creates a gap:

| What was done | Where it's reflected | Where it's NOT |
|--------------|---------------------|----------------|
| DevOps Engineer (#10) created | `~/.hermes/agents/devops-engineer.md` | Project `AGENTS.md` — no phase 6a |
| | Hermes memory | Project `structure.md` — agent not listed |
| Enterprise Architect (#11) created | `~/.hermes/agents/enterprise-architect.md` | Project `structure.md` — agent not listed |
| Phase 6a added to lifecycle | Orchestrator escalation chain | Project `AGENTS.md` — no integration gate section |

### Prevention Checklist

After creating/modifying agent infrastructure, verify:
- [ ] Project `AGENTS.md` lists the new agent in the lifecycle table
- [ ] Project `structure.md` includes the new agent in the agent tree
- [ ] Escalation chain is updated (if applicable)
- [ ] Phase gating is documented (e.g., "phase 6a: Integration Gate → DevOps Engineer")
- [ ] `docs/architecture/` has a dedicated artifact for each new gate phase

## Integration Gate — 7-Step Validation (DevOps Engineer)

```
Phase 6a: Integration Gate
Owner: DevOps Engineer (#10)
Input: Completed implementation artifacts
Output: PASS/FAIL with specific remediation

Steps:
  1. Cross-module imports — every module imported by at least one other
  2. Function call chains — orchestrator → scanner → parser → writer path verified
  3. MCP server registration — config.yaml matches actual server path
  4. Config propagation — exclude_patterns, connection strings flow to all consumers
  5. Plan vs. reality — every deliverable in the plan exists and compiles
  6. Neo4j connectivity — write path verified with test transaction
  7. Orphan detection — no .py file with zero incoming imports
```

## Verification Script

Run `scripts/verify-p0.py` from the project root for automated P0 health checks.
See the script for the 6-point verification covering all Phase 2 fixes.
