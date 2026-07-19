# Verified Run — 2026-07-11 (Session 20260711T230112Z)

**Date:** 2026-07-11 23:00 – 23:02 UTC (daily summary dated 2026-07-12)
**Session:** `20260711T230112Z`
**Registry:** `integrations.20260711T230038Z.json`
**Previous session:** `20260710T230431Z`

## All 5 Phases Passed

| Phase | Gate | Result |
|-------|------|--------|
| 1 Discover | ≥500 records, no ERROR | 519 records ✅ |
| 2 Process | Checkpoint exists, candidates >0 | 204 candidates ✅ |
| 3 Draft+Log | Daily summary >500 bytes | 4228 bytes ✅ |
| 4 Neo4j Sync | "sync complete", no MODULE_NOT_FOUND | sync complete ✅ |
| 5 Audit | Audit markdown created | 2067 bytes ✅ |

## Scanner Breakdown (519 total)

| Scanner | 07-10 | 07-11 | Δ | Notes |
|---------|-------|-------|---|-------|
| compose | 211 | 211 | 0 | Stabilized 5 cycles |
| skills | 126 | 127 | +1 | Broke zero-delta streak |
| mcp | 78 | 78 | 0 | Stable (audit delta table shows +78 — BUG) |
| process | 46 | 49 | +3 | Recovery continues |
| env | 28 | 28 | 0 | |
| scripts | 14 | 14 | 0 | |
| arch | 7 | 7 | 0 | |
| health | 4 | 4 | 0 | |
| litellm | 1 | 1 | 0 | |

## Process Scanner Recovery Trend

```
07-05: 81  (peak)
07-06: 74  (-7)
07-08: 68  (-6)
07-08: 70  (+2)
07-09: 41  (-29, cliff-drop -41.4%)
07-10: 46  (+5, +12.2%)
07-11: 49  (+3, +6.5%)  ← this cycle
```

Cumulative from peak: 81→49 (-39.5%). Recovery is gradual but consistent (+8 over 2 cycles since cliff).

## Compaction Candidates (204 total)

| Axis | Count | Action |
|------|------:|--------|
| prune | 123 | Log rationale |
| rebudget | 81 | Draft proposal |
| merge | 0 | — |
| collapse | 0 | — |
| mcp_dedupe | 0 | — |

## Neo4j Graph State

- Tool nodes: 78
- Evidence nodes: 81
- Session nodes: 798
- DEPENDS_ON relations: 9

## Audit Findings

- 20 orphan tools (no DEPENDS_ON) — compose services
- 6 CompactionPolicy entries with NULL threshold
- All 9 scanners healthy (✅)

## Known Bugs Observed This Cycle

1. **Audit Recommendations STALE/HC (7th cycle):** Audit printed "63 rebudget / 109 prune" but actual Phase 2 was 81 rebudget / 123 prune. Hardcoded strings in `claw-audit.py`.
2. **mcp delta anomaly (NEW):** Audit Delta Analysis showed mcp 0→78 (+78) but mcp was 78 in previous cycle too. Previous-snapshot comparison broken for mcp scanner.
3. **seq=undefined** in Phase 4 sync (known).
4. **Neo4j schema drift** — DBMS warnings for tool_id/tool_name/tool_type (known).

## Artifacts

- Registry: `~/.compactor/registry/integrations.20260711T230038Z.json`
- Checkpoints: `~/.compactor/sessions/20260711T230112Z/checkpoint.{2,3}.json`
- Daily summary: `~/.compactor/summaries/2026-07-12.md` (4228 bytes)
- Audit report: `~/.hermes/reports/claw-audit-20260711T230206Z.md` (2067 bytes)
- Phase logs: `/tmp/claw-phase{1-5}-*.log`
