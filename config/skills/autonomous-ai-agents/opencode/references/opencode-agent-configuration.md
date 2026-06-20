# OpenCode Agent Configuration — opencode+ Reference

> Captured from session analyzing the `general` agent in User's opencode+ setup.
> Config file: `/home/user/cursor/opencode+/configs/opencode.litellm-dual.json`
> Running server: `http://127.0.0.1:3400` (OpenCode v1.15.5)

## Agent roster

| Agent | Mode | Model | Temp | Permissions | Prompt | Description |
|-------|------|-------|------|-------------|--------|-------------|
| `general` | primary | qwen3.6-35b-heretic | default | `{}` — **unrestricted** | 15.9K chars | — |
| `build` | primary | qwen3.6-35b-heretic | default | `{}` — **unrestricted** | none | "Full development agent — edit + bash allowed" |
| `deep-explore` | primary | qwen3.6-35b-heretic | default | edit: deny, bash: deny | none | "Deep code research with extended reasoning" |
| `claw` | primary | qwen3.6-35b-heretic | 0.1 | Locked to `.compactor/` only | 6K chars | "Stateless skill/MCP compactor" |
| `composter` | primary | qwen3.6-35b-a3b-heretic (LM Studio) | 0.2 | edit: deny globally | 3.7K chars | "Stateful read-only audit-trail reader" |
| `plan` | secondary | qwen3.6-35b-heretic | default | inherited | none | — |
| `summary` | secondary | qwen3.6-35b-heretic | default | inherited | none | — |

## The `general` agent

### What it is

The `general` agent in opencode+ is a **direct port** of the Hermes Agent system prompt, frozen at version 1 (before Classification Gate, evidence quality scoring, and iterative data collection were added to the Hermes version).

### Prompt structure (15.9K chars, 410 lines)

9-phase SDLC with rigorous methodology:
1. Requirements → `docs/requirements/<slug>.md`
2. Deep Analysis (8 sub-phases of research methodology)
3. Architecture → `docs/architecture/<slug>.md`
4. Plan (BDUF) → `.hermes/plans/<ts>-<slug>.md`
5. Implement (TDD + secure-coding + SRP)
6. Quality (review + SAST gate)
7. Deployment
8. Post-Deployment Analysis
9. Iterate (retrospective + continuous improvement)

### Dead references (inherited from Hermes)

The prompt references Hermes-specific tools/skills/paths that **don't exist in OpenCode**:

| Reference | Count | Hermes equivalent | OpenCode reality |
|-----------|-------|-------------------|-----------------|
| `build-engineering-standards` | 4 | `skill_view("build-engineering-standards")` | No such skill |
| `requirements-analysis` | 2 | `skill_view("requirements-analysis")` | No such skill |
| `architecture-design` | 2 | `skill_view("architecture-design")` | No such skill |
| `test-driven-development` | 2 | `skill_view("test-driven-development")` | No such skill |
| `secure-coding` | 6 | `skill_view("secure-coding")` | No such skill |
| `sast-audit` | 7 | `skill_view("sast-audit")` | No such skill |
| `sast-setup` | 2 | `skill_view("sast-setup")` / `/sast-setup` | No such skill |
| `deployment-operations` | 2 | `skill_view("deployment-operations")` | No such skill |
| `continuous-improvement` | 2 | `skill_view("continuous-improvement")` | No such skill |
| `requesting-code-review` | 2 | `skill_view("requesting-code-review")` | No such skill |
| `implementation-delivery` | 2 | `skill_view("implementation-delivery")` | No such skill |
| `subagent-driven-development` | 1 | `skill_view("subagent-driven-development")` | No such skill |
| `delegate_task` | 2 | Hermes tool `delegate_task()` | OpenCode `task` tool (different API) |
| `.hermes/plans/` | 2 | Hermes plans directory | Path doesn't make sense in OpenCode |
| `/build`, `/security`, `/sast-setup` | 4 | Hermes slash commands | Not supported in OpenCode |

### Security gap

`permission: {}` — the `general` agent **inherits global permissions** (only `doom_loop: ask`). This means:
- Can edit ANY file in the workspace
- Can run ANY bash command (including destructive ones)
- Can make web requests
- Has no sandboxing beyond what OpenCode provides by default

Compare with `claw` (locked to `.compactor/`), `composter` (edit: deny globally), `deep-explore` (edit: deny + bash: deny).


---

## Adapted `general` agent (v2 — markdown-based, post-session)

After the analysis above, the `general` agent was recreated as a native
**OpenCode markdown agent** (`.opencode/agents/general.md`), replacing the
broken inline JSON definition.

### Key improvements

