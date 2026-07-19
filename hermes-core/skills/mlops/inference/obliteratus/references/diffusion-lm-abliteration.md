# Diffusion LLM Abliteration — Research Findings

## TL;DR

Standard directional weight-projection abliteration **does not work** on diffusion LMs —
refusal is a vocabulary-space attractor (high-probability denoising trajectory toward refusal
tokens), not a projectable direction in weight space. This was proven by DuoNeural's three
failed attempts (2026-06-10).

**However, newer methods have achieved partial-to-full success (as of 2026-07-14):**
- **ARA (Arbitrary-Rank Ablation)** — 4/100 refusals, KL=0.11. Works because it abandons
  refusal directions entirely: unconstrained matrix optimization (L-BFGS) with clamped KNN
  multi-directional overcorrection. See `Umranz/diffusiongemma-26B-A4B-it-abliteration`.
- **EGA (Expert-Granular Abliteration)** — 13/100 refusals, KL=0.49. Partial success via
  per-expert norm-preserving biprojection across all 128 MoE experts + Heretic patches.
  See `edwixx/diffusiongemma-26B-A4B-it-HERETIC-Uncensored`. Known "own" token artifact.

The key insight: the failure mode is method-specific, not architecture-wide. Projection-based
methods (RepE, orthogonal, diff-in-means) fail because the refusal signal is non-separable.
Optimization-based methods (ARA, EGA) succeed because they don't assume separability.

## Primary Source

**DuoNeural** (Archon + Jesse), 2026-06-10.
Model: `DuoNeural/diffusiongemma-26B-A4B-it-abliterated` on HuggingFace.
Base: `google/diffusiongemma-26B-A4B-it` (Google DeepMind, released same day).
Papers: https://zenodo.org/communities/duoneural

## Three Failed Attempts on DiffusionGemma

| Experiment | Target | Weights Modified | Result |
|---|---|---|---|
| v1: partial encoder | encoder L9-L15 o_proj + mlp.down_proj | 14 | refusal persists |
| v2: full encoder | ALL encoder layers, α=0.95 | ~62 | refusal persists |
| v3: decoder MoE | ALL decoder down_proj + 128 MoE experts × 30 layers | 91 | refusal persists |

### Why All Three Fail (Different Mechanisms)

**Encoder (v1/v2):** The encoder has exceptionally clean safety geometry
(cos=0.884 at L11 — highest DuoNeural has ever measured). But the encoder functions as a
harm **classifier**, not a generative gate. The decoder generates refusal templates
independently of encoder conditioning.

**Decoder (v3):** Decoder layer 22 shows cos(harmful, harmless) = **0.9360** — the harmful
and harmless intermediate activations are 93.6% similar. The refusal signal does not exist
as a projectable direction in decoder intermediate layers.

**Root Mechanism:** Refusal in DiffusionGemma is a **vocabulary-space attractor** — a
high-probability denoising trajectory toward specific refusal text tokens. This is not a
weight-space direction and cannot be removed by projection.

## Safety Geometry Comparison

| Component | Peak Layer | cos_global | Shape |
|---|---|---|---|
| DiffusionGemma Encoder | L11/30 (37%) | 0.884 | Symmetric bell — bidirectional |
| DiffusionGemma Decoder L22 | — | cos(h,s)=0.936 | No meaningful separation |
| AR Gemma-4-26B (contrast) | L22/46 (48%) | 0.751 | Asymmetric three-zone arc |

## DiffusionGemma Architecture

- **Encoder** (25.8B): bidirectional Gemma-4 transformer — harm CLASSIFIER
- **Decoder** (25.2B): iterative block diffusion denoiser, 128 MoE experts (8 active) — refusal GENERATOR
- Canvas length: 256 tokens, context: 256K, vocab: 262K
- Speed: 1100+ tokens/sec (H100, FP8)
- Multimodal: text, image, video input

## DiffusionGemma vs AR Gemma 4 Benchmarks

| Benchmark | DiffusionGemma 26B A4B | Gemma 4 26B A4B (AR) | Gap |
|---|---|---|---|
| MMLU Pro | 77.6% | 82.6% | −5.0 |
| AIME 2026 (no tools) | 69.1% | 88.3% | −19.2 |
| LiveCodeBench v6 | 69.1% | 77.1% | −8.0 |
| Codeforces ELO | 1429 | 1718 | −289 |
| GPQA Diamond | 73.2% | 82.3% | −9.1 |
| BigBench Extra Hard | 47.6% | 64.8% | −17.2 |
| MMMLU | 81.5% | 86.3% | −4.8 |
| MMMU Pro (vision) | 54.3% | 73.8% | −19.5 |
| MATH-Vision | 70.5% | 82.4% | −11.9 |

