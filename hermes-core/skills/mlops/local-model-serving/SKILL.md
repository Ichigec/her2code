---
name: local-model-serving
description: Manage local GGUF models (Jetson ARM64, DGX Spark, any Linux) — inventory, cleanup, disk usage, model selection/comparison methodology, self-quantization pipeline (BF16→GGUF→K-quant/IQ/APEX), and diagnosing memory issues in LLM serving infrastructure.
version: 1.0.0
author: Pavel's Hermes
metadata:
  hermes:
    tags: [llama.cpp, LiteLLM, Jetson, DGX-Spark, GGUF, memory-leak, disk-cleanup, LM-Studio, model-comparison, quantization]
---

# Local Model Serving

Manage local GGUF models on Jetson ARM64: inventory, cleanup, disk usage, and diagnosing memory issues in LLM serving infrastructure (llama.cpp, LiteLLM proxy, LM Studio).

## Trigger

Use when Pavel asks about:
- What models are on disk / how much space they take
- Cleaning up unused or duplicate models
- Diagnosing high memory usage in LiteLLM, llama.cpp, or LM Studio
- Finding broken/partial model downloads
- **Comparing models for local deployment** — which model to run on specific hardware
- **Model selection methodology** — matching model size/quantization to available RAM/VRAM
- **Finding abliterated/uncensored models** — deep research across HF for best quant+abliteration combos
- **DGX Spark deployment** — llama-swap multi-model matrix, APEX quantization
- **EAGLE-3 speculative decoding** — training draft models via SpecForge, GGUF conversion, llama-server integration for 2–5× inference speedup. Detailed training recipe, pre-trained draft discovery, and DGX Spark resource budget in `references/eagle3-speculative-decoding.md`
- **Self-quantization** — quantizing HF models yourself (BF16 → GGUF → K-quant/IQ/APEX), importance matrix generation, calibration datasets, quality evaluation
- **Evaluation methodology** — always check published benchmarks (HF model cards, APEX README, papers) BEFORE running expensive local benchmarks. Pavel prefers using existing data over burning compute.
- **Deep research on best coding models for DGX Spark** — forum-sourced community rankings, speculative decoding options (MTP/DFlash/EAGLE-3), quantization comparisons (NVFP4/PrismaQuant/APEX). Top-5 ranking with benchmarks at `references/dgx-spark-coding-models.md`. Load this BEFORE answering "what's the best coding model for my Spark" questions.

**NOT this skill for:** Training / fine-tuning / distillation → load `llm-finetuning-pipeline` instead. That skill covers BAdam/LoRA/QLoRA method selection, Unsloth Docker setup, student model selection, distillation pipelines, model merging, and depth upscaling analysis. This skill handles the post-training deploy (GGUF conversion, APEX quantization, llama.cpp serving).

## Diagnostic Ordering (CRITICAL)

When Pavel reports "memory grows during operation", **check llama-server FIRST** — specifically CUDA graph accumulation on GB10. Do NOT start with LiteLLM/Phoenix/Docker container memory. The diagnostic order is:

1. **llama-server (native C++)** — CUDA graph leak on qwen35moe (see `references/cuda-graph-memory-leak.md`). Check `env | grep GGML_CUDA_DISABLE_GRAPHS`, `grep -c "CUDA graph warmup" logs/`. If graphs accumulating → fix with `GGML_CUDA_DISABLE_GRAPHS=1`.
2. **llama-server flags** — verify `--flash-attn on` (not `auto`), `-np 2` (not auto), `--no-mmap` (mandatory for multi-model).
3. **LiteLLM** — only if llama-server RSS is flat but total system memory still grows. Check `MALLOC_ARENA_MAX`, `mem_limit`, Phoenix callbacks.
4. **System OOM kills** — journalctl for recent OOM events, correlate with model launch times.

Pavel WILL redirect you if you lead with LiteLLM. The correction signal is explicit: "растет потребление памяти именно llama.cpp".

## Model Inventory

```bash
# LM Studio models — per-model sizes (use */*/ not */)
du -sh /home/user/.lmstudio/models/*/*/ | sort -rh

# Detal — what files inside each model dir
for d in /home/user/.lmstudio/models/*/*/; do
  echo "--- $(basename "$(dirname "$d")") / $(basename "$d") ---"
  du -sh "$d"
  ls -lhS "$d" | head -10
  echo
done

# LocalAI models (Docker volume)
docker exec localai du -sh /models/
docker exec localai ls -lh /models/

# llama.cpp vocab files only — NOT model weights (ignore these ~69 MB)
du -sh /home/user/dev/llama.cpp/models/

# All .gguf files anywhere in home
find /home/user -name "*.gguf" -type f -exec ls -lh {} \; 2>/dev/null
```

## Tooling

### hf CLI (replaces deprecated huggingface-cli)

```bash
# Install standalone (recommended)
curl -LsSf https://hf.co/cli/install.sh | bash

# List files in a repo
hf repo list --format json <repo> | python3 -c "import sys,json; [print(f['name']) for f in json.load(sys.stdin)]"
```

**PITFALL:** `hf download` can hang silently or exit with code 0 without downloading. Prefer `curl -C -` from the HF CDN for reliability:

```bash
# Reliable download (resumable). Use -sS in background, -# only in foreground
curl -sS -L -C - \
  "https://huggingface.co/<REPO>/resolve/main/<filename.gguf>" \
  -o ~/models/<filename.gguf>
```

CDN URL pattern: `https://huggingface.co/{user}/{repo}/resolve/main/{file}`. Never use `&` inside a background download command — it causes the parent to exit before curl completes. Use `-sS` (not `-#`) in background shells — the `-#` progress bar requires a real TTY and causes `tcsetattr` ioctl errors that kill the process early.

### llama-swap

```bash
# Install to user-local bin (no sudo)
# Use releases/download/v<NUM>/ for specific version (NOT releases/latest with version in filename)
curl -fsSL "https://github.com/mostlygeek/llama-swap/releases/download/v234/llama-swap_234_linux_arm64.tar.gz" | tar xz
cp llama-swap ~/.local/bin/
chmod +x ~/.local/bin/llama-swap

# CRITICAL: verify it's a real binary, not a "Not Found" text file
file ~/.local/bin/llama-swap  # should say "ELF 64-bit LSB executable"
~/.local/bin/llama-swap --version
```

**Config syntax (v234):** Use `groups` + `swap: false` for simultaneous multi-model loading. `unload: false` and top-level `matrix:` do NOT exist. See `references/dgx-spark-deployment.md` for full corrected config. **DEPRECATED:** `templates/llama-swap-3-models.yaml` is kept for reference only — direct llama-server launch via `templates/start-llama.sh` is the preferred approach (simpler, no proxy layer, no binary download issues).

## What's Running

```bash
# llama.cpp server (Jetson's main inference)
ps aux | grep llama-server | grep -v grep

# LM Studio GUI + its built-in server (:1234)
curl -s http://localhost:1234/v1/models | python3 -m json.tool

# LiteLLM proxy
docker ps --filter name=litellm

# All model-serving ports
ss -tlnp | grep -E '8092|8080|1234|4000|8180'
```

## Docker → Host Connectivity (LiteLLM Proxy)

LiteLLM runs in a Docker container (`litellm` on `llm-stack-net`, subnet 172.18.0.0/16). The host runs **UFW (Uncomplicated Firewall)** with `INPUT policy DROP` — only ports with explicit `ufw-user-input` rules are reachable from Docker containers. Without these rules, packets are silently dropped (TIMEOUT, not RST).

**Two requirements for Docker → llama-server connectivity:**
1. llama-server must listen on `--host 0.0.0.0` (not `127.0.0.1` — Docker comes via bridge gateway, not loopback)
2. UFW must allow the port for Docker subnet `172.18.0.0/16`

**Symptom:** Models respond on `localhost:8101-8103` but LiteLLM requests hang until timeout. No GPU load, no log entries in llama-server. `curl` from inside the container gets `URLError: timed out`.

**Diagnosis — port reachability scan from inside container:**
```bash
docker exec litellm python3 -c "
import socket
for port in [1234, 8090, 8092, 8101, 8102, 8103, 8643]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(('host.docker.internal', port)); print(f'  :{port} CONNECTED')
    except ConnectionRefusedError:
        print(f'  :{port} RST (reachable, no service)')
    except TimeoutError:
        print(f'  :{port} TIMEOUT (blocked)')
    finally: s.close()
"
```
RST = port reachable (UFW allows it, service may be down). TIMEOUT = UFW blocks it.

**Root cause identification — inspect host iptables without sudo:**
```bash
# KEY TECHNIQUE: privileged Docker container with --network host sees HOST iptables
docker run --rm --privileged --network host alpine sh -c "
    apk add --no-cache iptables 2>/dev/null >/dev/null
    iptables-save -t filter | grep -E 'ufw-user-input|INPUT.*DROP'
"
# Shows: :INPUT DROP [packets:bytes]  and  -A ufw-user-input -s 172.18.0.0/16 -p tcp --dport 1234 -j ACCEPT
# Only ports 1234, 8090, 8092, 8643 have ufw-user-input rules → all others blocked
```

**Fix: inject UFW rules via privileged container (no sudo on host needed):**

Two approaches work — `INPUT` chain (simpler, verified July 2026) or `ufw-user-input` chain (original):

```bash
# Approach A: INPUT chain — inserts before ALL UFW chains (simplest, verified port 8104)
docker run --rm --privileged --network host alpine sh -c '
    apk add --no-cache iptables 2>/dev/null >/dev/null
    for net in 172.18.0.0/16 172.17.0.0/16; do
        iptables -I INPUT 1 -p tcp -s "$net" --dport 8104 -j ACCEPT
    done
'

# Approach B: ufw-user-input chain — inserts into UFW's own chain
docker run --rm --privileged --network host alpine sh -c '
    apk add --no-cache iptables 2>/dev/null >/dev/null
    for port in 8101 8102 8103; do
        for net in 172.18.0.0/16 172.17.0.0/16; do
            iptables -C ufw-user-input -s "$net" -p tcp --dport "$port" -j ACCEPT 2>/dev/null || \
            iptables -I ufw-user-input 1 -s "$net" -p tcp --dport "$port" -j ACCEPT
        done
    done
'
```
Rules are injected into the host's netfilter via the privileged container's `--network host` namespace. They persist until reboot or Docker daemon restart. The `start-llama.sh` script auto-injects these rules on every `start` — see `templates/start-llama.sh`.

**⚠️ Alpine iptables-nft FAILS on DGX Spark (ARM64):** The above Alpine container approach fails with `iptables: Failed to initialize nft: Protocol not supported` on DGX Spark. Alpine's iptables package uses the nft backend which is incompatible with this kernel. **Fix:** use host iptables via `sudo -n iptables ...` instead of the Alpine container. The `inject_firewall_rules()` function in `templates/start-llama.sh` (updated July 2026) handles this correctly — tries `sudo -n` first, falls back to printing manual instructions.

