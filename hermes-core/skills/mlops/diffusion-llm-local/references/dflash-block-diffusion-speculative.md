# DFlash: Block Diffusion for Flash Speculative Decoding

DFlash (ICML 2026, Z-Lab) uses a lightweight block-diffusion model as a **draft model** for
speculative decoding. The target AR LLM stays completely unchanged — DFlash only adds a small
diffusion-based drafter that generates 16 tokens in parallel per forward pass, then the AR target
verifies them. This achieves **4.5–6.1× lossless speedup** — 2.5× faster than EAGLE-3.

- **Paper**: arXiv:2602.06036 (Feb 2026, ICML 2026)
- **GitHub**: github.com/z-lab/dflash (open source)
- **HuggingFace**: huggingface.co/collections/z-lab/dflash

## How it works

```
Traditional speculative decoding (EAGLE-3):
  Draft (AR, 1 layer) → generates k tokens SEQUENTIALLY → Target verifies

DFlash:
  Draft (diffusion, 5 layers) → generates k=16 tokens PARALLEL in one forward pass
  → Target (Gemma 31B / Qwen3 / etc.) verifies all 16 in one AR forward
  → Accept longest matching prefix + 1 bonus token
```

Key innovation: the diffusion drafter is conditioned on **hidden features extracted from the target
model** (5 layers uniformly selected between layer 2 and 3rd-from-last). This KV injection enables
high acceptance rates despite the drafter being tiny (~5 layers, ~200-400M params).

## Draft model architecture

| Component | Value |
|:----------|:------|
| Layers | 5 (8 for code models) |
| Block size | 16 tokens (10 for LLaMA 3.1) |
| Target hidden features | 5 layers, uniformly between layer 2 and 3rd-from-last |
| Trainable params | Only draft Transformer layers (embeddings frozen from target) |
| Training data | ~800K samples (Nemotron Post-Training V2 + CodeAlpaca), responses from target model |

## Benchmark results (Qwen3-8B, Transformers backend, H200 GPU)

### Greedy decoding (temp=0)

| Method | GSM8K | MATH-500 | AIME25 | HumanEval | MBPP | LCB | MT-Bench | **Avg** |
|:-------|:------|:---------|:-------|:----------|:-----|:----|:---------|:--------|
| EAGLE-3 (tree=16) | 1.94× | 1.81× | 1.79× | 1.89× | 1.69× | 1.57× | 1.76× | **1.78×** |
| EAGLE-3 (tree=60) | 2.23× | 2.05× | 2.05× | 2.17× | 1.93× | 1.81× | 2.02× | **1.89×** |
| **DFlash (block=16)** | **5.15×** | **6.08×** | **5.62×** | **5.14×** | **4.65×** | **5.51×** | **4.86×** | **4.86×** |

### Sampling (temp=1)

| Method | GSM8K | MATH-500 | AIME25 | HumanEval | MBPP | LCB | MT-Bench | **Avg** |
|:-------|:------|:---------|:-------|:----------|:-----|:----|:---------|:--------|
| **DFlash (block=16)** | **4.67×** | **4.84×** | **3.57×** | **4.32×** | **4.04×** | **4.93×** | **4.03×** | **4.03×** |

### Acceptance length (τ)

DFlash: **6.5–7.9** tokens vs EAGLE-3: **3.0–3.5** tokens — nearly 2× longer acceptance.

### Reasoning models (thinking mode enabled)

| Model | Task | Concurrency=1 | Concurrency=4 | Concurrency=8 | Concurrency=16 | Concurrency=32 | τ |
|:------|:-----|:--------------|:--------------|:--------------|:---------------|:---------------|:--|
| Qwen3-4B | Math500 | 4.8× | 4.3× | 4.1× | 3.5× | 2.9× | 8.01 |
| Qwen3-4B | HumanEval | 4.0× | 3.6× | 3.2× | 2.7× | 2.2× | 6.63 |
| Qwen3-8B | Math500 | 4.2× | 3.6× | 3.6× | 3.0× | 2.4× | 6.50 |
| Qwen3-8B | HumanEval | 4.2× | 3.6× | 3.6× | 3.0× | 2.4× | 6.50 |

