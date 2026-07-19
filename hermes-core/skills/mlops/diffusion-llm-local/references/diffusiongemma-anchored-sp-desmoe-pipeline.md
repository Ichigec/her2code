# Anchored Self-Play + DES-MoE Pipeline for DiffusionGemma

Concrete implementation pipeline combining adversarial self-play (Code LoRA vs Test LoRA)
with DES-MoE 3-phase freeze schedule on DiffusionGemma 26B-A4B.

## Where the code lives

Full implementation (scripts, config, launcher, risk analysis):
`/home/user/dev/rldiffusion/`

## Architecture

```
DiffusionGemma 26B-A4B (FROZEN, 48GB FP16)
  ├── LoRA-Code (rank=64, ~67M) — generates functions
  └── LoRA-Test (rank=64, ~67M) — generates adversarial tests
         │
         ├── DES-MoE Correlation Matrix [64×2]: code-freq | test-freq
         │   → Phase 1: ALL experts trainable, build matrix
         │   → Phase 2: Domain-specific freeze (~12+12 experts)
         │   → Phase 3: Strict top-5 per domain only
         │
         └── StableDRL (instead of GRPO):
               unconditional clipping + self-normalization + staircase attn
```

## Phase Schedule (12 days, DGX Spark 128GB)

| Phase | Days | Steps | Experts | Diff Steps | LR | Key Activity |
|:------|:----:|:-----:|:--------|:----------:|:---|:-------------|
| 0: Prep | 1 | — | — | — | — | Reference bugs from 5 teachers |
| 1: Warm-up | 2-4 | ~450 | ALL 64 | 32 | 1e-3→5e-4 | Build correlation matrix |
| 2: Stabilize | 5-8 | ~750 | ~24 | 64 | 1e-4→5e-5 | Domain freeze, Mistake Book, PCGrad |
| 3: Polish | 9-11 | ~300 | 10 | 128 | 1e-5 | Top-5 only, max quality, early stopping |

## Self-Play Loop (per step)

```
Round 1 (Code→Test):
  LoRA-Code generates function → LoRA-Test writes adversarial tests → sandbox
  R_code = tests_passed/total, R_test = tests_found_bugs_with_quality

Round 2 (Test→Code):
  LoRA-Test generates tricky tests → LoRA-Code tries to pass → sandbox
  Reversed reward structure

Every 50 steps: Anchoring — inject 30-40% reference bugs from teacher pool
Every 50-100 steps: Mistake Book replay — 32 historical failures (prioritized)

StableDRL update:
  unconditional clipping [0.85, 1.15] → self-normalization → per-expert gradient
```

## Diffusion-Specific Advantages

1. **Parallel block generation**: Test LoRA sees entire code block atomically — no sequential error accumulation from AR generation. Better adversarial signal.
2. **TCOD + diffusion step synergy**: trajectory depth 1-2 steps → 32 diffusion steps; 3-4 → 64 steps; 10+ → 128 steps.
3. **DES-MoE correlation from diffusion forward**: per-step expert routing masks over 48 diffusion steps provide rich activation statistics.

## Key Risks & Mitigations

| # | Risk | Severity | Mitigation |
|:--|:-----|:---------|:-----------|
| 1 | GRPO collapse on diffusion | CRITICAL | StableDRL + VRPO fallback (reward-based, no logits needed) |
| 2 | LoRA support in llama-diffusion-cli | ✅ RESOLVED | `--lora` flag confirmed working (2026-07-14) |
| 3 | Routing stats unavailable | HIGH | VRPO reward-based update — doesn't require forward-pass logits |
| 4 | Test LoRA drift | MEDIUM | 30-40% reference bug anchoring (96 synthetic bugs ready) |
| 5 | Server stability | MEDIUM | Watchdog + health-check in launcher |
| 6 | ARM64 Docker emulation (QEMU) | MEDIUM | Use `arm64v8/python:3.12-slim` — native, not AMD64 |
| 7 | No logits from diffusion server | WORKAROUND | VRPO (`vrpo_update.py`) — reward-based, text-only compatible. **VRPO computes advantages but cannot compute gradients** without logits — LoRA weights are not updated. Full RL requires either: (a) modify llama.cpp diffusion-cli to return logits (~50-200 lines C++), (b) use vLLM forward hooks, or (c) Unsloth/PyTorch with `output.logits` |

**Blocker resolution (2026-07-14):**
- ✅ LoRA: `--lora FNAME` + `--lora-scaled FNAME:SCALE` work in `llama-diffusion-cli`
- ✅ Logits unavailable: VRPO reward-based fallback implemented (no ELBO needed)
- ✅ Reference bugs: 96 synthetic bugs across 5 failure types (edge_case, logic_error, perf, type_error)
- ✅ Sandbox: ARM64 native image (`arm64v8/python:3.12-slim`) — no QEMU penalty
- ✅ Resource limits: time-based CPU/RAM capping (70%/80% day → 90%/90% night MSK)

Full risk analysis: `/home/user/dev/rldiffusion/data/risk_analysis.md`

## CPU-Only Timing Reality (DGX Spark, no GPU)

**The pipeline launched successfully on 2026-07-15** on Pavel's DGX Spark (20-core ARM64, 122 GB RAM, CPU-only inference via llama.cpp):

| Metric | Value |
|:-------|:------|
| Model | DiffusionGemma 26B-A4B FP16 (48 GB GGUF) |
| Inference engine | `llama-diffusion-cli` (PR #24423), CPU-only |
| Time per generation (32 steps) | 2-5 minutes |
| Generations per step | 16 (8 code + 8 test × 2 rounds) |
| Time per step | 32-80 minutes |
| 1500 steps | **33-83 days** (impractical for CPU) |
| 100 steps | **2-5 days** (feasible CPU budget) |

**Recommendation for CPU-only training:**
- Reduce `total_steps` to **100-200** (2-10 days)
- Reduce `canvas_size` to **128** (2× faster generations)
- Reduce `diffusion_steps` minimum to **16** in Phase 1 (4× less compute)
- Consider overnight-only runs with resource limiter day/night windows

For GPU-accelerated inference (DGX Spark with vLLM Docker image), expect **100-500× speedup** — the full 1500-step pipeline becomes a few hours instead of months. See main skill body for vLLM deployment instructions.

## Related Research

- RL alignment catalog: `references/diffusion-llm-rl-alignment.md` — all 8 proven methods (VRPO, StableDRL, GDPO, diffu-GRPO/d1, Coupled-GRPO, Block-R1, ELBO-KTO)
- Post-training methods compatibility: `references/posttraining-methods-compatibility.md`
- VRPO fallback for llama.cpp: `references/vrpo-fallback-for-llama-cpp.md`
- Full research report (July 2026): `/home/user/dev/rldiffusion/RESEARCH_REPORT.md` — SOTA comparison, GDPO vs diffu-GRPO analysis, roadmap, bibliography
- Pipeline design doc: `/home/user/dev/posttrainingplan/07_diffusiongemma_anchored_sp_desmoe.md`
