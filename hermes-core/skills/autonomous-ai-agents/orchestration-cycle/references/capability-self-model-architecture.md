# Capability Self-Model — Phase 0 Bootstrap Architecture

> Reference for `orchestration-cycle` skill.
> Based on full plan2 cycle: `<SESSION_ID>` (2026-06-25).
> Research: 6-agent fan-out, 50+ sources, BA framework enrichment.

## Architecture Overview

The capability self-model plugs into Phase 0 bootstrap of `/agent plan2`. Before any phase starts, the orchestrator runs a capability check that discovers what the agent system CAN and CANNOT do.

### G0-G8 Module Stack

| Module | Role | Key Pattern |
|--------|------|------------|
| **G0: CapabilityGate** | Entry point. Calls G1-G5, evaluates Go/Kill/Hold/Recycle | PEP (RFC 2753) |
| **G1: CapabilityLoader** | Loads static inventory from `capability_inventory.yaml` | PCI enumeration |
| **G2: CapabilityProber** | Live probes for dynamic capabilities (cuda, docker, git, etc.) | K8s readiness/liveness |
| **G3: TaskInterviewer** | Two-level: L1 keyword matching (~60%), L2 BACCM structural inference (~85%) | Modernizr (probe, don't sniff) |
| **G4: CompositionEngine** | Derives gaps from tool combinations (A+B→C, A_missing→derived) | MUSE competence boundaries |
| **G5: GapResolver** | For each gap: what-can-be-done / what-is-missing / what-is-hard | Claude Code boundary detection |
| **G6: FabricationGuard** | Post-plan scan for impossible verification steps | — |
| **G7: ReportBuilder** | Pre-flight report ≤50 lines | — |

### Key Architecture Decisions

1. **K8s two-tier readiness/liveness**: Every capability has `reachable` (does it respond?) + `usable` (is it functional?)
2. **Circuit breaker per capability**: CLOSED → fail → OPEN → cooldown(30s) → HALF_OPEN → probe
3. **Modernizr pattern**: probe commands at runtime, never trust static availability claims
4. **Fail-open**: engine crash → status=ERROR → WARN, not BLOCK
5. **1 file = 1 dev**: 26 developers, no shared files

### Files Created

| File | Lines | Purpose |
|------|:-----:|---------|
| `~/.hermes/agents/capability_inventory.yaml` | 260 | Static inventory: 19 capabilities, keyword map, composition rules, BACCM template |
| `~/.hermes/scripts/capability_gate.py` | 850 | G0-G7 engine: load, probe, interview, compose, resolve, guard, report |
| `~/.hermes/gates/gates/capability_gate.py` | 270 | GatePlugin for existing gate system |
| `~/.hermes/gates/all_gates.yaml` | 560 | 15 pre-phase gate configurations |

### Integration Points

- **plan2.md Phase 0.2**: `python3 capability_gate.py --task "$TASK" --json`
- **plan2.md Pre-Phase Hook Protocol**: 15 gates, PEP/PDP architecture
- **plan2.md Artifact caching rule #5**: capability context injection into every delegate_task
- **plan2.md Phase 6.5**: GAP propagation check (new check #5)
- **plan2.md Phase 10**: G8 retrospective learning → Neo4j
- **Observer checkpoints**: active feedback loop (was fire-and-forget, now queries Neo4j for CRITICAL findings)

### Validation

```bash
# Validate inventory
python3 ~/.hermes/scripts/capability_gate.py --validate
# ✅ 19 capabilities loaded

# Full check with task
python3 ~/.hermes/scripts/capability_gate.py --task "сделай приложение с картинкой"
# → Go/Kill/Hold/Recycle verdict with gap resolution plans

# Post-plan fabrication scan
python3 ~/.hermes/scripts/capability_gate.py --post-plan .hermes/plans/<slug>.md
```
