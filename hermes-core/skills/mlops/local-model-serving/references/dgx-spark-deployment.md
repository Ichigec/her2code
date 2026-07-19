# DGX Spark (GB10, 128 GB) — Full Deployment Architecture

Deploying 3 abliterated MoE models simultaneously via llama-swap matrix mode.
All three in memory (~81 GB), instant switching. Stock llama.cpp — no forks needed.

## Hardware

- **GPU:** NVIDIA GB10 Grace Blackwell (SM 12.1 / sm_121)
- **Memory:** 128 GB unified LPDDR5X (~95 GB available after system)
- **CPU:** 20 ARM cores (Grace)
- **CUDA:** 13.2
- **OS:** Linux (ARM64, SBSA)

## Inference Engine

**Standard llama.cpp works.** The ARM64 build at `/home/user/dev/llama.cpp/build/bin/llama-server`
(v9247) links against `libggml-cuda.so`, `libcublas.so.13`, `libcudart.so.13`. No DGX-specific fork needed.

```bash
# Verify CUDA support
ldd llama-server | grep -E "cuda|cublas"
# → libggml-cuda.so, libcublas.so.13, libcudart.so.13
```

If standard build doesn't work: `croll83/llama.cpp-dgx` fork with `-DCMAKE_CUDA_ARCHITECTURES="121"`.

## Model Proxy — llama-swap

Install to user-local (no sudo):

```bash
# Download specific release (use v<NUM> path, NOT releases/latest with version in filename)
curl -fsSL "https://github.com/mostlygeek/llama-swap/releases/download/v234/llama-swap_234_linux_arm64.tar.gz" \
  | tar xz -C /tmp
cp /tmp/llama-swap ~/.local/bin/llama-swap
chmod +x ~/.local/bin/llama-swap
llama-swap --version  # verify it's an ELF binary, not "Not Found" text
```

**PITFALL:** The URL `releases/latest/download/llama-swap_234_linux_arm64.tar.gz` mixes `latest` redirect with a hardcoded version number — this can 404 and produce a 9-byte "Not Found" text file instead of a binary. Always use `releases/download/v<NUM>/...` for specific versions, or `releases/latest/download/llama-swap_linux_arm64.tar.gz` (without version) for latest.

**PITFALL:** After install, verify with `file ~/.local/bin/llama-swap` — should show "ELF 64-bit LSB executable". If it says "ASCII text", the download failed silently and you have a "Not Found" text file.

## Recommended Models (all abliterated, DGX-tested)

| Role | Model | Quant | Size | Key Benchmarks |
|------|-------|-------|------|----------------|
| 🤖 Coding | Nex-N2-mini (huihui-ai abliterated) | APEX-Quality | ~33 GB | SWE-Bench 74.4, Terminal-Bench 60.7 |
| 🧠 Reasoning | Qwen3.6-35B (Heretic v1.2.0) | APEX I-Quality | ~21 GB | GPQA 86.0, HellaSwag 83.5% |
| 🔮 Simulation | SuperQwen-AgentWorld (Obliteratus+Supertune) | Q4_K_M | ~20 GB | HumanEval+ 75.0 (+59 vs orig) |

**Why APEX over Q8_0:** APEX is MoE-aware mixed-precision quantization by the LocalAI team.
Works with **stock llama.cpp — no patches needed**. Beats Q8_0 on HellaSwag (+0.5pp), MMLU (+0.2pp),
at 38% smaller size. See `references/apex-quantization-benchmarks.md`.

**Why abliterated:** Heretic v1.2.0 has lowest KL divergence (0.0015) with 88% fewer refusals.
See `references/abliterated-model-selection.md`.

## Configuration

**CRITICAL: llama-swap v234 uses `groups` + `swap: false` for simultaneous multi-model loading.**

The keys `unload: false` and top-level `matrix:` do NOT exist in llama-swap — they are silently ignored.
The correct mechanism is a `groups` block with `swap: false`, which prevents models from being evicted
when another in the group is loaded. Use `${PORT}` macro (assigned from `startPort`) instead of
hardcoded ports. Use `hooks.on_startup.preload` to load all models at startup.

