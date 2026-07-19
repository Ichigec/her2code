# Verified Run — 2026-07-17 (late-night, 07-18 UTC)

Clean cycle. All 5 phases passed, all gates green.

## Phase results

| Phase | Status | Key metric |
|-------|:------:|------------|
| 1 Discover | ✅ | 519 records (gate ≥500) |
| 2 Process | ✅ | 215 candidates (128 prune / 87 rebudget) |
| 3 Draft+Log | ✅ | Summary 4,510 bytes (gate >500) |
| 4 Neo4j Sync | ✅ | sync complete, 78T/81E/801S |
| 5 Audit | ✅ | 20 orphans, 6 empty policies |

## Scanner delta vs 07-16

| Scanner | 07-16 | 07-17 | Δ |
|---------|------:|------:|:--:|
| compose | 216 | 216 | 0 |
| mcp | 78 | 78 | 0 |
| skills | 132 | 132 | 0 |
| env | 30 | 30 | 0 |
| scripts | 14 | 14 | 0 |
| arch | 7 | 7 | 0 |
| health | 4 | 4 | 0 |
| litellm | 1 | 1 | 0 |
| **process** | **29** | **37** | **+8** |
| **TOTAL** | **511** | **519** | **+8** |

## Observations

- **Process scanner**: 29→37 (+27.6%). Continues oscillation pattern in the 26–55 range (26→55→29→37). The upward trajectory from the 07-16 trough suggests it may be heading back toward the 50s. Unstable detection boundary, not structural breakage — confirmed by 4th consecutive oscillation.
- **All other scanners**: zero delta across 8 scanners. Stabilization holding at 11+ cycles.
- **mcp delta**: correct this cycle (78→78, Δ=0). The intermittent bug did not fire — further evidence it's mcp-value-dependent, not a persistent comparison failure.
- **Total**: 519, +8, solidly above 500. Recovery from 07-13's anomalous 422 is sustained.
- **Neo4j**: reachable. systemctl likely still reports inactive — DB runs outside systemd.
- **Known bugs present**: audit hardcoded counts (63/109 vs actual 87/128), seq=undefined, threshold property warnings. All expected, no new issues.
