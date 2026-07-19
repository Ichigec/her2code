# DiffusionGemma RL Training on CPU — Launch Experience

## Hardware context

- **Platform**: Jetson/DGX Spark ARM64, 20 cores, 122 GB RAM (unified memory)
- **Model**: edwixx__diffusiongemma-26B-A4B-it-HERETIC-Uncensored-FP16.gguf (48 GB)
- **Inference**: `llama-diffusion-cli` from PR #24423, CPU-only (`-ngl 99` loads to CPU when no GPU)
- **Sandbox**: `arm64v8/python:3.12-slim` (native ARM64, NOT AMD64 via QEMU)

## CPU inference timing (real measurements, 2026-07-15)

| diffusion_steps | max_tokens | Time per generation | CPU utilization | Notes |
|:----------------|:-----------|:--------------------|:----------------|:------|
| 8 | 64 | **~32s** | 101% (1 core) | Fast, usable for RL |
| 16 | 128 | **~4 min** | 101% (1 core) | Standard phase 1 |
| 32 | 128 | ~8 min (est.) | 101% | Phase 2 |
| 64 | 256 | ~16 min (est.) | 101% | Phase 3 |

**Critical**: diff_steps is the dominant factor — halving steps halves generation time. For CPU RL, start with steps=8 and only increase after the pipeline is stable. canvas_size has smaller impact (128→256 adds ~20%).

Model resident memory: ~23.7 GB RSS (virtual size ~113 GB due to memory mapping).

## Training step timing

Each training step generates 32 completions (8 code + 8 test per round × 2 rounds: code→test and test→code):

| Phase | steps | diff_steps | Time/step | Total |
|:------|:------|:-----------|:----------|:------|
| 1 (warm-up) | 30 | 16 | ~18 min | ~9 hrs |
| 2 (stabilize) | 50 | 32 | ~36 min | ~30 hrs |
| 3 (polish) | 20 | 64 | ~72 min | ~24 hrs |
| **Total** | **100** | — | — | **~63 hrs (~2.6 days)** |

Real measurement from step 0 (16 API calls): 1079s (~18 min). With 32 calls per full step (2 rounds): ~36 min at diff_steps=16.

## Combined launcher pattern (server + training in one process)

**Problem**: Hermes kills background processes between turns. Starting the server and training as separate background processes means the server dies when the turn ends, taking training with it (even with `setsid`).

**Fix**: Single Python script that starts the server as `subprocess.Popen` and training as `subprocess.run`. Both live under one Hermes background process:

```python
# run_all.py — see /home/user/dev/rldiffusion/run_all.py
server = subprocess.Popen([venv_python, server_script], env=env, ...)
# Wait for health check...
subprocess.run([venv_python, "-u", training_script], cwd=..., env=...)
server.terminate()
```

**Critical**: Use `subprocess.DEVNULL` for server stdout/stderr to avoid pipe buffer deadlocks. The training's stdout goes to the parent's pipe.

**Timeout**: Do NOT set `timeout` on the background terminal call. The default 180s kills the process after 3 minutes. Omit the parameter entirely for long-running training (exit code 143 = SIGTERM from timeout).

### Step 0 verification metrics

Confirmed working (2026-07-15):

```json
{"step": 0, "phase": 1, "code_reward_mean": 0.15, "test_reward_mean": 0.505,
 "code_reward_max": 1.0, "code_trainable": 64, "test_trainable": 64,
 "lr": 0.001, "mistake_book_size": 25, "step_time_s": 1061.5,
 "vrpo_adv_mean": -0.17, "vrpo_adv_std": 0.596, "sandbox_cpus": 4, "sandbox_mem_gb": 8}
```

## Background process exit code reference

| Code | Meaning | Typical cause |
|:-----|:--------|:--------------|
| 143 | SIGTERM (128+15) | Bash wrapper SIGTERM from background timeout, or process exceeded `timeout` parameter |
| -15 | SIGTERM | Hermes killed the process (turn end, timeout) |
| 1 | Python exception | Unhandled error in training script (e.g., `HTTPError: 500`) |
| 124 | `timeout` command | Linux `timeout` command ran out (not Hermes timeout) |

## Background process launch — gotchas

### Issue: bash wrapper SIGTERM

When running `terminal(background=true, command="cd dir && python3 script.py")`, the bash wrapper may receive `tcsetattr` errors and SIGTERM (exit 143) after ~80 seconds. The Python child process gets killed even though it was working.

**Root cause**: The background bash shell tries to interact with a non-existent terminal (job control, process group). The `tcsetattr` failure cascades to SIGTERM.

