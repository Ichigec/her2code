# OpenCode+ Orchestrator Pattern

When adapting the Hermes multi-agent orchestrator (`plan.md`) to OpenCode+, the
following are the key differences and the agent config shape.

## Config entry (opencode.json)

```json
"plan": {
  "mode": "primary",
  "description": "Orchestrator agent — 10-phase lifecycle",
  "model": "litellm/qwen3.6-35b-heretic",
  "options": { "chat_template_kwargs": { "enable_thinking": true } },
  "permission": {
    "edit": "ask",
    "bash": "ask",
    "read": "allow",
    "grep": "allow",
    "glob": "allow",
    "list": "allow",
    "task": "allow",
    "webfetch": "allow",
    "websearch": "allow"
  },
  "prompt": "<system prompt text or reference to .md file>"
}
```

## Key differences from Hermes

| Aspect | Hermes | OpenCode+ |
|--------|--------|-----------|
| Delegation tool | `delegate_task(model=..., provider=..., toolsets=[...], role="...")` | `task(subagent_name="build", description="...", prompt="...")` |
| Sub-agent identity | 12 specialized agent personas in `~/.hermes/agents/*.md` | 5 agents in config: build, deep-explore, summary, claw, composter |
| Role injection | Explicit `role`, `toolsets`, `model`, `provider` per call | Role described in `prompt` field; model inherited from agent config |
| Model routing | Per-call `model` + `provider` | Per-agent `model` in config; no provider concept |
| Tool scoping | `toolsets` list per delegation | `permission` object per agent (deny/ask/allow per tool) |
| System prompt | Markdown frontmatter + body in agent file | Embedded in JSON `prompt` field or referenced .md |
| Observability | Hermes session DB, memory, skills | Phoenix traces (via LiteLLM), step-reviewer plugin |

## Stack knowledge the orchestrator needs

1. **llama.cpp** — `:8092` host process, MTP speculative decoding, GGUF models
2. **LiteLLM** — Docker proxy `:4000`, model aliases, Phoenix traces
3. **LM Studio** — fallback on `:1234` when llama.cpp is off
4. **OpenCode web** — native binary `:3400`, full FS access, `OPENCODE_WORKSPACE_DIR`
5. **Profiles** — `opencode+/configs/profiles/*.env`, active in `opencode+/.env`
6. **Plugins** — `step-reviewer` (LLM overseer, nudges every 10 steps), `claw-compactor` (context management)
7. **Known bugs** — start-llama-qwen.sh clobbers profile, LiteLLM env-cache, workspace ACL for uid 10102

## Sub-agent usage pattern

Since OpenCode+ has fewer specialized agents than Hermes, the `build` agent plays
multiple roles. Inject the role description in the `prompt`:

```
task(
  subagent_name="build",
  description="System Analysis: root cause, goal tree, dev task spec",
  prompt="You are the System Analyst. Role: SMART analysis, 5 Whys, WSM/AHP.
          Requirements doc: docs/requirements/<slug>.md
          Output: docs/system-analysis/<slug>.md with sections:
          ## SMART Goal, ## 5 Whys, ## Goal Tree, ## Alternatives, ## Developer Task Spec"
)
```

For deep research (read-only, extended reasoning), use `deep-explore`:
```
task(
  subagent_name="deep-explore",
  description="Research: multi-source synthesis with citations",
  prompt="Research question: ... Sources to check: ... Output: docs/research/<slug>.md"
)
```

For implementation, spawn multiple `build` agents in parallel with TDD instructions.