**Also critical:** Always check `ss -tlnp` for existing services before assigning ports.
SearXNG Docker container uses 8081; other services may occupy 8080-8083.

```yaml
# llama-swap.yaml — corrected config for 3 simultaneous models
startPort: 8100
healthCheckTimeout: 300

models:
  nex:
    cmd: >
      /home/user/dev/llama.cpp/build/bin/llama-server
      -m /home/user/models/Huihui-Nex-N2-mini-abliterated-APEX-Quality.gguf
      --alias nex-n2-mini
      -ngl 99 -c 65536
      --cache-type-k q8_0 --cache-type-v q8_0
      --mlock
      --host 127.0.0.1 --port ${PORT}
    env:
      - "GGML_CUDA_ENABLE_UNIFIED_MEMORY=1"

  qwen:
    cmd: >
      /home/user/dev/llama.cpp/build/bin/llama-server
      -m /home/user/models/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-APEX-I-Quality.gguf
      --alias qwen3.6-35b
      -ngl 99 -c 65536
      --cache-type-k q8_0 --cache-type-v q8_0
      --mlock
      --host 127.0.0.1 --port ${PORT}
    env:
      - "GGML_CUDA_ENABLE_UNIFIED_MEMORY=1"

  world:
    cmd: >
      /home/user/dev/llama.cpp/build/bin/llama-server
      -m /home/user/models/SuperQwen-APEX-I-Quality-v3.gguf
      --alias agentworld
      -ngl 99 -c 32768
      --cache-type-k q8_0 --cache-type-v q8_0
      --mlock
      --host 127.0.0.1 --port ${PORT}
    env:
      - "GGML_CUDA_ENABLE_UNIFIED_MEMORY=1"

groups:
  all-models:
    members: [nex, qwen, world]
    swap: false          # ← THIS is what keeps models in memory (NOT "unload: false")

hooks:
  on_startup:
    preload: [nex, qwen, world]   # load all 3 at startup (5-10 min)
```

**Config syntax reference (llama-swap v229/v234):**

| Key | Level | Purpose |
|-----|-------|---------|
| `startPort` | top-level | Base port for `${PORT}` macro auto-assignment |
| `models.<name>.cmd` | model | Command with `${PORT}` macro (NOT hardcoded port) |
| `groups.<name>.members` | group | List of model names to keep co-resident |
| `groups.<name>.swap` | group | `false` = don't evict other members when loading one |
| `hooks.on_startup.preload` | hooks | Load models immediately at startup |
| `ttl` | model/global | Idle timeout before auto-unloading (0 = never) |

## Memory Budget

Real-world measured sizes (from GGUF metadata + disk):

```
Nex APEX-Quality (no imatrix):  33 GB (model) + ~2 GB (KV Q8_0, 64K)  = ~35 GB
Qwen APEX I-Quality:            22 GB (model) + ~2 GB (KV Q8_0, 64K)  = ~24 GB
AgentWorld APEX I-Quality v3:   22 GB (model) + ~1 GB (KV Q8_0, 32K)  = ~23 GB
llama-server overhead:          ~3 GB (3 instances)
                                TOTAL:                                 ~85 GB
                                Available (MemAvailable):             ~109 GB
                                Margin:                                24 GB ✅
```

Alternative with Q8_0 for AgentWorld (35 GB model): total ~98 GB, margin 11 GB — tight.
Alternative with Q4_K_M for AgentWorld (20 GB model): total ~83 GB, margin 26 GB — safe.

**Context window sizing:** 256K is excessive for orchestrator/subagent use (real prompts: 5-30K).
64K for Nex/Qwen and 32K for AgentWorld saves ~6 GB KV cache vs 256K/128K configs.

## Downloading Models

**Use curl, not `hf download`.** `hf download` silently fails in background shells.
`curl -C -` supports resume on connection drops:

