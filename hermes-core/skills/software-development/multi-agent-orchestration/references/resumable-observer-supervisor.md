# Resumable Observer Supervisor

Use this reference when a lifecycle needs Auditor, Critic, and Idea Generator to “watch the whole process” in Hermes.

## Runtime fact

Current `delegate_task` children are synchronous and stateless: spawn → receive explicit `goal/context/toolsets/model/provider` → run → return summary → exit. They do not stay alive across phases and do not see parent history unless the orchestrator passes it.

Therefore persistent observers should be implemented as **durable identity + checkpoint state**, not as a long-lived LLM process.

```text
observer identity = role + state.json + findings.jsonl + phase checkpoint history
```

## Target pattern

```text
Orchestrator lifecycle
  ├─ Phase 0/1/2/.../10
  ├─ after each major phase: Observer Checkpoint
  │    ├─ Auditor
  │    ├─ Critic
  │    └─ Idea Generator
  ├─ durable observer state
  ├─ open findings backlog
  └─ final observer report
```

Observers are re-spawned at each checkpoint, but receive prior state and artifacts, making them functionally continuous.

## Role boundaries

| Observer | Blocks? | Focus |
|---|---:|---|
| Auditor | Yes | Requirements, acceptance criteria, process completeness, evidence, compliance, delegation quality |
| Critic | Yes, when high risk | Weak architecture, edge cases, brittle runtime assumptions, maintainability, test gaps |
| Idea Generator | Rarely | Better alternatives, UX/devex/perf/product improvements, backlog opportunities |

Observers should normally be read-only. They recommend; they do not fix.

## Artifact layout

```text
.hermes/observer-runs/<run_id>/
  manifest.json
  events.jsonl
  phase-summaries/
    phase-01-requirements.md
    phase-02-research.md
  observers/
    auditor/
      state.json
      findings.jsonl
      phase-01.md
      final.md
    critic/
      state.json
      findings.jsonl
    ideagen/
      state.json
      ideas.jsonl
  gates/
    phase-01-gate.json
  final-observer-report.md
```

## Checkpoint input contract

Each observer receives:

- run manifest and phase name;
- user goal and constraints;
- phase summary;
- artifacts created/changed;
- test/check outputs;
- previous state for that observer;
- open findings from all observers;
- explicit role contract and output schema.

Do not rely on parent conversation memory.

## Output schema

Auditor/Critic:

```json
{
  "observer": "auditor",
  "phase": "phase-03-architecture",
  "decision": "continue | fix-first | escalate",
  "summary": "...",
  "findings": [
    {
      "id": "AUD-03-001",
      "severity": "blocker | high | medium | low",
      "type": "missing-requirement | architecture | test-gap | security | process",
      "evidence": "specific artifact/tool output",
      "recommendation": "actionable fix",
      "acceptance": "how to verify the fix",
      "owner": "orchestrator | architect | developer | tester"
    }
  ],
  "resolved_findings": [],
  "state_update": {"watchlist": []}
}
```

Idea Generator:

```json
{
  "observer": "ideagen",
  "phase": "phase-03-architecture",
  "decision": "continue | backlog",
  "ideas": [
    {
      "id": "IDEA-03-001",
      "impact": "high | medium | low",
      "effort": "high | medium | low",
      "category": "UX | devex | performance | architecture | automation",
      "proposal": "...",
      "why_now_or_later": "..."
    }
  ],
  "state_update": {"watchlist": []}
}
```

## Gate merge

```text
if any observer decision == escalate:
    gate = escalate
elif any blocker:
    gate = fix-first
elif high_count >= 2:
    gate = fix-first
elif auditor has high:
    gate = fix-first by default
else:
    gate = continue
```

High/blocker waivers require an explicit reason and expiry condition. Never silently continue past a blocker.

## Implementation roadmap

1. **Prompt-only MVP** — patch `~/.hermes/agents/plan.md` so after every major phase it writes a phase summary, delegates the three observers in a batch, stores outputs, merges gates, and includes a final observer report. This works with current runtime.
2. **Observer tool/state layer** — add `agent/observer_runtime.py` and `tools/observer_tool.py` with actions like `init_run`, `record_phase`, `checkpoint`, `resolve_finding`, `waive_finding`, and `final_report`.
3. **Event-sourced supervisor** — use lifecycle hooks (`pre_tool_call`, `post_tool_call`, `subagent_start`, `subagent_stop`, turn start/end) to write `events.jsonl`; schedule observers on phase completion, failed tests, security findings, final answer, or manual checkpoint. Do not invoke LLM observers on every tool event.

## Observer permission baseline

Auditor/Critic may need read-only files plus safe verification commands. IdeaGen should usually have no shell.

```yaml
Auditor:
  toolsets: [file_ro, terminal, session_search]
  permission:
    edit: deny
    bash:
      "*": ask
      "git diff *": allow
      "git status*": allow
      "pytest *": allow
      "npm test*": allow
      "semgrep *": allow
      "gitleaks *": allow

Critic:
  toolsets: [file_ro, terminal, search]
  permission:
    edit: deny
    bash:
      "*": ask
      "git diff *": allow
      "git status*": allow
      "pytest *": allow

IdeaGen:
  toolsets: [file_ro, session_search]
  permission:
    edit: deny
    bash: deny
```

## Testing checklist

- Observer state survives context compaction.
- Each phase produces phase summary + three observer outputs + gate decision.
- Blocker/high finding stops lifecycle unless explicitly waived with reason.
- Final report includes unresolved findings and observer summaries.
- Observers receive all needed context explicitly.
- Observers cannot mutate files.
- Regression: permission policy for `bash: ask` works for both sequential and concurrent tool execution.

## Runtime pitfall discovered in review

If permission policy is stored in `threading.local()` while tools run in `ThreadPoolExecutor`, worker threads may not see the parent thread’s active policy. In the reviewed runtime, `propagate_context_to_thread()` copies `contextvars` and approval/sudo callbacks, but not arbitrary thread-local fields. Prefer `ContextVar` for active permission policy or evaluate bash `ASK` before dispatching to worker threads. This matters for observer safety because observer tool restrictions must be enforced by runtime, not only by prompt.