DiffusionGemma trades 5-19 quality points for 4x speed. Standard projection abliteration
fails on the diffusion variant, but ARA (4/100 refusals, KL=0.11) and EGA (13/100, KL=0.49)
now work. AR variant remains easier and more reliable for abliteration.

## Working Abliterated Gemma 4 26B AR Variants

These use the AR (non-diffusion) Gemma 4 26B-A4B-it base where abliteration works normally.

| Model | Method | Refusals | KL | Notes |
|---|---|---|---|---|
| `neyo8826/gemma-4-26B-A4B-it-abliterix` V6 | Expert-Granular + Projected (grimjim) | 2/100 | 0.0005 | Best: all 128 experts × 30 layers |
| `huihui-ai/Huihui-gemma-4-26B-A4B-it-abliterated` | Standard projection (Sumandora) | ~3/100* | moderate | QAT q4_0 variant available |
| `EZForever/gemma-4-26B-A4B-it-qat-uncensored-heretic-UDmerge-GGUF` | Heretic + UD merge | low | — | GGUF, QAT |
| `prutser/gemma-4-26B-A4B-it-ara-abliterated` | Adaptive Refusal Abliteration (ARA) | low | — | GGUF quants |

*Many claimed refusal rates are inflated — see independent benchmark below.

## Independent Benchmark: 13 Abliteration Techniques on Gemma4-E2B

Source: Nathan Sapwell (DreamFast), 2026-07-09. 44 GPU-hours, RTX 5090, BF16,
lm-eval-harness via vLLM v0.20.0, HarmBench 400 prompts.
URL: https://nathan.sapwell.net/posts/gemma4-e2b-abliteration/

### Key Results (sorted by ASR)

| Variant | ASR | GSM8K Flex | MMLU | KL | Tensors |
|---|---|---|---|---|---|
| Base | 32.2% | 83.47% | 29.00 | — | — |
| coder3101 (Heretic, surgical) | 96.0% | 84.84% (+1.37) | 28.70 | 0.167 | 9 |
| llmfan46 (Heretic, lightest) | 83.8% | 83.93% (+0.46) | 28.36 | 0.068 | 7 |
| trevorjs | 99.5% | 82.49% | 28.94 | 0.365 | 35 layers |
| duoneural | 82.2% | 83.09% | 28.75 | 0.187 | moderate |
| treadon | 100.0% | 80.59% | 28.02 | 3.971 | heavy damage |
| ether4o4 | 95.2% | 76.57% (−6.9) | 28.23 | 0.669 | 166 tensors |

### Critical Findings

1. **KL spread 58.7x** (0.068 → 3.971) — widest ever measured across abliteration benchmarks
2. **DuoNeural claimed KL≈0.001, actual was 0.187** (187x higher). Corrected after challenge.
3. **Surgical methods (3% weights, o_proj only) outperform aggressive methods** — less collateral damage
4. **No universal abliteration subspace** — cosine similarity of many technique pairs ≈0.01 (near-orthogonal)
5. **GSM8K "degradation" on reasoning models is an artifact** — model thinks longer → exhausts token budget → empty answer scored wrong. When accounting for empty responses, gap narrows from 8.3 to ~3 points.
6. **Two variants actually BEAT base on GSM8K** (coder3101 +1.37, llmfan46 +0.46) — abliteration shortened thinking chains, letting more answers fit token budget.
7. **Shared-KV export bug**: 5 of 13 variants shipped missing 60 safetensor keys (abliteration tools only saved modified weights). Fix: copy missing weights from base model (lossless, byte-identical).

### Claim vs Reality Discrepancies

- **duoneural**: claimed "near-zero divergence ~0.001" → actual 0.187 (187x), 71 refusals on safety test
- **wwtcyberlab**: claimed "0.0% refusal rate, 101% quality preservation" → 2 refusals, LAMBADA perplexity 5.69x base
- **treadon**: claimed "same model, same weights" → KL 3.971 (4.1x higher than any other variant)
- **Honest creators**: coder3101 (0.1651 claimed vs 0.167 measured), pew (0.152 vs 0.153), trevorjs (0.346 vs 0.365)

### Best Technique Recommendations (AR models)

