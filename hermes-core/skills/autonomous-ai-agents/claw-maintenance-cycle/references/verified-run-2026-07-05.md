# Verified claw cycle execution — 2026-07-05

Agent: `claw-orchestrator` (cron)
Skill version: 1.1.0 (patched this run: audit count discrepancy pitfall added)
Scripts path: `/home/user/dev/codemes/<SESSION_ID>/her2code/config/scripts`
Sync fallback: `/home/user/cursor/first/opencode+/plugins/claw-neo4j/sync-from-compactor.js`

## Verified command sequence

```bash
export HOME=/home/user
SCRIPTS=/home/user/dev/codemes/<SESSION_ID>/her2code/config/scripts
SYNC_FALLBACK=/home/user/cursor/first/opencode+/plugins/claw-neo4j/sync-from-compactor.js

# Phase 1
python3 $SCRIPTS/claw-discovery.py
# Phase 2
python3 $SCRIPTS/claw-process.py
# Phase 3
python3 $SCRIPTS/claw-draft-log.py
# Phase 4
SESSION=$(cat /home/user/.compactor/.last_session)
REGISTRY=$(ls -t /home/user/.compactor/registry/integrations.*.json | head -1)
node $SYNC_FALLBACK --compactor /home/user/.compactor --session $SESSION --registry $REGISTRY
# Phase 5
python3 $SCRIPTS/claw-audit.py
```

Note: Phase 4 was run AFTER Phase 3 but BEFORE Phase 5 in this cycle (skill Quick Run
orders 1→2→3→4→5). All phases exited 0.

## Results this run

| Phase | Exit | Key output |
|-------|------|------------|
| Discover | 0 | 552 records; DBMS warnings for `tool_id`/`tool_name`/`tool_type` schema drift |
| Process | 0 | Session `20260704T230105Z`; 216 candidates (138 prune, 78 rebudget) |
| Draft+Log | 0 | 78 proposals, 216 log entries; summary `2026-07-05.md` (4056 bytes) |
| Neo4j Sync | 0 | Sync complete; `seq=undefined` on checkpoints (known) |
| Audit | 0 | Report `claw-audit-20260704T230212Z.md` |

## Audit warnings observed

- 20 orphan tools (no `DEPENDS_ON`)
- 6 `CompactionPolicy` nodes with NULL `threshold`
- Audit Recommendations says "63 rebudget / 109 prune" — **STALE/WRONG** (actual: 78 rebudget / 138 prune)

## ⚠️ NEW FINDING: Audit recommendation count discrepancy

The audit report's Recommendations section prints hardcoded "63 rebudget proposals" and
"109 prune candidates" — but Phase 2 actually produced 78 rebudget / 138 prune (216 total).

This mismatch was also present in the 2026-07-04 cycle (same 63/109 in audit vs same
78/138 from Phase 2). The audit script does not read live candidate counts from the
checkpoint; it uses fixed strings.

**Impact:** Any consumer trusting the audit Recommendations for action items will
undercount by ~15 rebudget and ~29 prune candidates.

**Fix needed:** Update `claw-audit.py` to read `classification_summary` from
`checkpoint.2.json` and report actual counts.

## Deltas vs previous cycle (2026-07-04)

| Scanner | Previous | Current | Δ |
|---------|----------|---------|---|
| compose | 203 | 203 | 0 |
| mcp | 78 | 78 | 0 |
| skills | 140 | 140 | 0 |
| env | 26 | 26 | 0 |
| scripts | 12 | 12 | 0 |
| arch | 7 | 7 | 0 |
| health | 4 | 4 | 0 |
| litellm | 1 | 1 | 0 |
| process | 77 | 81 | +4 |

Near-zero delta again. Only process scanner changed (+4).

## Neo4j graph state

- 78 Tool nodes
- 81 Evidence nodes
- 787 Session nodes
- 9 DEPENDS_ON relations

## Top rebudget candidates (skills > 8KB)

humanizer (29.3 KB), p5js (26.8 KB), comfyui (23.7 KB), claude-design (19.4 KB),
touchdesigner-mcp (15.1 KB), ascii-video (14.5 KB), pretext (13.8 KB),
requirements-analysis (13.1 KB), quality-gates (12.6 KB), android-hermes-app (12.7 KB)

## Phase logs

Captured at `/tmp/claw-phase{1-5}-20260705T0200*.log`
