# EAGLE-3 Speculative Decoding — Full Guide

> Research session: 2026-07-12. Target model: Agents-A1-35B (Qwen3.5 MoE). DGX Spark (GB10, 128 GB).

## What is EAGLE-3

Speculative decoding method (NeurIPS'25). Lightweight draft model (~400 MB, 1 transformer decoder layer) predicts K future tokens autoregressively, then the frozen target model verifies all K in a single parallel forward pass. Accepted tokens are kept, rejected ones discarded — **output distribution is mathematically identical to vanilla decoding** (lossless).

**Speedup:** 2–5.6× on decode. Draft model is 1–5% of target parameters.

### How EAGLE-3 differs from standard speculative decoding

Standard speculative decoding uses a small standalone LLM as draft. EAGLE-3's draft takes **hidden states from the frozen target model** (low, middle, high layers), fuses them, and autoregressively predicts tokens. This gives much higher acceptance rates than standalone draft models.

### Framework support

| Framework | Since | Flag |
|-----------|-------|------|
| **llama.cpp** | b9606 (June 2026) | `--spec-type draft-eagle3` |
| **vLLM** | v0.9.0+ | `--speculative-model eagle --num-speculative-tokens 5` |
| **SGLang** | Native | `--speculative-draft-model-path` |

**For DGX Spark: use llama.cpp only.** vLLM doesn't handle unified memory well.

## Architecture

EAGLE-3 draft for Qwen3.5-35B-A3B (from SpecForge config `qwen3.5-35b-a3b-eagle3.json`):

```json
{
  "architectures": ["LlamaForCausalLMEagle3"],
  "hidden_size": 2048,
  "num_hidden_layers": 1,
  "num_attention_heads": 16,
  "num_key_value_heads": 2,
  "head_dim": 256,
  "intermediate_size": 16384,
  "vocab_size": 248320,
  "draft_vocab_size": 32000,
  "max_position_embeddings": 262144
}
```

**Key insight:** `draft_vocab_size: 32000` — the draft predicts from a smaller candidate vocabulary (vs target's 248K), drastically reducing the output projection size. The draft shares the target's embedding layer (`embedding-key: model.embed_tokens.weight`).

**Size:** ~200M params ≈ 400 MB in BF16. This is 0.6% of the 35B target.

## Pre-Trained Drafts

### Available for Qwen family (HF)

| Draft | Target | Downloads | Notes |
|-------|--------|-----------|-------|
| `jiapingW/Qwen3.5-35B-A3B-Eagle3-Specforge` | Qwen3.5-35B-A3B | 87 | **Closest to Agents-A1** |
| `Tengyunw/qwen3_30b_moe_eagle3` | Qwen3-30B-A3B | 3,164 | Older Qwen3 arch |
| `AngelSlim/Qwen3-a3B_eagle3` | Qwen3-30B-A3B | ~3,000 | Alternative |
| `HathoraResearch/qwen3_30b_moe_eagle3-ultra-1k-sample` | Qwen3-30B-A3B | new | 366MB, trained 30min on H100 |
| `RedHatAI/Qwen3-8B-speculator.eagle3` | Qwen3-8B | 80,671 | Most popular |
| `wimmmm/Ex0bit-Qwen3.6-27B-PRISM-EAGLE3-GGUF` | Qwen3.6-27B dense | 1,889 | Already GGUF |

### For Agents-A1 specifically: NONE

Agents-A1 has different weights than vanilla Qwen3.5-35B-A3B (post-training: SFT + RL + long-horizon trajectories). The Qwen3.5 draft will have reduced acceptance rate because hidden states differ.

**Recommendation:** Quick-test the `jiapingW` draft first. If acceptance <30%, train a custom draft.

## llama.cpp Integration

### Requirements
- llama.cpp **b9606+** (June 2026, PR #18039)
- EAGLE-3 draft in GGUF format (converted from PyTorch safetensors)
- Target model in GGUF format

### Conversion: PyTorch draft → GGUF

```bash
python3 /home/user/dev/llama.cpp/convert_hf_to_gguf.py \
    /path/to/eagle3-draft-checkpoint/ \
    --outtype f16 \
    --outfile /home/user/models/agents-a1-eagle3-f16.gguf
```

The `convert_hf_to_gguf.py` in b9606+ recognizes `LlamaForCausalLMEagle3` architecture and produces correct GGUF with eagle3 metadata.

### Server launch

```bash
llama-server \
    -m /home/user/models/agents-a1-apex-i-quality.gguf \
    --model-draft /home/user/models/qwen35-eagle3-f16.gguf \
    --spec-type draft-eagle3 \
    --spec-draft-n-max 8 \
    --host 0.0.0.0 --port 8104 \
    --no-mmap --flash-attn on \
    --cache-type-k q8_0 --cache-type-v q8_0 \
    -c 65536 --reasoning off
# Memory: target (~22 GB) + draft (~0.4 GB) + KV = ~25 GB — fine on 128 GB

**Flags explained:**
- `--spec-type draft-eagle3` — tells llama.cpp this is an EAGLE-3 draft (extracts hidden states from target)
- `--spec-draft-n-max 8` — how many tokens to draft per step (2-12 range, EAGLE-3 paper uses 8)
- `--model-draft` / `-md` — path to draft model GGUF
- `--reasoning off` — disables thinking tokens for Agents-A1 (critical for chat)
- Memory: target (22 GB APEX) + draft (0.4 GB) + KV cache = ~25 GB ✅

### Health check

```bash
# Verify server responds
curl -s http://localhost:8104/v1/models | python3 -c "import sys,json; print(json.load(sys.stdin))"

# Test generation speed (compare with/without eagle3)
curl -s http://localhost:8104/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Explain quantum computing in detail"}],"max_tokens":500,"temperature":0}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'tokens: {d[\"usage\"][\"completion_tokens\"]}')"
```

## Training via SpecForge

### Installation

```bash
git clone https://github.com/sgl-project/SpecForge.git /home/user/dev/SpecForge
cd /home/user/dev/SpecForge
python3 -m venv ~/venvs/specforge
source ~/venvs/specforge/bin/activate
pip install -e .
pip install sglang[all]
```

### Configs already available

```bash
ls configs/ | grep qwen3.5
# qwen3.5-35b-a3b-dflash.json
# qwen3.5-35b-a3b-eagle3.json   ← USE THIS
```

### Data preparation

**CRITICAL: on-policy data only.** The draft learns to mimic the TARGET model's output distribution. Training on generic ShareGPT data produces a draft that predicts what ShareGPT would say — not what Agents-A1 would say.

Recipe from `migtissera/Tess-4-27B-EAGLE3` (proven):
- ~5,000 samples generated BY the target model
- Diverse: reasoning, coding, agentic tasks, multi-turn tool-call traces
- Format: ShareGPT JSONL

```jsonl
{"conversations": [{"from": "human", "value": "Write a function that..."}, {"from": "gpt", "value": "Here's the implementation..."}]}
```

Generate samples by running Agents-A1 against a diverse prompt set (~5000 prompts across reasoning, coding, search, tool-use domains).

### Training command

```bash
cd /home/user/dev/SpecForge

torchrun --standalone --nproc_per_node 1 \
    scripts/train_eagle3.py \
    --target-model-path /home/user/models/Agents-A1 \
    --draft-model-config configs/qwen3.5-35b-a3b-eagle3.json \
    --train-data-path cache/dataset/agents_a1_train.jsonl \
    --output-dir /home/user/models/agents-a1-eagle3-draft \
    --num-epochs 5 \
    --batch-size 1 \
    --learning-rate 1e-4 \
    --max-length 4096 \
    --chat-template qwen \
    --embedding-key model.embed_tokens.weight \
    --target-model-backend sglang \
    --sglang-mem-fraction-static 0.5 \
    --cache-dir cache \
    --report-to tensorboard
```

**Parameters:**
- `--num-epochs 5` — 5-10 epochs typical (HathoraResearch used 1 epoch × 625 steps; Tess used 2 epochs)
- `--batch-size 1` — batch size 1 (limited by GPU memory)
- `--learning-rate 1e-4` — standard
- `--max-length 4096` — max sequence length for training samples
- `--sglang-mem-fraction-static 0.5` — 50% of GPU memory for target model in SGLang

### DGX Spark resource budget

| Component | Memory |
|-----------|--------|
| Target model (APEX I-Quality) | ~22 GB |
| SGLang runtime overhead | ~4 GB |
| Draft model (training) | ~2 GB |
| **Total** | **~28 GB of 128 GB** ✅ |

Training time estimate: H100 = 30 min (HathoraResearch). DGX Spark ≈ 4–8× slower → **2–4 hours**.

### Output

Training produces `model.safetensors` + `config.json` in output dir. Convert to GGUF:

```bash
python3 /home/user/dev/llama.cpp/convert_hf_to_gguf.py \
    /home/user/models/agents-a1-eagle3-draft/ \
    --outtype f16 \
    --outfile /home/user/models/agents-a1-eagle3-f16.gguf
```

## Acceptance Rate Expectations

| Scenario | Acceptance Rate | Effective Speedup |
|----------|:--------------:|:-----------------:|
| Custom draft (trained on Agents-A1) | 70–85% | **2.5–4×** |
| Vanilla Qwen3.5 draft on Agents-A1 | 30–50% | **1.2–1.8×** |
| Cross-architecture draft | <20% | **<1.2×** (not worth it) |

Acceptance rate is measured as: `accepted_tokens / drafted_tokens`. Higher = more speedup.

## Three-Level Plan

| # | Action | Time | Risk | Speedup |
|---|--------|------|------|---------|
| **1. Quick test** | Download `jiapingW` draft, convert, test with Agents-A1 | 30 min | Low (no training) | 1.2–1.8× |
| **2. Full training** | Generate 5K on-policy samples, train via SpecForge | 4–8 hours | Medium (data quality) | 2.5–4× |
| **3. Production** | Integrate into `start-llama.sh`, port 8104, watchdog | +1 hour | Low | 2.5–4× |

**Recommendation:** start with level 1. If acceptance >50%, use as-is. Otherwise, level 2.

## Pitfalls

- **Draft is target-specific.** A draft trained on Qwen3.5-35B-A3B will NOT work well on Agents-A1, Nex, or SuperQwen — different weights = different hidden states = low acceptance.
- **On-policy data is mandatory.** Training on generic ShareGPT produces a draft that predicts generic outputs, not Agents-A1 outputs.
- **`--spec-type draft-eagle3` must be explicit.** llama.cpp defaults to standard draft model if the spec type flag is omitted — won't extract hidden states from target.
- **`--reasoning off` for Agents-A1.** Without this, thinking tokens consume the draft budget.
- **Don't overtrain.** 5 epochs is plenty. More epochs → overfitting to training distribution → worse generalization on real prompts.
- **KV cache quantization still requires `--flash-attn on`** — same rule as standard llama-server.
- **Draft in BF16 is fine.** Quantizing the draft (Q8_0/Q4_K_M) may reduce acceptance rate; the draft is only 400 MB — not worth quantizing.
- **EAGLE-3 ≠ MTP.** Qwen3.6 has native MTP (Multi-Token Prediction) — this is a DIFFERENT speculative decoding method built into the model. EAGLE-3 is an external draft. Don't confuse them. For Qwen3.5-based models (like Agents-A1), MTP may not be available — EAGLE-3 is the right approach.
- **`convert_hf_to_gguf.py` must be from b9606+.** Older versions don't recognize `LlamaForCausalLMEagle3` architecture.
- **SGLang on DGX Spark may need `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1`** — same env var as llama.cpp.

## References

- Paper: [EAGLE-3: Scaling up Inference Acceleration of Large Language Models](https://arxiv.org/abs/2503.01840) (NeurIPS 2025)
- SpecForge: [github.com/sgl-project/SpecForge](https://github.com/sgl-project/SpecForge)
- SpecForge paper: [arXiv 2603.18567](https://arxiv.org/abs/2603.18567)
- llama.cpp EAGLE-3 PR: [#18039](https://github.com/ggml-org/llama.cpp/pull/18039)
- llama.cpp EAGLE-3 discussion: [#15902](https://github.com/ggml-org/llama.cpp/discussions/15902)
- Original EAGLE repo: [SafeAILab/EAGLE](https://github.com/SafeAILab/EAGLE)
- EAGLE-Qwen3 fork: [HuYunhai-Alex/EAGLE-Qwen3](https://github.com/HuYunhai-Alex/EAGLE-Qwen3)
- Tess-4-EAGLE3 training recipe: [migtissera/Tess-4-27B-EAGLE3](https://huggingface.co/migtissera/Tess-4-27B-EAGLE3)
- Qwen3.5 MoE draft example: [HathoraResearch/qwen3_30b_moe_eagle3-ultra-1k-sample](https://huggingface.co/HathoraResearch/qwen3_30b_moe_eagle3-ultra-1k-sample)
