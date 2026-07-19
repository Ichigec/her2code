# Idea Generator Checkpoint — Architecture Artifact Review

A checkpoint pass over a finished (or draft) architecture document to find missed ideas, hidden connections, untapped sources, and premature optimizations before implementation begins.

Use this after `docs/architecture/<slug>.md` exists and before the plan/implementation phase. The goal is not to rewrite the architecture, but to surface gaps the original author likely missed because they were deep in design mode.

## When to Run

- User asks for a "checkpoint", "review", "missed connections", or "ideas" on an architecture artifact.
- Before signing off on architecture — as a second pair of eyes.
- When the artifact feels "too clean" or assumes a greenfield runtime.

## Inputs to Collect

1. The architecture artifact itself (`docs/architecture/<slug>.md`).
2. Upstream documents: `docs/requirements/<slug>.md`, `docs/system-analysis/<slug>.md`, `docs/research/<slug>.md`.
3. Tech lead plan, if it exists: `.hermes/plans/<ts>-<slug>.md`.
4. Real code: at minimum the host project's plugin/hook system, profile/runtime isolation, delegation, and any module the artifact claims to integrate with.
5. Existing skills and references that cover the same territory.

## Review Lenses

### 1. Existing-runtime lens
Does the architecture reuse what already exists, or does it silently reinvent it?

- **Hook / plugin system** — can the feature be built as a plugin or hook subscription instead of a new engine? Check the host's `VALID_HOOKS`, `PluginContext` API, auxiliary tasks, slash commands, CLI command registration.
- **Isolation mechanism** — does the sandbox/profiling layer already have a clone API? (e.g., `ProfileManager.create_profile(..., clone_all=True)`)
- **Delegation / orchestration** — can evaluation steps run as subagent tasks via the existing delegation runtime instead of a monolithic engine?
- **Observability / audit sinks** — can audit events flow into existing structured sinks (relay, Langfuse, SQLite session DB) in addition to the markdown log the artifact prescribes?

### 2. Data-flow lens
Trace each data structure from creation to archival. Look for:

- Missing producers or consumers.
- Places where a metric is defined but no one is assigned to compute it.
- Audit events that never reach a human-visible surface.
- Metrics that ignore runtime costs that the host cares about (e.g., prompt-cache invalidation, cache-write tokens).

### 3. Human-in-the-loop lens

- How do MEDIUM/HIGH-risk decisions reach a human? Is there an existing task/notification mechanism (auxiliary tasks, TUI prompts, slash commands) that could be reused?
- Is there a canary or staged-apply step between "auto-apply" and "rollback"?

### 4. Extensibility lens

- Does the design naturally support Phase B/C extensions (e.g., skill evolution after prompt evolution) with the same validation pipeline?
- Are target types and operators modeled as enums/registries so new ones do not require engine changes?

### 5. Performance / overhead lens

- Does the design meet its own NFRs under realistic data sizes? (e.g., full `shutil.copytree` of a profile vs. copy-on-write / overlayfs / partial clone.)
- Does validation cost account for cold-start effects (cache misses, model warm-up) that disappear in steady state?

## Common Missed Connections in Hermes-like Runtimes

| Artifact claims | Often-missed existing mechanism |
|-----------------|--------------------------------|
| Explicit periodic command to collect cycle data | `subagent_start`/`subagent_stop`, `post_tool_call`, `on_session_end` hooks |
| New UI for human review | `register_auxiliary_task` + TUI gateway task list |
| Standalone CLI subcommand | `register_cli_command` via plugin context |
| Sandbox profile clone | `hermes_cli.profiles.create_profile(..., clone_all=True)` |
| Isolated agent evaluation | `delegate_task` with custom `HERMES_HOME` / profile |
| Audit trail only in markdown | Nemo relay / Langfuse plugins + SQLite session DB |
| Cost metric = token count | Prompt-cache read/write tokens, cache invalidation penalty |
| Auto-apply → 3-cycle rollback | Canary apply gate (1-cycle smoke test) between them |

## Output Format

Structure findings into four buckets:

1. **Missed ideas** — new capabilities enabled by existing mechanisms.
2. **Hidden connections** — which components should be wired together.
3. **Sources to consult** — exact files, skills, or reference docs still worth reading.
4. **Optimizations / simplifications** — ways to reduce code, overhead, or blast radius.

Keep each item concrete: cite the file/skill/mechanism and the section of the architecture it affects.

## Pitfalls

- **Do not** treat the architecture artifact as the only source of truth; real code always wins.
- **Do not** propose only additions — often the best finding is "delete this module and use X instead."
- **Do not** turn the checkpoint into a rewrite; flag issues, estimate impact, let the user prioritize.