Speedup decreases with concurrency (more batches = less benefit), but remains >2× even at c=32.

### SGLang production serving

DFlash on SGLang with FA4 backend: stable **4.5× at concurrency=1**, maintains advantage to c=32.

## Speedup estimates for Gemma 4 31B

Ready-made draft model: `z-lab/gemma-4-31B-it-DFlash` (HuggingFace).

| Metric | Estimate | Rationale |
|:-------|:---------|:----------|
| Speedup (greedy) | **4.5–6.0×** | Qwen3-8B: 4.86× avg; 31B → better acceptance (larger models predict future better, per Nemotron scaling: TPF grows 3B→4.36×, 8B→4.67×, 14B→5.96×) |
| Speedup (sampling) | **3.5–4.5×** | Qwen3-8B temp=1: 4.03×; slightly lower for 31B due to higher draft cost |
| Acceptance length (τ) | **6.5–8.0** | Qwen3-8B: ~6.5; larger target → better drafts |
| vs EAGLE-3 | **2.0–2.5× faster** | Confirmed across all benchmarks |
| vs MTP (Gemma native) | **1.5–2.0× faster** | MTP gives 2-3×, DFlash gives 4-6× |
| Quality loss | **0 (lossless)** | Speculative decoding preserves output distribution |

### DGX Spark (128GB, Blackwell) estimates

| Config | Baseline (AR) | DFlash | Real speed |
|:-------|:-------------|:-------|:-----------|
| Gemma 31B BF16, batch=1 | ~35-40 tok/s | ~160-240 tok/s | 4.5-6× |
| Gemma 31B Q4, batch=1 | ~60-80 tok/s | ~270-400 tok/s | 4.5-5× |
| Gemma 31B BF16, batch=4 | ~120 tok/s total | ~400-500 tok/s | 3.5× at concurrency |

## Deployment

### vLLM (recommended for Gemma 4)

Gemma 4 requires a special Docker image with Gemma4 DFlash support:

```bash
docker run --rm -it --gpus all --ipc=host --shm-size=16g -p 8000:8000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  ghcr.io/z-lab/vllm-openai:gemma4-dflash-cu130 \
  google/gemma-4-31B-it \
  --host 0.0.0.0 --port 8000 \
  --speculative-config '{"method": "dflash", "model": "z-lab/gemma-4-31B-it-DFlash", "num_speculative_tokens": 15, "attention_backend": "flash_attn"}' \
  --attention-backend triton_attn \
  --max-num-batched-tokens 32768 \
  --trust-remote-code
```

Non-Gemma4 models (standard vLLM v0.20.1+):

```bash
vllm serve Qwen/Qwen3.5-27B \
  --speculative-config '{"method": "dflash", "model": "z-lab/Qwen3.5-27B-DFlash", "num_speculative_tokens": 15}' \
  --attention-backend flash_attn \
  --max-num-batched-tokens 32768
```

### SGLang

```bash
python -m sglang.launch_server \
    --model-path Qwen/Qwen3.5-35B-A3B \
    --speculative-algorithm DFLASH \
    --speculative-draft-model-path z-lab/Qwen3.5-35B-A3B-DFlash \
    --speculative-num-draft-tokens 16 \
    --tp-size 1 \
    --attention-backend trtllm_mha \
    --speculative-draft-attention-backend fa4 \
    --mem-fraction-static 0.75 \
    --trust-remote-code
```

### Transformers backend (fallback when vLLM unavailable)

Works with any model that transformers supports. Slower serving than vLLM/SGLang but
simplest setup — just `pip install dflash[transformers]`.