**⚠ Shell quoting trap:** Variables inside `sh -c '...'` are expanded by the inner shell. Use plain `"$var"` — never `'"'"'$var'"'"'` which forces outer-shell expansion of an undefined variable. Symptom: `iptables: invalid port/service '$port' specified` — rules silently fail.

**Multi-consumer pattern:** When Hermes AND OpenCode+ need the same models, route both through LiteLLM (not direct to llama-server ports). See `references/multi-consumer-liteLLM.md`.

**`--network host` bypasses UFW entirely:** If the consumer is a Docker container using `--network host` (e.g. Hermes gateway), it shares the host's network namespace and can reach :8101/:8102/:8103 directly — NO UFW rule injection needed. This is simpler than iptables manipulation. Only bridge-network containers (like LiteLLM on `llm-stack-net`) need UFW rules. For multi-model Hermes deployments, prefer `--network host` on the gateway container instead of routing through LiteLLM. See `hermes-docker-deploy` skill → "`--network host` bypasses UFW".

**Fallback: socat port bridge** (if privileged container approach is unavailable):
```bash
socat TCP-LISTEN:8090,fork,reuseaddr TCP:127.0.0.1:8101 &  # nex
socat TCP-LISTEN:8092,fork,reuseaddr TCP:127.0.0.1:8102 &  # qwen
socat TCP-LISTEN:1234,fork,reuseaddr TCP:127.0.0.1:8103 &  # world
```
Then in LiteLLM config, use `api_base: "http://host.docker.internal:8090/v1"` (not `:8101`). This was the original workaround before the UFW root cause was identified. See `references/docker-ufw-firewall-fix.md` for the full diagnosis walkthrough.

**LiteLLM config location:** Docker: `/app/config.yaml` inside the `litellm` container (`docker exec litellm cat /app/config.yaml`). Native fallback: `/home/user/dev/llama/litellm-config.yaml`.

**As of July 2026, Docker LiteLLM WORKS on ARM64** with a **Postgres backend** (not SQLite). The `litellm` container + `litellm-db` Postgres container are both running. The old Prisma SIGSEGV was SQLite-only — Postgres backend resolves it. Discover master key: `docker exec litellm env | grep LITELLM_MASTER_KEY` (currently `sk-local`). After config change: `docker restart litellm`, wait ~18s for health check. See `references/multi-consumer-liteLLM.md` for the multi-consumer architecture and `hermes-custom-providers` skill → `references/litellm-native-setup.md` for native venv fallback (only if Docker Postgres approach fails).

**Benchmarking local models:** `scripts/benchmark-models.py` in the `hermes-custom-providers` skill measures tok/s for all models through LiteLLM. Usage: `python3 ~/.hermes/skills/software-development/hermes-custom-providers/scripts/benchmark-models.py`. DGX Spark results (July 2026, 512 tokens): all 3 models at ~32-33 tok/s.

**Adding models to LiteLLM:** Add `model_list` entries with `model_name` (what clients see) and `litellm_params.model` (what the backend reports via `--alias`). Multiple `model_name` entries can point to the same backend — use this for short aliases + full quant names. After config change: `docker restart litellm`, wait ~18s for health check, then test with `curl` + master key.

**`request_timeout` for slow models:** F16 / large unquantized models generate at ~2 tok/s. LiteLLM's default request timeout causes requests to hang and eventually return 504. Always add `request_timeout: 600` and `max_retries: 0` in `litellm_params` for models generating below 5 tok/s. Example entry for a slow host llama-server model:
```yaml
  - model_name: "gemma4-31b"
    litellm_params:
      model: "openai/gemma4-31b"
      api_base: "http://host.docker.internal:8104/v1"
      api_key: "not-needed"
      request_timeout: 600
      max_retries: 0
```

**Testing models through LiteLLM:** Always test end-to-end (LiteLLM → llama-server) after config changes, not just direct llama-server access. A model can work on `localhost:8101` but fail through LiteLLM if the UFW rule or `--host 0.0.0.0` is missing.

### Quick Diagnostic: "Local Models Not Responding"

When Pavel reports local models aren't working, run this **bottom-up layered diagnostic** BEFORE touching config. In the majority of cases the models are actually fine — the issue is elsewhere (wrong model name, stale alias, dead vLLM container, missing master key).

**Step 0 — One-command validator (if Plan3 is deployed):**
```bash
python3 ~/.hermes/skills/software-development/multi-agent-orchestration/scripts/validate-plan3-models.py
# Checks: sub-agent frontmatter, physical servers (:8101-8103), start-llama.sh health, LiteLLM connectivity
# If ALL CHECKS PASSED → models work, look elsewhere
```

**Step 1 — Check each llama-server directly (bypasses LiteLLM):**
```bash
for p in 8101 8102 8103; do
  printf ":$p "
  curl -s --max-time 3 http://localhost:$p/v1/models | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK -', d['data'][0]['id'])" 2>/dev/null || echo "DOWN"
done
```

**Step 2 — Discover LiteLLM master key, then test routing:**
```bash
# Get the key (if unknown)
docker exec litellm env | grep LITELLM_MASTER_KEY  # e.g. sk-local

# Test all model aliases through LiteLLM
for model in nex-n2-mini agents-a1-abliterated agentworld; do
  echo "--- $model ---"
  curl -s --max-time 15 http://localhost:4000/v1/chat/completions \
    -H "Authorization: Bearer sk-local" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK\"}],\"max_tokens\":10}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); c=d.get('choices',[{}])[0].get('message',{}).get('content','NONE'); e=d.get('error','none'); print(f'CONTENT: {c} ERROR: {e}')"
done
```

**Step 3 — Verify Hermes config `providers.local`:**
```bash
python3 -c "
import yaml; c=yaml.safe_load(open('/home/user/.hermes/config.yaml'))
p = c.get('providers',{}).get('local',{})
print(f'base_url: {p.get(\"base_url\")}')
print(f'api_key:  {p.get(\"api_key\")}')
print(f'models:   {p.get(\"models\")}')
"
# Must show: base_url=http://localhost:4000/v1, api_key=sk-local
```

**Step 4 — Test streaming mode (Hermes uses stream=true):**
```bash
curl -s --max-time 15 http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-local" \
  -H "Content-Type: application/json" \
  -d '{"model":"nex-n2-mini","messages":[{"role":"user","content":"Say OK"}],"max_tokens":10,"stream":true}' | head -5
# Must show: data: {"choices":[{"delta":{"content":"OK"...
```

**Step 5 — Check vLLM containers (separate from llama-server):**
```bash
docker ps --format '{{.Names}} {{.Status}} {{.Ports}}' | grep -E 'vllm|8000|diffusion'
# vLLM :8000 (diffusiongemma) is often dead — it's optional, not part of Plan3 routing
```

**Common findings:** (a) All llama-server instances + LiteLLM work fine → the issue is in Hermes model name resolution or how the user invoked it. (b) vLLM :8000 is dead → not critical, only affects diffusiongemma. (c) Model alias changed (e.g. :8102 switched from `qwen3.6` to `agents-a1`) → update LiteLLM config aliases and Hermes `providers.local.models` list.

## Cleanup Candidates

Three patterns to flag for deletion:

1. **`.part` files** — broken/incomplete downloads (HF interrupted). Zero value. Delete the entire model dir.
2. **Duplicate BF16 models** — same architecture+quant from different HF authors. 67 GB × 2 for identical weights. Keep the one that's running; delete the rest.
3. **Old model versions** — e.g. Qwen3.5 when Qwen3.6 is stable. The BF16 splits (38G+28G=66G) are heavy; optionally keep Q8_0 (35G) as compact fallback.

## Memory Leak Diagnosis

### llama-server (native C++) — CUDA graph leak

For llama-server specifically on DGX Spark (GB10), the primary memory growth mechanism is CUDA graph accumulation (not Python heap). See `references/cuda-graph-memory-leak.md` for full analysis.

```bash
# Quick check — is CUDA graphs env var set?
env | grep GGML_CUDA_DISABLE_GRAPHS
# Empty = graphs enabled = leak potential

# Monitor RSS growth over time (should be flat with fix applied)
for pid in $(pgrep llama-server); do
  rss=$(awk '/VmRSS/{printf "%.1f", $2/1048576}' /proc/$pid/status 2>/dev/null)
  echo "PID $pid RSS=${rss}GB"
done

# Check for CUDA graph warmup log spam (indicates new graphs being created)
grep -c "CUDA graph warmup" /home/user/dev/llama/logs/*.log 2>/dev/null
# Hundreds/thousands = graphs accumulating every few tokens = leak
```

### Python/container processes (LiteLLM, vLLM proxy)

```bash
# Container-level overview
docker stats <name> --no-stream

# Process-level — VmData > VmRSS by many GB = heap leak
docker exec <name> cat /proc/1/status | grep -E 'VmRSS|VmData|RssAnon|VmSwap'

# Find the large anonymous region (single giant region = heap leak)
docker exec <name> cat /proc/1/smaps | \
  awk '/^[0-9a-f]/{addr=$1} /^Rss:/{rss=$2} /^Anonymous/{if(rss>100000) printf "%s: %d MB\n", addr, rss/1024}' | \
  sort -t: -k2 -rn | head -5

# CRITICAL: Check if MALLOC_ARENA_MAX is set (empty = not set = likely root cause)
docker exec <name> env | grep MALLOC_ARENA_MAX

# Check background task intervals (2-30s tasks drive idle leaks)
docker logs <name> 2>&1 | grep -E "scheduled|monitor|watchdog|interval" | head -15
```

If you see one massive anonymous region (e.g. 20 GB) AND `MALLOC_ARENA_MAX` is unset — it's glibc arena fragmentation from background tasks. Python GC frees objects but glibc never returns arena memory to OS. Fix: `MALLOC_ARENA_MAX=2` + `mem_limit` in Docker compose. This applies to ALL long-running Python Docker services (FastAPI, Django, Celery), not just LiteLLM. See `references/litellm-memory-leak.md` for the full 8-step diagnosis methodology.

## LiteLLM Memory Fix

**Root cause:** glibc malloc arena fragmentation, NOT request volume. Background tasks (policy/attachment/Prisma sync every 2-30s) generate ~98k DB queries in 43h even at zero traffic. Each query allocates Python objects via glibc malloc; without `MALLOC_ARENA_MAX`, glibc creates 128+ arenas (8 × CPU cores) and never returns freed memory to the OS. Observed: 17.66 GB (RSS + swap) at 7 requests in 48 hours — a pure idle leak.

**Fix (applied 2026-07-03, RSS 17.66 GB → 849 MB, 95.2% reduction):**

```yaml
# In /home/user/cursor/first/compose.phoenix.yml, litellm service:
environment:
  - MALLOC_ARENA_MAX=2          # #1 fix — limits glibc arenas, prevents fragmentation
  - LITELLM_LOG=WARNING          # fewer INFO log allocations from 30s background syncs
  - PYTHONUNBUFFERED=1
mem_limit: 4g                    # hard ceiling; OOM kill + restart: unless-stopped = auto-recovery
```