| Use case | Recommended | Why |
|---|---|---|
| Best overall tradeoff | coder3101 (Heretic Magnitude-Preserving Orthogonal) | 96% ASR, 9 tensors, beats base on GSM8K, KL 0.167 |
| Most conservative | llmfan46 (Heretic, lightest) | 7 tensors, KL 0.068, but only 83.8% ASR |
| Max safety removal, controlled damage | trevorjs | 99.5% ASR, 2 refusals, zero truncations, KL 0.365 |
| Avoid for general use | ether4o4 | −6.9 GSM8K, 84 empty responses, 166 tensors |

## Diffusion LLM Landscape (Open Weights)

| Model | Params | License | Speed | Notes |
|---|---|---|---|---|
| DiffusionGemma 26B A4B | 25.2B/3.8B active | Apache 2.0 | 1100+ tok/s | Google, Jun 2026, encoder-decoder MoE |
| LLaDA 8B | 8B dense | MIT | ~200 tok/s | Feb 2025, competitive with LLaMA3 8B |
| MMaDA-8B | 8B multimodal | MIT | — | NeurIPS 2025, text+image gen, UniGRPO RL |
| Mercury Coder Mini/Small | closed | API only | 1109/737 tok/s | Inception Labs, Jun 2025 |
| Mercury 2 | closed | API only | 1000+ tok/s | Feb 2026, reasoning LLM |
| Seed Diffusion | closed | API only | 2146 tok/s | ByteDance, Aug 2025, code SOTA |

**DiffusionGemma is now abliterated** (ARA method, 4/100 refusals). Other diffusion LMs
(LLaDA, MMaDA, Mercury, Seed) remain untested. Standard projection methods remain
architecturally incompatible; ARA and EGA are the viable alternatives.

## Successfully Abliterated DiffusionGemma Variants (2026-07 landscape)

Complete landscape discovered via HuggingFace API search + README parsing. Metrics
self-reported by authors; verify independently before production use.

| Model | Method | Refusals | KL Div | Notes |
|---|---|---|---|---|
| `Umranz/diffusiongemma-26B-A4B-it-abliteration` | **ARA** (Arbitrary-Rank Ablation) | **4/100** | **0.1106** | Best overall. Trial 144 of 150-trial Optuna search. Layers 1-20, attn.o_proj + mlp.down_proj. Clamped KNN multi-directional overcorrection + per-layer adaptive steering. Author: umran666, Heretic PR #400. |
| `edwixx/diffusiongemma-26B-A4B-it-HERETIC-Uncensored` | **EGA** (Expert-Granular + Heretic directional) | 13/100 | 0.4909 | First successful abliteration (Jun 25). Trial 89 of 200. Per-expert ablation across all 128 MoE experts. Known "own" token artifact in output. 1563 downloads. |
| `FredyRivera-dev/diffusiongemma-26B-A4B-it-HERETIC-Uncensored` | Clone of edwixx + processor_config.json | 13/100 | 0.49 | Identical to edwixx. |
| `DuoNeural/diffusiongemma-26B-A4B-it-abliterated` | RepE / Orthogonal Projection | **100/100** | — | **FAILED.** Research artifact documenting failure. 3 experiments, 91 weights modified, all still refuse. |

**GGUF/quant derivatives**: `yabaimimi/edwixx__...-GGUF` (9380 dl), `Coquelicots/...-FP8-dynamic` (gated).

### Why ARA Succeeds Where Projection Fails (Umranz/umran666, Heretic PR #400)

ARA fundamentally differs from all projection-based methods:
- **No refusal directions**: Doesn't extract a PCA/SVD direction at all. Captures input/output
  tensors at each module via PyTorch hooks, then directly optimizes the weight matrix.
- **L-BFGS optimization**: Affine-convex objective, converges in 2-3 iterations. Optimizes
  3 competing goals: (1) harmless outputs change minimally, (2) harmful outputs approach
  harmless ones, (3) harmful outputs overcorrect away from original harmful state.
- **Clamped KNN overcorrection**: Instead of single-direction steering, uses KNN-based
  multi-directional approach with mathematical clamp on negative loss term. Without the
  clamp, optimizer exploits unbounded negative term → KL explodes to 20+.
- **Per-layer adaptive steering**: Splits layer range into thirds (early/core/late),
  applies different steering pressure per zone. DiffusionGemma's refusal circuit is in core layers.
- **DiffusionGemma-specific patches**: MoE experts stored as batched tensor [128, 2816, 704]
  — iterates all 128 slices. Encoder-decoder weight tying fixed with context manager merging
  LoRA into shared weights before generation. PEFT task type = FEATURE_EXTRACTION (not
  CAUSAL_LM, since DiffusionGemma's generate() doesn't implement prepare_inputs_for_generation).

