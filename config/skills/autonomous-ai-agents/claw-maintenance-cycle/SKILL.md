---
name: claw-maintenance-cycle
description: Run the claw graph 5-phase maintenance cycle (Discover → Process → Draft+Log → Neo4j Sync → Audit). Use when cron fires or when user asks to run claw cycle.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [claw, maintenance, neo4j, compaction, cron]
    related_skills: [orchestration-cycle]
---

# Claw Maintenance Cycle

Run the 5-phase claw graph maintenance cycle for the Neo4j claw graph
(Tool, Evidence, Session, CompactionPolicy, RegistrySnapshot nodes).

## When to use

- Cron fires: "Run claw orchestration cycle: Phase 1 Discover → Phase 2 Process → Phase 3 Draft+Log → Phase 4 Neo4j Sync → Phase 5 Audit"
- User says: "run claw cycle", "claw maintenance"
- User says: "check claw graph", "audit claw"

## Quick run

```bash
# Phase 1: Discover
python3 ~/.hermes/scripts/claw-discovery.py

# Phase 2: Process
python3 ~/.hermes/scripts/claw-process.py

# Phase 3: Draft+Log
python3 ~/.hermes/scripts/claw-draft-log.py

# Phase 4: Neo4j Sync
node ~/.hermes/plugins/claw-neo4j/sync-from-compactor.js \
  --compactor ~/.compactor \
  --session $(cat ~/.compactor/.last_session) \
  --registry $(ls -t ~/.compactor/registry/integrations.*.json | head -1)

# Phase 5: Audit
python3 ~/.hermes/scripts/claw-audit.py
```

## Scripts

| Phase | Script |
|-------|--------|
| 1 Discover | `~/.hermes/scripts/claw-discovery.py` |
| 2 Process | `~/.hermes/scripts/claw-process.py` |
| 3 Draft+Log | `~/.hermes/scripts/claw-draft-log.py` |
| 4 Neo4j Sync | `~/.hermes/plugins/claw-neo4j/sync-from-compactor.js` |
| 5 Audit | `~/.hermes/scripts/claw-audit.py` |

## Directory structure

```
~/.compactor/
  registry/          — integrations.<ts>.json snapshots
  sessions/<sid>/    — checkpoint.2-5.json
  drafts/<op-id>/    — compaction proposal drafts
  summaries/         — YYYY-MM-DD.md daily summaries
  log.jsonl          — append-only compaction log
  .last_session      — session ID of latest cycle
```

## 9 Scanners

compose, mcp, skills, env, scripts, arch, health, litellm, process

## 5 Compaction Axes

merge, prune, collapse, rebudget, mcp-dedupe

## Pitfalls

- The sync-from-compactor.js default compactor path points to `opencode+/opencode_claw/.compactor/` — always pass `--compactor ~/.compactor` explicitly.
- Tool nodes in Neo4j use property `name` not `tool_name`. Discovery registry uses `tool_name`.
- First cycle has no previous snapshot to compare against — audit notes this as "baseline cycle".
- Some skill `tool_name` values may be None; guard with `(x or '')`.
