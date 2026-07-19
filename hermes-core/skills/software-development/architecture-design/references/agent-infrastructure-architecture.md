# Agent Infrastructure Architecture — Patterns

> When the architecture IS a framework for agents and tools, component contracts
> are naturally interface definitions. This reference captures the pattern used
> in the Quality Gate Runner architecture session.

## When This Pattern Applies

The standard `architecture-design` template optimizes for application architectures
(REST APIs, services, data stores). Use this extended pattern when designing:

- Agent orchestration frameworks
- Tool/plugin registries with common interfaces
- Gate/check/pipeline systems
- Self-improving agent infrastructure
- Any system where **components are code-level contracts** (ABCs, JSON schemas, protocol specs)

## Additional Sections for Agent Infrastructure

Beyond the standard template, add these sections when relevant:

### Component Contracts as Interface Definitions

For agent infrastructure, **ABC definitions, data schemas, and protocol specs ARE
the architecture**, not implementation detail. Include them explicitly:

```markdown
## Component Contracts

### GatePlugin ABC (base class)
```python
class GatePlugin(ABC):
    name: str
    def applicable(artifacts: dict) -> bool
    def check(artifacts: dict, workdir: str) -> GateResult
```

### GateVerdict JSON Schema
```json
{ "verdict": "ALL_PASSED | FAILED", "action": { "fix_phase": int, ... } }
```

This is NOT the same as "implementation pseudocode" — it defines the WIRE PROTOCOL
between components. An orchestrator that reads GateVerdict JSON must know the schema;
a gate developer implementing a plugin must know the ABC contract.
```

### Gate/Check Specifications

When the system is a pipeline of checks/gates, each deserves its own spec with:

- Trigger condition (`applicable()`)
- Contract (interface signature)
- Check inventory (what each checks, with pass/fail criteria)
- Fix routing (what phase/agent to call on failure)

### Data Flows (Orchestrator Integration)

Show the loop: orchestrator → delegate → gate_runner → JSON verdict → route → delegate → ...

Use sequential numbered flows, not just box diagrams. Show who calls what and what
JSON is exchanged at each step.

### File Layout

Physical tree of where files go under `~/.hermes/`. Critical for agent infrastructure
where `scripts/`, `gates/`, and `config.yaml` must coexist with existing subsystems.

### Phased Rollout Plan

Gate/agent systems benefit from incremental rollout because each phase exercises
the gate runner against real code. Plan: Core → Traceability → History DB → Parallel → Orchestrator v3.

## The Analysis→Architecture Workflow

When the user asks for a **deep analysis** of a system design problem, the natural
flow is:

1. **Analysis phase**: Load `hermes-agent` skill, read AGENTS.md, read existing scripts.
   Produce `analysis.md` with:
   - Current state diagnosis (what's broken and why)
   - Proposed architecture (high-level)
   - Traceability chain (if applicable)
   - What to build
   - Answers to "how do we know X is working?"

2. **Architecture phase**: User says "Давай начнем с архитектуры" — produce
   `docs/architecture/<slug>.md` with the full architecture artifact.

The analysis document serves as a **combined Requirements + System Analysis** for
the architecture phase. Reference it from the architecture artifact.

## When Pseudocode IS Architecture

For framework designs, these are architecture, not implementation:

| Item | Why it's architecture |
|------|----------------------|
| ABC with `@abstractmethod` signatures | Defines the contract all plugins must fulfill |
| JSON schema for wire protocol | Defines the data contract between orchestrator and gate runner |
| `@dataclass` with field types | Defines the shape of data flowing between components |
| SQL `CREATE TABLE` statements | Defines the persistence schema — data architecture |
| `GateVerdict` data model | Defines the result contract all gates must produce |

What's still implementation (belongs in Plan/Implementation):
- Function bodies (`def check(): ...`)
- Business logic (> 5 lines of procedural code)
- Detailed algorithm steps
- Error handling try/except blocks

**Rule of thumb**: If removing the line changes the CONTRACT between components,
it's architecture. If it only changes HOW a component works internally,
it's implementation.
