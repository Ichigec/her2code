# Verified Run — 2026-07-16 / early 2026-07-17 UTC

## Cycle Summary

- **Session:** `20260716T230440Z`
- **Total records:** 511 (above 500 gate, down from 537)
- **Neo4j:** Reachable (78 Tool / 81 Evidence / 800 Session nodes)
- **All gates passed:** Phase 1 (511≥500), Phase 2 (215 candidates), Phase 3 (4,510 bytes), Phase 4 (sync complete), Phase 5 (audit generated)

## Scanner Deltas

| Scanner | 07-15 | 07-16 | Δ |
|---------|-------|-------|---|
| compose | 216 | 216 | 0 |
| mcp | 78 | 78 | 0 |
| skills | 132 | 132 | 0 |
| env | 30 | 30 | 0 |
| scripts | 14 | 14 | 0 |
| arch | 7 | 7 | 0 |
| health | 4 | 4 | 0 |
| litellm | 1 | 1 | 0 |
| **process** | **55** | **29** | **-26** |

## Key Findings

**Process scanner oscillating (55→29, -47%):** After a +29 recovery (26→55) on 07-15, the process scanner dropped back to 29. The oscillation pattern (26↔55) confirms this is an unstable detection boundary, not monotonic growth or decline. Full trend: 81→74→68→70→41→46→49→26→55→29.

**All other scanners stable:** 8 of 9 scanners at zero delta — the graph has reached equilibrium for most categories. Process remains the sole volatile signal.

**Compose has moved up (211→216):** Settled at 216 after being pinned at 211 for 6+ cycles. The change occurred during 07-15 (first verified at 216 in 07-15 audit, now confirmed stable at 216).

**Skills continued growth (131→132, +1):** Incremental, consistent with prior trend.

**Candidates:** 215 total (128 prune, 87 rebudget, 0 merge/collapse/mcp-dedupe).

**Known bugs persist:**
- Audit Recommendations hardcoded "63 rebudget / 109 prune" vs actual 87/128
- `threshold` property missing on CompactionPolicy nodes (DBMS warning)
- `seq=undefined` in Phase 4 sync
- 20 orphan tools + 6 NULL-threshold policies (unchanged)
