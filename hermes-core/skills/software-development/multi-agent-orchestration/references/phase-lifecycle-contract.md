# Phase Lifecycle Contract

Each phase in the orchestration cycle has three conditions. The orchestrator
MUST verify ENTRY before starting and EXIT before declaring a phase complete.
When a phase fails irrecoverably, follow ROLLBACK.

| # | Phase | ENTRY condition | EXIT condition | ROLLBACK |
|---|-------|----------------|----------------|----------|
| 1 | Requirements | Task description from user | `docs/requirements/<slug>.md` exists + clarifying questions answered | Delete artifact, re-ask user |
| 2 | System Analysis | Requirements artifact exists | SMART goal + root cause + developer task spec written | Return to Phase 1 if requirements unclear |
| 3 | Research | System Analysis artifact exists; research questions defined | Research doc exists; all RQs answered with citations | Skip research if `skipResearch` flag set |
| 4 | Architecture | Research + System Analysis artifacts exist | Architecture doc exists; user sign-off obtained | Return to Research if missing info |
| 5 | Plan | Architecture signed off | Plan saved to `.hermes/plans/`; principles checklist passed | Return to Architecture if unscopable |
| 6 | Implement | Plan exists; file ownership assigned | All code complete + tests green | Git revert to pre-phase state |
| 6.5 | Verification | Implementation complete; code available | All 4 checks passed; deviation routing resolved | Return to Phase 6 for fixes |
| 7 | Quality | Verification passed | SAST clean (no High/Critical); team safety confirmed | Fix vulnerabilities → re-run SAST |
| 8 | Deployment | Quality passed | System deployed + verified operational | Rollback deployment |
| 8.5 | Acceptance Test | Deployment verified; system operational | Traceability matrix complete; all 🔴 resolved or accepted | Return to Phase 6 for fixes |
| 9 | Post-Deploy | Acceptance tests passed | Evidence quality-scored; hypotheses validated | Skip if no data to collect |
| 10 | Iterate + Audit | All prior phases complete | Auditor report delivered | N/A (final phase) |

## Usage

```python
# Before starting Phase N:
if not ENTRY_condition_met():
    go_back_to_prerequisite_phase()

# Before declaring Phase N done:
if not EXIT_condition_met():
    phase_is_NOT_complete()

# If Phase N fails irrecoverably:
ROLLBACK()
```

## Auditor cross-reference

The Auditor (#10) uses this contract to flag skipped phases and incomplete
deliverables. A phase marked complete without EXIT = delegation quality failure.
