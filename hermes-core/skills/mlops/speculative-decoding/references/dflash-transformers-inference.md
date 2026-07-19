# DFlash Transformers-Native Inference

Run DFlash speculative decoding directly via `dflash_generate()` — no vLLM/SGLang needed.
Verified: Jul 14 2026 on GB10 (DGX Spark), transformers 5.13.1, torch 2.11.0+cu130.

## When to Use This Path

- Quick local benchmarking or interactive chat with DFlash
- vLLM/SGLang unavailable or unwanted for single-user inference
- DGX Spark / single GPU testing

For production serving, prefer vLLM 0.25.0+ (native DFlash) or SGLang.

## Environment

```bash
# Use the vllm venv — it has transformers + torch + CUDA already
/home/user/vllm_venv/bin/python  # transformers 5.13.1, torch 2.11.0+cu130
```

## Model Inventory (Local Paths)

| Target Model | Class | Draft Model | VRAM Target |
|---|---|---|---|
| `/home/user/models/Qwen3.6-27B` | `Qwen3_5ForConditionalGeneration` | `Qwen3.6-27B-DFlash` | ~55 GB |
| `/home/user/models/Qwen3.6-35B-A3B` | `Qwen3_5MoeForConditionalGeneration` | `Qwen3.6-35B-A3B-DFlash` | ~70 GB |

Dense: `from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration`
MoE: `from transformers.models.qwen3_5_moe.modeling_qwen3_5_moe import Qwen3_5MoeForConditionalGeneration`

## Loading Sequence

```python
import importlib.util, torch
from transformers import AutoTokenizer, AutoModel, AutoConfig

TARGET = "/home/user/models/Qwen3.6-27B"  # or Qwen3.6-35B-A3B
DRAFT  = "/home/user/models/Qwen3.6-27B-DFlash"  # or Qwen3.6-35B-A3B-DFlash
DEV    = "cuda:0"

# 1. Tokenizer
tok = AutoTokenizer.from_pretrained(TARGET)

# 2. Target model — use dtype= NOT torch_dtype= (deprecated in v5)
#    Use .to(DEV) NOT device_map= (requires accelerate package)
target = Qwen3_5ForConditionalGeneration.from_pretrained(TARGET, dtype=torch.bfloat16).to(DEV)
target.eval()

# 3. CRITICAL: alias embed_tokens (dflash.py accesses target.model.embed_tokens,
#    but Qwen3_5/Qwen3_5Moe nests it under target.model.language_model.embed_tokens)
target.model.embed_tokens = target.model.language_model.embed_tokens

# 4. Draft model — 35B needs config fix for block_size location
draft_cfg = AutoConfig.from_pretrained(DRAFT, trust_remote_code=True)
if not hasattr(draft_cfg, "block_size") and hasattr(draft_cfg, "dflash_config"):
    draft_cfg.block_size = draft_cfg.dflash_config.get("block_size", 16)
draft = AutoModel.from_pretrained(
    DRAFT, config=draft_cfg, dtype=torch.bfloat16, trust_remote_code=True
).to(DEV)
draft.eval()

# 5. Load dflash.py from the model directory (NOT a pip package!)
spec = importlib.util.spec_from_file_location("dflash_mod", DRAFT + "/dflash.py")
dflash_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dflash_mod)
```

## Tokenizing (CRITICAL: transformers v5 BatchEncoding)

`apply_chat_template(return_tensors="pt")` returns a `BatchEncoding` object in
transformers v5. This is NOT a `dict` subclass — `isinstance(r, dict)` is `False`.
It has `.to()` (moves tensors) but `.shape` raises `KeyError: 'shape'`.

```python
messages = [{"role": "user", "content": "Hello!"}]
try:
    r = tok.apply_chat_template(messages, return_tensors="pt",
                                add_generation_prompt=True, enable_thinking=False)
except TypeError:
    r = tok.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True)

# Robust extraction — handles Tensor, dict, BatchEncoding, list
if isinstance(r, torch.Tensor):
    input_ids = r
elif isinstance(r, dict):
    input_ids = r["input_ids"]
else:
    input_ids = getattr(r, "input_ids", r)
if not isinstance(input_ids, torch.Tensor):
    input_ids = torch.tensor(input_ids, dtype=torch.long)
input_ids = input_ids.to(DEV)
if input_ids.dim() == 1:
    input_ids = input_ids.unsqueeze(0)
```

## Generating with Stats

