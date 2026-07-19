# VRPO Fallback for llama.cpp Diffusion RL

## Problem

`llama-diffusion-cli` and the Python FastAPI wrapper (`diffusion-server.py`) only return generated text via `/v1/chat/completions`. They do NOT expose forward-pass logits, token probabilities, or per-step diffusion state.

Standard diffusion RL methods (StableDRL, VRPO with ELBO) require:
- Logits from the diffusion forward pass at masked positions
- Per-step expert routing masks (for DES-MoE)
- Token-level probability estimates for importance ratio computation

Without these, ELBO-based methods (importance ratio = exp(ELBO_new - ELBO_old)) are impossible.

## Solution: Reward-based VRPO

Vanilla Reward-based Policy Optimization uses only the composite reward signal from sandbox execution — no logits needed.

### Reward function

```python
composite_reward = alpha * code_pass_rate + (1 - alpha) * test_quality * fail_rate

# Where:
#   code_pass_rate = passed_tests / total
#   fail_rate = failed_tests / total
#   test_quality = heuristic based on edge cases found
#   alpha = 0.6 (weight toward code LoRA)
```

### Update rule

```
A_j = (R_j - baseline) / (std(R) + ε)       # group-normalized advantages
∇J = Σ_j A_j · ∇log π(a_j)                  # per-sample gradient
```

Advantages are clipped to [-1/clip_low, 1/clip_low] to prevent extreme updates.

### Baseline

Exponential moving average of rewards (alpha=0.1), capped at last 1000 rewards.

## When to use

| Condition | Use |
|:----------|:----|
| Text-only API (diffusion-server.py) | **VRPO** |
| llama-diffusion-cli subprocess | **VRPO** |
| vLLM with logits enabled | StableDRL (ELBO-based) |
| Unsloth with forward hook | StableDRL (ELBO-based) |

## Implementation

Working code: `/home/user/dev/rldiffusion/scripts/vrpo_update.py`

```python
from vrpo_update import VRPO
import numpy as np

vrpo = VRPO(clip_low=0.80, clip_high=1.20)
rewards = np.array([0.8, 0.3, 0.7, 0.1, 0.9, 0.5, 0.2, 0.95])
advantages, metrics = vrpo.step(rewards)
# advantages.shape == (8,) — per-sample update weights
# metrics.advantage_mean, .advantage_std, .update_norm, .n_clipped
```

## Limitations

- **Higher variance** than ELBO-based methods (no importance ratio)
- **No per-token signal** — reward is per-sample, not per-masked-position
- **Cannot compute policy drift** — no reference policy ELBO to compare against
- Group size must be ≥4 for stable advantage normalization
- **CPU inference is SLOW** — on DGX Spark (20-core ARM64, 48 GB DiffusionGemma FP16): 2-5 min per generation. At 16 generations/step, expect 30-80 min/step. With 1500 steps → 33-83 days on CPU. Reduce `total_steps` to 100-200 or use GPU (vLLM Docker) for practical training timelines.

## Verified Working (2026-07-15)

Full pipeline launched and verified on Pavel's DGX Spark:
- Model: DiffusionGemma 26B-A4B FP16 (48 GB) via `llama-diffusion-cli --lora`
- Server: `diffusion-server.py` on :8646, health-check passed, generation confirmed
- VRPO: `vrpo_update.py` integrated into `self_play_loop.py`, computes per-step advantages
- Sandbox: `arm64v8/python:3.12-slim` (native ARM64, no QEMU)
- Reference bugs: 96 synthetic bugs loaded (33 edge_case, 29 logic_error, 21 perf, 13 type_error)
- Resource limiter: time-based CPU/RAM caps operational (70/80% day → 90/90% night MSK)
- Logging: JSONL per-step metrics with VRPO advantage stats

## Upgrade path

When logits become available (vLLM forward hook, custom llama.cpp build, or Unsloth):
1. Switch from VRPO to StableDRL
2. Enable staircase attention ELBO estimation
3. Add unconditional clipping + self-normalization
4. Integrate with DES-MoE routing stats for per-expert freeze masks
