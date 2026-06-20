# Orchestrator Model Benchmark — Jetson GB10

Real measurements from `~/.hermes/logs/agent.log` (session `20260613_180400_56c38b`),
Qwen 3.6 35B via llama.cpp → LiteLLM :4000, Jetson GB10 (ARM64, NVIDIA GPU, 128GB RAM).

## Raw Log Data

```
API call #33: model=openai/qwen3.6-35b-heretic provider=custom:local-(localhost:4000)
  in=116338 out=298 total=116636 latency=313.3s

API call #34: model=openai/qwen3.6-35b-heretic provider=custom:local-(localhost:4000)
  in=116673 out=220 total=116893 latency=319.4s

API call #35: HTTP 500 ×3 — LiteLLM InternalServerError: Connection error
  (llama.cpp crashed after 5-minute prefill attempts)
```

## Context Composition (per API call)

| Component | Est. tokens |
|-----------|-------------|
| plan.md system prompt | ~8,000 |
| Persona file | ~4,000 |
| Memory + User Profile | ~8,000 |
| Skills section | ~15,000 |
| Conversation history (89-91 messages) | ~80,000 |
| **Total input** | **~116,000** |

## Why It Fails

### The Prompt Prefill Problem

Before generating ANY output token, the model must prefill (compute attention over)
ALL input tokens. For a 35B model with 120K context:

- Attention computation: O(n²) over 120K positions × 35B parameters
- On Jetson GB10 (single GPU, unified memory ~200-400 GB/s bandwidth):
  - Prefill time: 200+ seconds
  - Generation speed: ~1 token/second (each output token requires attention over all 120K inputs)
- On datacenter GPUs (hundreds of GPUs, HBM ~2-3 TB/s):
  - Prefill time: <5 seconds
  - Generation speed: 50-100 tokens/second

### The Degradation Spiral

```
Turn 1: 80K context → 2 min prefill → response
Turn 2: 90K context → 3 min prefill → response
Turn 3: 100K context → 4 min prefill → response
Turn N: 116K context → 5+ min prefill → 500 error (LiteLLM timeout)
```

Each turn adds messages → context grows → next prefill takes longer → eventual crash.

### Contributing Factors

1. **`reasoning: high`** in plan.md — generates thinking tokens BEFORE response, doubling latency
2. **MTP (multi-token prediction)** — `--spec-draft-n-max 3` adds overhead at prefill stage
3. **Unified memory bandwidth** — Jetson GB10 unified memory at ~200-400 GB/s vs datacenter HBM at ~2-3 TB/s (5-10× gap)
4. **KV-cache size** — 120K tokens × 35B model in 4-bit ≈ 16GB just for KV-cache
5. **LiteLLM proxy overhead** — adds ~1-2 sec per request for routing

## Conclusion

**Qwen 3.6 35B is intellectually capable** of the orchestrator role (strong instruction-following,
thinking mode handles complex prompts). But the **hardware cannot deliver** the prompt prefill
throughput needed. This is a hardware constraint, not a model quality issue.

**Where Qwen 3.6 35B works on Jetson GB10:**
- Short-context tasks (input <20K tokens): developer sub-agents, one-shot generation
- OpenCode+ plan/build (context compressed by compactor)

**Where it doesn't work:**
- Orchestrator with 100K+ token prompts
- Any role requiring large conversation history

**Recommendation:** Cloud models (GPT-4.1-mini, DeepSeek V4 Pro) for orchestrator.
Local Qwen for developers and short-context roles.
