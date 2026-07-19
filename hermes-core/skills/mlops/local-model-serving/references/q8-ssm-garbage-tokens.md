# Q8_0 on SSM/DeltaNet Tensors = Garbage Tokens

> Verified July 3, 2026 on DGX Spark (GB10, 128 GB, CUDA 13.2, llama.cpp build 9247).

## The Problem

SuperQwen-AgentWorld-35B-A3B in Q8_0 quantization generates only token ID 14 (`/`) regardless of input prompt, temperature, or context size. The model loads without errors but is completely unusable.

## Root Cause: Q8_0 on SSM Tensors

The qwen35moe architecture uses a hybrid layout: **10 attention + 30 SSM/DeltaNet blocks** (40 total, verified from GGUF metadata). SSM (State Space Model) layers use recurrent computations where state passes from token to token — errors compound exponentially.

Q8_0 quantization (8-bit block quantization, 1 scale per 32 elements) creates systematic rounding errors on SSM weight matrices. Unlike attention layers (where each token is computed independently), SSM recurrence means the error accumulates across the entire sequence, quickly collapsing the output distribution to a single token.

## Tensor-Type Comparison (via `gguf` Python package)

```python
# pip install gguf --break-system-packages
import gguf
from collections import Counter

reader = gguf.GGUFReader(path)
ssm, attn, ffn, other = Counter(), Counter(), Counter(), Counter()
for t in reader.tensors:
    tname = str(t.tensor_type).split('.')[-1]
    if 'ssm_' in t.name: ssm[tname] += 1
    elif 'attn_' in t.name: attn[tname] += 1
    elif 'ffn_' in t.name: ffn[tname] += 1
    else: other[tname] += 1
```

Results across 5 SuperQwen GGUF files (733 tensors each):

| Model | SSM weights (90) | Attention | FFN | Result |
|-------|:---:|:---:|:---:|:---:|
| Q8_0 (BROKEN) | **Q8_0** | Q8_0 | Q8_0 | `////` garbage |
| Q4_K_M (works) | Q4_K | Q4_K + Q6_K | Q4_K + Q6_K | Coherent output |
| APEX I-Quality v1 (works) | Q6_K | Q6_K | Q8_0 + Q6_K + Q5_K + IQ4_XS | Coherent output |
| APEX I-Quality v3 (works) | Q6_K | Q6_K | Q8_0 + Q6_K + Q5_K + IQ4_XS | Coherent output |

**Key insight:** 120 small SSM tensors (ssm_a, ssm_dt.bias, ssm_norm.weight) remain F32 in ALL quants — only the 90 weight-bearing SSM tensors (ssm_conv1d, ssm_beta, ssm_alpha, ssm_out) differ.

The difference is the quant type on those 90 SSM weights: Q8_0 breaks, Q4_K and Q6_K work.

## Why Q8_0 Breaks but Q4_K Doesn't

- **Q8_0**: Single scale factor per 32-element block. Systematic bias in rounding affects the recurrent state update identically each step → exponential error growth.
- **Q4_K / Q6_K**: Super-block structure with sub-block scales. Different rounding pattern that (perhaps accidentally) preserves the critical bits in SSM weight matrices better.
- **Hypothesis**: SSM conv1d and gate matrices have specific value distributions where Q8_0's symmetric block scaling introduces a consistent bias that Q4_K's more granular scaling avoids.

## How to Detect

### Quick check (after model load)

```bash
# Send a simple prompt and check for garbage
curl -s http://127.0.0.1:PORT/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"test","prompt":"What is 2+2?","max_tokens":16,"temperature":0}' \
  | python3 -c "
import sys, json
r = json.load(sys.stdin)
t = r['choices'][0]['text'].strip()
if set(t) <= set('/'):
    print('GARBAGE: model produces only / tokens')
elif len(t) == 0:
    print('EMPTY: check chat template / reasoning_content')
else:
    print('OK:', repr(t[:80]))
"
```

### Server log diagnosis

In `--verbose` mode, llama-server logs each decoded token:
```
D slot process_toke: id 1 | task 164 | n_decoded = 15, next token: 14 '/'
```
Token ID 14 repeating = the `/` garbage pattern. The model has collapsed to a single-token loop.

## Testing Methodology (Session 2026-07-03)

Each model tested individually (kill all llama-server, load one, test, kill, repeat):

| # | Model | Quant | Size | Raw Completion | Chat Content | Verdict |
|---|-------|-------|:---:|---|---|---|
| 1 | Qwen3.6-35B Heretic | APEX I-Quality | 22 GB | `2+2 equals 4...` | Works (reasoning in reasoning_content) | OK |
| 2 | Nex-N2-mini | APEX-Quality | 33 GB | `2+2 equals 4...` | `Hello!`, `def reverse(s): return s[::-1]` | OK |
| 3 | SuperQwen APEX v1 | APEX I-Quality | 22 GB | `<think>Thinking Process...` | `Final answer: Hello!` | OK |
| 4 | SuperQwen APEX v3 | APEX I-Quality | 22 GB | `<think>Thinking Process...` | `Final answer: Hello!` | OK |
| 5 | SuperQwen Q4_K_M | Q4_K_M | 20 GB | `<think>Thinking Process...` | `Final answer: Hello!` | OK |
| 6 | SuperQwen Q8_0 | Q8_0 | 35 GB | `////` | `////` | BROKEN |

**Note:** Qwen3.6 APEX initially produced `////` when 4 models were loaded simultaneously (memory pressure). Retested alone — works correctly. This confirms memory pressure is a separate but related cause of garbage tokens.

## Implications

1. **Never use Q8_0 on qwen35moe models.** Use APEX I-Quality (22 GB, Q6_K on SSM) or Q4_K_M (20 GB).
2. **Never use Q8_0 as a KL-divergence reference** for qwen35moe — the reference itself is broken. Use Q4_K_M instead.
3. **APEX is not "junk" — it's the correct choice** for this architecture. The Q6_K on SSM tensors is what makes APEX work where Q8_0 fails.
4. **Memory pressure can mimic the same symptom.** Even working models produce `////` when 4+ models compete for unified memory. Test each model alone first.
5. **Chat template matters.** Without `--jinja`, chat completions may return empty `content` with text in `reasoning_content`. Always test both `/v1/completions` (raw) and `/v1/chat/completions` (templated).
