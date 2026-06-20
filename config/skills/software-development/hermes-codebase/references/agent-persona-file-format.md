# Agent Persona File Format

Each agent persona lives at `~/.hermes/agents/<id>.md` — a Markdown file with
YAML frontmatter + a system prompt body. This overrides the built-in agent
definition (from `agent/agents.py::_BUILTIN_AGENTS`). Config.yaml's `agents:`
block wins over both.

## File Structure

```markdown
---
description: One-line summary for the agent picker UI
mode: primary              # "primary" or "subagent"
reasoning: medium          # none|minimal|low|medium|high|xhigh
toolsets: []               # empty = all tools; list = restrict
label: Build               # display name in sidebar
emoji: 🔨                  # icon in sidebar
model: null                # null = session default; string = force model
temperature: null          # null = default; float = override
---

# Agent Title (optional H1 — purely cosmetic, not parsed)

Body text after the closing `---` becomes the `system_prompt` field.
This is injected as the ephemeral system prompt when the user switches
to this agent. Write it as you would a persona prompt — first-person,
instructional, defining the agent's role and methodology.
```

## Loading and Precedence

Three sources, merged in increasing precedence (from `agent/agents.py`):

1. **Built-in** — `_BUILTIN_AGENTS` dict in `agent/agents.py`. Defines
   `general`, `build`, `plan`, `review`, `safe`, `claw`, `composter`,
   `explore`, `scout`.
2. **Disk** — `~/.hermes/agents/*.md` files. Override built-in agents
   with the same `id` (derived from filename stem or `id` field in
   frontmatter).
3. **Config** — `config.yaml → agents:` block (mapping or list). Highest
   precedence — wins over both built-in and disk.

The merge layer (`_merge_layer`) carries over `emoji` and `label` from
lower-priority layers when the higher-priority layer omits them, so a
disk file without `emoji` doesn't blank out the built-in emoji.

`permission` (opencode-style) is ONLY used by subagents (`mode: "subagent"`).
Primary agents ignore it.

## Relevant Fields (from `AgentDef` dataclass)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | str | filename stem | Lowercase, unique |
| `label` | str | `id.title()` | Display name in sidebar |
| `description` | str | `""` | One-line for picker UI |
| `mode` | str | `"primary"` | `"primary"` or `"subagent"` |
| `emoji` | str | `""` | Sidebar icon |
| `model` | str\|None | None | Force a model; null = session default |
| `temperature` | float\|None | None | Force temperature |
| `reasoning` | str | `"medium"` | Reasoning effort level |
| `toolsets` | list[str] | `[]` | Empty = all tools enabled |
| `system_prompt` | str | `""` | Everything after the frontmatter `---` |
| `permission` | Any | None | Opencode-style deny/allow (subagents only) |

## How System Prompt Is Applied

From `agent/agents.py::apply_agent()` — the `system_prompt` body becomes
`agent.ephemeral_system_prompt`, which is appended after the main system
prompt (NOT replacing it). The main prompt carries tools, environment hints,
memory, skills — the ephemeral prompt adds the agent's persona on top.

```python
# In chat_completion_helpers.py:
effective_system = agent._cached_system_prompt or ""
if agent.ephemeral_system_prompt:
    effective_system = (effective_system + "\n\n" + agent.ephemeral_system_prompt).strip()
```

This means the persona prompt should be **additive** — it defines role,
methodology, and rules, but doesn't need to repeat tool documentation
or environment facts.

## Example: Current Agent Personas

All three agents share the same 10-phase + 1-gate lifecycle (~982 lines, ~40 KB),
differing only in frontmatter identity:

| Field | general.md | build.md | plan.md |
|-------|-----------|----------|---------|
| `label` | General | Build | Plan |
| `emoji` | 🧠 | 🔨 | 📋 |
| `description` | All tools — full lifecycle | Full dev access — full lifecycle | Planning specialist — full lifecycle |
| Intro role | versatile AI assistant | senior software engineer | planning specialist |

**Lifecycle** (10 phases + 1 verification gate):
Requirements → System Analysis → Deep Analysis → Architecture → Plan →
Implement → Verification Gate → Quality → Deployment → Post-Deploy Analysis → Iterate

