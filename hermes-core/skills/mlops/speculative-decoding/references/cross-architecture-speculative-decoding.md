# Cross-Architecture Speculative Decoding

Research findings on using a model from **family A** as a draft model for a target model from **family B**. Verified Jul 14, 2026.

## The Three Hard Blockers

### 1. Tokenizer/Vocabulary Mismatch (FATAL)

Speculative decoding works by comparing **token IDs** — draft proposes ID `1234`, target checks the same ID. If draft and target use different tokenizers, the IDs are meaningless to each other.

| Model Family | Vocab Size | Tokenizer |
|---|---|---|
| Qwen3.5/3.6 | 248,320 | BPE (Qwen-specific) |
| Gemma 4 / DiffusionGemma | 262,144 | SentencePiece (Gemma-specific) |
| LLaMA 3.x | 128,256 | BPE (tiktoken-based) |
| DeepSeek V3 | 129,280 | BPE |

**Example:** DiffusionGemma (262,144 vocab) cannot draft for Qwen3.6-27B (248,320 vocab). Token IDs don't align. This is unfixable without retraining one model on the other's tokenizer.

### 2. Size Ratio (PRACTICAL)

Draft model should be **10-50x smaller** than target. Both models must coexist in VRAM simultaneously.

| Draft | Target | Ratio | VRAM (both) | Feasible on GB10? |
|---|---|---|---|---|
| DFlash (0.7GB) | Qwen3.6-27B (54GB) | 77x | ~58GB | ✅ |
| EAGLE3 (~0.4B) | Qwen3.6-27B (54GB) | 135x | ~56GB | ✅ |
| DiffusionGemma (52GB) | Qwen3.6-27B (54GB) | 1x | ~108GB | ❌ OOM |
| Qwen3.6-27B INT4 (17.5GB) | Qwen3.6-27B bf16 (54GB) | 3x | ~74GB | ⚠️ tight |

### 3. Hidden State Format (ARCHITECTURAL)

EAGLE3 and DFlash condition the draft on hidden states from the target's intermediate layers. Different architectures have different hidden state dimensions:

| Model | Hidden Size | Layers |
|---|---|---|
| Qwen3.6-27B | 5120 | 64 |
| Qwen3.6-35B-A3B | 2048 | 40 |
| DiffusionGemma | 2816 | 30 |

A projection layer (trainable) is needed when dimensions differ. DFlash/EAGLE3 handle this via `fc` projection, but it must be trained.

## What Actually Works: Trained Diffusion Drafters

### DEER (Dec 2025, arXiv:2512.15176)

DEER is the SOTA approach for diffusion-based speculative drafting of AR models. Key insight: train a **small** (0.5B) discrete diffusion model under the **target model's tokenizer**.

**Architecture:**
- Draft: 0.5B discrete diffusion LLM (dLLM), 470M params
- Target: any AR LLM (tested on Qwen3-8B, Qwen3-14B, Qwen3-30B-A3B)
- Both share the target's tokenizer (no vocab mismatch)

**Two-stage training:**
- **Stage I — AR-style Distillation**: Train the diffusion draft to mimic the AR target's token distribution. Uses the target model's hidden states as conditioning.
- **Stage II — Scribe Refinement**: Fine-tune on hard examples where the draft's first-pass predictions diverge from the target.

**Results (Qwen3-30B-A3B):**
| Metric | DEER | EAGLE-3 |
|---|---|---|
| Draft acceptance length | **up to 32 tokens** | 10 tokens |
| Speedup (HumanEval) | **5.54x** | 2.41x |
| Draft model size | 470M | 140M |

**Why DEER beats EAGLE-3:**
- Block generation (parallel) eliminates sequential error accumulation
- Diffusion denoising naturally self-corrects within the block
- Single forward pass for entire draft block (like DFlash)

### DiffuSpec (Sep 2025, arXiv:2510.02358)

Training-free approach: reuses a pretrained DLM as drafter for any AR verifier. Adds:
- **CPS (Causal-Consistency Path Search)**: extracts a left-to-right causal path from the diffusion token lattice to align with AR verification
- **ADL (Adaptive Draft Length)**: dynamically adjusts draft length based on recent acceptance stats

Results: up to 3x wall-clock speedup. Lower than DEER (no targeted training) but zero training cost.

**Requirement:** DLM and AR verifier must share the same tokenizer (DiffuSpec is training-free but NOT tokenizer-free).

### DFlash (Z-Lab, Feb 2026)

DFlash IS a diffusion drafter for AR models, but purpose-built (not a reused DLM). The draft model is trained from scratch on the target's architecture and tokenizer. See main skill body for DFlash details.

## Decision Matrix: What Draft Approach to Use

| Scenario | Best Approach |
|---|---|
| Same architecture family (Qwen→Qwen) | DFlash (parallel, 2-3x) or EAGLE3 (sequential, 2-6x) |
| Cross-family, can train | DEER (train 0.5B diffusion under target tokenizer) |
| Cross-family, cannot train | DiffuSpec (if shared tokenizer) or n-gram (if different tokenizer) |
| Different tokenizer entirely | ❌ Blocked — must retrain one model or use n-gram/prompt-lookup |

## Papers

- **DEER** (Dec 2025): Draft with Diffusion, Verify with AR. arXiv:2512.15176. 5.54x speedup, 32-token acceptance on Qwen3-30B-A3B.
- **DiffuSpec** (Sep 2025): Unlocking DLMs for Speculative Decoding. arXiv:2510.02358. 3x speedup, training-free.
- **DART** (Jan 2026): Diffusion-Inspired Speculative Decoding. arXiv:2601.19278.
- **ML-SpecQD** (Mar 2025): Multi-Level Speculative Decoding with Quantized Drafts. arXiv:2503.13565. 2.72x using MXFP4 quantized drafts + recursive speculation.
- **MoE-SpeQ** (Nov 2025): Speculative Quantized Decoding for MoE. arXiv:2511.14102. Co-design of spec execution + expert offloading.
- **LayerSkip** (Apr 2024): Early-exit self-speculative. arXiv:2404.16710. No draft model needed.
