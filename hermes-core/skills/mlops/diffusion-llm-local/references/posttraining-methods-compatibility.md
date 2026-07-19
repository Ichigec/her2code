# Post-Training Methods Compatibility with DiffusionGemma

Analysis of 9 methods from `dev/posttrainingplan/` — originally selected for Qwen3.5-35B-A3B
MoE (AR), evaluated for DiffusionGemma 26B-A4B (block-diffusion).

## Core insight: GRPO is BROKEN for diffusion LLMs

Standard GRPO collapses at ~300 steps on dLLMs (StableDRL, ICML 2026). Any method that
uses GRPO internally needs StableDRL (unconditional clipping + self-normalization) FIRST.

## Tier 1: Directly compatible (architecture-independent)

| Method | What it does | Why it works for DG |
|:-------|:-------------|:--------------------|
| **DES-MoE** (2509.16882) | 3-phase MoE freezing schedule | Routing statistics + freezing logic independent of AR/diffusion |
| **Synergistic Reg.** (2602.14159) | R_sp + R_cp plug-and-play losses | Loss terms only — no dependence on decoding type |
| **Agent Distillation** (2505.17612) | First-thought prefix + self-consistent filtering | Data strategy — teacher/student architecture irrelevant |
| **TCOD** (2604.24005) | Progressive trajectory depth curriculum | Curriculum strategy — pairs well with diffusion steps |
| **Mistake Book** | Ring buffer of failures, replay every 100 steps | Data strategy — 0 lines of adaptation needed |

## Tier 2: Need StableDRL first (GRPO-dependent)

| Method | What it does | Dependency | DG adaptation |
|:-------|:-------------|:-----------|:---------------|
| **RO-GRPO** (ICLR 2026) | Routing entropy → GRPO reward | StableDRL | Routing stats collection from diffusion forward pass |
| **Anchored Self-Play** (2607.03523) | Code LLM vs Test LLM adversarial | StableDRL | Diffusion may BENEFIT — parallel block gen = better adversarial signal |
| **GAD** (2511.10643) | Adversarial distillation (discriminator) | StableDRL or VRPO | Concept works; can replace GRPO with VRPO |
| **G-OPD** (2602.12125) | Reward extrapolation λ=1.25 | StableDRL + white-box teacher | Only with white-box diffusion teacher |

## StableDRL → RO-GRPO dependency chain

DiffusionGemma is block-diffusion MoE. RO-GRPO prevents routing collapse when doing RL
on MoE (routing entropy + load_var → scalar reward). But GRPO itself is unstable on dLLMs.
StableDRL fixes GRPO for block-diffusion via staircase attention. Result:

```
StableDRL (staircase attention + unconditional clipping) → GRPO works
  └─ RO-GRPO (routing reward) → MoE routing doesn't collapse
      └─ Anchored Self-Play / GAD / G-OPD → full RL pipeline
```

## DiffusionGemma-specific bonuses

- **Anchored Self-Play**: diffusion parallel generation = test LoRA evaluates entire
  code blocks atomically → better adversarial signal than token-by-token AR. No sequential
  error accumulation — Test LLM sees complete function, finds holistic bugs.
- **TCOD + diffusion steps synergy**: Epoch 1: short trajectories + 32 diffusion steps
  → Epoch 4: full trajectories + 128 steps. Natural alignment between trajectory depth
  curriculum and diffusion denoising budget.
- **DES-MoE**: DiffusionGemma is MoE (26B-A4B, top-4 routing). DES-MoE correlation
  matrix + 3-phase freezing schedule works directly — just collect routing statistics
  from diffusion forward pass (llama.cpp PR #24423 exposes these).

## What does NOT work

- **GRPO (raw)** → collapse at ~300 steps (StableDRL paper)
- **DPO (raw)** → intractable likelihood for diffusion
- **RLHF/PPO** → same importance ratio problem as GRPO
- **G-OPD with black-box teachers** → needs white-box logits for λ-extrapolation
