# Auditor as Evolution Driver

## From Reporter to Evolution Engine

**Before:** Auditor silently observes → Phase 10 one-shot report → done. Stateless — no cross-cycle memory.

**After:** Auditor is a **persistent evolution driver** with cross-cycle memory, auto-apply safe changes, and mutation proposals.

## Core Mechanisms

### 1. Cross-Cycle Memory (`auditor_memory.md`)

Append-only markdown file at `~/.hermes/auditor_memory.md`. Auditor reads it at cycle start, appends after Phase 10.

```markdown
# Auditor Memory — Cross-Cycle Evolution Log

## Meta
- Cycles observed: N
- Mutations proposed: N
- Mutations accepted: N
- Auto-applied changes: N

## Cycle Log
### Cycle YYYY-MM-DD-NNN (<task>)
- Duration, phases completed, verdict
- Agent performance table
- Delegation quality table
- Proposed mutations
- Auto-applied changes
```

### 2. Auto-Apply Safe Changes

| Change type | Auto? | Condition |
|------------|:-----:|-----------|
| AGENTS.md pitfalls | ✅ | Detected ≥2 cycles |
| AGENTS.md environment facts | ✅ | Fact changed (new port, version) |
| AGENTS.md build commands | ✅ | Verified (exit code 0) |
| Agent file prompt mutation | ❌ | Proposed as patch — needs review |
| Topology change (add/remove agent) | ❌ | Proposed as design — needs review |
| Escalation path change | ❌ | Proposed as design — needs review |

### 3. Mutation Proposals (Promptbreeder-inspired)

Auditor proposes concrete patches to agent files based on failure patterns:

```
## Proposed Mutation: <agent-file> §<section>

### Rationale
<evidence: N cycles with specific failure counts>

### Current text
<exact excerpt from agent file>

### Proposed text
<new version>

### Expected impact
<quantified prediction — e.g. "+30% spec conformance first pass">

### Mutation type
ADD_INSTRUCTION | REMOVE_INSTRUCTION | REWORD | REORDER | ADD_EXAMPLE
```

### 4. Phase 10 Output Format

```
## 🔍 Auditor Report

### Cycle Summary
- Duration, phases completed, verdict

### Agent Performance
| Agent | Phase | Success | Pattern |

### Delegation Quality
| # | Phase | Agent | Issue | Severity |

### Cross-Cycle Trends
- Patterns observed across ≥2 cycles

### Proposed Mutations
- MUT-XXX: <description> (status: PROPOSED)

### Auto-Applied Changes
- AUTO-XXX: <description>
```

### 5. What Auditor Checks

- Subagent failures (timeouts, errors, partial output)
- Phase re-executions (what had to be redone)
- Context loss (information dropped between phases)
- Tool misuse (wrong tools for the agent)
- Plan deviations
- Token waste (redundant calls, repeated operations)
- Race conditions (parallel agent conflicts)
- **Delegation quality** — complete context? Correct toolsets?
- **Requirement propagation** — did requirements survive all phases?
- **Agent accountability** — did any agent claim "done" without producing?
- **Tester autonomy violations** — did Tester ask user to test?
- **Mutation acceptance rate** — how many proposed mutations were accepted?

## EvoAgentX Inspiration

| Source | What we apply |
|--------|--------------|
| **Promptbreeder** (ICML'24) | Mutation proposals on agent files — ADD_INSTRUCTION, REMOVE, REWORD |
| **ADAS** (ICLR'25) | Topology proposals — add/remove gates, change escalation paths |
| **Agent Workflow Memory** (ICML'24) | Remember successful agent+workflow combinations |
| **Symbolic Learning** (Arxiv'24) | Agents improve through concrete text edits proposed by Auditor |
| **Building Self-Evolving Agents** (Arxiv'25) | Experience-driven lifelong learning — Auditor as lifelong learner |

## plan.md Integration

In `~/.hermes/agents/plan.md`, the Auditor section is replaced with the Evolution Driver section. Key additions:

1. `read_file("~/.hermes/auditor_memory.md")` at cycle start
2. Auto-apply rules table
3. Mutation proposal format
4. Phase 10 output with cross-cycle trends, mutations, auto-applied changes

## auditor_memory.md Initialization

```bash
cat > ~/.hermes/auditor_memory.md << 'EOF'
# Auditor Memory — Cross-Cycle Evolution Log

> **Auto-generated. Append-only.** Never delete — only append.
> Used by Auditor to detect cross-cycle patterns.

## Meta
- Created: YYYY-MM-DD
- Cycles observed: 0
- Mutations proposed: 0
- Mutations accepted: 0
- Auto-applied changes: 0

## Cycle Log

<!-- Cycles appended below -->
EOF
```
