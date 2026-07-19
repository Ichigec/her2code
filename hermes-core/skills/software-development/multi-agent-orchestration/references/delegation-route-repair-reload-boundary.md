# Delegation route repair: reload boundary and proof pattern

Use this reference when fixing Hermes delegation/model-provider routing itself, especially after a failed `delegate_task` smoke with HTTP 404/400.

## Durable lesson

A live Hermes session may keep already-imported `tools.delegate_tool`, `runtime_provider`, and runtime `CLI_CONFIG` in memory. After patching files under `~/.hermes/hermes-agent` or editing `~/.hermes/config.yaml`, a `delegate_task` called from the same old session can still fail on the old route. That failure does not necessarily falsify the disk fix.

## Required proof sequence

1. **TDD RED**: add a regression test for the exact route bug and verify it fails for the expected reason.
   - Example invariant: `custom:openai` with `base_url=https://api.openai.com/v1` must resolve to `api_mode=codex_responses` even if config had stale `chat_completions`.
2. **GREEN minimal core fix**: prefer URL-derived transport for known endpoint shapes over stale saved config. For OpenAI direct API, `api.openai.com` implies Responses API routing for GPT-5.x children.
3. **Targeted tests**: run the new regression plus delegation schema/per-task routing tests.
4. **Config boundary**: if live config has stale route fields, create a timestamped backup before the minimal edit.
   - Example backup: `cp -p ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-delegation-routing-$(date +%Y%m%d_%H%M%S)`.
5. **Do not trust same-session smoke after source/config repair**: the parent process may be stale. Use a fresh Hermes process from the patched checkout for live proof.
6. **Fresh-process smoke**: start `./venv/bin/hermes chat -Q --toolsets delegation ...` and ask it to run one tiny `delegate_task` with explicit `model` and `provider`. Accept only a child completion containing the sentinel.
7. **Full touched-file regression**: run the complete tests for every modified runtime/test file.
8. **Rollback doc**: record exact repo files, config backup path, and `git restore`/`cp -p` rollback commands. Do not use `git restore .` in Pavel's Hermes repo because unrelated local work is often present.

## Smoke probe template

```bash
cd /home/user/.hermes/hermes-agent
./venv/bin/hermes chat -Q --toolsets delegation \
  --model gpt-5.5 --provider custom:openai \
  -q "Run exactly one delegate_task smoke probe. Use delegate_task with goal: 'Reply exactly CHILD_SMOKE_OK and nothing else', context: 'live delegation route smoke', toolsets: [], model: 'gpt-5.5', provider: 'custom:openai'. After the tool result, answer with SMOKE_PASS if the child completed and its summary contains CHILD_SMOKE_OK; otherwise answer SMOKE_FAIL plus the raw status."
```

Expected output shape:

```text
session_id: <fresh-session-id>
SMOKE_PASS
```

## Rollback template

```bash
cd /home/user/.hermes/hermes-agent
git restore \
  hermes_cli/runtime_provider.py \
  tests/hermes_cli/test_runtime_provider_resolution.py \
  tests/tools/test_delegate.py \
  tools/delegate_tool.py

cp -p \
  /home/user/.hermes/config.yaml.bak-delegation-routing-YYYYMMDD_HHMMSS \
  /home/user/.hermes/config.yaml
```

## Pitfalls

- A default `delegate_task` smoke proves only child spawning, not the intended model/provider route.
- A failed same-session smoke after patching Hermes may be stale-process evidence, not a failed disk fix.
- Editing `~/.hermes/config.yaml` is a user-visible side effect: backup first and document rollback.
- Keep rollback scoped to touched files; Pavel's Hermes checkout commonly has unrelated modified/untracked files.