**Fix**: Use `workdir` parameter + direct Python path:
```
terminal(background=true, workdir="/path/to/dir", command="/path/to/venv/bin/python3 -u script.py")
```

No shell wrapping = no terminal interaction = no SIGTERM.

### Issue: stdout buffering in background

Even with `python3 -u` (unbuffered), Hermes process log may show 0 lines until the process completes. The pipe buffering in the Hermes process manager captures output but may not show incremental lines.

**Workaround**: Monitor progress via the JSONL log file, not stdout:
```bash
tail -1 logs/training_*.jsonl
wc -l logs/training_*.jsonl
```

### Process debugging commands

```bash
# Find Python child under bash wrapper
ps --ppid <bash_pid> -o pid,state,%cpu,etime,cmd

# What's the process waiting on?
cat /proc/<python_pid>/wchan    # poll_schedule_timeout = network I/O
cat /proc/<python_pid>/status   # VmRSS, VmSize, Threads

# Network connections
ss -tnp | grep <python_pid>     # ESTAB = active HTTP call
ls -la /proc/<python_pid>/fd/   # socket + log file

# Current llama-diffusion-cli subprocess
pgrep -a llama-diffusion         # shows full command with prompt
```

## Resource limiter pattern

MSK-time-based CPU/RAM limits implemented via `/proc/stat` and `/proc/meminfo`:

```
Day (before 02:00 MSK = before 23:00 UTC):
  CPU max: 70% (sandbox: 3 cores)
  RAM max: 80% (sandbox: 6 GB)

Night (after 02:00 MSK = after 23:00 UTC):
  CPU max: 90% (sandbox: 4 cores)
  RAM max: 90% (sandbox: 8 GB)
```

Implementation: `scripts/resource_limiter.py` in the rldiffusion pipeline.

Checks every 50 training steps — if CPU/RAM exceeds limit + 5%, pauses and waits.

## LoRA support confirmed

`llama-diffusion-cli` from PR #24423 build (2026-07-14) supports:
- `--lora FNAME` — single or comma-separated LoRA adapters
- `--lora-scaled FNAME:SCALE,...` — per-adapter scaling

This means RL-trained LoRA weights can be loaded at inference time without merging.

## Logits limitation

`llama-diffusion-cli` does NOT return logits — only text output. The Python wrapper (`diffusion-server.py`) wraps this as an HTTP API, so `/v1/chat/completions` returns text only.

**Consequence**: ELBO-based RL methods (StableDRL) cannot be used directly. Must use reward-based methods (VRPO) that only need text output + sandbox execution results.

VRPO implementation: `scripts/vrpo_update.py` — computes advantages from composite rewards (code_pass_rate + test_quality × fail_rate) with exponential moving average baseline.

## CRITICAL: Binary version mismatch

There are TWO llama.cpp builds on the system, and they're different versions:

| Path | Version | diffusion-gemma? |
|:-----|:--------|:-----------------|
| `/tmp/llama-diffusion-fresh/build/bin/llama-diffusion-cli` | **9886** (c3fb97241) | ✅ YES |
| `/home/user/dev/llama.cpp/build/bin/llama-diffusion-cli` | 9247 (57ebaf4ed) | ❌ NO |

**Symptom of wrong binary**: `500 Internal Server Error: unknown model architecture: 'diffusion-gemma'`. Server health check passes (it's FastAPI), but first inference fails. The error is buried in the server's stderr — check with `curl` directly to see `{"detail":"Inference failed..."}`.

**How this happens**: The `diffusion-server.py` env var `DG_BINARY` was set to the wrong path when the server was first started (e.g., via `launch.sh`). Restarting the server requires setting ALL env vars correctly:

```bash
# Kill old server first
pkill -f diffusion-server.py

# Start fresh with correct binary
DG_BINARY="/tmp/llama-diffusion-fresh/build/bin/llama-diffusion-cli" \
DG_MODEL_PATH="/path/to/model.gguf" \
DG_NGL=99 DG_CTX_SIZE=65536 DG_PORT=8646 \
DG_DEFAULT_STEPS=16 \
python3 /home/user/dev/Opencode/diffusion-server.py &
```

**Check which binary the server is using**:
```bash
curl -s http://localhost:8646/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"diffusion-gemma-26b","messages":[{"role":"user","content":"hi"}],"max_tokens":5,"diffusion_steps":4}'
# If 500 with "unknown model architecture" → wrong binary
# If 200 with content → correct binary
```
