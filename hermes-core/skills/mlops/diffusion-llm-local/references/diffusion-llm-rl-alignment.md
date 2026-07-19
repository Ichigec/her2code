# RL Alignment for Diffusion LLMs — Complete Reference

Deep-dive research (July 2026). Covers all proven RL methods for diffusion text models,
with DiffusionGemma-specific compatibility and implementation guidance.

## Core Problem: Why Standard RL Fails on Diffusion LLMs

Diffusion LMs have no exact log-likelihood — it's intractable (requires marginalizing over n! masking trajectories).
RL methods (PPO, GRPO, DPO) all use importance ratios π_θ/π_old. When substituting noisy ELBO estimates:

- `exp(ELBO_noise)` → long-tail distribution → estimated ratios explode to 10⁵
- Conditional clipping in GRPO is anomalously bypassed by model-agnostic noise → gradient spikes
- Fixed group-size normalization amplifies fluctuations → **reward collapse at ~300 steps**
- This forms a **self-reinforcing instability loop**: noise → spikes → policy drift → more noise

## Method Catalog

### VRPO — Variance-Reduced Preference Optimization
- **Paper**: arXiv:2505.19223 (May 2025, ACL 2026)
- **Code**: github.com/ML-GSAI/LLaDA-1.5
- **Base**: LLaDA-8B
- **Results**: +8-12 pp on alignment benchmarks (GSM8K +4.7, HumanEval +3.0, IFEval +4.0, Arena-Hard +4.3)
- **Mechanism**: Three variance reduction strategies — optimal MC budget allocation, antithetic sampling, increased MC budget
- **DiffusionGemma compat**: 🟢 DIRECT — both use masked diffusion, surface-level method

### StableDRL — The Critical Foundation
- **Paper**: arXiv:2603.06743 (Mar 2026, ICML 2026)
- **Code**: github.com/JianyuanZhong/StableDRL
- **Base**: LLaDA-8B (full-attn), SDAR-8B (block diffusion)
- **Key claim**: FIRST method enabling stable full-parameter RL on dLLMs for 1000+ steps
- **Mechanism**: (i) unconditional clipping — strict bounds on ratios regardless of advantage; (ii) self-normalization — normalize by sum of clipped ratios, not fixed group size; (iii) staircase attention for block-diffusion models
- **Results on full-attn LLaDA-8B**: MATH500 84.2 (+4.5), AIME'24 16.7 (+4.9), GSM8K 91.5 (+8.5)
- **Results on block-diff SDAR-8B**: MATH500 50.6 (+14.8!), AIME'24 11.0 (+5.0), Sudoku 77.8 (+7.2)
- **DiffusionGemma compat**: 🟢 CRITICAL — only proven method for block-diffusion RL, DiffusionGemma is block-diffusion

### diffu-GRPO / d1 — First RL for Masked Diffusion LLMs
- **Paper**: arXiv:2504.12216 (Apr 2025, NeurIPS 2025)
- **Code**: github.com/dllm-reasoning/d1
- **Model**: d1-LLaDA (LLaDA-8B-Instruct + SFT + diffu-GRPO)
- **Mechanism**: Two-stage — (1) Masked SFT on s1k (1000 high-quality reasoning traces with self-correction), (2) Critic-free policy gradient with random masking and 1-step unmasking for token-level log-probability estimation
- **Key insight**: Random masking > fixed masking — allows scaling μ (gradient updates per batch) to much higher values while maintaining performance
- **Results**: Best on GSM8K (d1-LLaDA), competitive on MATH500, shows "aha moments" (self-verification and backtracking) in reasoning traces
- **DiffusionGemma compat**: 🟢 DIRECT — masked diffusion architecture, random masking applies to MoE too

### GDPO — Group Diffusion Policy Optimization (Lower-Variance ELBO)
- **Paper**: arXiv:2510.08554 (Oct 2025)
- **Mechanism**: Semi-deterministic Monte Carlo for ELBO estimation — disentangles variance sources, uses deterministic integral approximations on pivotal dimensions instead of double MC sampling. Provably lower-variance estimator under tight evaluation budgets
- **Key claim**: Outperforms diffu-GRPO on majority of math benchmarks. Costs comparable to diffu-GRPO but with much better variance properties
- **DiffusionGemma compat**: 🟢 HIGH — general masked diffusion method, compatible with block-diffusion. Better variance → more stable training on MoE architectures