Key methodology sections:
- **Phase 2: System Analysis** — 9-stage workflow (SMART → Data → Structure →
  5 Whys → Goal Tree → Alternatives → Model → Sensitivity → WSM/AHP + Task Spec),
  6 core principles (Final Goal, Integrity, Hierarchy, Multiplicity,
  Historicism, Conflict-free), 5 heuristics
- **Phase 3: Deep Analysis** — research methodology with classification gate
  (skipResearch/depthMode), iterative data collection (2-25 iterations),
  source deduplication + quality scoring, hypothesis formation/validation,
  structured citations
- **Phase 6.5: Verification Gate** — 4 checks (spec conformance, goal tree,
  root cause, abstraction level) + deviation routing
- **Phase 9: Post-Deployment Analysis** — mirrors Deep Analysis for evidence:
  iterative collection, evidence quality scoring, hypothesis validation,
  surprise discovery

## Pitfalls

- **Disk files override built-ins by id, not by filename.** If the
  frontmatter has `id: something-else`, that becomes the agent id,
  not the filename stem. Prefer keeping filename == id to avoid
  confusion.
- **Empty body = empty system_prompt.** If you only write frontmatter
  with no body, the agent won't get a persona — it'll fall back to
  the built-in system prompt (which is usually empty for `general`).
- **`reasoning` is a string, not a boolean.** Valid values:
  `none`, `minimal`, `low`, `medium`, `high`, `xhigh`.
- **Sub-phase references survive heading renumbering.** References like
  "see 8.3" or "skip to 2.8" are in prose, not headings — they won't be
  caught by heading-level patches. Scan the displaced phase's body text
  for `X.Y` patterns and update them manually.


When inserting a new phase into an existing agent persona with numbered phases:

0. **Back up the file first** — `cp agent.md agent.md.bak`. If Hermes runtime
   reverts your edits mid-session, you can recover from the backup. Keep the
   backup until all verification steps pass.
1. **Update the lifecycle table first** — replace the entire table with the
   new numbering. This gives you a canonical reference for all subsequent edits.
2. **Insert the new phase section** — use a patch that matches the separator
   text between the preceding phase and the heading you're displacing. Include
   the new phase content AND the renamed heading of the displaced phase in one
   patch to avoid leaving orphaned `---` separators.
3. **Renumber displaced phases one by one** — each `### Phase N` heading is
   unique enough for a targeted patch. Do all renumberings in parallel
   (multiple `patch()` calls in one turn) to minimise turn count.
4. **Update sub-phase numbers** (e.g., `#### 8.0` → `#### 9.0`) — these are
   in the displaced phase's section. Renumber all sub-phases in parallel.
5. **Update cross-references** — phases often reference each other (e.g.,
   "mirroring Phase 2.6", "proceed to Phase 9"). Search for the old phase
   numbers and update them. Pay special attention to references in the
   displaced phase's own body.
6. **Update the gates table** — add gates for the new phase, update
   transition labels for displaced phases.
7. **Update the depth/complexity table** — phases may be referenced by number
   in these tables.
8. **Verify immediately** — after all patches, run `wc -l` on the file and
   check key headings with `search_files(pattern="^### Phase")`. If the file
   reverted (line count dropped, old headings reappeared), recover from the
   backup and re-apply patches. The reversion can happen silently between any
   two tool calls.
9. **Update line/fact counts** — any documentation that mentions "N phases"
   or "X lines" needs refreshing.

- **The persona prompt is appended, not prepended.** Skill loads and
  tool definitions come first (in the main system prompt), then the
  ephemeral persona is appended. Write the persona assuming tool
  documentation is already present.
- **Frontmatter must start at byte 0** — no leading whitespace,
  BOM, or blank line before `---`.

- **Hermes runtime may overwrite persona files.** After editing
  `~/.hermes/agents/*.md`, the runtime (gateway, auto-save, or profile
  sync) may revert the file to a previous version. Always verify
  immediately after editing: `wc -l` + check key headings. If the file
  reverted, recover from a known-good copy (e.g., `cp build.md general.md`
  then re-patch the frontmatter). Keep one agent file as a backup while
  editing another — never edit the only copy of a large persona.
