# Hermes Desktop Crash Investigation

Quick diagnostic workflow when the Electron desktop app crashes or dies unexpectedly.

## Log Locations

| Log | Path | What it covers |
|-----|------|---------------|
| Desktop events | `~/.hermes/logs/desktop.log` | Electron boot sequences, JSON-RPC events, subagent progress |
| GUI / Gateway WS | `~/.hermes/logs/gui.log` | WebSocket connections, backend lifecycle, plugin mounts |
| Errors | `~/.hermes/logs/errors.log` | Warnings, tool failures, provider/config issues |
| Agent runtime | `~/.hermes/logs/agent.log` | Conversation loops, API calls, model routing, MCP registration |
| Gateway | `~/.hermes/logs/gateway.log` | Platform connections, gateway lifecycle |

## Diagnostic Commands

```bash
# 1. Is the desktop currently running?
ps aux | grep -i hermes | grep -v grep

# 2. Check system memory (OOM indicator)
free -h

# 3. Find crash signature
grep "render-process-gone\|exitCode=" ~/.hermes/logs/desktop.log | tail -5

# 4. Check if desktop was in a boot loop
grep "\[boot\] Resolving" ~/.hermes/logs/desktop.log | tail -20

# 5. WebSocket disconnects (timeout = desktop unresponsive)
grep "ws.*write failed\|ws.*send failed\|WebSocketDisconnect" ~/.hermes/logs/gui.log | tail -10

# 6. Check if desktop was in a boot loop
grep "\\[boot\\] Resolving" ~/.hermes/logs/desktop.log | tail -20

# 7. Confirm an OS-level OOM kill (journalctl / dmesg)
journalctl --since "10 minutes ago" -q | grep -iE "Killed process .*Hermes|oom.*Hermes|NVRM:.*Out of memory"
```

## Crash Signatures

### SIGKILL / OOM Kill (most common)

```
[renderer] render-process-gone reason=killed exitCode=9
```

**exitCode=9 = SIGKILL.** The Electron renderer was killed by the OS — almost always
the OOM killer when swap is high. Check `free -h` — swap >80% confirms memory pressure.

**Cross-check system logs:** If the *entire* Hermes process is killed by the kernel,
`desktop.log` may show nothing except a sudden stop, or only a generic
`render-process-gone` if the renderer was killed first. To confirm an OS-level OOM
kill, search journalctl/dmesg:

```bash
journalctl --since "20 minutes ago" -q | grep -iE "Killed process|oom|Out of memory"
dmesg -T | grep -iE "Killed process|oom|Out of memory" | tail -20
```

Look for a line naming `Hermes`, e.g.:

```
Killed process 3719365 (Hermes) total-vm:...kB, anon-rss:...kB, file-rss:...kB, shmem-rss:...kB
```

If you find a matching `Killed process <pid> (Hermes)`, the crash is a **kernel OOM
kill**, not a renderer bug. The `oom_score_adj` (e.g., `300`) tells you how eagerly
the kernel selected the process. The WebSocket disconnect in `gui.log` will usually
appear a few seconds later.

Common contributors:
- **Observer subagent event floods:** Every `subagent.tool`/`subagent.progress`/`subagent.thinking` event carries the full ~1200-byte goal text. Multiple observer subagents × dozens of tool calls = enormous event volume pumped to the desktop's WebSocket.
- **Heavy background processes:** GPU-intensive workloads (lm-eval, perplexity, model inference) compete for system RAM.
- **Multiple slash workers:** Each active session spawns a `slash_worker` process.
- **Context compression failure:** If the compression model returns an error (e.g., GLM-4.7 → "Unknown Model" error 1211), the context stays at full size (~219K+ tokens in observed crash).

### Boot Loop
Multiple rapid `[boot] Resolving Hermes backend` sequences without much work between them indicate the desktop is crashing and auto-restarting. Each cycle accumulates pending events from the gateway, compounding memory pressure.

### WebSocket Timeout → Desktop Unresponsive
```
ws write failed peer=127.0.0.1:XXXXX error_type=TimeoutError
ws response send failed peer=127.0.0.1:XXXXX id=N method=setup.runtime_check
ws closed peer=127.0.0.1:XXXXX reason=send_failed_after_response messages=N
```
The gateway can't reach the desktop — the renderer is hung or already dying.

### Context Compression Failure
```
⚠ Compression summary failed: Error code: 400 - 
  {'error': {'code': '1211', 'message': 'Unknown Model, please check the model code.'}}
```
The model used for compression (typically GLM-4.7 via Z.ai) is not recognized. The context remains uncompressed, adding memory pressure. This was observed with `glm-4.7` on 2026-07-02.

## Recovery

The desktop auto-restarts on crash — no manual intervention needed. If it doesn't:
```bash
# Kill any stale processes
pkill -f "Hermes --no-sandbox" 2>/dev/null
pkill -f "hermes gui" 2>/dev/null

# Restart
hermes gui
```

## Prevention

- **Reduce observer event payloads:** Don't repeat the full goal text in every subagent event.
- **Limit concurrent observers:** Depth-1 spawning (observer spawning its own observers) doubles event volume.
- **Fix compression model:** Use a reliable model for context compression (not GLM-4.7 if it returns "Unknown Model").
- **Monitor swap:** If swap >10GB on a 121GB system, there's a memory leak or too many concurrent processes.
