# Hermes Mutability Map — What Promptbreeder Can & Cannot Mutate

> Reference for `orchestration-cycle` skill. Created 2026-06-15.

## Four tiers

### 🔴 IMMUTABLE SAFETY CORE — Never mutated
```
Auth/API keys  •  Model settings (model, provider, base_url)  •  Permissions
Tool guardrails (tool_guardrails.py)  •  PII protection  •  File placement rules
Security config (approvals.mode, tirith)  •  AGENTS.md principles
Core Python source code  •  config.yaml security sections
```

### 🟡 CONDITIONAL — Human review required
```
Toolsets  •  Reasoning level  •  Temperature  •  Skill references/scripts
Plan templates
```

### 🟢 MUTABLE — Auto-apply with sandbox validation
```
Agent system prompt body (*.md)  •  Skills (SKILL.md)  •  Label/description
Emoji  •  Examples  •  Instruction order  •  Wording  •  Add/remove instructions
Crossover between agents
```

### ⚪ OUT OF SCOPE — Not mutated (future phases)
```
Model weights  •  Agent topology (Phase C)  •  Gateway config  •  Cron definitions
```

## Promptbreeder operators (6)

| Operator | Target | Risk |
|----------|--------|:----:|
| ADD_INSTRUCTION | System prompt, skills | LOW |
| REMOVE_INSTRUCTION | System prompt, skills | LOW |
| REWORD | System prompt, skills | LOW |
| REORDER | System prompt, skills | LOW |
| ADD_EXAMPLE | System prompt, skills | LOW |
| CROSSOVER | Two agent prompts | MEDIUM |

## Mutation flow

```
Auditor proposes mutation
  → SandboxProfileManager clones profile
  → PromptMutator applies operator to sandbox
  → ABTestRunner runs representative task suite
  → LOW risk + ≥10% improvement → auto-promote
  → MEDIUM/HIGH → human review
  → CRITICAL → blocked
  → Backup before promote (.bak)
  → Rollback on degradation (≥5% over 3 cycles)
```
