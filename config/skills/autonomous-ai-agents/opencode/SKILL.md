---
name: opencode
description: "Delegate coding to OpenCode CLI (features, PR review)."
version: 1.3.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, OpenCode, Autonomous, Refactoring, Code-Review]
    related_skills: [claude-code, codex, hermes-agent]
---

# OpenCode CLI

Use [OpenCode](https://opencode.ai) as an autonomous coding worker orchestrated by Hermes terminal/process tools. OpenCode is a provider-agnostic, open-source AI coding agent with a TUI and CLI.

## When to Use

- User explicitly asks to use OpenCode
- You want an external coding agent to implement/refactor/review code
- You need long-running coding sessions with progress checks
- You want parallel task execution in isolated workdirs/worktrees

## Prerequisites

- OpenCode installed: `npm i -g opencode-ai@latest` or `brew install anomalyco/tap/opencode`
- Auth configured: `opencode auth login` or set provider env vars (OPENROUTER_API_KEY, etc.)
- Verify: `opencode auth list` should show at least one provider
- Git repository for code tasks (recommended)
- `pty=true` for interactive TUI sessions

## OpenCode HTTP API (Headless Sessions / "Subagents")

OpenCode runs as an HTTP server when started with `opencode web --hostname 127.0.0.1 --port 3400`. This provides full programmatic control:

```
HTTP API endpoints:
  GET  /global/health              — health check (returns version)
  GET  /provider                   — list all providers and models
  GET  /config                     — read opencode config
  POST /session                    — create a new session (a "subagent")
  DELETE /session/:id              — delete a session
  POST /session/:id/abort          — abort current generation
  POST /session/:id/message        — send a message to a session
  GET  /event                      — SSE stream of all events
```

Session creation payload:
```json
{
  "title": "agent-name",
  "agent": "build",       // or "plan"
  "model": {"providerID": "openai", "modelID": "gpt-5.5"}
}
```

Message payload:
```json
{
  "parts": [{"type": "text", "text": "your task here"}],
  "model": {"providerID": "...", "modelID": "..."}  // optional
}
```

SSE event filtering: events contain `sessionID` in properties — filter server-side or client-side.

Python client template: see `references/opencode-http-api.md`.

## Binary Resolution (Important)

Shell environments may resolve different OpenCode binaries. If behavior differs between your terminal and Hermes, check:

```
terminal(command="which -a opencode")
terminal(command="opencode --version")
```

If needed, pin an explicit binary path:

```
terminal(command="$HOME/.opencode/bin/opencode run '...'", workdir="~/project", pty=true)
```

## One-Shot Tasks

Use `opencode run` for bounded, non-interactive tasks:

```
terminal(command="opencode run 'Add retry logic to API calls and update tests'", workdir="~/project")
```

Attach context files with `-f`:

```
terminal(command="opencode run 'Review this config for security issues' -f config.yaml -f .env.example", workdir="~/project")
```

Show model thinking with `--thinking`:

```
terminal(command="opencode run 'Debug why tests fail in CI' --thinking", workdir="~/project")
```

Force a specific model:

```
terminal(command="opencode run 'Refactor auth module' --model openrouter/anthropic/claude-sonnet-4", workdir="~/project")
```

## Interactive Sessions (Background)

For iterative work requiring multiple exchanges, start the TUI in background:

```
terminal(command="opencode", workdir="~/project", background=true, pty=true)
# Returns session_id

# Send a prompt
process(action="submit", session_id="<id>", data="Implement OAuth refresh flow and add tests")

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send follow-up input
process(action="submit", session_id="<id>", data="Now add error handling for token expiry")

# Exit cleanly — Ctrl+C
process(action="write", session_id="<id>", data="\x03")
# Or just kill the process
process(action="kill", session_id="<id>")
```

**Important:** Do NOT use `/exit` — it is not a valid OpenCode command and will open an agent selector dialog instead. Use Ctrl+C (`\x03`) or `process(action="kill")` to exit.

### TUI Keybindings

| Key | Action |
|-----|--------|
| `Enter` | Submit message (press twice if needed) |
| `Tab` | Switch between agents (build/plan) |
| `Ctrl+P` | Open command palette |
| `Ctrl+X L` | Switch session |
| `Ctrl+X M` | Switch model |
| `Ctrl+X N` | New session |
| `Ctrl+X E` | Open editor |
| `Ctrl+C` | Exit OpenCode |

### Resuming Sessions

After exiting, OpenCode prints a session ID. Resume with:

```
terminal(command="opencode -c", workdir="~/project", background=true, pty=true)  # Continue last session
terminal(command="opencode -s ses_abc123", workdir="~/project", background=true, pty=true)  # Specific session
```

## Common Flags

| Flag | Use |
|------|-----|
| `run 'prompt'` | One-shot execution and exit |
| `--continue` / `-c` | Continue the last OpenCode session |
| `--session <id>` / `-s` | Continue a specific session |
| `--agent <name>` | Choose OpenCode agent (build or plan) |
| `--model provider/model` | Force specific model |
| `--format json` | Machine-readable output/events |
| `--file <path>` / `-f` | Attach file(s) to the message |
| `--thinking` | Show model thinking blocks |
| `--variant <level>` | Reasoning effort (high, max, minimal) |
| `--title <name>` | Name the session |
| `--attach <url>` | Connect to a running opencode server |

## Procedure

1. Verify tool readiness:
   - `terminal(command="opencode --version")`
   - `terminal(command="opencode auth list")`
2. For bounded tasks, use `opencode run '...'` (no pty needed).
3. For iterative tasks, start `opencode` with `background=true, pty=true`.
4. Monitor long tasks with `process(action="poll"|"log")`.
5. If OpenCode asks for input, respond via `process(action="submit", ...)`.
6. Exit with `process(action="write", data="\x03")` or `process(action="kill")`.
7. Summarize file changes, test results, and next steps back to user.

## Agent Configuration & Presets

OpenCode agent presets are defined in `opencode.json` under the `agent` key. Each agent is a named block that bundles model, permissions, system prompt, and UX metadata.

### Configuration Schema

```json
{
  "agent": {
    "<name>": {
      "mode": "primary",              // primary: main tab | secondary: agent selector
      "model": "provider/model-id",   // override default model
      "temperature": 0.1,            // optional, default: provider default
      "description": "...",          // shown in UI agent selector
      "options": {                   // provider-specific kwargs
        "chat_template_kwargs": {
          "enable_thinking": true
        }
      },
      "permission": {                // agent-specific permission overrides
        "read": { "**": "allow", "secrets/**": "deny" },
        "edit": { "**": "ask", "src/**": "allow" },
        "bash": { "*": "ask", "git *": "allow" },
        "webfetch": "deny",
        "websearch": "allow",
        "task": "deny"
      },
      "prompt": "..."                // inline system prompt (markdown)
    }
  }
}
```

### Key fields

| Field | Required | Notes |
|-------|----------|-------|
| `mode` | No | `"primary"` = main tab; omit/`"secondary"` = available via agent selector. Plan/summary agents are typically secondary. |
| `model` | No | Overrides global `model`. Use to give different agents different models (e.g. cheap model for plan, powerful for build). |
| `permission` | **Strongly recommended** | Empty `{}` inherits global permissions — dangerous for agents that write code. Lock down `edit` and `bash` scopes, deny `task`/`webfetch` for read-only agents. |
| `prompt` | No | Inline system prompt. Can reference `AGENTS.md` or `.ai/skills/` via relative paths. Keep under 5K chars — large prompts eat context tokens before work starts. |
| `temperature` | No | Lower (0.1–0.2) for analytical/planning agents, default for creative. |

### Live inspection

Query the running OpenCode server for the active agent config:

```bash
curl -s http://127.0.0.1:3400/config | python3 -c "
import sys, json
c = json.load(sys.stdin)
agents = c.get('agent', {})
for name, cfg in agents.items():
    prompt_len = len(cfg.get('prompt', ''))
    perms = 'custom' if 'permission' in cfg else 'inherited'
    print(f'{name}: mode={cfg.get(\"mode\",\"?\")}, model={cfg.get(\"model\",\"?\")}, '
          f'prompt={prompt_len}chars, perms={perms}')
"
```

### opencode+ agent ecosystem

For User's opencode+ setup (`/home/user/cursor/opencode+/configs/opencode.litellm-dual.json`), see `references/opencode-agent-configuration.md` for the full agent comparison table, the `general` agent deep-dive, and the Hermes→OpenCode prompt porting analysis.

## Pitfall: Cross-ecosystem prompt porting

Copying a system prompt from one agent framework (e.g. Hermes) into OpenCode without adaptation produces **dead instructions** — references to tools/skills/paths that don't exist in OpenCode. Before porting a prompt, verify every tool name, skill reference, and file path resolves in the target ecosystem.

**Consequence of dead references:** constraints that reference non-existent tools become cosmetic — the agent sees "run SAST audit" but can't, so the constraint doesn't bite. This creates a "constraint relaxation" effect where an agent with more dead refs is paradoxically *more* flexible (less constrained) than one with all tools working. See `references/dead-refs-constraint-relaxation.md` for the full analysis with real examples from the opencode+ `general` agent.

See `references/opencode-agent-configuration.md` for concrete examples from the opencode+ `general` agent.

## OpenCode+ Claw Compactor & Neo4j

When working with the opencode+ ecosystem (claw agent, composter, Neo4j graph,
`.compactor/` audit trail), load `references/opencode-plus-claw-neo4j.md` — it
covers the claw-compactor plugin config, Neo4j sync commands, graph traversal
patterns, and pitfalls (parameterised variable-length Cypher patterns, registry
vs checkpoint sync semantics, depends_on coverage targets).

## PR Review Workflow

OpenCode has a built-in PR command:

```
terminal(command="opencode pr 42", workdir="~/project", pty=true)
```

Or review in a temporary clone for isolation:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && opencode run 'Review this PR vs main. Report bugs, security risks, test gaps, and style issues.' -f $(git diff origin/main --name-only | head -20 | tr '\n' ' ')", pty=true)
```

## Parallel Work Pattern

Use separate workdirs/worktrees to avoid collisions:

```
terminal(command="opencode run 'Fix issue #101 and commit'", workdir="/tmp/issue-101", background=true, pty=true)
terminal(command="opencode run 'Add parser regression tests and commit'", workdir="/tmp/issue-102", background=true, pty=true)
process(action="list")
```

## Session & Cost Management

List past sessions:

```
terminal(command="opencode session list")
```

Check token usage and costs:

```
terminal(command="opencode stats")
terminal(command="opencode stats --days 7 --models anthropic/claude-sonnet-4")
```

## Pitfalls

- Interactive `opencode` (TUI) sessions require `pty=true`. The `opencode run` command does NOT need pty.
- `/exit` is NOT a valid command — it opens an agent selector. Use Ctrl+C to exit the TUI.
- PATH mismatch can select the wrong OpenCode binary/model config.
- **HTTP API `POST /session` 400 error**: Happens when the modelID doesn't exist in the specified provider. Always `GET /provider` first to get the live model list, then pick a modelID from the provider's `models` dict. The `connected` array shows which providers are authenticated.
- If OpenCode appears stuck, inspect logs before killing:
  - `process(action="log", session_id="<id>")`
- Avoid sharing one working directory across parallel OpenCode sessions.
- Enter may need to be pressed twice to submit in the TUI (once to finalize text, once to send).
- **JSON `agent` section rejects non-agent keys.** Do not add `_comment` or `_note` fields inside `"agent": {}` — OpenCode validates every key as an agent object. Use markdown agents (`.opencode/agents/<name>.md`) or external docs for commentary.
- **Cross-ecosystem prompt porting produces dead instructions.** Copying a system prompt from Hermes into OpenCode without adapting tool names, skill references, and file paths leaves 80% of instructions unexecutable. See `references/opencode-agent-configuration.md` for the full checklist and concrete examples.

## Verification

Smoke test:

```
terminal(command="opencode run 'Respond with exactly: OPENCODE_SMOKE_OK'")
```

Success criteria:
- Output includes `OPENCODE_SMOKE_OK`
- Command exits without provider/model errors
- For code tasks: expected files changed and tests pass

## Rules

1. Prefer `opencode run` for one-shot automation — it's simpler and doesn't need pty.
2. Use interactive background mode only when iteration is needed.
3. Always scope OpenCode sessions to a single repo/workdir.
4. For long tasks, provide progress updates from `process` logs.
5. Report concrete outcomes (files changed, tests, remaining risks).
6. Exit interactive sessions with Ctrl+C or kill, never `/exit`.