### Coupled-GRPO — RL for Code Generation
- **Paper**: arXiv:2506.20639 (Jun 2025, Apple+HKU)
- **Code**: github.com/apple/ml-diffucoder
- **Model**: DiffuCoder-7B-cpGRPO on HuggingFace (apple/DiffuCoder-7B-cpGRPO)
- **Mechanism**: Complementary mask noise for paired rollouts — one gets pattern M, other gets 1-M; reduces variance without extra forward passes
- **Results**: +4.4% on EvalPlus, reduces AR bias in decoding
- **Insight**: dLLMs can decide how causal generation should be; higher temperature diversifies generation ORDER, creating rich RL rollout space
- **DiffusionGemma compat**: 🟢 HIGH — DG already hits 91.1 tok/s on code (1.8× prose), RL can add +4-5%

### Block-R1 — Dynamic Block Size for Multi-Domain RL
- **Paper**: arXiv:2605.11726 (May 2026)
- **Code**: github.com/YanJiangJerry/Block-R1
- **Dataset**: Block-R1-41K (41K multi-domain reasoning samples)
- **Problem**: Fixed block size limits multi-domain RL — math and code need different block sizes
- **Solution**: Teacher-student filtering for sample-level optimal block sizes + b1 dynamic block-size generation via entropy analysis
- **DiffusionGemma compat**: 🟢 DIRECT — DG uses fixed canvas=256, Block-R1 shows this is suboptimal for multi-domain

### ELBO-KTO — Unpaired Preference Optimization
- **Paper**: arXiv:2510.23658 (Oct 2025)
- **Code**: github.com/vaibhavjindal/elbo-kto
- **Mechanism**: ELBO surrogate + prospect-theoretic KTO objective — only needs good/bad labels, no pairwise data
- **Results**: On par with or better than base model on GSM8K, MMLU
- **DiffusionGemma compat**: 🟡 PARTIAL — useful when paired preference data unavailable

## Compatibility Matrix for DiffusionGemma

| Method | Compat | Reason | GPU-days | Complexity |
|:-------|:------:|:-------|:---------|:-----------|
| VRPO | 🟢 Direct | Masked diffusion, surface-level | 4-8 | Medium |
| StableDRL | 🟢 Critical | Only proven block-diffusion RL | 8-16 | High |
| GDPO | 🟢 High | Lower-variance ELBO, general diffusion | 8-16 | High |
| diffu-GRPO (d1) | 🟢 Direct | Masked diffusion, random masking | 4-8 | Medium |
| Coupled-GRPO | 🟢 High | Masked diffusion, coupled sampling | 2-4 | Medium |
| Block-R1 | 🟢 Direct | Block-diffusion native | 4-8 | High |
| ELBO-KTO | 🟡 Partial | Unpaired data only | 1-2 | Low |
| Raw DPO | 🔴 No | Needs exact likelihood | — | — |
| Raw GRPO | 🔴 Collapse | Reward collapse at ~300 steps | — | — |

## Practical Roadmap for DiffusionGemma

### Phase 1: Quick Wins (no RL)
- Abliteration ✓ (already done — heretic model)
- Thinking mode ✓ (already working)
- Steps tuning ✓ (already configurable)
- Prompt engineering for infilling (framed with `<mask>` placeholders)

### Phase 2: Light RL (1 week)
1. ELBO-KTO on unpaired data (1-2 GPU-days): rubricate DG responses as good/bad
2. VRPO on paired data (4-8 GPU-days): synthetic preferences from DG

### Phase 3: Full GRPO via StableDRL (2-3 weeks)
1. Implement StableDRL for DG: staircase attention for block-diffusion, unconditional clipping, self-normalization
2. RL on reasoning data: +10-15 pp expected on math (SDAR-8B analog)
3. Multi-domain RL with Block-R1: dynamic block sizes

### Phase 4: Code-Specialized RL
1. Coupled-GRPO on code data: DG's 91.1 tok/s on code + RL = +4-5% quality

## StableDRL Implementation Notes for llama.cpp PR #24423

Current stack: llama-diffusion-cli → diffusion-server.py (FastAPI) → LiteLLM