### DiffusionGemma Abliteration Heretic Development Timeline

- **PR #378** (edwixx, Jun 16): First patches to support DiffusionGemma in Heretic. EGA across
  128 MoE experts, weight tying fix, FEATURE_EXTRACTION task type, forward hooks for hidden states.
- **PR #211** (p-e-w, base ARA): Arbitrary-Rank Ablation — fundamentally new method, no refusal
  directions. Open as of 2026-07-05.
- **PR #400** (umran666, Jul 5-14): Clamped KNN objective + adaptive steering for DiffusionGemma.
  Closed (needs clean rebase as of Jul 14). Active development.
- **PR #332** (ARA-LoRA variant): ARA as LoRA adapters instead of full weight modification.

## What Might Work Next (Speculative → Tested as of 2026-07)

Since refusal in diffusion LMs is a vocabulary-space attractor, potential approaches:

**TESTED AND WORKING:**
- ✅ **ARA (Arbitrary-Rank Ablation)**: 4/100 refusals, KL=0.11. See Umranz model above.
- ✅ **EGA (Expert-Granular Abliteration)**: 13/100 refusals, KL=0.49. Partial success.

**TESTED AND FAILED:**
- ❌ **RepE / Orthogonal Projection** (DuoNeural): 100/100 refusals persist after 91 weight mods.
- ❌ **Standard directional ablation** (diff-in-means): fails for same reason as DuoNeural.

**NOT YET TESTED on diffusion LMs:**
- **Fine-tuning/SFT**: shift the attractor basin through gradient updates. edwixx noted a small
  LoRA fine-tune on clean data would reduce the "own" token artifact.
- **DPO/ORPO**: the most reliable uncensoring approach but expensive. No one has tried it on
  DiffusionGemma yet (released Jun 10 2026, ecosystem is still young).
- **Vocabulary/token-level intervention**: modify the denoising trajectory directly via logit bias.
- **Inference-time steering**: though DuoNeural's research suggests the signal isn't separable,
  logit-level intervention might work.

### Researching Uncensored Model Variants on HuggingFace

When a user asks "is there a better uncensored/abliterated model for X?", use this workflow.
Model authors use inconsistent tags — a single search term misses variants.

```bash
# 1a. Multi-term search: run each keyword variant separately (HF API matches on
#     search-visible fields, not tags — so a model tagged "heretic" but titled
#     "diffusiongemma-26B-A4B-it" won't appear under "uncensored" search).
for term in "uncensored" "abliteration" "abliterated" "heretic" "nsfw" "abliterate"; do
  echo "=== $term ==="
  curl -sL "https://huggingface.co/api/models?search=MODELNAME+$term&limit=20" | python3 -c "
import json,sys
data=json.load(sys.stdin)
[print(f'{m[\"id\"]}  dl={m.get(\"downloads\",0)}  likes={m.get(\"likes\",0)}') for m in data]
"
done

# 1b. Full search + client-side tag filter: catches models whose tags contain the
#     keyword but whose title/search fields don't. This finds ~30% more variants.
curl -sL "https://huggingface.co/api/models?search=MODELNAME&limit=50&full=true" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for m in data:
    tags = str(m.get('tags',[])).lower()
    if any(k in tags for k in ['uncensored','abliteration','heretic','ara','nsfw']):
        print(f'{m[\"id\"]}  dl={m.get(\"downloads\",0)}  mod={m.get(\"lastModified\",\"?\")[:10]}')
"

# 1c. Deduplicate across all searches — same model appears under multiple terms.

# 2. Get detailed metadata for each candidate (tags, config architecture, timestamps)
curl -sL "https://huggingface.co/api/models/{org}/{model}" | python3 -m json.tool

# 3. Get metrics from each model's README (refusal rate, KL, method)
curl -sL "https://huggingface.co/{org}/{model}/raw/main/README.md" | head -200

# 4. Cross-reference with GitHub PRs for development status and known issues
curl -sL "https://api.github.com/repos/{repo}/pulls?state=all&per_page=20&sort=updated&direction=desc" | python3 -m json.tool
# Then drill into specific PRs for body + comments:
curl -sL "https://api.github.com/repos/{repo}/pulls/{number}" | python3 -m json.tool
curl -sL "https://api.github.com/repos/{repo}/issues/{number}/comments" | python3 -m json.tool

# 5. Compare on TWO axes: refusal rate (lower=better) AND KL divergence (lower=less damage)
#    High refusal + high KL = worst. Low refusal + low KL = best (Pareto-optimal).
#    Also flag clones (identical README/metrics to another model = repost, not a new variant).
```
