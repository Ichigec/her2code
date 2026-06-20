# hermes-opencode

opencode-style **agents**, **permissions**, and **tools** for Hermes.

## What it provides

- **Declarative permission engine** (`agent/permissions.py`): per-tool
  `allow` / `ask` / `deny` with glob + command patterns, per-model gating, and
  a global + per-agent merge. This plugin primes the engine and acts as the
  update-safe `deny` enforcement point via a `pre_tool_call` hook.
- **opencode-parity tools**: `glob`, `list`, `lsp` (self-registering in
  `tools/glob_tool.py`, `tools/list_tool.py`, `tools/lsp_tool.py`; grouped into
  the `file` and `lsp` toolsets).
- **Agent registry** (`agent/agents.py`): one source of truth for `/agent`
  presets across CLI, TUI, gateway, and desktop, including the read-only
  opencode subagents `explore` and `scout`.

## Enabling

This plugin lives in `~/.hermes/plugins/` and is opt-in:

```
hermes plugins enable hermes-opencode
```

The permission engine and the `glob`/`list`/`lsp` tools work without the plugin
(they are wired into core); enabling the plugin adds the redundant, update-safe
`deny` enforcement hook and primes plugin-declared rights.

## Permission model

A `permission:` block (in `config.yaml`, a per-agent definition, or this
plugin's `plugin.yaml`) maps capability **keys** to actions:

```yaml
permission:
  edit: deny                 # shorthand: applies to write_file / patch
  bash:                      # {pattern: action}, last-match-wins; "*" = default
    "*": allow
    "git push *": ask
    "rm -rf *": deny
  webfetch: ask
```

Precedence (lowest → highest): **plugin** rights → **global** `config.yaml`
`permission:` → **per-agent** `permission:`. The cross-cutting
`model_policies:` layer is merged in *most-restrictive-wins*.

### Capability key → Hermes tool mapping

| opencode key | Hermes tool(s)                          | pattern subject |
| ------------ | --------------------------------------- | --------------- |
| `read`       | `read_file`                             | path            |
| `edit`       | `write_file`, `patch`, `apply_patch`    | path            |
| `bash`       | `terminal`, `process`, `execute_code`   | command/code    |
| `webfetch`   | `web_extract`                           | url             |
| `websearch`  | `web_search`                            | query           |
| `task`       | `delegate_task`                         | subagent name   |
| `glob`       | `glob`, `search_files(target=files)`    | pattern         |
| `grep`       | `grep`, `search_files(target=content)`  | pattern         |
| `list`       | `list`                                  | path            |
| `todowrite`  | `todo`                                  | —               |
| `question`   | `clarify`                               | —               |
| `lsp`        | `lsp`                                   | path            |

### model_policies (cross-cutting)

```yaml
model_policies:
  - models: ["*mini*", "*haiku*"]
    permission:
      task: deny          # small/cheap models may not spawn subagents
      bash: deny
```

## Tool aliasing (opencode name → Hermes tool)

opencode's tool names map onto existing Hermes tools — no new code, just naming:

| opencode tool | Hermes tool      | notes                                  |
| ------------- | ---------------- | -------------------------------------- |
| `apply_patch` | `patch`          | V4A multi-file patches (`mode=patch`)  |
| `todowrite`   | `todo`           | task planning / tracking               |
| `question`    | `clarify`        | multiple-choice / open-ended questions |
| `task`        | `delegate_task`  | spawn a subagent                       |
| `glob`        | `glob`           | first-class (this plugin)              |
| `list`        | `list`           | first-class (this plugin)              |
| `lsp`         | `lsp`            | first-class (this plugin)              |
| `read`        | `read_file`      |                                        |
| `edit`/`write`| `write_file`     |                                        |
| `bash`        | `terminal`       |                                        |
| `grep`        | `search_files`   | `target=content`                       |
| `webfetch`    | `web_extract`    |                                        |
| `websearch`   | `web_search`     |                                        |

## Authoring agents

Drop a Markdown file with YAML frontmatter in `~/.hermes/agents/<id>.md`:

```markdown
---
description: Read-only reviewer
mode: primary
model: anthropic/claude-sonnet-4
reasoning: medium
toolsets: [web, search, file]
permission:
  edit: deny
  bash: deny
---
You are a meticulous code reviewer. Do not modify files.
```

Or inline under `config.yaml -> agents:`. Both override the built-ins by id.
Switch with `/agent <id>` on any surface.
