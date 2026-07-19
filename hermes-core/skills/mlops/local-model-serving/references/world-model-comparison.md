# World Model & Agent Model Comparison (Updated July 9, 2026)

## What is a Language World Model (LWM)?

Ordinary LLMs generate responses to prompts. A Language World Model **predicts the next environment state** given an agent's action and history — "what will the terminal show after `git rebase`?", "what HTML will the server return after this click?".

Qwen-AgentWorld (June 2026) is the **first and currently only** open-weight LWM. It was trained via a 3-stage pipeline (CPT→SFT→RL) on 10M+ environment interaction trajectories across 7 domains: MCP, Search, Terminal, SWE, Web, OS, Android.

## Qwen-AgentWorld Family

| Model | Total/Active | AgentWorldBench | vs Best Proprietary | Local? |
|-------|:---:|:---:|------|:---:|
| **AgentWorld-397B-A17B** | 397B/17B | **58.71** | Beats GPT-5.4 (58.25) | No (120+ GB) |
| **AgentWorld-35B-A3B** | 35B/3B | **56.39** | Beats Claude Sonnet 4.6 (56.04) | Yes, Q4_K_M ~20 GB |

## Direct Competitors (World Models)

**None at 35B scale.** LingBot-World is video-generation, WebWorld is web-only. Qwen-AgentWorld is the sole open-weight language world model for agent simulation.

## Agents-A1 Deep Analysis (InternScience, June 26, 2026)

35B MoE (Qwen3.5 base), 3B active, 262K context, multimodal (VLM), Apache 2.0.
Architecture: `Qwen3_5MoeForConditionalGeneration`, native tool calling (`qwen3_coder` parser).

**Key idea (arXiv:2606.30616):** "Scaling the Horizon, Not the Parameters" — reaches trillion-parameter agent performance by scaling long-horizon trajectories (avg 45K token training trajectories) and heterogeneous agent abilities via multi-teacher domain-routed on-policy distillation across 6 domains.

### Full Head-to-Head: Agents-A1 vs current stack models

Direct comparison from InternScience README (all scores from their original papers):

| Benchmark | Qwen3.6-35B-A3B | Nex-N2-mini | **Agents-A1** | GPT-5.5 | DeepSeek-V4-pro |
|-----------|:---:|:---:|:---:|:---:|:---:|
| **Long-horizon Search** | | | | | |
| BrowseComp | 67.93 | 74.1 | **75.51** | 84.4 | 83.4 |
| GAIA | 78.64 | 82.52 | **96.04** | 87.38 | 98.06 |
| Seal0 | 38.74 | 49.55 | **56.36 (SOTA)** | 42.34 | 54.95 |
| XBench-DS-2510 | 71.0 | 82.0 | **86.0** | 84.0 | 90.0 |
| **Engineering** | | | | | |
| SciCode | 35.8 | 29.9 | **44.33** | 56.1 | 50.0 |
| MLE-Lite | 34.85 | 34.85 | **43.94** | 72.73 | 63.64 |
| **Scientific Research** | | | | | |
| HLE w/ tools | 36.2 | 32.0 | **47.6** | 52.2 | 48.2 |
| HiPhO | 37.7 | 38.5 | **46.4 (SOTA)** | 43.3 | 38.7 |
| FrontierScience-Olympiad | 60.3 | 52.0 | **79.0 (SOTA)** | 78.0 | 76.0 |
| FrontierScience-Research | 2.9 | 5.0 | **40.0 (SOTA)** | 26.7 | 13.3 |
| **Instruction Following** | | | | | |
| IFBench | 64.4 | 54.08 | **80.61 (SOTA)** | 75.9 | 73.47 |
| IFEval | 91.3 | 88.4 | **94.82 (SOTA)** | 93.35 | 93.35 |
| **General Agentic** | | | | | |
| tau2-Bench | 79.0 | 74.53 | **79.81** | 81.63 | 82.2 |

**Verdict: Agents-A1 dominates Qwen3.6-35B-A3B on ALL 14 published benchmarks.**

### CRITICAL: Agents-A1 is NOT a coding model

Agents-A1 does NOT report SWE-Bench Verified, SWE-Bench Pro, or Terminal-Bench scores.
Community note (HF discussions): "coding capabilities may require a much larger model, perhaps the 397B model instead."
SWE-Pro is "a tier behind" compared to Nex-N2-mini (SWE-Bench Verified 74.4, SWE-Bench Pro 50.2, Terminal-Bench 60.7).

**Model selection rule:** Agents-A1 is a reasoning/search/science agent — do NOT use it for coding/SWE/terminal tasks. Keep Nex-N2-mini for coding.

### Abliterated variants (July 2026)