```python
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer
import time

target = AutoModelForCausalLM.from_pretrained('/path/to/Qwen3.6-27B', dtype='bfloat16', device_map='cuda:0').eval()
draft = AutoModel.from_pretrained('/path/to/Qwen3.6-27B-DFlash', trust_remote_code=True, dtype='bfloat16', device_map='cuda:0').eval()
tokenizer = AutoTokenizer.from_pretrained('/path/to/Qwen3.6-27B')

messages = [{'role':'user','content':'Write a Python binary search function.'}]

# ⚠️ transformers v5: apply_chat_template returns dict, not tensor!
inputs = tokenizer.apply_chat_template(messages, return_tensors='pt', add_generation_prompt=True, enable_thinking=False)
input_ids = inputs['input_ids'].to('cuda:0') if isinstance(inputs, dict) else inputs.to('cuda:0')

t0 = time.time()
output = draft.spec_generate(input_ids=input_ids, max_new_tokens=512, temperature=0.0, target=target, stop_token_ids=[tokenizer.eos_token_id])
t1 = time.time()

toks = output.shape[1] - input_ids.shape[1]
print(f'{toks} tokens in {t1-t0:.1f}s = {toks/(t1-t0):.1f} tok/s')
```

**Known issues:**
- `flash-linear-attention` warning is benign (falls back to torch implementation)
- Model loading is sequential (~4 min for 27B BF16 on GB10) — no parallel weight loading
- Only Qwen3 and LLaMA-3.1 families support the transformers backend
- DFlash draft model config includes `dflash.py` (custom code via `trust_remote_code=True`)

### MLX (Apple Silicon)

```python
from dflash.model_mlx import load, load_draft, stream_generate
model, tokenizer = load("Qwen/Qwen3.5-4B")
draft = load_draft("z-lab/Qwen3.5-4B-DFlash")
# stream_generate(model, draft, tokenizer, prompt, block_size=16, ...)
```

## Supported target models (ready-made draft models)

| Target | Draft model |
|:-------|:------------|
| gemma-4-31B-it | z-lab/gemma-4-31B-it-DFlash |
| gemma-4-26B-A4B-it | z-lab/gemma-4-26B-A4B-it-DFlash |
| Qwen3.5-{4B,9B,27B,35B-A3B,122B-A10B} | z-lab/Qwen3.5-*-DFlash |
| Qwen3.6-{27B,35B-A3B} | z-lab/Qwen3.6-*-DFlash |
| Qwen3-{4B,8B} (non-thinking) | z-lab/Qwen3-*-DFlash-b16 |
| Qwen3-Coder-{Next,30B-A3B} | z-lab/Qwen3-Coder-*-DFlash |
| LLaMA-3.1-8B-Instruct | z-lab/LLaMA3.1-8B-Instruct-DFlash-UltraChat |
| gpt-oss-{20b,120b} | z-lab/gpt-oss-*-DFlash |
| Kimi-K2.{5,6} | z-lab/Kimi-K2.*-DFlash |
| MiniMax-M2.{5,7} | z-lab/MiniMax-M2.*-DFlash |

Training recipe is open-source — can train custom DFlash draft for any LLM.

## Comparison summary

| Method | Speedup | Lossless | Retrain target? | Draft size | Gemma 31B? |
|:-------|:--------|:---------|:----------------|:-----------|:-----------|
| **DFlash** | **4.5-6×** | ✅ | ❌ | ~5 layers | ✅ Ready |
| EAGLE-3 | 1.8-2.2× | ✅ | ❌ | 1 layer | ⚠️ Need draft |
| MTP (Gemma native) | 2-3× | ✅ | ❌ | built-in | ✅ Native |
| Nemotron self-spec | 1.75-1.98× | ~0.1% drop | ❌ | LoRA ~36M | ❌ Nemotron only |
| S2D2 | 4.7× | ✅ | ❌ | Same model | ⚠️ Need adapt |
| Fast-dLLM v2 | 2.5× | <2% loss | ❌ | Training-free | ⚠️ Need adapt |
