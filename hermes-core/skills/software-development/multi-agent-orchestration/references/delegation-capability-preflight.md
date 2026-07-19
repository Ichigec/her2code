# Delegation Capability Preflight

Use this reference when an orchestration cycle depends on model-routed subagents, persistent observers, or role-specific providers.

## Durable lesson

Do not assume the live `delegate_task` tool has the same capability surface as the desired architecture. Tool schemas, provider defaults, and gateway routing can change by Hermes version/profile. Before launching expensive batches or observer checkpoints, run a small capability preflight and record the result as an artifact.

This is a **fix pattern**, not a permanent claim that a given provider/tool is broken.

## Preflight checklist

1. **Inspect available delegation interface**
   - Determine whether the current `delegate_task` shape exposes explicit `model` and `provider` fields, or only `goal/context/toolsets/role`.
   - If explicit routing fields are absent, do not pretend role-specific model routing is enforced by the tool call itself.

2. **Run a tiny smoke probe before batches**
   - Single child, tiny goal, no side effects.
   - Ask it to report observable runtime metadata if available.
   - Capture: status, model/provider requested, model/provider actually observed if known, error text, and timestamp.

3. **Classify capability**
   - `READY`: schema and smoke prove the route needed for the phase.
   - `DEGRADED`: delegation works, but requested model/provider route is not proven, or smoke uses a fallback/default.
   - `BLOCKED`: required schema/capability is absent or smoke fails consistently for the required role.

4. **Gate observer/developer launch**
   - `READY`: launch normal role agents.
   - `DEGRADED`: continue only with degraded orchestration safeguards: deviation note, real local verification, separated artifacts, explicit Phase 10 disclosure.
   - `BLOCKED`: do not launch pretend observers/reviewers. Either fix config/tooling or switch to a documented fallback.

5. **Persist evidence**
   - Add a short artifact such as `docs/tests/delegation-preflight.md` or `.observations/delegation-preflight.md`.
   - Link it from the issue ledger if this preflight resolves or mitigates a delegation issue.

## Minimal project runtime object

For long projects, add a small project-local `DelegationPreflight` / `CapabilityReport` abstraction so phases do not duplicate checks.

Recommended fields:

```python
class DelegationStatus(Enum):
    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"

@dataclass(frozen=True)
class DelegationCapabilityReport:
    status: DelegationStatus
    requested_provider: str | None
    requested_model: str | None
    schema_supports_model: bool
    schema_supports_provider: bool
    smoke_ok: bool
    actual_provider: str | None = None
    actual_model: str | None = None
    error: str | None = None
    recommendation: str = ""
```

## Safety boundary for live Hermes route repair

When the issue is a live Hermes delegation/provider route (for example, a project issue such as `MAR-ERR-001` where `gpt-5.5` model routing failed), separate **project-local mitigation** from **live Hermes repair**:

| Scope | Safe default | Why |
|---|---|---|
| Project repo under `~/dev/codemes/<project>/` | Create a feature branch and add preflight/tests there | Clean rollback boundary; project tests prove mitigation without mutating active Hermes |
| `~/.hermes/config.yaml` | Do not edit without explicit permission | Active profile config affects the current agent session |
| `~/.hermes/hermes-agent` source | Do not patch in-place unless the worktree is clean or a separate worktree/branch exists | Active Hermes may contain unrelated modified/untracked files; route repair can mix with GUI/tooling changes |

Recommended sequence:

1. In the project repo, verify `git status --short`, last baseline commit, and regression tests before starting the slice.
2. Add/extend project-local `DelegationPreflight` tests so the issue remains visible until the intended route is actually proven.
3. For live Hermes changes, first create an isolated branch/worktree or otherwise protect existing local changes.
4. Only then patch the live route/schema/provider alias and run Hermes' targeted tests.

## Default-route smoke is not model-route proof

A successful `delegate_task` smoke with no explicit routing proves only that **some** child route works. It does **not** close a model-routing issue. To classify `READY` for role-routed orchestration, the evidence must prove the intended route, e.g. requested provider/model (`custom:openai` + `gpt-5.5`) and observed success through that route.

If the active tool schema lacks explicit `model`/`provider` parameters, record this as `DEGRADED` or `BLOCKED` for model-routed phases even if default delegation works. The correct next action is either route via verified Hermes delegation config or extend/repair the tool schema/provider alias in an isolated live-Hermes worktree.

## Anti-patterns

- Launching 8+ subagents before proving a single route works.
- Writing observer reports locally while presenting them as independent subagent output.
- Treating a desired routing table as runtime truth without schema/smoke evidence.
- Treating a default-route smoke as proof that a specific provider/model route works.
- Patching live `~/.hermes/hermes-agent` in-place when its git tree already has unrelated modified/untracked files.
- Marking delegation/model-routing issues resolved merely because a fallback produced tests.

## Acceptance evidence

A delegation preflight slice is complete when:

- Unit tests cover `READY`, `DEGRADED`, and `BLOCKED` decisions.
- Full project regression is green.
- The issue ledger distinguishes tooling/config still `OPEN` from runtime mitigation `RESOLVED`.
- Future phases consume the preflight result before spawning observers or batches.
