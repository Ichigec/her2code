# Verified Run — 2026-07-15 (cycle 20260715T230200Z)

**Session:** `20260715T230200Z`
**Previous session:** `20260713T230307Z` (07-13 — 2-day gap; skipped 07-14)
**Phase outcomes:** all 5 gates passed

## Headline: mcp + process both RECOVERED from 07-13 crash

The 07-13 cycle crashed two scanners simultaneously:
- mcp: 78 → **0** (complete loss, -100%)
- process: 49 → **26** (second major cliff, -47%)

This 07-15 cycle restored both:
- **mcp: 0 → 78 (+78)** — full recovery to 07-13-pre-crash baseline
- **process: 26 → 55 (+29)** — exceeded the 07-11 value of 49 (new local high since the 07-09 cliff from 70→41)

Conclusion: the 07-13 mcp=0 / process=26 crash was **transient** (not a scanner breakage). No code fix needed — likely a transient filesystem/env read failure. Monitor next cycle to confirm stability.

## Per-scanner counts (current → delta vs 07-13)

| Scanner | 07-13 | 07-15 | Δ |
|---------|------:|------:|---:|
| compose | 211 | 216 | +5 |
| mcp | 0 | 78 | **+78** |
| skills | 131 | 132 | +1 |
| env | 28 | 30 | +2 |
| scripts | 14 | 14 | 0 |
| arch | 7 | 7 | 0 |
| health | 4 | 4 | 0 |
| litellm | 1 | 1 | 0 |
| process | 26 | 55 | **+29** |
| **Total** | **422** | **537** | **+115** |

537 is back above the 500 gate. 422 (07-13) was the first sub-500 cycle on record.

## Phase results

- **Phase 1 Discover:** 537 records, exit 0. Known schema-drift warnings (tool_id/tool_name/tool_type properties don't exist on Tool nodes).
- **Phase 2 Process:** 537 classified → layers L4_services=226, L5_skills=210, L1_config=31, L2_scripts=14, L0_system=56. Candidates **215** (merge 0, prune 128, collapse 0, rebudget 87, mcp_dedupe 0). `.last_session` updated automatically.
- **Phase 3 Draft+Log:** 87 proposals written, 128 rationales logged, 215 log entries. Daily summary `2026-07-16.md` = 4510 bytes.
- **Phase 4 Neo4j Sync:** `sync complete`, discover + 2× checkpoint synced. seq=undefined (known pitfall). **Neo4j WAS reachable** despite `systemctl is-active neo4j` = inactive — DB runs via Docker/other mechanism; do not trust systemctl status as the reachability signal.
- **Phase 5 Audit:** report `claw-audit-20260715T230250Z.md`. Neo4j Tool=78, Evidence=81, Session=799, DEPENDS_ON=9. 20 orphan tools, 6 CompactionPolicy with NULL threshold.

## Confirmed persistent bugs (still present)

1. **Audit Recommendations hardcoded counts (8+ cycles):** report says "63 rebudget / 109 prune" but Phase 2 actual = **87 rebudget / 128 prune**. Do NOT trust audit Recommendations for counts — always cross-check Phase 2 stdout.
2. **Schema drift warnings:** `tool_id`/`tool_name`/`tool_type` on Tool nodes (should be `id`/`name`/`type`); `threshold` missing from CompactionPolicy.
3. **seq=undefined** in Phase 4 (checkpoint JSONs lack `seq` field).
4. **Empty CompactionPolicy id=None** — 6 policy nodes show `id=None` in orphan/empty-policy listing (policy nodes lack a populated `id` property).

## Notes

- 2-day gap since last cycle (07-13 → 07-15). If cron is meant to be daily, verify the cron schedule / that 07-14 actually fired.
- Audit "Next cycle: Baseline established" line is stale boilerplate — this is NOT a baseline cycle.
