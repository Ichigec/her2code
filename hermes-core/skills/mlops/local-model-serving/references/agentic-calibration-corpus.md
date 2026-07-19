# Agentic Calibration Corpus for MoE Imatrix

How to build a domain-specific calibration corpus for APEX I-variant quantization of agentic models (AgentWorld, tool-calling models). Based on the July 2026 SuperQwen session.

## Why Agentic Corpus?

APEX I-variants use "diverse calibration (chat, code, reasoning, tool-calling — no Wikipedia)". Standard calibration corpora (eaddario/imatrix-calibration) provide code+tools+math but lack function calling traces and multi-turn chat. For models like SuperQwen-AgentWorld that are specifically trained for tool use, the calibration corpus should include FC examples in the model's native chat format.

## Corpus Composition (v3, validated)

| Domain | Share | ~MB | Source |
|--------|:-----:|:---:|--------|
| Function calling | 42% | 8 | Hermes FC (4MB) + Glaive FC (4MB) |
| Chat | 16% | 3 | UltraChat 200k |
| Code | 21% | 4 | eaddario code_medium.parquet |
| Tools | 11% | 2 | eaddario tools_medium.parquet |
| Math/reasoning | 11% | 2 | eaddario combined_math_code_medium.parquet |

Total: ~19 MB, ~5M tokens. imatrix uses 256K tokens (5.2% of corpus) via `--chunks 125 -c 2048`.

## Dataset Sources

| Dataset | HF Repo | Gated? | Format | Size |
|---------|---------|:------:|--------|------|
| Hermes Function Calling v1 | `NousResearch/hermes-function-calling-v1` | No | conversations[] + tools[] | 60k samples |
| Glaive Function Calling | `glaiveai/glaive-function-calling` | No | plain text "SYSTEM:... USER:... ASSISTANT:..." | 52k samples |
| UltraChat 200k | `HuggingFaceH4/ultrachat_200k` | No | messages[] (role/content) | 200k samples |
| xLAM Function Calling 60k | `Salesforce/xlam-function-calling-60k` | **YES** (needs HF token) | tools[] + query + answers[] | 60k samples |
| eaddario calibration | `eaddario/imatrix-calibration` | No | parquet (single-row, giant text) | code+tools+math |

## Model-Specific Chat Format

Calibration text must match the model's inference-time token patterns. For Qwen3.5/3.6 MoE:

```
<|im_start|>system
# Tools

You have access to the following functions:

<tools>
{...tool JSON...}
</tools><|im_end|>
<|im_start|>user
{user message}<|im_end|>
<|im_start|>assistant
{assistant response}<|im_end|>
```

Extract the chat template from the model's HF repo:
```bash
cat /path/to/model/chat_template.jinja  # Qwen uses separate file
# Or from tokenizer_config.json: "chat_template" field
```

## Download + Format Script

