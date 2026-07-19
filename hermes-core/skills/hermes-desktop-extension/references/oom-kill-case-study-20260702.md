# Case Study: Hermes Desktop OOM-killed during concurrent benchmarks

**Session:** `20260702_203717_b49469`  
**Outcome:** Hermes Desktop GUI process was killed by the kernel OOM killer at 20:50:39.

## Timeline

| Time (UTC+3) | Event | Evidence |
|--------------|-------|----------|
| 20:43:29 | First `llama-perplexity` benchmark timed out after 300s | `agent.log` |
| 20:50:39 | Hermes Desktop main process killed by kernel OOM killer | `journalctl` |
| 20:50:42 | WebSocket to gateway closed (`ws closed peer=... reason=...`) | `gui.log` |
| 20:50:42 | Second `llama-perplexity` timeout recorded | `agent.log` |

## Key log excerpts

### `~/.hermes/logs/desktop.log`

Final entries before the kill:

```
[renderer] render-process-gone reason=killed exitCode=9
```

Also present earlier in the session:

```
Error code: 400 - {'error': {'code': '1211', 'message': 'Unknown Model'}}
```

This came from the context-compression fallback model (`glm-4.7` configured via custom
provider), causing the context to stay at full size (~219K+ tokens) instead of being
compressed.

### `~/.hermes/logs/gui.log`

```
ws closed peer=127.0.0.1:XXXXX reason=send_failed_after_response messages=N
```

The WebSocket disconnect happened ~3 seconds after the OS killed the process, because
the desktop process no longer existed to keep the socket open.

### `journalctl` / `dmesg` OOM evidence

```
Killed process 3719365 (Hermes) total-vm:..., anon-rss:..., file-rss:..., shmem-rss:...
NVRM: Out of memory
```

Within the same ~15-minute window, the kernel also killed:

- `chrome` (browser, unrelated tab load)
- `cursor` (IDE)
- `llama-perplexit` (the running benchmark)

This confirms system-wide memory pressure rather than a Hermes-specific leak.

## Contributing factors

1. **Two concurrent `llama.cpp` benchmarks** (`llama-perplexity` / PPL and HellaSwag APEX)
   were running with 300s timeouts, consuming large chunks of RAM/VRAM.
2. **Context compression failure:** the fallback compression model returned "Unknown Model",
   so the desktop/backend had to keep the uncompressed context in memory.
3. **High `oom_score_adj`:** Hermes Desktop had `oom_score_adj=300`, making it a likely
   victim once the kernel started selecting processes.

## Lesson

When the desktop dies with `render-process-gone reason=killed exitCode=9`, always cross-check
`journalctl`/`dmesg` for `Killed process ... (Hermes)`. The renderer death can be a symptom
of a kernel OOM kill that originated outside the renderer. In this case the root cause was
concurrent heavy CPU/GPU workloads, not a UI bug.
