# Change-analysis checklist for Hermes Agent and related projects

Use this when the user asks "проведи глубокий анализ изменений" / "всё ли работает" / "review what we changed today" across Hermes Agent, agent configs, and companion projects (Android, OpenCode+, etc.).

## 1. Scope the day

- List recent sessions with `session_search(limit=10)` or `session_search(query="...")`.
- Identify which projects were touched. Common set:
  - `~/.hermes/hermes-agent/` (Hermes Agent source)
  - `~/.hermes/agents/` (agent personas)
  - `~/.hermes/config.yaml`
  - `/home/user/dev/Opencode/` (Android app)
  - `~/.hermes/scripts/`, `~/.hermes/plugins/`
- Record mtime of key files: `stat -c '%y %n' <paths>`.

## 2. Source inventory

| Project | Command | What to look for |
|---|---|---|
| Hermes Agent | `git log --oneline --since='YYYY-MM-DD 00:00' main..dev` | Commits today in dev |
| Hermes Agent | `git diff --stat main..dev` | Which files changed |
| Android | `git log --oneline --since='YYYY-MM-DD 00:00' --all` | Commits today |
| Android | `git diff --stat initial..master` (or appropriate base) | Changes since baseline |

## 3. Syntax / build verification

| Layer | Command | Expected |
|---|---|---|
| Changed Python modules | `python3 -m py_compile <files>` | exit 0 |
| Targeted tests | `pytest <relevant tests> -x -q` | all passed |
| Desktop UI | `npm run type-check` (in `apps/desktop/`) | `tsc -b` exit 0 |
| Android | `./gradlew assembleDebug` | exit 0 |

## 4. Agent-config validation

- Validate YAML frontmatter on every changed `~/.hermes/agents/**/*.md`:
  ```python
  import yaml
  if content.startswith('---'):
      _, front, _ = content.split('---', 2)
      meta = yaml.safe_load(front)
  ```
- Check `mode` consistency with orchestrator expectations (e.g. Tech Lead v3 for Phase 6 should be `mode: primary`).
- **Resolve every distinct provider** used by changed agents:
  ```python
  from hermes_cli.runtime_provider import resolve_runtime_provider
  resolve_runtime_provider(requested='<provider>', target_model='<model>')
  ```
  A "Unknown provider" error here means the agent cannot run even if everything else is correct.
- Compare `~/.hermes/config.yaml` against its latest backup (`~/.hermes/backups/config.yaml.stable-*`) to spot unintended changes to default model/provider.

## 5. Plugin / provider runtime checks

```python
from hermes_cli.plugins import discover_plugins
from plugins.memory import load_memory_provider

discover_plugins(force=True)
load_memory_provider('<name>')
```

- Verify the plugin registers the expected hooks.
- Verify memory providers load and `is_available()` is `True`.
- For `observer-hook`, confirm `observer_worker.py` exists at the path the plugin expects.

## 5a. Code quality / dead-code scan

When the user asks for depth beyond "does it build" — evaluate code quality, redundancy, and performance:

- **Two-write-path detection:** Search for multiple INSERT/UPDATE patterns writing to the same table. E.g. `ConsolidationManager._write_consolidation()` and `SegTreeMem.consolidate()` both write to `memory_consolidations` — one is likely dead code.
- **O(n) in loops**: Scan for `.index()`, `.count()`, `for x in y: z.index(x)` patterns in hot paths (query handlers, scorers).
- **Dead methods**: Search for method definitions with no callers (`grep` for method name across codebase). Quick probe: `grep -r "method_name" --include='*.py' | grep -v "def method_name"`.
- **Orphan agent configs**: Cross-reference `~/.hermes/agents/planN/*.md` files against the desktop dropdown arrays in `subagent-dropdown.tsx`. Files that exist but aren't in the dropdown cannot be selected via UI.
- **Degraded fallbacks**: Does the code have a graceful degradation path (e.g. `_build_placeholder_summary`) that works when LLM is unavailable? Is that path tested?
- **Missing test coverage**: Check if new modules (segtree, observer-hook) have dedicated test files. `glob('tests/**/test_*segtree*')` → empty = risk of regression.

Reference: `references/segtree-consolidation-code-review.md` for worked examples from a real audit.

## 6. Sensitive-data scan

Search changed files for:
- `api_key:` in `config.yaml`
- fallback credentials like `neo4j:<YOUR_NEO4J_PASSWORD>` in plugin code
- hardcoded tokens, passwords, or secrets

Replace findings with `[REDACTED]` in reports and recommend env-var or credential-pool migration.

## 7. Synthesize the report

Structure:
1. Executive summary (works / doesn't work).
2. Inventory of changes per project.
3. Verification results table.
4. Problems ranked by severity with reproducible evidence.
5. Actionable fixes in priority order.

Always answer the user's implicit question directly: e.g. "Всё ли работает как надо?" → explicit yes/no per layer.