| Aspect | Old (JSON inline) | New (`.opencode/agents/general.md`) |
|--------|------------------|--------------------------------------|
| **Format** | Inline JSON string in `opencode.json` | Markdown with YAML frontmatter — auto-discovered by OpenCode |
| **Prompt** | 15.9K chars, Hermes v1 (dead references) | 25.6K chars, adapted for OpenCode-native tools |
| **Classification Gate** | ❌ | ✅ Phase 2.0: skipResearch, depthMode, parallelWidgets |
| **Iterative Data Collection** | ❌ | ✅ Iteration budget (2/6/25), reasoning preamble, iteration log |
| **Source Quality Scoring** | ❌ | ✅ 4-criterion (Authority/Recency/Relevance/Corroboration 0-2) |
| **Source Deduplication** | ❌ | ✅ Dedup report |
| **Structured Citations** | ❌ | ✅ RQ→sources index mapping |
| **Evidence Quality (Phase 8)** | ❌ | ✅ 4-criterion (Reliability/Precision/Relevance/Reproducibility 0-2) |
| **Iterative Evidence (Phase 8)** | ❌ | ✅ Iteration budget, evidence collection log |
| **Tools referenced** | Hermes-specific (skill_view, delegate_task, /build) — none work | OpenCode-native (grep, glob, edit, bash, task, websearch, webfetch, todowrite) |
| **Permissions** | `{}` — unrestricted | `edit: ask`, `bash: ask` with safe allowlist, `task: allow`, `webfetch/websearch: allow` |
| **Model** | `qwen3.6-35b-heretic` (general-purpose) | `deepseek-reasoner` (thinking model for analytical depth) |
| **Temperature** | default | `0.1` (deterministic analysis) |
| **Steps limit** | Not set | `90` (explicit iteration cap) |

### File locations

```
/home/user/cursor/first/.opencode/agents/general.md  ← workspace (source of truth)
~/.config/opencode/agents/general.md                    ← global copy
```

Both are auto-discovered. The inline JSON definition was **removed** from
`opencode.litellm-dual.json` to avoid conflicts.

### Permissions design

Designed for BDUF safety — analytical agent with cautious defaults:

```yaml
permission:
  read: allow          # always
  edit: ask            # prompt before any file write
  glob: allow          # safe
  grep: allow          # safe
  list: allow          # safe
  bash:
    "*": ask           # prompt before any command
    "git status*": allow
    "git diff*": allow
    "git log*": allow
    "grep *": allow
    "rg *": allow
    "find *": allow
    "ls *": allow
    "cat *": allow
    "head *": allow
    "tail *": allow
    "wc *": allow
  task: allow          # can spawn subagents for parallel work
  webfetch: allow      # research needs web access
  websearch: allow     # research needs web access
  todowrite: allow     # track phase progress
  todoread: allow      # track phase progress
```

### Verification

```bash
curl -s http://127.0.0.1:3400/config | python3 -c "
import sys, json
c = json.load(sys.stdin)
g = c['agent']['general']
print(f'mode={g[\"mode\"]}, model={g[\"model\"]}, prompt={len(g[\"prompt\"])}chars')
print(f'perms: {list(g[\"permission\"].keys())}')
"
# → mode=primary, model=litellm/deepseek-reasoner, prompt=25555chars
# → perms: ['read', 'edit', 'glob', 'grep', 'list', 'bash', 'task', 'webfetch', 'websearch', 'todowrite', 'todoread']
```

## Agent definition formats

OpenCode supports two formats for agent definitions:

### 1. JSON inline (in `opencode.json`)

```json
{
  "agent": {
    "my-agent": {
      "mode": "primary",
      "model": "provider/model-id",
      "temperature": 0.1,
      "description": "What this agent does",
      "permission": { "edit": "ask", "bash": "ask" },
      "prompt": "You are the my-agent assistant..."
    }
  }
}
```

**Pitfalls:**
- Prompt escapes are painful (JSON strings with `\n`, `\"`, unicode)
- Large prompts bloat the config file
- No syntax highlighting support for the prompt content
- Config validation rejects unknown keys — `_comment` fields break it

### 2. Markdown files (`.opencode/agents/<name>.md`)

```markdown
---
description: What this agent does
mode: primary
model: provider/model-id
temperature: 0.1
permission:
  edit: ask
  bash: ask
---
You are the my-agent assistant...
```

**Advantages over JSON inline:**
- Auto-discovered — no need to register in `opencode.json`
- Markdown body is the system prompt — clean, syntax-highlighted, no escaping
- YAML frontmatter is the config — compact, readable
- Easy to edit: open in any editor, no JSON parsing
- Works in both `~/.config/opencode/agents/` (global) and `.opencode/agents/` (project)

**Discovery priority:** `.opencode/agents/` (project) overrides `~/.config/opencode/agents/` (global). Both are merged with the JSON config's `agent` section.

**Known issue:** `_comment_*` keys in the JSON `agent` section are NOT allowed — OpenCode validates every key as an agent object. Use comments in the prompt body or separate documentation files instead.

## Cross-ecosystem prompt porting checklist

When porting a system prompt from one agent framework to another (e.g. Hermes → OpenCode):

1. **Tool names** — map every tool reference: `skill_view()` → `AGENTS.md`/`.ai/`, `delegate_task` → `task`, `patch()` → `edit`, `web_search` → `websearch`
2. **Skill references** — if target has no skill system, inline the methodology or reference project docs
3. **File paths** — `.hermes/plans/` → `docs/plans/`, `~/.hermes/skills/` → `.ai/skills/`
4. **Slash commands** — `/build`, `/security` → describe in prose
5. **Permission model** — Hermes sandbox ≠ OpenCode permissions; add explicit `permission` blocks
6. **Memory/persistence** — Hermes has `memory()` + `session_search()`; OpenCode has neither. Don't reference.
7. **Subagent API** — Hermes `delegate_task(goal, context, toolsets)` ≠ OpenCode `task` tool. Adapt accordingly.
8. **Model selection** — match agent purpose to available model capabilities (thinking models for analysis, fast models for plan)