```python
import json, os, random, re
from datasets import load_dataset
import pandas as pd
random.seed(42)

OUT_DIR = "/home/user/models/imatrix-cal-v3"
os.makedirs(OUT_DIR, exist_ok=True)

# === 1. Hermes Function Calling ===
def format_hermes(ex):
    conversations = ex.get("conversations", [])
    tools_str = ex.get("tools", "[]")
    tools = json.loads(tools_str) if isinstance(tools_str, str) else tools_str
    parts = []
    if tools:
        parts.append("<|im_start|>system\n# Tools\n\n<tools>")
        for t in tools:
            parts.append(json.dumps(t, indent=2))  # indent=2, NOT character-by-character
        parts.append("</tools><|im_end|>")
    for msg in conversations:
        role = msg.get("from", "")
        content = msg.get("value", "")
        if role in ("human", "user"): role = "user"
        elif role in ("gpt", "assistant"): role = "assistant"
        elif role == "system":
            if tools: continue  # already added tools as system
            role = "system"
        elif role in ("tool", "function"): role = "user"
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    return "\n".join(parts)

ds = load_dataset("NousResearch/hermes-function-calling-v1", split="train", streaming=True)
with open(f"{OUT_DIR}/hermes_fc.txt", "w") as f:
    written = 0
    for ex in ds:
        text = format_hermes(ex)
        if len(text.strip()) > 100:
            f.write(text + "\n\n")
            written += len(text.encode("utf-8"))
            if written >= 4*1024*1024: break

# === 2. Glaive Function Calling (plain text parsing) ===
def parse_glaive(sample):
    parts = re.split(r'(SYSTEM:|USER:|ASSISTANT:|FUNCTION RESPONSE:|FUNCTION REQUEST:)', sample)
    text_parts, role, content = [], None, []
    for part in parts:
        part = part.strip()
        if part in ("SYSTEM:", "USER:", "ASSISTANT:", "FUNCTION RESPONSE:", "FUNCTION REQUEST:"):
            if role:
                text_parts.append(f"<|im_start|>{role}\n" + "\n".join(content) + "<|im_end|>")
            role = {"SYSTEM:":"system","USER:":"user","ASSISTANT:":"assistant",
                    "FUNCTION RESPONSE:":"user","FUNCTION REQUEST:":"assistant"}[part]
            content = []
        elif part and role:
            content.append(part)
    if role and content:
        text_parts.append(f"<|im_start|>{role}\n" + "\n".join(content) + "<|im_end|>")
    return "\n".join(text_parts)

ds = load_dataset("glaiveai/glaive-function-calling", split="train", streaming=True)
with open(f"{OUT_DIR}/glaive_fc.txt", "w") as f:
    written = 0
    for ex in ds:
        text = parse_glaive(ex.get("sample", ""))
        if len(text.strip()) > 100:
            f.write(text + "\n\n")
            written += len(text.encode("utf-8"))
            if written >= 4*1024*1024: break

# === 3. UltraChat ===
ds = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft", streaming=True)
with open(f"{OUT_DIR}/ultrachat.txt", "w") as f:
    written = 0
    for ex in ds:
        parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in ex.get("messages", [])]
        text = "\n".join(parts)
        if len(text.strip()) > 100:
            f.write(text + "\n\n")
            written += len(text.encode("utf-8"))
            if written >= 3*1024*1024: break

# === 4. Merge with balanced proportions ===
def collect_plain(path, target_mb):
    if not os.path.exists(path): return []
    chunks = [c.strip() for c in open(path).read().split("\n\n") if len(c.strip()) > 50]
    random.shuffle(chunks)
    result, written = [], 0
    for c in chunks:
        if written >= target_mb * 1024 * 1024: break
        result.append(c)
        written += len(c.encode("utf-8"))
    return result

def collect_parquet_chunked(path, target_mb):
    """eaddario parquets are single-row giant texts — must chunk"""
    if not os.path.exists(path): return []
    df = pd.read_parquet(path)
    col = "content" if "content" in df.columns else df.columns[0]
    text = str(df[col].iloc[0])
    lines = text.split("\n")
    chunks, current, size = [], [], 0
    for line in lines:
        current.append(line)
        size += len(line)
        if size >= 2000:
            chunks.append("\n".join(current).strip())
            current, size = [], 0
    if current: chunks.append("\n".join(current).strip())
    chunks = [c for c in chunks if len(c) > 50]
    random.shuffle(chunks)
    result, written = [], 0
    for c in chunks:
        if written >= target_mb * 1024 * 1024: break
        result.append(c)
        written += len(c.encode("utf-8"))
    return result

all_chunks = []
all_chunks += collect_plain(f"{OUT_DIR}/hermes_fc.txt", 4)
all_chunks += collect_plain(f"{OUT_DIR}/glaive_fc.txt", 4)
all_chunks += collect_plain(f"{OUT_DIR}/ultrachat.txt", 4)
all_chunks += collect_parquet_chunked("/home/user/models/imatrix-cal/code_medium.parquet", 4)
all_chunks += collect_parquet_chunked("/home/user/models/imatrix-cal/tools_medium.parquet", 2)
all_chunks += collect_parquet_chunked("/home/user/models/imatrix-cal/combined_math_code_medium.parquet", 2)
random.shuffle(all_chunks)

with open(f"{OUT_DIR}/calibration_v3.txt", "w") as f:
    for c in all_chunks:
        f.write(c + "\n\n")

total = os.path.getsize(f"{OUT_DIR}/calibration_v3.txt")
print(f"TOTAL: {total/1024/1024:.1f} MB, {len(all_chunks)} chunks")
```

## Pitfalls

1. **Hermes FC formatting bug**: if you iterate over a tools list character-by-character instead of using `json.dumps(tool, indent=2)`, each character ends up on its own line. The `tools` field in Hermes FC is a JSON string, not a list — parse it first with `json.loads()`.

2. **Glaive FC format**: uses plain text with `SYSTEM:`, `USER:`, `ASSISTANT:` markers. Must regex-split and reformat. The `sample` field is a single string, not structured messages.

3. **eaddario parquet files are single-row**: `code_medium.parquet` has 1 row with 37MB of text. `pd.read_parquet()` then iterating rows gives only 1 sample. Must extract the string and chunk it manually into ~2KB segments.

4. **xLAM is gated**: `Salesforce/xlam-function-calling-60k` requires HF authentication. If no `HF_TOKEN` env var or `~/.cache/huggingface/token` file, it fails silently. Use Hermes FC + Glaive FC instead (80k combined samples, ungated).

5. **`datasets` library not in system Python**: On Pavel's DGX Spark, `pip install --break-system-packages datasets pandas pyarrow` is needed (PEP 668). Or use the jupyterlab venv: `/home/user/jupyterlab/.venv/bin/python3`.

6. **Streaming downloads are slow**: `load_dataset(..., streaming=True)` downloads one sample at a time. For 4MB target (~3000 samples), expect 30-60 seconds per dataset. Use `streaming=True` to avoid downloading the full 200k-sample dataset.