| Repo | Format | Base | Notes |
|------|--------|------|-------|
| `huihui-ai/Huihui-Agents-A1-abliterated` | safetensors | Agents-A1 | Updated 2026-07-09. Full-precision, needs conversion to GGUF. |
| `Abiray/Agents-A1-Q4_K_M-GGUF` | GGUF | Agents-A1 (original, not abliterated) | ~21 GB, ready for llama.cpp |
| `iamhsouna/Huihui-Qwen-AgentWorld-35B-A3B-abliterated-GGUF` | GGUF Q4_K_M | AgentWorld | Abliterated AgentWorld in GGUF |

**Gap:** No abliterated Agents-A1 GGUF yet (as of July 9). Path: download huihui safetensors -> convert with `convert_hf_to_gguf.py` -> APEX quantize. Or wait for community GGUF.

### vLLM deployment

```bash
vllm serve InternScience/Agents-A1 \
  --port 8000 --tensor-parallel-size 1 \
  --max-model-len 262144 \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  --language-model-only   # skips vision encoder, frees KV cache
```

Sampling (recommended by authors): temp=0.85, top_p=0.95, top_k=20, presence_penalty=1.1, repetition_penalty=1.0.
VRAM: ~22 GB in FP8 (only 3B active params per token).

## Other Adjacent Models (Agent-Capable, Same Scale)

### Ornith-1.0-35B (DeepReinforce, June 25, 2026)

35B MoE (Qwen3.5 base), self-scaffolding RL:
- Terminal-Bench 2.1: 64.2 (beats Qwen3.5-397B at 53.5!)
- SWE-Bench Verified: 75.6
- Coding-focused, NOT a world model

GGUF: `deepreinforce-ai/Ornith-1.0-35B-GGUF` + APEX: `SC117/Ornith-1.0-35B-MTP-APEX-GGUF`.

### Qwen3-Coder-Next (Alibaba, Feb 2026)

80B total / **3B active** MoE. Apache 2.0. Coding agent specialist.
- SWE-Bench Verified: 70.6-74.2%
- SWE-Bench Pro: 44.3% (beats GLM-4.7 40.6% and DeepSeek-V3.2 40.9%)
- Context: 256K. Compatible with Claude Code, Qwen Code, Cline.

Heavier than Nex-N2-mini (80B vs 35B total) with comparable SWE scores — Nex remains the better local choice.

## Decision Matrix for Pavel's DGX Spark Stack

Three roles, three slots, ~95 GB budget:

| Slot | Current | Best Alternative | Verdict |
|------|---------|-----------------|---------|
| Coding | Nex APEX (~33 GB) | Ornith-1.0, Qwen3-Coder-Next | Nex is SOTA in 35B class (SWE 74.4, Terminal 60.7) — keep |
| Reasoning | Qwen3.6 APEX (~22 GB) | **Agents-A1** | Agents-A1 dominates on 14/15 benchmarks — strong upgrade candidate |
| World/Agent | SuperQwen (~37 GB) | Agents-A1, Ornith | SuperQwen = only LWM. Agents-A1 = stronger general agent but loses world simulation |

### Agents-A1 as Reasoning Replacement (new analysis July 9, 2026)

Replacing Qwen3.6-35B with Agents-A1 for the reasoning role:
- **Pros:** +18 points on GAIA (78.64->96.04), +16 on Seal0 (38.74->56.36), +16 on IFBench (64.4->80.61), native tool calling (critical for orchestrator), multimodal (vision for browser/tester tasks), uncensored abliterated variant available.
- **Cons:** Coding weakness irrelevant (reasoning slot uses Nex for code). GPQA not published by Agents-A1 (Qwen3.6 has 86.0). No abliterated GGUF yet — needs conversion.
- **Decision:** Strong candidate for next model refresh. When abliterated GGUF becomes available, test directly.

### Key trade-off (World Model slot)

- **Keep SuperQwen**: retain unique world simulation capability (Sim RL, state prediction, AgentWorldBench 56.39)
- **Swap to Agents-A1**: gain +20-25 points on agent benchmarks (SEAL-0, IFBench, etc.) but lose world simulation entirely
- **Swap to Ornith**: gain +24.6 on Terminal-Bench but lose world simulation + general agent versatility

For Pavel's Plan2/Plan3 architecture where AgentWorld runs Sim RL, **SuperQwen remains the best fit** — no other model can replace its unique capability.

## Supertune (Jiunsong's Post-Training Method)

SuperQwen-AgentWorld adds Supertune on top of the base Qwen-AgentWorld:
1. **AgentWorld observation formatting** — improved environment simulation output structure
2. **Direct task completion** — model can execute tasks, not just simulate
3. **JSON/tool formatting** — structured output for tool calling pipelines
4. **Korean technical answers** — bilingual capability (author is Korean)
5. **Regression resistance** — base model quality is preserved (no fine-tuning degradation)

Single checkpoint, no runtime adapter required. Combined with abliteration (refusal removal) for an uncensored world model.
