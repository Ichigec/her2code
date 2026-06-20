# Promptbreeder Hot-Swap Patterns for Hermes

> Condensed from research cycle `promptbreeder-hotswap_20260615_213730`.
> Use when architecting agent evolution or prompt mutation features.

## Core Insight

Hermes already has everything needed for hot-swap prompt evolution:
- `apply_agent()` → `ephemeral_system_prompt` (hot-swap without restart)
- Profiles → full isolation (separate DB, config, identity, skills)
- Cron + Plugin API → scheduled evolution cycles

## Agent Loading Architecture

```
Layer 1: _BUILTIN_AGENTS (hardcoded in agents.py)
  ↓ overridden by
Layer 2: ~/.hermes/agents/*.md (YAML frontmatter + Markdown body)
  ↓ overridden by
Layer 3: config.yaml → agents: (inline mapping/list)
```

`load_agents(force=False)` merges all layers and caches in `_registry_cache`.
`save_agent()` invalidates the cache. `/agent <id>` applies via `apply_agent()`.

## Hot-Swap Mechanism

`apply_agent(agent_obj, agent_def)` mutates the running `AIAgent` in-place via `ephemeral_system_prompt`. No process restart needed. The `_cached_system_prompt` is NOT rebuilt — only the ephemeral prompt changes. Identity (SOUL.md) remains unchanged.

**Cache impact:** 1 turn cold cache after mutation. Acceptable for daily mutations.

## Profile-Based Sandbox Pattern

```
1. Create sandbox profile: hermes profile create promptbreeder-sandbox
2. Copy baseline agent to sandbox: cp ~/.hermes/agents/plan.md ~/.hermes/profiles/sandbox/agents/
3. Apply mutation to sandbox copy: PromptMutator.apply(operator, target, diff)
4. Run A/B evaluation: same task suite on baseline and mutated profiles
5. Compare metrics: Task Success Rate, token cost, latency, spec conformance
6. If improvement confirmed → atomic promote: copy mutated to production + reset_cache()
7. User does /agent plan → mutation is active
```

## Promptbreeder Operators

| Operator | Action | Risk |
|----------|--------|:----:|
| ADD_INSTRUCTION | Add new instruction to agent prompt | LOW |
| REMOVE_INSTRUCTION | Remove failing instruction | LOW |
| REWORD | Rephrase existing instruction | LOW |
| REORDER | Change instruction priority/order | LOW |
| ADD_EXAMPLE | Add example to prompt | LOW |
| CROSSOVER | Merge two agents' prompts | MEDIUM* |

*CROSSOVER requires human review due to complexity.

## Immutable Safety Core

These can NEVER be mutated:
- Auth & API keys
- Model settings (model, provider, base_url)
- Permissions
- Tool guardrails (tool_guardrails.py)
- PII protection (redact_pii)
- File placement rules (enforce-workspace.py)
- Security config (approvals.mode, tirith)
- Core source code
- config.yaml security sections

## Key Pitfalls

- `toolsets: []` in agent frontmatter = ALL tools enabled (falsy empty list). Always use explicit list.
- Symlink isolation: `Path.root / target` mishandles absolute symlinks. Use `resolve()` + `relative_to()`.
- Profile clone is not Docker isolation — same process, filesystem, network. Guard with file placement rules.
- Mutation invalidates prompt cache prefix for 1 turn — acceptable at daily frequency, not for real-time.
