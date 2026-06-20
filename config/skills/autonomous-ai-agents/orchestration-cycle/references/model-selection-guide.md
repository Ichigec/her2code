# Orchestrator Model Selection — Verified Data

> Last updated: 2026-06-15. Source: delegation tests, research cycle execution, User's direct testing.

## The orchestrator role is unique
The orchestrator does NOT write code. It manages 10 phases, delegates to sub-agents,
follows 430+ lines of instructions, and tracks context across a multi-turn conversation.
These are **manager skills**, not coding skills.

## Delegation results by provider (June 2026)

| Provider | Model | Batch delegation | Single delegation | Verdict |
|----------|-------|:----------------:|:-----------------:|:-------:|
| DeepSeek | deepseek-v4-pro | ✅ Works (3 children) | ✅ Works (705s research) | **DEFAULT** |
| Kimi | kimi-k2.7-code | ❌ All INTERRUPTED | 🤷 Untested | Fallback leaf only |
| OpenAI | gpt-5.5 | ❌ Quota exceeded | ❌ Quota exceeded | REMOVED |

## DeepSeek V4 Pro — v2.3 DEFAULT

**1M context, $0.28/1M input — cheapest of all providers.** Proven in production:

- **Auditor** (120s, 17 API calls): Deep analysis of workspace, cross-cycle pattern detection, root cause analysis, mutation proposals
- **Critic** (71s, 7 API calls): Artifact-by-artifact review, over-engineering detection, noise/signal ratio analysis
- **Researcher** (705s, 61 API calls): 8-iteration deep research, 33 sources, 348-line report
- **Batch delegation**: 3 concurrent observers — all completed successfully

**Multi-turn coherence**: Handles full orchestration lifecycle without drift.
The "drifts on management" claim was based on earlier models — current DeepSeek V4 Pro
performs well on management tasks.

## Kimi K2.7 — Leaf fallback only

**262K context, $0.60/1M input.** Benchmarks well but:

- **Batch delegation FAILS**: 3 observers spawned simultaneously → all INTERRUPTED
  ("Parent agent interrupted — child did not finish in time")
- This was a 166s wait with zero results
- Single-task delegation may still work, but batch mode is unreliable on current provider
- Use for leaf subagents only, not for parallel observer spawning

## GPT-5.5 — REMOVED (quota)

$10/1M output. Quota exhausted on `sk-proj-...Cr8A`. No longer usable.

## Local models (llama.cpp)

Not suitable for orchestration on Jetson CPU due to context accumulation:
- Orchestrator hits 116K tokens by Phase 3-4
- Qwen 3.6 35B on CPU: 5+ min per turn at 116K context
- Free but too slow for interactive use
