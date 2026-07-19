# Plan3 Pre-Delegation Hook Enforcement (2026-07-15)

Real-time model routing enforcement via Hermes `pre_tool_call` plugin hook.
Blocks invalid `delegate_task` calls BEFORE the subagent spawns — prevents
cloud models or wrong-role models from ever reaching a sub-agent.

## Architecture

```
delegate_task(model="deepseek-v4-pro", provider="deepseek", goal="Research GRPO...")
    │
    ▼
handle_function_call() → get_pre_tool_call_block_message()
    │
    ▼
plan3-routing-enforcer plugin: _on_pre_tool_call()
    │
    ├─ classify_role("Research GRPO...") → "reasoning"
    ├─ validate: deepseek = CLOUD ❌
    ├─ validate: deepseek-v4-pro ≠ agents-a1-abliterated ❌
    └─ return {"action": "block", "message": "🚫 CLOUD PROVIDER..."}
    
→ delegate_task BLOCKED, error returned to orchestrator
→ Orchestrator can correct model/provider and retry
```

## Three-Layer Defense

| Layer | Component | Path | Scope |
|:-----:|-----------|------|-------|
| 1 — Runtime | **Hermes Plugin** `plan3-routing-enforcer` | `~/.hermes/plugins/plan3-routing-enforcer/` | Blocks invalid `delegate_task` in real-time via `pre_tool_call` hook |
| 2 — Manual | **Validation Script** | `~/.hermes/scripts/validate-plan3-delegation.py` | CLI tool for pre-delegation manual checks |
| 3 — Session | **Plan3 Profile** | `~/.hermes/profiles/plan3/` | Ensures orchestrator session itself uses local model (not cloud default) |

## Layer 1: Hermes Plugin

### Mechanism

Uses `pre_tool_call` hook — fires BEFORE any tool executes. When the tool is
`delegate_task`, extracts `model`, `provider`, and `goal` from args, classifies
the role, and validates against the routing table.

Returns `{"action": "block", "message": "..."}` to block invalid calls, or
`None` to allow.

### Routing Table (hardcoded in plugin)

```python
ROUTING = {
    "reasoning":  {"model": "agents-a1-abliterated", "provider": "custom:local", "port": 8102},
    "coding":     {"model": "nex-n2-mini",           "provider": "custom:local", "port": 8101},
    "simulation": {"model": "agentworld",            "provider": "custom:local", "port": 8103},
}
```

### Role Classification

Auto-classifies from `goal` text using keyword matching (Russian + English).
203 keywords across 3 categories. Falls back to "reasoning" if no match.

### Block Message Format

```
╔══════════════════════════════════════════════════════════════╗
║  PLAN3 ROUTING ENFORCER — DELEGATION BLOCKED               ║
╠══════════════════════════════════════════════════════════════╣
║  🚫 CLOUD PROVIDER 'deepseek' — plan3 requires LOCAL only.  ║
║  🔀 WRONG MODEL: 'deepseek-v4-pro' for reasoning role.      ║
╠══════════════════════════════════════════════════════════════╣
║  FIX: delegate_task(model='agents-a1-abliterated',          ║
║       provider='custom:local', role='...')                  ║
╠══════════════════════════════════════════════════════════════╣
║  Model routing (plan3):                                     ║
║    Reasoning  → agents-a1-abliterated :8102                ║
║    Coding     → nex-n2-mini           :8101                ║
║    Simulation → agentworld            :8103                ║
╚══════════════════════════════════════════════════════════════╝
```

### Configuration

```bash
# Emergency disable (not recommended)
export PLAN3_ROUTING_DISABLE=1

# Warn-only mode (log warning, don't block)
export PLAN3_ROUTING_WARN_ONLY=1
```

### Supported Modes

- **Single-task**: `delegate_task(goal=..., model=..., provider=...)`
- **Batch**: `delegate_task(tasks=[{goal, model, provider}, ...])` — validates each task, blocks on first invalid

Only validates when `model`/`provider` are explicitly set AND `goal` is present.
Pass-through calls without explicit routing are unaffected.

## Layer 2: Validation Script

```bash
# Auto-classify from goal text
python3 ~/.hermes/scripts/validate-plan3-delegation.py \
  --model agents-a1-abliterated --provider custom:local \
  --goal "Research GRPO papers"
# → {"valid": true, "role": "reasoning", ...}

# Explicit role
python3 ~/.hermes/scripts/validate-plan3-delegation.py \
  --model deepseek-v4-pro --provider deepseek --role coding
# → {"valid": false, "errors": ["CLOUD PROVIDER...", "WRONG MODEL..."]}
# Exit code: 1 (invalid), 0 (valid)

# Dump routing table
python3 ~/.hermes/scripts/validate-plan3-delegation.py --json
```

## Layer 3: Plan3 Profile

```bash
# One-time setup
hermes profile create plan3 --clone-from default
hermes --profile plan3 config set model.default agents-a1-abliterated
hermes --profile plan3 config set model.provider custom:local
hermes --profile plan3 config set delegation.model agents-a1-abliterated
hermes --profile plan3 config set delegation.provider custom:local

# Usage
hermes --profile plan3          # start session with local model
/profile plan3                  # switch in-session
```

Without the profile, orchestrator session runs on `config.yaml`'s
`model.default` (could be `deepseek-v4-pro`) — split-brain: orchestrator
on cloud, sub-agents on local.

## Integration with plan3.md

The `plan3.md` orchestrator file includes a section `### Automated Pre-Delegation Enforcement (HOOK)` that documents:
- The plugin and what it blocks
- How to disable/warn-only
- The validation script
- The plan3 profile
- Updated Pre-Delegation Checklist

## Pitfalls

- **Plugin auto-discovery**: User plugins in `~/.hermes/plugins/` are auto-discovered by Hermes on startup. No manual install needed.
- **Profile-aware paths**: The plugin uses `get_hermes_home()` so it works correctly across profiles.
- **Warn-only for rollout**: Start with `PLAN3_ROUTING_WARN_ONLY=1` to observe what would be blocked without actually blocking. Review logs, then enable full blocking.
- **Keyword classification edge cases**: If a goal has zero keyword matches, it defaults to "reasoning". If confidence is below 30%, the delegation proceeds with a log warning. Review warn-only logs before enabling blocking to catch misclassifications.
- **Not a replacement for `validate-plan3-models.py`**: The static validation script checks frontmatter/registry drift at rest. The hook enforces runtime routing. Both are needed.