```bash
# Always use -sS (silent+errors), NOT -# (progress bar breaks in bg shells)
curl -sS -L -C - "<HF_CDN_URL>" -o ~/models/file.gguf

# CDN URL pattern:
# https://huggingface.co/{user}/{repo}/resolve/main/{filename}
```

The `-C -` flag resumes partial downloads — critical for multi-GB files on unstable connections.

For download scripts, use `curl -sS` (not `-#`) in background processes.
The `-#` progress bar requires a real TTY and causes `tcsetattr` ioctl errors
that can kill the process early.

## Hermes Integration

```yaml
# ~/.hermes/config.yaml
custom_providers:
  local:
    name: "DGX Spark (llama-swap)"
    api_base: http://localhost:8080/v1
    api_key: not-needed
    models: [nex-n2-mini, qwen3.6-35b, agentworld]
    aliases:
      nex: nex-n2-mini
      qwen: qwen3.6-35b
      world: agentworld
```

Switch: `/model custom:local:nex`, `/model custom:local:qwen`, `/model custom:local:world`

## Model Selection Methodology

When researching local models (especially abliterated/quantized):
1. Search HF for abliterated GGUF repos (huihui-ai, Heretic, Obliteratus variants)
2. Check actual files via HF API: `curl -s "https://huggingface.co/api/models/{repo}?expand[]=siblings"`
3. Compare quantization quality — APEX beats Q8_0 for MoE models at half size
4. For AgentWorld specifically: prefer SuperQwen (Supertune post-training) over plain abliteration
5. Verify stock llama.cpp compatibility — APEX works, some formats (NVFP4, TQ) don't

See `references/abliterated-model-selection.md` for full methodology.

## Pitfalls

- **Standard llama.cpp works on DGX Spark** — no fork needed if CUDA-linked (verify with `ldd`)
- **`hf download` fails silently in background** — use `curl -sS -L -C -` with HF CDN URLs
- **`-#` progress bar kills background curls** — use `-sS` in bg shells
- **Nex APEX-Quality is ~33 GB** (not ~21 GB like Qwen) — APEX-Quality (without imatrix) uses higher precision per tensor, producing larger files. APEX I-Quality (with imatrix) is ~21 GB. Both are standard GGUF, loadable in stock llama.cpp.
- **Heretic v1.2.0 has lowest KL divergence** (0.0015) of all abliteration methods
- **SuperQwen-AgentWorld > huihui-AgentWorld** — Supertune post-training adds +59 HumanEval+
- **Abliterated Nex has no Q8_0** — only APEX and Q4_K_M available; APEX-Quality is best
- **`--mlock` critical** on unified memory — prevents model pages from being swapped. BUT requires `memlock` ulimit set to unlimited: `ulimit -l unlimited` or `/etc/security/limits.d/llama.conf` with `* soft memlock unlimited` / `* hard memlock unlimited`. Default memlock on DGX Spark is ~15 MB — `--mlock` silently fails without unlimited.
- **Use absolute paths** in llama-swap config — Hermes runtime may have different `$HOME`
- **Memory budgeting**: count 1-2 GB per llama-server instance overhead
- **llama-swap `unload: false` does NOT exist** — use `groups` + `swap: false` instead. The `matrix:` top-level key is also wrong. See Configuration section above for correct syntax.
- **Port conflicts** — always check `ss -tlnp` before assigning ports. SearXNG Docker uses 8081, LM Studio uses 1234, LiteLLM uses 4000. Use `startPort: 8100` with `${PORT}` macro to avoid conflicts.
- **llama-swap download URL** — `releases/latest/download/llama-swap_234_linux_arm64.tar.gz` can 404 (mixing `latest` redirect with hardcoded version). Use `releases/download/v234/...` or `releases/latest/download/llama-swap_linux_arm64.tar.gz` (no version).
- **nvidia-smi shows "Not Supported" for memory on DGX Spark** — this is EXPECTED on unified memory architecture (UMA). GPU memory is not separately attributable. Use `free -h` for total system memory instead.
- **`GGML_CUDA_ENABLE_UNIFIED_MEMORY=1` is essential** — without it, llama.cpp uses `cudaMemGetInfo()` which returns a smaller-than-expected value on UMA, causing OOM. With it, `cudaMallocManaged()` allocates from the full 128 GB pool.
- **Model loading takes 5-10 minutes** for 85 GB of models — need a health check loop (`curl /v1/models` every 10s) before sending requests.
- **No watchdog by default** — if llama-swap crashes, all models are lost. Use systemd unit with `Restart=always`.

