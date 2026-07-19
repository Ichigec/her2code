# Runtime Change Review Checklist

Use this when auditing or committing Hermes runtime changes: provider routing, agent presets, permission policy, tool registry/toolsets, gateway/CLI/TUI/desktop integration, or delegate-task behaviour.

## What to inspect

1. **Git surface**
   - `git status --short`
   - `git diff --stat` and `git diff --name-status`
   - `git diff --check`
   - `git log -1 --pretty=fuller` after commit
2. **Runtime files to correlate**
   - Agent registry: `agent/agents.py`
   - Permission policy: `agent/permissions.py`
   - Tool execution enforcement: `agent/tool_executor.py`
   - System prompt/toolset exposure: `agent/system_prompt.py`, `toolsets.py`, `tools/registry.py`
   - Provider routing: `agent/runtime_provider.py` and provider/model config paths
   - Slash command integration: `hermes_cli/commands.py`, `cli.py`, `gateway/run.py`
   - Desktop integration: `apps/desktop/src/app/desktop-controller.tsx`, shell/statusbar hooks, role/preset panels
3. **Semantic grouping**
   - Agent/persona registry and config loading
   - Permission policy and enforcement semantics (`allow` / `ask` / `deny`)
   - Provider/model routing, especially direct OpenAI vs custom providers
   - Tool registry/toolset changes and child-agent tool availability
   - UI exposure: desktop role panel, config overlays, statusbar entries
   - Tests/docs/schema changes

## Verification commands

Run the smallest set that exercises the changed layers, then broaden if failures indicate cross-cutting issues.

```bash
cd ~/.hermes/hermes-agent

git diff --check

# Syntax check changed Python files only
python3 - <<'PY'
import pathlib, subprocess, sys
files = subprocess.check_output(['git', 'diff', '--name-only', '--cached'], text=True).splitlines()
py = [f for f in files if f.endswith('.py') and pathlib.Path(f).exists()]
if py:
    subprocess.check_call([sys.executable, '-m', 'py_compile', *py])
print('py_compile files:', len(py))
PY

# Target runtime/CLI/tool tests; adjust names to the touched files.
venv/bin/python -m pytest tests/hermes_cli tests/tools -q

# Desktop UI changes
cd apps/desktop && npm run build
```

## TypeScript typecheck (desktop UI)

Run from **inside `apps/desktop/`**, not the repo root:

```bash
cd ~/.hermes/hermes-agent/apps/desktop
npx tsc -b
```

A clean exit (no output) means no type errors. Common failures:

- **Missing i18n key**: if you add a key to `types.ts` + `en.ts`, the typescript compiler will catch missing keys in `ja.ts`, `zh.ts`, and `zh-hant.ts`. Fix all four locale files together — never assume they'll be caught later.

## Python runtime import smoke tests

Quick verification that key runtime modules load without side effects:

```bash
cd ~/.hermes/hermes-agent
python3 -c "from agent.agents import list_agents; print(len(list_agents()), 'agents')"
python3 -c "from agent.permissions import PermissionPolicy, ALLOW, ASK, DENY; print('permissions OK')"
python3 -c "from tools.delegate_tool import delegate_task; print('delegate_task OK')"
```

Use `list_agents()` not `AgentRegistry` — the class is `AgentDef`, and `list_agents()` returns a list of them. Fields: `id`, `label`, `description`, `emoji`, `mode`, `model`, `permission`, `toolsets`, `system_prompt`, `temperature`, `reasoning`, `tool_summary`.

## API health check

Verify the runtime is serving requests:

```bash
curl -s http://localhost:8643/health
# Expected: {"status":"ok"}
```

If port 8643 serves the unified proxy (not the gateway itself), check both:
```bash
curl -s http://localhost:8643/health    # unified proxy
curl -s http://localhost:8642/health    # gateway directly
```

## Smoke checks worth doing

- Load agent registry and assert expected defaults exist (`general`, `plan`) without removing user presets.
- Resolve permission policy examples for at least one `allow`, one `ask`, and one `deny` rule.
- Confirm newly added tools appear in `tools/registry.py` and in intended `toolsets.py` entries.
- For provider-routing changes, verify direct `api.openai.com` URLs use the intended OpenAI transport/Responses path rather than stale `api_mode` from config.
- For `delegate_task` routing, verify per-call `model` and `provider` override the child agent without mutating parent/session defaults.

## Review risks

- Secret-like strings in diffs or generated config examples.
- Accidental broad permission defaults (`allow` where policy should be `ask` or `deny`).
- Desktop-only command support: if a slash command is added, confirm gateway dispatch exists, not just CLI registration.
- Tool registry assumptions: prefer public registry/listing APIs or smoke imports; do not assume internal dict helpers like `ToolRegistry.get()` exist.
- Agent presets and personas are separate concepts. Do not remove core presets while adding personas or role UI.

## Commit hygiene

Use a message that names the runtime class, not only the UI symptom, for example:

```text
feat(runtime): add agent registry and permission policies
```

After committing, verify:

```bash
git status --short
git log -1 --pretty=format:'%h %s'
git show --stat --oneline -1
```