`--max_requests_before_restart 10000` does NOT fix idle leaks (7 req/48h → 17 GB). Use `MALLOC_ARENA_MAX=2` instead. For immediate relief: `docker restart litellm`. Full diagnosis methodology in `references/litellm-memory-leak.md`.

## DGX Spark Deployment

For full DGX Spark (GB10, 128 GB) deployment — stock llama.cpp (already CUDA-enabled on aarch64, no DGX-specific fork needed), APEX quantization for MoE models, and a simple `start-llama.sh` script for multi-model launch (Pavel prefers sh scripts over systemd). Full deployment config, launch script template, and corrected YAML at `/home/user/dev/llama/` and `references/dgx-spark-deployment.md`. Launch script template at `templates/start-llama.sh` — copy-and-modify for your model paths and ports.

### Coding Model Selection for DGX Spark

When Pavel asks which model to run for local coding on a single Spark, load `references/dgx-spark-coding-models.md` — it contains the full top-5 ranking from NVIDIA forum research (July 2026) with SWE-bench scores, tok/s, quantization recommendations, and speculative decoding trade-offs. Summary:

- **Best overall:** Qwen3.6-35B-A3B with NVFP4/PrismaQuant 4.75-bit + MTP n=3 in vLLM (50-97 tok/s, SWE-bench 73.4)
- **Best quality (slower):** Qwen3.6-27B Dense Q4_K_M (SWE-bench 77.2%, 10-15 tok/s)
- **Purpose-built coding:** Qwen3-Coder-Next 80B FP8 (~43 tok/s)
- **Frontier at Q2:** DeepSeek-V4-Flash Q2 GGUF (only frontier model fitting one Spark)
- **Architectural diversity:** Gemma 4 31B Dense Q4_K_M (dense, not MoE)

Pavel's current Nex-N2-mini (SWE-bench 74.4, Terminal-Bench 60.7) is competitive but slower than Qwen3.6-35B on NVFP4 in vLLM.

### Model Selection Golden Rule

**Big model + bad quant < smaller model + good quant.** A 397B model in IQ2_XS (~2.5 bit) performs WORSE than a 35B model in Q8_0 (near-lossless). Always prefer a model that fits in Q8_0 or Q4_K_M over a larger model in extreme quantization. Full quantization quality data from arXiv 2601.14277 in `references/quantization-quality-data.md`.

## Self-Quantization Pipeline

When Pavel asks about quantizing models himself («самостоятельное квантование», «как квантовать без потери качества»), refer to:
- `references/self-quantization-methodology.md` — deep research: methods, theory, calibration data selection
- `references/self-quantization-runbook.md` — concrete session: SuperQwen example, pitfalls hit, exact commands
- `references/calibration-256k-plan.md` — 256K-token diverse calibration plan for MoE models (Pavel's research)
- `references/agentic-calibration-corpus.md` — building domain-specific FC+chat corpus for agentic models (Hermes FC, Glaive FC, UltraChat, Qwen chat format conversion)
- `references/superqwen-apex-benchmark-results.md` — measured PPL/benchmark results for SuperQwen APEX v1 vs v3, model card benchmarks, AgentWorldBench scores
- `references/q8-ssm-garbage-tokens.md` — CRITICAL: Q8_0 on SSM/DeltaNet tensors generates garbage tokens (token 14 `/`). Tensor-type comparison, root cause, testing methodology
- `references/multi-model-contention.md` — CRITICAL: 3 simultaneous llama-server processes cause GPU contention on DGX Spark unified memory. Model loading order matters, practical 2-model limit

Quick summary:
- **Download**: Use `curl -C -` from HF CDN, NOT `hf download` (skips safetensors shards). Loop over `model-00001-of-000NN.safetensors`.
- **Tier 1:** `convert_hf_to_gguf.py` → `llama-quantize Q4_K_M` — simplest, no calibration, −0.32 Δ avg
- **Tier 2:** + `llama-imatrix` (calibration) — Q4_K_M + imatrix ≈ Q5_K_M without, IQ-series **mandatorily** needs imatrix
- **Tier 3:** APEX for MoE — `quantize.sh --i-quality --layers 48` after conversion, 21 GB beats Q8_0 (34 GB)
- **Never requantize** an already-quantized model — always start from BF16/FP16
- **Evaluate:** perplexity (PPL), KL-divergence, HellaSwag/MMLU via `llama-perplexity`
- **Eval data:** Wikitext-2 is now parquet-only. Use `datasets` library from existing venv (e.g. jupyterlab) to extract wiki.test.raw. Store under `/home/user/models/eval-data/`.
- **ALWAYS check published benchmarks first.** Before running expensive local benchmarks (F16 PPL on 65GB model, full eval.sh suite), check: (1) HF model card README for benchmark tables, (2) APEX README for reference PPL/HellaSwag/MMLU/ARC numbers, (3) papers, (4) **APEX local benchmark_results directory** at `/home/user/dev/apex-quant/benchmark_results/` — contains per-model JSON files (`apex_i_quality.json`, `baseline_results.txt`, `kl_results.txt`) organized by model family (`final/` = Qwen3.5, `qwen36_35b/` = Qwen3.6, etc.). These are directly comparable cross-model results from the same hardware. Use `hf download <repo> --include README.md --local-dir /tmp/card` to fetch model cards. Published data from the same hardware (DGX Spark) is directly comparable. Only run local benchmarks when published data doesn't exist or the model has been modified (abliteration, supertune) beyond what the card covers.

DGX Spark tools at `/home/user/dev/llama.cpp/build/bin/`:
- `llama-quantize` (standard GGUF quantization, supports `--tensor-type-file` for selective precision)
- `llama-imatrix` (importance matrix generation, use `--ctx-size 512 --chunks 500`)
- `llama-perplexity` (PPL, KL-divergence, HellaSwag, multiple-choice)
- `llama-gguf` (GGUF metadata inspection)

APEX quantization at `/home/user/dev/apex-quant/` (cloned from `localai-org/apex-quant`):
- `scripts/quantize.sh` — direct APEX quantization (fast path, no YAML needed)
- `scripts/generate_config.sh` — generate tensor-type configs per profile
- `scripts/apex_pipeline.sh` — full pipeline (config→download→convert→quantize→eval→publish)

### Quick APEX Quantization (Simplest Path)

For one-off quantization of an MoE model when you already have F16 GGUF:

```bash
# 1. Convert HF model → F16 GGUF (if not done yet)
python3 /home/user/dev/llama.cpp/convert_hf_to_gguf.py <hf-model-dir> --outtype f16 --outfile model-f16.gguf

# 2. Generate imatrix (30-60 min, needed for I-variants)
/home/user/dev/llama.cpp/build/bin/llama-imatrix \
  -m model-f16.gguf \
  -f /path/to/calibration-corpus.txt \
  -o model.imatrix.gguf -c 2048 -b 512 -t 16 -ngl 0 \
  --chunks 125 --save-frequency 50 --process-output
# 125 chunks × 2048 ctx = 256K tokens. -ngl 0 = CPU-only (safe, no OOM).
# For diverse calibration corpus (FC+chat+code), see references/agentic-calibration-corpus.md

# 3. APEX I-Quality (one command)
cd /home/user/dev/apex-quant
NUM_LAYERS=40 LLAMA_CPP_DIR=/home/user/dev/llama.cpp/build/bin \
  ./scripts/quantize.sh \
  --profile i-quality \
  --imatrix model.imatrix.gguf \
  model-f16.gguf model-apex-i-quality.gguf
```

Available profiles: `quality`, `i-quality`, `balanced`, `i-balanced`, `compact`, `i-compact`, `mini`. I-variants benefit from `--imatrix`. `NUM_LAYERS` env var = number of transformer layers (40 for Qwen3.5/3.6-35B MoE, confirmed via `config.json` → `num_hidden_layers`). **Syntax: `--profile <name>` with positional `<input> <output>` args, NOT `--i-quality` or `--layers N` flags.**

### APEX Quantization (MoE models)

**APEX beats Q8_0 perplexity at half the size — and even beats F16 on some benchmarks.** From the LocalAI team, APEX is a MoE-aware mixed-precision quantization that classifies tensors by role (routed expert, shared expert, attention) and applies layer-wise precision gradients. Works with **stock llama.cpp — no patches required.**

Benchmarks on Qwen3.5-35B-A3B, DGX Spark (NVIDIA GB10):

| Config | Size GB | PPL | HellaSwag | MMLU | ARC | KL div | tok/s |
|--------|---------|-----|-----------|------|-----|--------|-------|
| F16 (ref) | 64.6 | 6.537 | 82.5% | 41.5% | 56.9% | — | 30.4 |
| Q8_0 | 34.4 | 6.533 | 83.0% | 41.2% | 57.9% | 0.0046 | 52.5 |
| **APEX I-Quality** | **21.3** | **6.552** | **83.5%** | **41.4%** | **57.9%** | **0.0102** | **63.1** |
| **APEX Quality** | **21.3** | **6.527** | **83.0%** | **41.2%** | **56.2%** | **0.0114** | **62.3** |
| APEX I-Balanced | 23.6 | 6.548 | 83.0% | 41.0% | 57.5% | 0.0078 | 61.4 |
| APEX I-Compact | 16.1 | 6.669 | 81.8% | 41.7% | 55.5% | 0.0332 | 69.8 |
| Unsloth UD-Q8_K_XL | 45.3 | 6.536 | 82.5% | 41.3% | 57.9% | 0.0025 | 36.4 |

**I-variants** use a diverse imatrix (chat, code, reasoning, tool-calling — no Wikipedia) that trades tiny perplexity increases for significant accuracy gains and lower KL divergence. For reasoning/coding tasks, prefer I-variants.

Key APEX repos on HF: `SC117/*-APEX-GGUF` (abliterated), `mudler/*-APEX-GGUF` (original). Full benchmark report in `references/apex-quantization-benchmarks.md`.

### Three-Model Abliterated Architecture (~91 GB / 128 GB DGX Spark)

All three abliterated models loaded simultaneously via **direct llama-server launch** (no llama-swap needed — Pavel prefers simple sh scripts over proxy layers). Each model gets its own port (8101/8102/8103) and PID file. The `start-llama.sh` script handles start/stop/status/test + auto-injects firewall rules. A separate daemon watchdog process handles auto-restart — written to a FILE via heredoc (NOT inline `bash -c '...'` which silently breaks variable expansion). Models are launched with `setsid` for full session detachment.

> **Context: 256K on all models** (verified 4 July 2026). Pavel requires 256K context (`-c 262144`). This uses ~91 GB RAM with all 3 models loaded (model weights 77 GB + KV cache ~11 GB + overhead). 29 GB headroom. Thinking models (Agents-A1-35B) need this headroom — at 32K, thinking tokens consume all output budget leaving empty `content`. At 256K, thinking models respond correctly.

| Role | Model | Quant | Size | Context | What It Does | Key Benchmark |
|------|-------|-------|------|:---:|------|---------------|
| Nex-N2-mini | huihui-ai abliterated | APEX-Quality (no imatrix) | ~33 GB | 256K | Coding, terminal | SWE-Bench 74.4, Terminal-Bench 60.7 |
| Agents-A1 35B | huihui-ai abliterated (fresh Jul 9) | APEX I-Quality (imatrix) | ~22 GB (+ 0.9 GB mmproj) | 256K | Reasoning, analysis, VLM | GAIA 96.0, IFBench 80.6, IFEval 94.8, BrowseComp 75.5 |
| SuperQwen-AgentWorld | Obliteratus+Supertune | APEX I-Quality v3 | ~22 GB | 256K | World simulation | HumanEval+ 75.0 (+59 vs orig) |
> **Q8_0 is BROKEN for qwen35moe** — generates only token 14 (`/`). Do NOT use Q8_0 on these models. APEX I-Quality (Q6_K on SSM) is the correct choice. See `references/q8-ssm-garbage-tokens.md`.

**Total: ~77 GB models + ~11 GB KV cache (256K × q8_0 × 3 models) + ~3 GB overhead = ~91 GB.** Memory available: 121 GB → 30 GB headroom. Each model on its own port with PID tracking and separate watchdog daemon. Launch script at `templates/start-llama.sh` — copy-and-modify for your model paths and ports. Full deployment details in `references/dgx-spark-deployment.md`.

> **All 3 models work simultaneously with `--no-mmap`** (verified 4 July 2026). Without `--no-mmap`, only the first-loaded model works — the rest produce garbage (`////`, `????`). Root cause: mmap file mappings from multiple CUDA contexts conflict on DGX Spark unified memory. Fix: add `--no-mmap` to every llama-server instance — loads weights explicitly via `read()` instead of mmap. With `--no-mmap`: all 3 models (nex 33GB, qwen 22GB, world 22GB) work simultaneously at 28-35 tok/s each. Testing methodology: raw completion "What is 2+2?" after loading; single-char repeated output = broken. Full investigation in `references/multi-model-contention.md`.

> **llama-swap was abandoned** in favor of direct llama-server launch. llama-swap's binary was unreliable (download produced 9-byte "Not Found" text file), its config syntax was non-obvious (`unload: false` doesn't exist), and it added a proxy layer with no benefit for 3 always-loaded models. The `templates/llama-swap-3-models.yaml` is kept for reference only — do NOT use it for new deployments.