Needed additions:
1. ELBO estimator in diffusion-server.py — multi-step MC ELBO for importance ratios, access to internal logits per diffusion step, rollout trajectory storage
2. Unconditional clipping: `ρ_clipped = clamp(ρ, 1-ε, 1+ε)` always (not conditional on advantage)
3. Self-normalization: `update = sum(ρ_clipped * A * g) / sum(ρ_clipped)` instead of dividing by G
4. Staircase attention: split canvas=256 into sub-blocks, structured attention mask for leak-free probability estimation
5. RL loop: 4-8 rollouts/prompt → verifiable reward (math answer matching) or reward model → StableDRL gradient step → 500-1000 iterations

## Key Papers Summary

| Paper | ID | Date | Type | Block-diff? | Code? |
|:------|:---|:-----|:-----|:-----------|:------|
| d1 / diffu-GRPO | 2504.12216 | Apr 2025 | Policy Grad | ✅ | Yes |
| VRPO (LLaDA 1.5) | 2505.19223 | May 2025 | Preference | ✅ | Yes |
| Coupled-GRPO (DiffuCoder) | 2506.20639 | Jun 2025 | Policy Grad | ✅ | Yes |
| ELBO-KTO | 2510.23658 | Oct 2025 | Preference (unpaired) | ✅ | Yes |
| GDPO | 2510.08554 | Oct 2025 | Policy Grad | ✅ | Yes |
| StableDRL | 2603.06743 | Mar 2026 | Policy Grad | ✅ (staircase) | Yes |
| Block-R1 | 2605.11726 | May 2026 | Policy Grad + Adaptive | ✅ (core) | Yes |
| DreamReasoner-8B | 2606.19257 | Jun 2026 | Curriculum RL | ✅ | Yes |

## Source Quality Notes

- StableDRL paper (arXiv:2603.06743) — extracted via pdftotext, full algorithm details verified. ICML 2026 accepted.
- VRPO paper (arXiv:2505.19223) — ACL 2026 accepted. Three variance reduction strategies confirmed from paper + demo page.
- d1 paper (arXiv:2504.12216) — NeurIPS 2025. Two-stage: masked SFT → diffu-GRPO. Code at github.com/dllm-reasoning/d1.
- GDPO paper (arXiv:2510.08554) — Semi-deterministic MC ELBO. Outperforms diffu-GRPO. 
- DiffuCoder paper (arXiv:2506.20639) — Apple+HKU, weights on HuggingFace (apple/DiffuCoder-7B-cpGRPO). Coupled-GRPO details from DeepWiki analysis.
- Block-R1 — GitHub repo active, Block-R1-41K dataset available.
- All methods independently verified against local skill references and web search results.
- Comprehensive survey: "Diffusion Language Models — Part Four (Post-training with RL)" by Kelvin (Oct 2025, hankelvin.github.io) — covers online policy-gradient + offline methods for DLMs.

## rldiffusion Implementation

Concrete working implementation at `/home/user/dev/rldiffusion/` (Pavel's DGX Spark):

**Components**: Anchored Self-Play (Code vs Test LoRA adversarial), DES-MoE 3-phase freeze schedule (64 MoE experts), StableDRL (unconditional clipping + self-norm), VRPO fallback (reward-only, no logits), Mistake Book (prioritized experience replay, 10K capacity), Reference Bug anchoring (5 teachers: GPT-5, GLM-5.2, DeepSeek-V4, Fable-5, Qwen-3.7), Docker sandbox (code execution), Resource limiter (MSK time-based CPU/RAM caps).

**Critical limitation**: `llama-diffusion-cli` returns text only — NO logits. This means StableDRL ELBO computation is impossible, and VRPO reward-based updates cannot compute actual LoRA gradients. The pipeline currently collects data but **does not update LoRA weights**. To unlock full RL training, one of:
1. Modify llama.cpp diffusion-cli to return logits (50-200 lines C++)
2. Use vLLM with forward hooks (if diffusion support matures)
3. Use Unsloth/PyTorch inference with `output.logits` access

Full research report: `/home/user/dev/rldiffusion/RESEARCH_REPORT.md` (July 2026, 18.8 KB) — covers SOTA comparison, DES-MoE architecture, GDPO vs diffu-GRPO analysis, roadmap with priorities.