## Systemd Unit (recommended)

```ini
# /etc/systemd/system/llama-swap.service
[Unit]
Description=llama-swap (3 models on DGX Spark)
After=network.target

[Service]
Type=simple
User=pavel
ExecStart=/home/user/.local/bin/llama-swap --config /home/user/dev/llama/llama-swap.yaml
Restart=always
RestartSec=30
LimitMEMLOCK=infinity
Environment=GGML_CUDA_ENABLE_UNIFIED_MEMORY=1

[Install]
WantedBy=multi-user.target
```

## GGUF Metadata Verification

Before launching, verify all model files have correct architecture and parameters:

```bash
python3 -c "
import struct, os, sys

for f in sys.argv[1:]:
    path = f'/home/user/models/{f}'
    if not os.path.exists(path):
        print(f'❌ {f}: FILE NOT FOUND')
        continue
    with open(path, 'rb') as fh:
        magic = fh.read(4)
        if magic != b'GGUF':
            print(f'❌ {f}: NOT GGUF')
            continue
        version = struct.unpack('<I', fh.read(4))[0]
        tensor_count = struct.unpack('<Q', fh.read(8))[0]
        kv_count = struct.unpack('<Q', fh.read(8))[0]
        arch, name, ctx, blocks, experts = '?','?','?','?','?'
        for i in range(kv_count):
            klen = struct.unpack('<Q', fh.read(8))[0]
            key = fh.read(klen).decode('utf-8', errors='replace')
            vtype = struct.unpack('<I', fh.read(4))[0]
            if vtype == 4: val = struct.unpack('<I', fh.read(4))[0]
            elif vtype == 5: val = struct.unpack('<i', fh.read(4))[0]
            elif vtype == 6: val = struct.unpack('<f', fh.read(4))[0]
            elif vtype == 8:
                slen = struct.unpack('<Q', fh.read(8))[0]
                val = fh.read(slen).decode('utf-8', errors='replace')
            elif vtype == 10: val = struct.unpack('<Q', fh.read(8))[0]
            elif vtype == 0: val = struct.unpack('<B', fh.read(1))[0]
            elif vtype == 2: val = struct.unpack('<H', fh.read(2))[0]
            elif vtype == 12: val = struct.unpack('<B', fh.read(1))[0]
            elif vtype == 9:  # ARRAY
                inner = struct.unpack('<I', fh.read(4))[0]
                count = struct.unpack('<Q', fh.read(8))[0]
                if inner in (4,5): fh.read(count * 4)
                elif inner == 10: fh.read(count * 8)
                elif inner == 8:
                    for _ in range(count):
                        sl = struct.unpack('<Q', fh.read(8))[0]; fh.read(sl)
                val = 'ARRAY'
            else: break
            if key == 'general.architecture': arch = val
            if key == 'general.name': name = val
            if key.endswith('.context_length'): ctx = val
            if key.endswith('.block_count'): blocks = val
            if key.endswith('.expert_count') and 'used' not in key: experts = val
        size = os.path.getsize(path) / (1024**3)
        print(f'✅ {f}: arch={arch} blocks={blocks} experts={experts} ctx={ctx} tensors={tensor_count} size={size:.1f}GB')
" "Huihui-Nex-N2-mini-abliterated-APEX-Quality.gguf" \
  "Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-APEX-I-Quality.gguf" \
  "SuperQwen-APEX-I-Quality-v3.gguf"
```

Expected output: all three should show `arch=qwen35moe`, `blocks=40`, `experts=256`, `ctx=262144`.