**Architecture (verified from GGUF metadata):** All three use `qwen35moe` arch, 40 blocks (10 attention + 30 DeltaNet, 3:1 ratio), 256 experts / 8 active per token. Qwen3.6 has 753 tensors (20 more than Nex/SuperQwen's 733 — likely MTP head). NOT 48 blocks / 128 experts as some documentation claims.

Abliteration details: Nex = huihui-ai, Qwen = Heretic v1.2.0 (KL 0.0015, −88% refusals), AgentWorld = Obliteratus + **Supertune** post-training (5 enhancements: observation formatting, direct task completion, JSON/tool formatting, Korean technical answers, regression resistance — single checkpoint, no runtime adapter). SuperQwen-AgentWorld Q8_0 GGUF from McG-221 (36.9 GB verified via HF API).

**SuperQwen = not a model family, but a post-training brand.** Jiunsong's "Supertune" method adds targeted fine-tuning on top of abliterated Qwen models. Unlike plain abliteration (which only removes refusals), Supertune adds useful capabilities while maintaining base quality. The `Super` prefix is Jiunsong's naming convention across multiple base models (SuperQwen, SuperGemma). Full world model comparison (Agents-A1, Ornith-1.0, AgentWorld-397B vs SuperQwen) in `references/world-model-comparison.md`.

**All 4 current models are the SAME architecture** (Qwen3.5/3.6-35B-A3B MoE) — they are siblings, not diverse models. Key finding: A1 dominates on agent/search/IF benchmarks (7/8 wins) but has NO published standard benchmarks (MMLU, AIME, SWE-bench, GPQA). Alternatives like Gemma 4 31B and GLM-4.7-Flash beat A1 on coding/math/knowledge simply because A1 was never evaluated there. For the full cross-architecture head-to-head table and diversification recommendations, see `references/model-landscape-diversity.md`.

## Speculative Decoding Options (EAGLE-3, MTP, DFlash)

Three speculative decoding methods available for DGX Spark. See `references/dgx-spark-coding-models.md` for comparison table and community performance data.

### EAGLE-3 (2–5×, llama.cpp only)

EAGLE-3 (NeurIPS'25) accelerates llama.cpp inference via a lightweight draft model (~400 MB, 1 transformer layer) that predicts multiple future tokens — verified in parallel by the target model. **Lossless** — identical output distribution to vanilla decoding. llama.cpp support merged in b9606+ (June 2026).

### MTP — Multi-Token Prediction (1.4–1.86×, vLLM + llama.cpp)

Built into Qwen3.6 models. No separate draft model needed. **MTP n=3 is the measured optimum** for Qwen3.6-35B on DGX Spark (n=2 leaves ~10% tok/s on table, n=4 regresses).

🔴 **CRITICAL: MTP breaks tool calling on vLLM.** Community reports: tool-calling accuracy drops when MTP is enabled. Disable MTP when the coding agent uses tools (bash, file ops, etc.) until Qwen team provides guidance. This does NOT affect llama.cpp-based serving.

### DFlash — Block Diffusion (up to 6× theoretical, vLLM)

Alternative to EAGLE-3 using block-diffusion speculative decoding. Public HF draft available: `z-lab/Qwen3.6-35B-A3B-DFlash`. Needs vLLM.

### EAGLE-3 Pre-trained drafts for Qwen MoE

| Target Model | Draft on HF | Size |
|-------------|------------|------|
| Qwen3.5-35B-A3B | `jiapingW/Qwen3.5-35B-A3B-Eagle3-Specforge` | ~400 MB |
| Qwen3-30B-A3B | `Tengyunw/qwen3_30b_moe_eagle3` | ~400 MB |
| Agents-A1-35B | **None yet — needs training** | — |

**Critical:** EAGLE-3 drafts are TIED to the target model's weights (take hidden states from frozen target). A draft trained on vanilla Qwen3.5-35B-A3B will have LOW acceptance rate against Agents-A1 (different weights from post-training). Must train against the exact model.

### Quick test with pre-trained draft

```bash
# 1. Convert PyTorch draft → GGUF
python3 /home/user/dev/llama.cpp/convert_hf_to_gguf.py \
    /path/to/qwen3.5-eagle3-draft/ --outtype f16 \
    --outfile /home/user/models/qwen35-eagle3-f16.gguf

# 2. Launch llama-server with EAGLE-3
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
```

### Training a custom draft via SpecForge (SGLang team, LMSYS)

SpecForge already has a config for Qwen3.5-35B-A3B: `configs/qwen3.5-35b-a3b-eagle3.json`. Draft = 1 layer, hidden_size=2048, ~200M params.

```bash
git clone https://github.com/sgl-project/SpecForge.git /home/user/dev/SpecForge
cd /home/user/dev/SpecForge
python3 -m venv ~/venvs/specforge && source ~/venvs/specforge/bin/activate
pip install -e . && pip install sglang[all]

# Online training (target model runs in SGLang during training)
torchrun --standalone --nproc_per_node 1 \
    scripts/train_eagle3.py \
    --target-model-path /home/user/models/Agents-A1 \
    --draft-model-config configs/qwen3.5-35b-a3b-eagle3.json \
    --train-data-path cache/dataset/agents_a1_train.jsonl \
    --output-dir /home/user/models/agents-a1-eagle3-draft \
    --num-epochs 5 --batch-size 1 --learning-rate 1e-4 \
    --max-length 4096 --chat-template qwen \
    --embedding-key model.embed_tokens.weight \
    --target-model-backend sglang \
    --sglang-mem-fraction-static 0.5
# ~1-4 hours on DGX Spark. Produces model.safetensors (~400 MB).
```

**Data requirement:** ~5,000 on-policy samples (generated BY Agents-A1 itself) in ShareGPT JSONL format. Reasoning + coding + agentic + tool-call traces. The draft learns to mimic the target's output distribution from its hidden states.

**DGX Spark budget:** Target model (APEX ~22 GB) + SGLang overhead (~4 GB) + draft training (~2 GB) = ~28 GB RAM. Well within 128 GB.

Full methodology, pitfalls, and acceptance-rate expectations in `references/eagle3-speculative-decoding.md`.

## Starting llama-server

### For knowledge curator / cron ingestion — multi-port fallback

The knowledge curator (`~/.hermes/scripts/knowledge-curator-ingest-llm.py`) and daily orchestrator (`curator-daily.sh`) depend on a local llama-server. Originally hardcoded to port 8092, both scripts now support **multi-port fallback** (8092 → 8102 → 8103 → 8101) with a content-generation health check.

**Critical:** A `/v1/models` check is NOT sufficient to validate an LLM server for extraction. Port 8102 (Qwen3.6-35B APEX) responds to `/v1/models` but generates **empty `content`** when `max_tokens` is low (1200) — reasoning tokens consume the entire budget. The health check sends a test chat completion and verifies non-empty `content` before accepting a server.

Both scripts respect `LLAMA_URL` and `LLAMA_MAX_TOKENS` env vars. For reasoning models, use at least 4000 tokens (the default 1200 is too low — reasoning tokens consume the entire budget, producing empty `content`).

Full start command, port reference table, and recovery procedures are documented in `neo4j-knowledge-graph` → `references/knowledge-curator-cron.md` (Multi-Port Fallback section).

**Pitfall:** The managed start script (`start-llama-qwen.sh --daemon`) can fail under Hermes Agent because `EFFECTIVE_HOME` resolves to the session-isolated home. Start directly with explicit paths instead.

### Health check (with content verification)

```bash
# Basic: is the server up?
curl -fsS -m 3 http://127.0.0.1:8092/v1/models | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['models'][0]['name'])"

# Full: does it actually generate content? (reasoning models may return empty content)
curl -s -m 30 http://127.0.0.1:8092/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say OK"}],"max_tokens":50,"temperature":0}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); c=d['choices'][0]['message'].get('content',''); print(f'Content: [{c}] (empty = reasoning-only, needs higher max_tokens)')"
```

## Abliterated Model Research

When Pavel wants uncensored/abliterated models, follow this methodology:

### ⚠️ WORKFLOW: Research first, present findings, get confirmation, THEN download

1. **DO NOT start downloading immediately.** Pavel wants deep research FIRST.
2. **Present key changes** before any execution — a summary of what changed vs the original plan, what models were chosen and why, memory budget, and what will be downloaded.
3. **Ask for confirmation** before starting downloads or launching services.

### Step 1: Search for abliterated GGUF variants

```bash
# Search HF API for abliterated GGUF repos
curl -s "https://huggingface.co/api/models?search=<MODEL>+abliterated+GGUF&sort=downloads&limit=15" \
  | python3 -c "import sys,json; [print(f'{m[\"id\"]} — {m.get(\"downloads\",0)}') for m in json.load(sys.stdin)]"
```

### Step 2: Check available quantization levels

```bash
# List GGUF files in the repo (not just top-level — expand siblings)
curl -s "https://huggingface.co/api/models/<REPO>?expand[]=siblings" \
  | python3 -c "
import sys,json; data=json.load(sys.stdin)
for s in data.get('siblings',[]):
    if '.gguf' in s.get('rfilename','').lower():
        print(f'  {s[\"rfilename\"]}')
"
```

**CRITICAL:** Do NOT assume filenames. Always verify via API before downloading. Common traps:
- `APEX-I-Quality.gguf` vs `APEX-Quality.gguf` (I-prefix varies by repo)
- `UD-Q4_K_M.gguf` vs `Q4_K_M.gguf` (Unsloth Dynamic prefix)
- Model name variations: `nex-agi_Nex-N2-mini` vs `Huihui-Nex-N2-mini`

### Step 3: Compare abliteration methods

| Method | KL Divergence | Refusals (of 100) | Quality | Notes |
|--------|:-----------:|:-----------------:|---------|-------|
| **Heretic v1.2.0** | **0.0015** | ~10 | 🥇 Best | MPOA decensoring, lowest KL |
| Huihui | ~0.003 | ~15 | 🥈 Good | Standard abliteration |
| Obliteratus | ~0.005 | ~20 | 🥈 Good | Can be combined with Supertune |
| Abliterix | ~0.010 | ~25 | 🥉 OK | Higher KL, more quality loss |

**Heretic is the gold standard** — 6.5× lower KL than Abliterix, 88% fewer refusals.

### Step 4: Check for post-trained variants

Some abliterated models have additional fine-tuning that dramatically improves benchmarks. Key example: **SuperQwen-AgentWorld** adds Supertune post-training → HumanEval+ +59, MBPP+ +44 vs original. Always prefer post-trained abliterated variants when available.

### Step 5: Read the README for compatibility notes

```bash
curl -sL "https://huggingface.co/<REPO>/raw/main/README.md" | head -120
```

Critical compatibility checks:
- APEX quants: "stock llama.cpp, no patches required" ✅
- Nex thinking mode: "requires Nex's patched llama.cpp" — ONLY for think tags, model works fine without
- MTP quants: require llama.cpp with MTP support (v4000+)
- Vision models: need `--mmproj` flag

See `references/abliterated-model-selection.md` for full benchmark tables and the session that discovered the APEX + SuperQwen combination.

### Tracked abliterated model sources (35B MoE class, updated July 2026)

| Base Model | Abliterated Repo | Format | Notes |
|------------|-----------------|--------|-------|
| Agents-A1 (InternScience) | `huihui-ai/Huihui-Agents-A1-abliterated` | safetensors | Fresh (Jul 9). **APEX GGUF available:** `mudler/Agents-A1-APEX-GGUF` (I-Quality 22.8 GB + mmproj 0.9 GB). **FP8 available:** `InternScience/Agents-A1-FP8` (37.7 GB single safetensors). See `references/world-model-comparison.md` for full benchmark analysis. |
| Qwen-AgentWorld-35B-A3B | `iamhsouna/Huihui-Qwen-AgentWorld-35B-A3B-abliterated-GGUF` | Q4_K_M GGUF | Ready for llama.cpp. |
| Nex-N2-mini | huihui-ai (APEX) | APEX-Quality GGUF | Already deployed (~33 GB). |
| Qwen3.6-35B | Heretic v1.2.0 (KL 0.0015) | APEX I-Quality GGUF | Already deployed (~22 GB). |

**Agents-A1 is a strong reasoning-replacement candidate** — dominates Qwen3.6-35B on 14/15 published benchmarks (GAIA 96 vs 78.6, IFBench 80.6 vs 64.4, Seal0 56.4 vs 38.7). Native tool calling, multimodal. But **NOT a coding model** — does not report SWE-Bench/Pro or Terminal-Bench; "coding capabilities may require a much larger model" (HF discussions). Full head-to-head table and deployment specs in `references/world-model-comparison.md`.

## OOM Killer Diagnosis

When Hermes Desktop (Electron) or other GUI apps crash unexpectedly during model operations, **always check for OOM killer first** before investigating app bugs. Symptoms: sudden window disappearance, process restarts, no crash dump in Crashpad.

### Quick Check

```bash
# Check kernel OOM kills in a time window
journalctl --since "2026-07-02 20:00:00" --until "2026-07-02 22:00:00" --no-pager | grep "Out of memory: Killed"

# Check oom_score_adj of Hermes processes (300 = prime target)
for pid in $(pgrep -f "Hermes"); do
  echo "PID $pid: oom_score_adj=$(cat /proc/$pid/oom_score_adj 2>/dev/null), oom_score=$(cat /proc/$pid/oom_score 2>/dev/null)"
done
```

### Why Hermes is the First Victim

Electron processes have `oom_score_adj=300` (high), making them primary OOM-killer targets. When `llama-perplexity`, `llama-imatrix`, or `llama-quantize` loads a large model (16+ GB RSS), the kernel prefers killing Hermes over the compute process (which often has `oom_score_adj=200`).

### Correlating Crashes with Session Activity

```bash
# 1. Find the session timestamp range in state.db
python3 -c "
import sqlite3, time
db = sqlite3.connect('~/.hermes/state.db')  # expand ~
msgs = db.execute(\"SELECT timestamp FROM messages WHERE session_id='SESSION_ID' ORDER BY id\").fetchall()
print(f'First: {time.strftime(\"%H:%M:%S\", time.localtime(msgs[0][0]))}')
print(f'Last:  {time.strftime(\"%H:%M:%S\", time.localtime(msgs[-1][0]))}')
"

# 2. Match OOM kills to that window
journalctl --since "2026-07-02 20:00:00" --until "2026-07-02 22:00:00" --no-pager | grep -E "Out of memory|oom-killer"

# 3. Check what terminal commands the session was running (look for llama-* binaries)
python3 -c "
import sqlite3, json
db = sqlite3.connect('~/.hermes/state.db')
for m in db.execute(\"SELECT tool_calls FROM messages WHERE session_id='SESSION_ID' AND role='assistant'\").fetchall():
    if m[0] and 'llama' in m[0].lower(): print(m[0][:300])
"
```

### Tracing Crashes Across Multiple Reboots

When OOM crashes are severe enough to reboot the machine (common with vLLM + BF16 models on DGX Spark — see `speculative-decoding` skill pitfall #17), use `journalctl --list-boots` to trace the full timeline:

```bash
# List all boots — shows crash/reboot timeline
journalctl --list-boots

# For each boot period, check for OOM kills and memory pressure
journalctl -b -2 --no-pager | grep -iE "oom|out of memory|killed process|invoked oom"
journalctl -b -1 --no-pager | grep -iE "oom|out of memory|killed process|invoked oom"
journalctl -b 0 --no-pager | grep -iE "oom|out of memory|killed process|invoked oom"

# Memory pressure warning sign — appears for hours before a crash
journalctl -b -2 --no-pager | grep "Under memory pressure" | tail -20

# Last lines before a crash (what killed the machine)
journalctl -b -2 --no-pager | tail -20
```

Key pattern: "Under memory pressure, flushing caches" appearing every ~20 seconds for hours = system is swapping to death. Next step is OOM kills, then full crash. The `oom_score_adj` column in OOM output shows why Hermes (300) and Chromium (200-300) die first — the kernel preferentially kills high-score processes.

Full forensic walkthrough (timeline, memory budget, oom_score_adj analysis) in `references/oom-killer-forensics.md`.

## Pitfalls

- `du -sh ~/.lmstudio/models/*/` shows per-author totals, not per-model. Use `*/*/` for per-model sizes.
- LM Studio GUI may auto-download models while open — check for unexpected new author dirs if totals don't add up.
- `--no-mmap --direct-io` on llama.cpp means the model file is NOT counted in process RSS — intentional on Jetson to avoid GPU memory pressure.
- Llama.cpp models in `/home/user/dev/llama.cpp/models/` are just vocab files (~69 MB) — not actual weights.
- On Jetson ARM64, ctranslate2 has 0 CUDA devices (no pip CUDA support for aarch64). GPU unusable for STT via faster-whisper; use CPU.
- **CRITICAL — Quantization vs parameter count:** A large model in extreme quantization (IQ2_XS, ~2.5 bit) is often WORSE than a smaller model in Q8_0 (near-lossless). Big model + bad quant < smaller model + good quant. Never recommend a 397B model in IQ2_XS when a 35B model in Q8_0 fits the hardware. The quality degradation from extreme quantization eats the parameter-count advantage. See `references/quantization-quality-data.md` for the full benchmark table from arXiv 2601.14277.
- **Model comparison data sources:** For deep model comparisons, the reliable data-gathering pipeline is: HF API (`/api/models/...`) for metadata → README raw for benchmark tables → arxiv paper → `pdftotext` → `grep` for specific benchmark numbers. See `references/model-comparison-technique.md`.
- **`hf download` fails silently with safetensors shards** — even with `--include` patterns, it often downloads only metadata (config.json, README) and skips model weights. Verified June 2026: `hf download` on Jiunsong/SuperQwen fetched 5 small files (9 GB) but skipped all 21 safetensors shards. Fix: enumerate shards and download with `curl -sS -L -C -` from HF CDN. Loop over `model-00001-of-00021.safetensors` etc. `curl -C -` supports resume on connection drop.

Reliable download pattern for safetensors models:
```bash
DEST="/home/user/models/Model-bf16"
BASE="https://huggingface.co/USER/REPO/resolve/main"
SHARDS=21  # from HF API: /api/models/USER/REPO?expand[]=siblings
for i in $(seq -w 1 $SHARDS); do
  F="model-000${i}-of-$(printf '%05d' $SHARDS).safetensors"
  curl -sS -L -C - "$BASE/$F" -o "$DEST/$F" && echo "[$i/$SHARDS] OK" || echo "[$i/$SHARDS] FAIL"
done
# When bg process gets SIGTERM mid-download: just re-run. curl -C - skips completed shards and resumes partial ones.
# PARALLEL BATCHES FOR LARGE MODELS: sequential loops in background may die (SIGTERM on GUI restart).
# Split into parallel batches of 4-5 shards each:
#   Batch 1: shards 01-05, Batch 2: 06-10, Batch 3: 11-15, Batch 4: 16-21
# Each batch is its own background process with notify_on_complete=true.
# curl -C - handles resume if a batch is interrupted mid-shard.
```
- **`curl -#` progress bar kills background processes** — the progress bar needs a real TTY. Use `-sS` (silent+errors) in background/automated contexts.
- **Abliterated Nex has NO Q8_0** — only APEX (Quality/Balanced/Compact) and Q4_K_M are available. APEX-Quality is the best option at ~33 GB.
- **Nex APEX-Quality is ~33 GB** (not ~21 GB like Qwen APEX) — APEX-Quality (without imatrix) uses higher precision per tensor. APEX I-Quality (with imatrix) is ~21 GB. Both are standard GGUF, loadable in stock llama.cpp.
- **AgentWorld: SuperQwen > huihui** — Jiunsong's Supertune post-training adds massive benchmark improvements (+59 HumanEval+) over plain huihui abliteration.
- **CRITICAL — llama-swap config syntax:** `unload: false` and top-level `matrix:` key do NOT exist in llama-swap v229/v234 — they are silently ignored. Use `groups` + `swap: false` to keep models co-resident. Use `${PORT}` macro (from `startPort`) instead of hardcoded ports. Use `hooks.on_startup.preload` to load at startup. See `references/dgx-spark-deployment.md` Configuration section for correct YAML.
- **CRITICAL — memlock on DGX Spark:** Default `ulimit -l` is ~15 MB. `--mlock` silently fails without `memlock unlimited`. Set `/etc/security/limits.d/llama.conf` with `* soft/hard memlock unlimited`, or use systemd unit with `LimitMEMLOCK=infinity`.
- **CRITICAL — llama-swap download URL:** `releases/latest/download/llama-swap_234_linux_arm64.tar.gz` mixes `latest` redirect with hardcoded version — can 404 and produce a 9-byte "Not Found" text file. Use `releases/download/v234/...` (specific) or `releases/latest/download/llama-swap_linux_arm64.tar.gz` (no version). Always verify with `file` command after install.
- **nvidia-smi "Not Supported" for memory on DGX Spark** — EXPECTED on unified memory architecture (UMA). GPU memory is not separately attributable. Use `free -h` for total system memory. `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1` env var is ESSENTIAL — without it, llama.cpp underestimates available memory and OOMs.
- **qwen35moe known llama.cpp bugs:** KV cache reuse is silently disabled for hybrid models (every request = full prefill recompute). Recurrent state (DeltaNet) is not persisted between requests. Context checkpoint restore is broken for hybrid models. These are upstream issues (#18497, #24043, #22384) — 256K context gives no caching benefit. Use 64K for realistic orchestrator workloads.
- **Always verify GGUF metadata before launching** — architecture, block_count, expert_count, context_length. A Python GGUF header reader script is in `references/dgx-spark-deployment.md` (GGUF Metadata Verification section). Verified: Nex/SuperQwen have 40 blocks, 256 experts; Qwen3.6 has 753 tensors (vs 733 for Nex/SuperQwen). For qwen35moe models, ALSO check tensor quantization types: if SSM tensors use Q8_0, the model will produce garbage. Use `pip install gguf` + the script in `references/q8-ssm-garbage-tokens.md` to inspect.
- **`huggingface-cli` is DEPRECATED.** Use `hf` CLI instead: `curl -LsSf https://hf.co/cli/install.sh | bash`. Old `huggingface-cli` returns errors on modern HF repos.
- **HF filenames ≠ what you expect.** Always verify exact filenames via `/api/models/<repo>?expand[]=siblings` BEFORE downloading. APEX repos use `APEX-Quality` (no `I-` prefix) for some models but `APEX-I-Quality` for others. Unsloth repos use `UD-` prefix on dynamic quants. Assumed filenames waste download time.
- **safetensors ≠ GGUF.** Models in `/home/user/models/` may be original safetensors (114 GB) — useless for llama.cpp. Always check: `file <model>` returns "ELF" for GGUF, "data" for safetensors. Delete safetensors in models/ after confirming GGUF copies exist.
- **Memory budget MUST include KV cache. CRITICAL for MoE models:** Qwen3.5/Qwen3.6 MoE (35B/3B) have only 10 attention layers out of 40 total (3:1 DeltaNet:Attention ratio) — the remaining 30 are DeltaNet (Gated DeltaNet linear-attention) with near-zero state overhead. **Verified from GGUF metadata: `block_count=40`, not 48 as some docs claim. `expert_count=256`, not 128.** KV cache is ~4× smaller than a naive layer-count estimate. With Q8_0 KV cache: 256K context ≈ **3 GB** (not 8 GB!), 64K ≈ **1.5 GB**. Always add 1-2 GB per llama-server instance for overhead. See `references/moe-kv-cache-sizing.md` for full calculation.
- **`/workspace` is not writable on Pavel's DGX Spark** — the APEX pipeline defaults `WORK_DIR` to `/workspace/data/apex`. Use `--work-dir /home/user/models/apex-work` instead, or set `WORK_DIR=/home/user/models/apex-work` env var. Eval data goes under `/home/user/models/eval-data/`.
- **CRITICAL — Never requantize.** Quantizing an already-quantized model (`--allow-requantize`) severely degrades quality. Always start from BF16/FP16. `llama-quantize` warns: "WARNING: this can severely reduce quality compared to quantizing from 16bit or 32bit!" If you only have a Q4_K_M file and need Q8_0 — download the BF16 weights and quantize fresh.
- **IQ3_XXS without imatrix is BROKEN.** IQ-series (IQ2_XXS through IQ4_NL) uses importance-matrix-aware non-linear quantization. Running `llama-quantize model.gguf output.gguf IQ3_XXS` without `--imatrix` produces catastrophic quality loss. Always generate imatrix first.
- **MTP phantom layers:** Abliterated Qwen models may have `mtp_num_hidden_layers: 1` in config but no MTP weights. Add `--no-mtp` to `convert_hf_to_gguf.py` to avoid "missing tensor blk.40.*" errors. Verify with: check `config.json` for `mtp_num_hidden_layers` AND `model.safetensors.index.json` weight_map for `mtp` keys.
- **Root-owned llama.cpp:** If the repo is owned by root (Docker-created), clone a fresh `--depth 1` copy for Python scripts. Keep the root-owned build for binaries.
- **Partial shards from parallel downloads:** After downloading safetensors shards in parallel, verify all sizes — truncated shards (31 MB vs 3 GB) cause `mmap length is greater than file size`. Delete and re-download truncated shards from scratch.
- **`hf download` silently skips files:** Use explicit `--include "*.safetensors" --include "*.json" --include "*.jinja"` or download metadata files (tokenizer.json, tokenizer_config.json) separately via curl.
- **APEX `quantize.sh` syntax:** Use `--profile i-quality` (NOT `--i-quality`). Input/output are positional args, NOT flags. Set `NUM_LAYERS=40` env var (NOT `--layers 40` flag). Must set `LLAMA_CPP_DIR` explicitly. `NUM_LAYERS=40` for Qwen3.5/3.6-35B MoE (confirmed via `config.json` → `num_hidden_layers`). Full example: `NUM_LAYERS=40 LLAMA_CPP_DIR=/home/user/dev/llama.cpp/build/bin ./scripts/quantize.sh --profile i-quality --imatrix <file> <input.gguf> <output.gguf>`.
- **Imatrix timing on DGX Spark:** For 35B MoE with 256K tokens: ~23 minutes (CPU-only, `-ngl 0`). Much faster than dense 70B models on x86 (2-5 hours).
- **PTQ ≠ QAT — quantization does NOT need retraining.** Users sometimes ask "will I need to fine-tune after quantization?" The answer is no. llama.cpp and APEX use Post-Training Quantization (PTQ) — a mathematical compression step that rounds weights to lower precision. All post-training improvements (Supertune, abliteration, fine-tunes) are preserved. Quantization-Aware Training (QAT) is a different technique that trains the model to tolerate low precision, requiring full GPU training. PTQ is sufficient — APEX I-Quality already beats FP16 on downstream benchmarks without any retraining.
- **llama.cpp repo owned by root → conversion scripts can't be edited.** On Pavel's DGX Spark, `/home/user/dev/llama.cpp/` and its build directory are owned by root (created during initial Docker-based setup). This means `convert_hf_to_gguf.py` and `conversion/base.py` can't be patched in-place, and `cmake` rebuilds fail with permission errors. **Workaround:** copy conversion files to a writable location (`/tmp/gguf-convert`), apply any needed patches there, and run from the copy: `cp convert_hf_to_gguf.py conversion/ gguf-py/gguf/ /tmp/gguf-convert/`. The pre-built binaries (`llama-quantize`, `llama-imatrix`, `llama-perplexity`) are unaffected — only the Python conversion scripts need this treatment.
- **`convert_hf_to_gguf.py` requires ALL model files, not just safetensors.** Missing `tokenizer.json` causes `NotImplementedError: BPE pre-tokenizer was not recognized`. Missing `model.safetensors.index.json` causes weight map loading failures. After downloading shards, always also fetch: `tokenizer.json`, `tokenizer_config.json`, `model.safetensors.index.json`. Confirmed: `curl` download scripts that only target `*.safetensors` patterns silently skip these small-but-critical files.
- **CRITICAL — `llama-perplexity` / `llama-imatrix` inside Hermes terminal can OOM-kill Hermes itself.** These tools load the entire model into RAM (16+ GB for 20-35B models). When run via `terminal(background=true)` inside Electron, the combined memory pressure (model + 20 Docker containers + 4 Electron apps) triggers the Linux OOM killer, which preferentially targets Hermes (`oom_score_adj=300`). **Mitigation:** (1) Run heavy llama.cpp tools in a separate SSH/tmux session, NOT inside Hermes terminal. (2) If must use Hermes terminal, stop non-essential Docker containers first (`docker stop dify-* openhands`). (3) Use `-ngl 0` for CPU-only or `-c 128` for smaller context to reduce peak RSS. (4) Check `free -h` and `swapon --show` before launching — if swap is >50% full, you're already on the edge. See `references/oom-killer-forensics.md` for full diagnosis workflow.
- **Never run PPL benchmarks in parallel with imatrix.** Both load large models into RAM. imatrix (F16, 65GB) + PPL (APEX, 22GB) = 87GB contention → swap thrashing, 2× runtime. Run sequentially: imatrix first, then PPL/eval.
- **CRITICAL — Q8_0 on SSM/DeltaNet tensors GENERATES GARBAGE TOKENS.** Verified July 2026: SuperQwen-AgentWorld Q8_0 (35 GB) on qwen35moe architecture emits only token ID 14 (`/`) repeatedly, regardless of prompt or temperature. Root cause: Q8_0 block quantization (1 scale per 32 elements) creates systematic rounding errors in SSM recurrent layers that compound exponentially. APEX (Q6_K on SSM) and Q4_K_M (Q4_K on SSM) work correctly. **Do NOT use Q8_0 as a KL reference for qwen35moe models.** Use Q4_K_M (20 GB) or APEX I-Quality (22 GB) as reference instead. Full tensor-type analysis in `references/q8-ssm-garbage-tokens.md`.
- **THINKING MODELS — `content` empty, `reasoning_content` has text.** Thinking models (Agents-A1, Qwen with `--jinja`) generate ALL output tokens as `reasoning_content` (thinking) before producing actual `content`. Symptom: `choices[0].message.content == ""` but `reasoning_content` has text. For trivial queries like "Say hi", the model spends 568 tokens on reasoning before the 33-character response — an 18:1 ratio. For Hermes queries with full system prompts (75K chars ≈ 20K tokens), reasoning can consume thousands of tokens. 

  **🔴 Hermes retry loop amplifies this:** When `content` is empty but `reasoning_content` is present:
  1. `_is_thinking_only_message()` in `conversation_loop.py` detects it
  2. Thinking prefill retry (×2): Hermes asks model to "continue" — model generates MORE reasoning, each retry adding previous reasoning to context
  3. Empty content retry (×3): Hermes retries the request — same result
  4. After 5 retries → `final_response = "(empty)"` → user sees nothing

  **Fix — TWO layers (belt and suspenders):**

  **Layer 1 (server-level, SIMPLEST):** Add `--reasoning off` to llama-server startup:
  ```bash
  llama-server -m model.gguf ... --reasoning off --jinja
  ```
  This disables thinking at the server level regardless of what the client sends. Verified July 2026: model responds in 0.6s with normal content, zero `reasoning_content`.

  **Layer 2 (config-level, backup):** Add `extra_body` to Hermes `custom_providers`:
  ```yaml
  custom_providers:
    - name: local
      extra_body:
        chat_template_kwargs:
          enable_thinking: false
  ```

  **⚠️ Do NOT increase context as a fix.** The old workaround of increasing `-c` from 32K to 256K doesn't solve the root cause — the model still generates reasoning tokens first, just with more budget. With full Hermes system prompts, the reasoning budget explosion is worse. The correct fix is `--reasoning off`, not larger context.

  **Diagnosis pipeline — 4 layers, test each in order:**
  1. Direct llama-server (bypass LiteLLM): `curl localhost:8102/v1/chat/completions` → confirms model itself works
  2. Via LiteLLM proxy: `curl localhost:4000/v1/chat/completions -H "Authorization: Bearer sk-local"` → confirms routing
  3. Hermes CLI inside container: `python3 -c "from run_agent import AIAgent; ..."` → confirms Hermes→model end-to-end
  4. Dashboard WS: `prompt.submit` → confirms full stack with observer/gateway
  Each layer isolates the next. If step 3 works but step 4 doesn't, the observer is the bottleneck.

  Full recipe with Hermes code paths and evidence in `references/thinking-model-diagnosis.md`.

  **Diagnosis pipeline — 4 layers, test each in order:**
  1. Direct llama-server (bypass LiteLLM): `curl localhost:8102/v1/chat/completions` → confirms model itself works
  2. Via LiteLLM proxy: `curl localhost:4000/v1/chat/completions -H "Authorization: Bearer sk-local"` → confirms routing
  3. Hermes CLI inside container: `python3 -c "from run_agent import AIAgent; ..."` → confirms Hermes→model end-to-end
  4. Dashboard WS: `prompt.submit` → confirms full stack with observer/gateway
  Each layer isolates the next. If step 3 works but step 4 doesn't, the observer is the bottleneck.
  
  **Diagnostic test — verify thinking is disabled:**
  ```bash
  curl -s http://localhost:8102/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"model":"agents-a1","messages":[{"role":"user","content":"Say hi"}],"max_tokens":100}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); m=d['choices'][0]['message']; print(f'content=[{m.get(\"content\",\"\")}], reasoning_len={len(m.get(\"reasoning_content\",\"\"))}')"
  # BEFORE fix: content=[], reasoning_len=3498
  # AFTER fix:  content=[Hi!], reasoning_len=0
  ```
- **INJECT_HERMES_CONFIG conflict with providers.local.** Old `start-llama.sh`'s `inject_hermes_config()` writes a `custom_providers:` dict block into `config.yaml`. This conflicts with v12+ `providers:` format (Hermes warns: "custom_providers is a dict — must be a YAML list"). Fix: remove the function entirely from `start-llama.sh`. Use `providers.local` (keyed dict → LiteLLM proxy) instead. Also update all `~/.hermes/agents/plan3/*.md` frontmatter from `provider: custom:local` → `provider: local`.
- **eval.sh HOME path pitfall:** Under Hermes Agent, `HOME=/home/user/.hermes/home` (not `/home/user`). eval.sh defaults `EVAL_DATA_DIR` to `$HOME/.cache/apex-quant/eval-data`, which resolves wrong. Always pass `EVAL_DATA_DIR=/home/user/.cache/apex-quant/eval-data` explicitly. Also create symlink: `mkdir -p /home/user/.cache/apex-quant/wikitext-2-raw && ln -sf /home/user/.cache/apex-quant/eval-data/wiki.test.raw /home/user/.cache/apex-quant/wikitext-2-raw/wiki.test.raw` — eval.sh looks for wikitext at `${EVAL_DATA_DIR}/../wikitext-2-raw/wiki.test.raw`.
- **eaddario parquet files are single-row giant texts** (code_medium.parquet = 1 row, 37MB). Must split into ~2KB chunks before sampling for calibration corpus. Use `pd.read_parquet()` → `str(df[col].iloc[0])` → split by newlines into paragraphs → group into 2KB chunks.
- **xLAM function-calling-60k is gated** — requires HF token. `NousResearch/hermes-function-calling-v1` and `glaiveai/glaive-function-calling` work without token. See `references/agentic-calibration-corpus.md` for download + formatting instructions.
- **Imatrix PPL varies by corpus composition, not model quality.** A corpus with function calling JSON and multi-turn chat (v3, PPL=3.349) will have higher imatrix PPL than pure code (v1, PPL=3.004) because FC/chat patterns are inherently harder to predict than code. This is EXPECTED — imatrix optimizes weight importance distribution, not PPL minimization. The final quantized model PPL (on wikitext) is statistically identical between v1 and v3 (5.868 vs 5.870, Δ within ±0.036 error).
- **APEX v1 vs v3 (agentic corpus) are statistically identical on standard benchmarks.** 42% FC data in calibration corpus does NOT improve HellaSwag/MMLU/ARC (all within ±2.5% at 400 tasks). The benefit is theoretical: calibration matches inference-time token patterns for agentic use. Standard benchmarks don't measure tool-calling accuracy. Full results in `references/superqwen-apex-benchmark-results.md`.
- **CRITICAL — Always sanity-check model output after loading.** A model can load without errors and still generate garbage (repeated single token, empty content, or `////`). After `llama-server` starts, send a simple prompt (`"What is 2+2?"`) and verify the response is coherent BEFORE trusting the model. Check both `/v1/completions` (raw) and `/v1/chat/completions` (templated) — chat template issues can cause empty `content` with text in `reasoning_content`. Test procedure: (1) send raw completion, check for repeated single char, (2) send chat completion, check `content` is non-empty, (3) if `content` is empty but `reasoning_content` has text, the model works but the chat template needs `--jinja` flag. Full test methodology in `references/q8-ssm-garbage-tokens.md`.
- **CRITICAL — Memory pressure causes garbage tokens in unified memory.** Running 4 models simultaneously (~100 GB in 121 GB RAM with Docker + Electron) can corrupt model weights in DGX Spark unified memory, producing the same `////` garbage as Q8_0-on-SSM. A model that works alone may produce garbage when 3+ models share memory. Always test each model individually first, then test in multi-model configuration. If a working model starts producing garbage in multi-model mode, reduce to fewer simultaneous models or stop Docker containers.
- **CRITICAL — `--no-mmap` is MANDATORY for multi-model serving on DGX Spark.** On DGX Spark unified memory, llama-server defaults to `--mmap` (memory-maps GGUF files). When multiple llama-server processes mmap model files simultaneously, the CUDA UVA driver cannot isolate mmap mappings between CUDA contexts, causing silent data corruption: models load without errors (`/v1/models` responds) but generate garbage tokens (`////`, `????`). **Only the first-loaded model works with mmap.** Fix: add `--no-mmap` to EVERY llama-server instance — loads model weights into memory explicitly instead of mmap'ing. Verified July 2026: all 3 models (nex 33GB, qwen 22GB, world 22GB) work simultaneously with `--no-mmap`. Independent confirmation: ai-girls.org DGX Spark guide and NVIDIA Developer Forums both cite mmap issues on this platform. `--no-mmap` also measurably faster on DGX Spark (avoids unnecessary page faults on unified memory). Full experimental data in `references/multi-model-contention.md`.
- **Pavel prefers simple sh scripts, NOT systemd.** For multi-model serving, use a plain `start-llama.sh` script with `start|stop|status|test` subcommands — not systemd units. The script should: (1) kill existing llama-server processes, (2) start each model sequentially with health-check wait loop, (3) run an auto-test after loading (check for garbage tokens), (4) launch a daemon watchdog via `setsid`. Template at `templates/start-llama.sh`.
- **CRITICAL — Watchdog `bash -c '...'` silently breaks variable expansion.** When writing a daemon watchdog that restarts dead models, NEVER use `nohup bash -c '...'` with inline single-quoted strings. Variables like `${MODEL_NEX}`, `${PORT_NEX}` inside the single-quoted block are NOT expanded — they become empty strings. The watchdog tries to restart models with `llama-server -m ""` → instant crash → 30s later it tries again → infinite crash loop. **Symptom:** watchdog log shows `WARNING: nex dead, restarting...` every 30s but models never come back. **Fix:** write the watchdog script to a FILE via unquoted heredoc — variables expand AT WRITE TIME, runtime variables escaped with `\$`: `cat > "$wd_script" <<EOF ... "$MODEL_NEX" ... \${!MODELS[@]} ... EOF`. Then launch with `setsid bash "$wd_script" &`. Template at `templates/start-llama.sh` → `start_watchdog()`. Verified July 2026.
- **CRITICAL — Use `setsid`, NOT just `disown`, for daemon model processes.** `disown` removes a process from the shell's job table but does NOT prevent SIGHUP from reaching it when the parent script/terminal exits. `setsid` creates a new session (new session ID, no controlling terminal), fully detaching the process. Always use `setsid "$LLAMA_SERVER" ... &` for model launch and `setsid bash "$wd_script" &` for the watchdog. Combine with `disown` for belt-and-suspenders. Verified July 2026: models survived after `start-llama.sh` exited because `setsid` detached them.
- **CRITICAL — iptables-nft fails in Alpine containers on ARM64 DGX Spark.** `docker run --rm --privileged --network host alpine sh -c 'iptables ...'` fails with `iptables: Failed to initialize nft: Protocol not supported` on DGX Spark (ARM64). The nft backend in Alpine's iptables package is incompatible with the kernel's netfilter subsystem on this platform. **Fix:** prefer host iptables via `sudo -n iptables ...` (if passwordless sudo is available), or print manual instructions for the user to run. Do NOT rely on the Alpine container approach for UFW rule injection on DGX Spark. The `inject_firewall_rules()` function in `templates/start-llama.sh` handles this correctly.
- **CRITICAL — `--host 0.0.0.0` required for Docker connectivity.** llama-server defaults to `127.0.0.1` (loopback only). Docker containers connect via the bridge gateway (172.17/18.0.1), not loopback. Without `--host 0.0.0.0`, Docker containers cannot reach the server even if UFW allows the port. Always use `--host 0.0.0.0` when serving models that LiteLLM (or any Docker service) needs to access.
- **CRITICAL — UFW blocks Docker → host ports by default.** The host runs UFW with `INPUT policy DROP`. Only ports with explicit `ufw-user-input` rules are reachable from Docker. To add ports without sudo: `docker run --rm --privileged --network host alpine sh -c "apk add iptables && iptables -I ufw-user-input 1 -s 172.18.0.0/16 -p tcp --dport PORT -j ACCEPT"`. Rules don't persist across reboots — `start-llama.sh` auto-injects them. See `references/docker-ufw-firewall-fix.md` for full diagnosis. Key technique: `--privileged --network host` (not just `--cap-add=NET_ADMIN`) is needed to see/modify HOST iptables from a container.
- **CRITICAL — Shell quoting in `docker run sh -c '...'` UFW injection.** When the `sh -c` argument is single-quoted, shell variables (`$port`, `$net`) are expanded by the INNER sh (correct). But if you "escape" single quotes with the `'"'"'$var'"'"'` pattern, the OUTER bash expands `$var` (which doesn't exist), producing literal errors like `iptables: invalid port/service '$port' specified`. Use plain `"$var"` inside single-quoted `sh -c '...'` — the single quotes protect variables from the outer shell, and the inner sh expands them correctly. Never use `'"'"'` escaping for variables that should be expanded inside the container.
- **CRITICAL — Background process SIGTERM kills models.** `start-llama.sh` launched via Hermes `terminal(background=true)` receives SIGTERM (exit code 143) when the Hermes session ends or a new turn starts. The watchdog dies, taking all llama-server instances with it. For persistent model serving: (1) use `nohup`-disowned watchdog (`nohup bash ./start-llama.sh watchdog </dev/null >/dev/null 2>&1 &`), (2) run the main script synchronously first to start models, (3) then launch watchdog separately. `setsid` alone does NOT prevent SIGTERM from Hermes terminal background processes — the watch...
- **Always kill existing llama-server BEFORE testing a new model.** Running `llama-server` while another instance is already loaded causes port conflicts, memory contention, and unreliable test results. Before each model test: `for pid in $(pgrep -x llama-server); do kill -9 $pid; done; sleep 3` — then verify with `pgrep -x llama-server` (should be empty) and `free -h` (memory should be freed). Only then start the next model. SIGTERM may not kill llama-server reliably — use `kill -9` (SIGKILL).
- **Agents-A1 is NOT a coding model.** Despite dominating Qwen3.6-35B on 14/15 agentic/reasoning benchmarks, Agents-A1 does NOT report SWE-Bench, SWE-Pro, or Terminal-Bench. Community note: "coding capabilities may require a 397B model." Use Agents-A1 for reasoning/search/science agent roles, NOT for coding/SWE/terminal. Keep Nex-N2-mini (SWE-Bench 74.4, Terminal-Bench 60.7) for coding. See `references/world-model-comparison.md` for the full head-to-head comparison.
- **Model routing gap in Plan3 — Qwen→Agents migration procedure.** Plan3's orchestrator has an architectural split: the local Model Routing Table lists models but actual `delegate_task` calls almost universally use cloud models. When converting plan3 from Qwen3.6 to Agents-A1 (or any model swap), update THREE sections in `~/.hermes/agents/plan3.md`:

  1. **Model Routing Table** (lines ~146-158): Replace model name, add real benchmarks (not placeholder). Agents-A1 example: GAIA 96.0, IFBench 80.6, IFEval 94.8, BrowseComp 75.5, Seal0 56.4.
  2. **Pipeline Modes** (lines ~166-175): Replace model references in Fugu/Fusion pipelines.
  3. **Routing Rules** (lines ~258-271): Add a LOCAL routing table alongside CLOUD table — shows which local model handles which agent roles. Include Hermes model aliases (`/model custom:local:agents`, etc.) and server info.
  
  Also update `~/dev/llama/roles.md` (29-agent role distribution) and `~/dev/llama/start-llama.sh` (server launch script). The migration is a 3-file cross-reference pattern: plan3.md (orchestration), roles.md (distribution), start-llama.sh (serving). AGENTS-A1 PITFALL: it is NOT a coding model — keep Nex-N2-mini for SWE/terminal roles.
- **LM Studio NVML error on Jetson/DGX Spark (GB10 unified memory).** LM Studio reports: `Could not calculate augmented gpu offload layers to respect strict GPU VRAM cap. Error: Cannot obtain free VRAM bytes for GPU0: NVIDIA GB10`. Root cause: LM Studio uses NVML to query free VRAM, but on unified memory architecture (UMA) there is no discrete VRAM — GPU shares system RAM. NVML returns 0 or errors. **Workaround:** disable auto GPU offload in LM Studio Hardware Settings, set GPU offload layers manually (`max` or `99`). For reliable serving on GB10, prefer `llama-server` CLI directly — it handles unified memory correctly (especially with `--no-mmap`). This is a permanent platform limitation, not a fixable config issue.
- **LiteLLM bridge → host unreachable: recreate with `--network host`.** When UFW iptables rules aren't injectable (no sudo, no privileged container), the definitive fix is recreating the LiteLLM container with `--network host`. Bridge-mode containers cannot reach host services; host-mode shares the host's network namespace so `localhost:8000` = host's vLLM. Steps: (1) `docker stop litellm && docker rm litellm`, (2) extract API keys via `docker exec ... base64` pipeline (see `hermes-custom-providers` → `references/redaction-workaround.md`), (3) update `api_base` in config from `172.18.0.1` → `localhost`, (4) update `database_url` from `litellm-db:5432` → `localhost:5432`, (5) `docker run -d --network host ...`. Full recipe: `hermes-custom-providers` → `references/direct-vllm-bypass.md` (\"Root-Cause Fix\" section).
- **`convert_hf_to_gguf.py` TypeError on `target_model_dir`/`fp8_as_q8`.** API drift bug: the script passes kwargs that `ModelBase.__init__()` doesn't accept. Fix: `sed -i '/target_model_dir=/d; /fp8_as_q8=/d' convert_hf_to_gguf.py`. If file is root-owned, the script itself (`convert_hf_to_gguf.py`) may still be writable by `pavel` — edit it directly to remove those two kwargs. Full fix details in `llama-cpp` skill → `references/troubleshooting.md`.
- **CRITICAL — KV cache quantization (`-ctk q8_0 -ctv q8_0`) REQUIRES flash attention.** Without `-fa 1` (llama-bench/CLI) or `--flash-attn on` (llama-server), context creation fails: `llama_init_from_model: V cache quantization requires flash_attn` → `error: failed to create context`. This is a hard requirement, not an optimization. ALL of Pavel's llama-server instances use `--cache-type-k q8_0 --cache-type-v q8_0` for KV cache savings — always pair with `--flash-attn on` (or `-fa 1` in llama-bench). Note: `llama-bench` uses single-dash flags (`-fa`, `-mmp`, `-ctk`), while `llama-server` uses long flags (`--flash-attn`, `--mmap`, `--cache-type-k`).
- **CRITICAL — CUDA Graph memory leak on GB10 with qwen35moe.** llama.cpp caches CUDA graphs for performance. On qwen35moe (Nex, Agents-A1, SuperQwen — all 3 of Pavel's models), the hybrid attention/DeltaNet architecture creates a new graph every 2 tokens instead of every 256. On unified memory (GB10), this accumulates in system RAM: ~500 graphs × 30 MB = 15 GB during a single generation. Eviction sweeps every 5s help but don't prevent growth during active inference. **Fix:** `export GGML_CUDA_DISABLE_GRAPHS=1` before launching llama-server — disables CUDA graphs entirely, stops memory growth. −5-10% tok/s tradeoff. GB10 (SM 12.1) is NOT auto-excluded from graph capture. Confirmed in llama.cpp issues #20315 (GB10-specific) and #21265. Full analysis in `references/cuda-graph-memory-leak.md`.
- **CRITICAL — `-fa` now REQUIRES an explicit value (not a bare flag).** In newer llama.cpp builds (b9606+, June 2026), `-fa` / `--flash-attn` expects `on|off|auto` — it is no longer a boolean flag. If you write `-fa --mlock`, the `--mlock` gets consumed as the value of `-fa`, producing: `error: unknown value for --flash-attn: '--mlock'`. Always write `--flash-attn on --mlock` or `-fa on --mlock`. The `start.sh` script in `/home/user/dev/codemes_apk/start.sh` has this bug on line 224 — `-fa --mlock` crashes the server. Use `-fa auto --mlock` if you want auto-detection with mlock.
- **CRITICAL — Always set `--flash-attn on` explicitly, NOT `auto`.** The `auto` default MAY work on CUDA but is not guaranteed. Without flash attention, KV cache quantization silently falls back to f16 (2× memory per slot). Combined with q8_0 KV cache, the explicit `--flash-attn on` flag is a hard requirement verified in llama.cpp source: `llama_init_from_model: V cache quantization requires flash_attn`. Every llama-server instance in `start-llama.sh` should have `--flash-attn on`.
- **`-np 2` — limit parallel slots to cap KV cache memory.** Default `-np -1` (auto) may create 4-8 slots based on CPU count. Each slot reserves KV cache. With 256K context and q8_0: ~3 GB per slot. Set `-np 2` to limit to 2 concurrent requests and cap KV cache at ~6 GB per model (vs. ~12-24 GB with auto). For Pavel's 3-model setup with 128 GB total, this is the difference between OOM and stable operation.
- **Gemma4 31B F16 on GB10 benchmarks (July 2026):** `pp128 = 154.44 tok/s`, `tg64 = 1.85 tok/s` — generation is extremely slow for F16 (57 GiB). Needs quantization (Q8_0 or Q4_K_M) for usable chat speeds. Architecture: `Gemma4ForConditionalGeneration`, 60 layers (5 sliding_attention + 1 full_attention pattern), sliding_window=1024, hidden=5376, vocab=262144. Conversion: `convert_hf_to_gguf.py` supports it natively (class `Gemma4Model` in `conversion/gemma.py`). **Chat template caveat:** Gemma4 with `--jinja` can emit raw template tokens (`<|im_end|>`) in response content — the built-in Jinja template may not match Gemma4's native chat format. If responses contain template artifacts, verify the chat template in the GGUF metadata or test with a raw completion endpoint first.
- **CRITICAL — MTP breaks tool calling on vLLM (forum consensus).** Community reports that enabling MTP speculative decoding on vLLM causes tool-calling accuracy to drop (dredyson.com, May 2026). Disable MTP when serving coding agents that rely on tool calls (Hermes → bash, file operations). This is a vLLM-specific issue — llama.cpp MTP support does NOT have the same problem. Monitor the Qwen team for official guidance.
- **CRITICAL — `hf download` `--local-dir` in Hermes terminal resolves `~` to session-isolated HOME.** `hf download --local-dir ~/models/` inside Hermes `terminal()` puts files in `/home/user/.hermes/home/models/` — NOT `/home/user/models/`. `start-llama.sh` can't find them. Always use **absolute paths**: `--local-dir /home/user/models/`. Verify: `ls -lh /home/user/models/`. If files landed in the wrong place: `mv /home/user/.hermes/home/models/*.gguf /home/user/models/`. Session 2026-07-10: APEX GGUF + mmproj landed in isolated HOME, moved manually.
