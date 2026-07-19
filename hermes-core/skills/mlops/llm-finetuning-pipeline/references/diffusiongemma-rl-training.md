# DiffusionGemma RL Training — Research & Pipeline (July 2026)

> **Model:** DiffusionGemma 26B-A4B (MoE, 64 experts, block-diffusion)  
> **Platform:** DGX Spark, llama.cpp diffusion-cli, Docker sandbox  
> **Pipeline:** `rldiffusion/` — Anchored Self-Play + DES-MoE + StableDRL

## Architecture: Adversarial Self-Play with Dual LoRA

```
Code LoRA ←→ Test LoRA (adversarial rounds)
     ↓            ↓
  Docker Sandbox (memory=8GB, cpus=4, network=none, timeout=30s)
     ↓
  Reward: pass_rate × 0.6 + fail_rate × quality × 0.4
```

Two LoRA adapters on the same DiffusionGemma model, playing adversarial rounds:
- **Round 1 (Code→Test):** Code LoRA generates functions, Test LoRA generates tests, execute
- **Round 2 (Test→Code):** Test LoRA generates adversarial tests, Code LoRA tries to pass them

## Components

| Component | Role | Key Innovation |
|-----------|------|----------------|
| **DES-MoE Scheduler** | 3-phase expert freeze | Correlation matrix (64×2), progressive freezing |
| **StableDRL** | Stabilized GRPO | Unconditional clipping + self-normalization |
| **VRPO** (fallback) | Reward-only policy | Works without logits (current limitation) |
| **Mistake Book** | Prioritized replay | 10K capacity, biased sampling by difficulty |
| **Reference Bugs** | Anchoring | 5 teachers prevent test-drift |
| **Resource Limiter** | MSK time-based | Day: 70% CPU/80% RAM, Night: 90%/90% |

## DES-MoE: 3-Phase Expert Freeze

| Phase | Steps | Trainable | LR | Diffusion Steps |
|-------|-------|-----------|-----|-----------------|
| 1 (Warm-up) | 0–29 | All 64 experts | 0.001→0.0005 | 16 |
| 2 (Stabilize) | 30–79 | Domain-specific (top-50%) | 0.0001→0.00005 | 32 |
| 3 (Polish) | 80–99 | Top-5 per domain | 0.00001 | 64 |

At end of Phase 1: build correlation matrix A[64×2] = activation frequency per expert for code/test tokens. Phase 2 freezes experts below threshold × max. Phase 3 freezes all but top-5.

## SOTA Landscape: RL for Diffusion Text Models (2025–2026)

| Method | Paper | Date | Key Innovation | vs Baseline |
|--------|-------|------|----------------|-------------|
| **GDPO** | arXiv:2510.08554 | 2025 | Semi-deterministic MC ELBO | > diffu-GRPO |
| **diffu-GRPO (d1)** | arXiv:2504.12216 | NeurIPS 2025 | Random masking, first PG for dLLMs | +significant on math |
| **StableDRL** | arXiv:2603.06743 | ICML 2026 | Unconditional clipping, self-normalization | Prevents collapse |
| **DDPO** | Black et al. | 2024 | Diffusion as multi-step MDP | Images (Stable Diffusion) |
| **VRPO** | ACL 2026 | 2026 | Robust value under noise | Reward-only fallback |

**GDPO > diffu-GRPO > StableDRL** for final quality, but StableDRL is most stable.

### The Core Challenge

Standard GRPO collapses on diffusion LLMs because:
1. **Intractable likelihood** — no sequence probabilities, must estimate via ELBO
2. **Variance explosion** — double MC sampling → noisy importance ratios
3. **Conditional clipping bypassed** — noise can bypass GRPO clipping → gradient spikes

### StableDRL Fixes (used in rldiffusion)

- **Unconditional clipping:** always clip ρ ∈ [0.80, 1.20] regardless of advantage sign
- **Self-normalization:** divide by Σρ_clipped instead of fixed G
- **Staircase attention:** block-diffusion aware ELBO (each block with clean context)

```
∇J = Σⱼ clip(ρⱼ) · Aⱼ · gⱼ / Σⱼ clip(ρⱼ)
```

## Critical Blocker: No Logits from llama.cpp

**The pipeline cannot update LoRA weights** because `llama-diffusion-cli` (and `diffusion-server.py`) only return text — no logits. VRPO computes advantages from rewards but has no gradients to apply.

### Solutions (ordered by feasibility)

1. **Modify llama-diffusion-cli** to return log-probs (`--logits` flag) — 50-200 lines of C++
2. **Use HuggingFace transformers** for DiffusionGemma inference (gives logits via `output.logits`)
3. **vLLM with diffusion support** — not yet available for diffusion models

### What Works Without Logits

- Data collection (self-play rounds + sandbox execution)
- Mistake Book population
- Routing statistics (DES-MoE correlation matrix)
- VRPO advantage computation (reward-only)
- Reference bug anchoring

### What Needs Logits

- StableDRL/GDPO gradient computation
- LoRA weight updates
- Actual model improvement

## Launch Pattern (DGX Spark)

```bash
# run_all.py spawns server + training as subprocesses — single process tree
cd /home/user/dev/rldiffusion
/home/user/.hermes/hermes-agent/venv/bin/python3 -u run_all.py

# Under Hermes: MUST use background=true to survive session boundaries
# Training takes ~30 hours (100 steps × 18 min)
# Monitor: tail -1 logs/training_*.jsonl
```

Server: `diffusion-server.py` on port 8646, spawns `llama-diffusion-cli` per request.
Model: 48GB FP16 GGUF, 64 experts (top-4), 256K context, 16 diffusion steps.

## Memory Pattern (Normal)

llama-diffusion-cli mmaps 48GB model per request (~10s), exits, memory freed.
32 API calls per step → memory oscillates between baseline and +50GB.
This is NORMAL — not a leak. The server is stateless (one process per request).

## Comparison: rldiffusion vs SOTA

| Feature | rldiffusion | d1 | GDPO | StableDRL |
|---------|:---:|:---:|:---:|:---:|
| MoE-aware | ✅ DES-MoE | ❌ | ❌ | ❌ |
| Self-play | ✅ Adversarial | ❌ | ❌ | ❌ |
| Mistake replay | ✅ Prioritized | ❌ | ❌ | ❌ |
| Anchoring | ✅ 5 teachers | ❌ | ❌ | ❌ |
| Logits/gradients | ❌ | ✅ | ✅ | ✅ |
| CPU-only | ✅ llama.cpp | ❌ | ❌ | ❌ |

**rldiffusion has the richest technique set but is bottlenecked by no logits.**

## Key Papers

1. **d1 (Zhao et al.)** — diffu-GRPO, masked SFT→RL pipeline, LLaDA-8B — [arXiv:2504.12216](https://arxiv.org/abs/2504.12216)
2. **GDPO** — Semi-deterministic MC, lower variance ELBO — [arXiv:2510.08554](https://arxiv.org/abs/2510.08554)
3. **StableDRL** — Unconditional clipping, self-normalization — [arXiv:2603.06743](https://arxiv.org/abs/2603.06743)
4. **DDPO (Black et al.)** — Multi-step MDP for diffusion — [rl-diffusion.github.io](https://rl-diffusion.github.io/)
5. **Diffusion LM Post-Training (Kelvin)** — Comprehensive survey — [blog](https://hankelvin.github.io/articles/25/Diffusion_LM_P4)