```python
# Stop tokens
stops = list(set(
    [tok.encode(t, add_special_tokens=False)[-1]
     for t in ["<|im_end|>", "<|endoftext|>"]
     if tok.encode(t, add_special_tokens=False)]
    + ([tok.eos_token_id] if tok.eos_token_id else [])
))

# Generate
with torch.inference_mode():
    stats = dflash_mod.dflash_generate(
        model=draft, target=target, input_ids=input_ids,
        max_new_tokens=512, stop_token_ids=stops,
        temperature=0.0, return_stats=True,
    )

# Stats: num_output_tokens, time_to_first_token, time_per_output_token, acceptance_lengths
text = tok.decode(stats.output_ids[0, input_ids.shape[1]:], skip_special_tokens=True)
```

## dflash_generate() API

```python
dflash_generate(
    model: DFlashDraftModel,    # the draft model
    target: nn.Module,          # the target model
    input_ids: torch.LongTensor,  # [1, seq_len]
    max_new_tokens: int,
    stop_token_ids: list[int],
    temperature: float,         # 0.0 = greedy
    block_size: int = None,     # defaults to model.block_size (16)
    mask_token_id: int = None,  # defaults to model.mask_token_id
    return_stats: bool = False, # return SimpleNamespace with stats
)
```

## Benchmark Results (Jul 14 2026, GB10)

### Qwen3.6-27B (dense) + DFlash

| Metric | Value |
|---|---|
| Decode throughput | 23.5 tok/s |
| TTFT | 1.1s |
| Avg acceptance | 13.4 / 16 (84%) |
| VRAM total | ~58 GB (55 target + 3 draft) |
| Block size | 16 |
| Draft layers | 5 |

### Qwen3.6-35B-A3B (MoE) + DFlash

Model loads successfully (70.2 GB target + 0.8 GB draft = ~71 GB). Generation pending.
Uses `Qwen3_5MoeForConditionalGeneration` class. Block size 16, 6 draft layers.

## dflash.py Version Differences (27B vs 35B)

The 27B and 35B-A3B DFlash models ship DIFFERENT `dflash.py` files:

| Issue | 27B-DFlash | 35B-A3B-DFlash |
|---|---|---|
| `block_size` in config | Top-level `config.block_size` | Nested in `dflash_config.block_size` |
| `DynamicCache` init | `DynamicCache(config=_target_cfg)` ✅ | Bare `DynamicCache()` ❌ |

**27B-DFlash** (newer code) has the fixes needed for linear-attention targets:
```python
# 27B version (correct)
_target_cfg = getattr(target, "config", None)
if _target_cfg is not None and hasattr(_target_cfg, "text_config"):
    _target_cfg = _target_cfg.text_config
past_key_values_target = DynamicCache(config=_target_cfg)
```

**35B-A3B-DFlash** (older code) is missing this:
```python
# 35B version (broken for linear-attention)
past_key_values_target = DynamicCache()  # crashes on Qwen3_5 linear layers
```

**FIX for 35B**: Patch the `dflash.py` in the model directory directly — copy the
config-aware DynamicCache initialization from 27B's dflash.py. Then clear the HF
remote-code cache: `rm -rf ~/.cache/huggingface/modules/transformers_modules/*DFlash*`

## HF Remote-Code Cache (Gotcha)

`trust_remote_code=True` caches `dflash.py` in
`~/.cache/huggingface/modules/transformers_modules/<sanitized_name>/`.
If you patch the model directory's `dflash.py`, the CACHED copy is still used.

**Always clear after patching:**
```bash
rm -rf ~/.cache/huggingface/modules/transformers_modules/*DFlash*
```

## vLLM Serving (Native in 0.25.0+)

vLLM 0.25.0 has DFlash built in — no custom build or PR needed.

```bash
vllm serve /home/user/models/Qwen3.6-27B \
  --served-model-name "qwen3.6-27b-dflash" \
  --speculative-config '{"method":"dflash","model":"/home/user/models/Qwen3.6-27B-DFlash","num_speculative_tokens":15}' \
  --attention-backend flash_attn \
  --max-num-batched-tokens 32768 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 32768 \
  --trust-remote-code \
  --dtype bfloat16
```

## SGLang Serving (Production, Fastest)

```bash
export SGLANG_ENABLE_OVERLAP_PLAN_STREAM=1

python -m sglang.launch_server \
  --model-path /home/user/models/Qwen3.6-35B-A3B \
  --trust-remote-code \
  --speculative-algorithm DFLASH \
  --speculative-draft-model-path /home/user/models/Qwen3.6-35B-A3B-DFlash \
  --speculative-dflash-block-size 8 \
  --attention-backend trtllm_mha \
  --linear-attn-prefill-backend flashinfer \
  --linear-attn-decode-backend flashinfer \
  --mamba-scheduler-strategy extra_buffer \
  --tp-size 1 --max-running-requests 32 \
  --mem-fraction-static 0.8 \
  --port 30000
```

Block size 8 = higher concurrency. Block size 16 = max single-user throughput.
