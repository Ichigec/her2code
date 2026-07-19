# Model Comparison Technique

Reliable data-gathering pipeline for deep model comparisons. Use when comparing 2+ models for local deployment.

## Pipeline

```
1. HF API        → metadata (params, arch, tags, downloads)
2. README raw    → benchmark tables, usage instructions
3. arxiv paper   → peer-reviewed benchmarks, methodology
4. pdftotext     → extract structured data from PDF
5. grep/sed      → isolate specific benchmark numbers
6. web_search    → community benchmarks, reviews, GGUF availability
```

## Step 1: HF API — Metadata

```bash
curl -sL -H 'User-Agent: Mozilla/5.0' \
  'https://huggingface.co/api/models/<org>/<model>' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for k in ['modelId','author','pipeline_tag','tags','safetensors','config']:
    print(f'{k}: {data.get(k)}')
"
```

Key fields:
- `config.architectures` — model architecture
- `config.model_type` — model family
- `safetensors.parameters` — total parameters
- `cardData.base_model` — upstream lineage
- `tags` — abliterated, uncensored, MoE, etc.

## Step 2: README Raw — Benchmarks

```bash
curl -sL -H 'User-Agent: Mozilla/5.0' \
  'https://huggingface.co/<org>/<model>/raw/main/README.md' | head -300
```

Look for:
- Benchmark tables (SWE-Bench, GPQA, BrowseComp, etc.)
- Usage instructions (sglang flags, sampling params)
- Architecture details (layers, experts, attention type)

## Step 3: arxiv Paper — Peer-Reviewed Data

```bash
# Find paper
web_search("model_name arxiv paper 2025 2026")

# Get abstract
curl -sL -H 'User-Agent: Mozilla/5.0' \
  'https://arxiv.org/abs/<id>' \
  | python3 -c "import sys,re; html=sys.stdin.read(); ..."

# Get full PDF → text
curl -sL -o /tmp/paper.pdf 'https://arxiv.org/pdf/<id>'
pdftotext /tmp/paper.pdf /tmp/paper.txt
```

## Step 4: pdftotext → grep — Extract Numbers

```bash
# Find benchmark tables
grep -n 'Table\|SWE-Bench\|GPQA\|Terminal-Bench' /tmp/paper.txt

# Extract specific section
sed -n '<start>,<end>p' /tmp/paper.txt
```

## Step 5: web_search — Community Data

```bash
# GGUF availability
web_search("model_name GGUF ollama llama.cpp quantized")

# Community benchmarks
web_search("model_name local deployment benchmark tok/s review 2026")

# Known issues
web_search("model_name bug issue pitfall local inference")
```

## Key Data Points to Collect

For each model in a comparison, collect:
- Architecture (MoE/dense, layers, experts, attention type)
- Total parameters vs active parameters
- Context length (native)
- Key benchmarks (SWE-Bench, GPQA, Terminal-Bench, AgentWorldBench)
- GGUF availability (bartowski, unsloth, mradermacher)
- Inference requirements (VRAM, CUDA version, special forks)
- Quantization options (Q8_0 size, Q4_K_M size)

## Example: Three-Model Comparison Output

| Model | Arch | Total/Active | SWE-Bench | GPQA | Term-Bench | Q8_0 size | Status |
|-------|------|-------------|-----------|------|------------|-----------|--------|
| Nex-N2-mini | Qwen3.5-MoE | 35B/3B | 74.4 | 82.6 | 60.7 | 35 GB | ✅ GGUF |
| Qwen3.6-35B | Qwen3.5-MoE | 35B/3B | 73.4 | 86.0 | 51.5 | 35 GB | ✅ GGUF |
| AgentWorld | Qwen3.5-MoE | 35B/3B | ~67.9 | — | 39.6 | 35 GB | ✅ GGUF |

## Pitfalls

- `web_extract` with DuckDuckGo backend cannot extract page content — use `curl` + Python HTML-stripping instead
- arxiv HTML pages have JS-loaded content that doesn't extract well — use PDF + pdftotext for the most reliable data
- Some models (Huihui) don't publish independent benchmarks — rely on base model data + estimated abliteration loss
- GGUF availability ≠ quality — check the quantizer (bartowski/unsloth vs random uploader)
- MoE models: active parameter count is a better predictor of quantization sensitivity than total
