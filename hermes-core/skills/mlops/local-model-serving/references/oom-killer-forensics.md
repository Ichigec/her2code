# OOM Killer Forensics: Diagnosing Hermes Crashes During Model Operations

## Scenario

Hermes Desktop (Electron) crashed multiple times during a session that ran `llama-perplexity` for PPL measurement of a 22GB GGUF model. No crash dumps in Crashpad. Root cause: Linux OOM killer.

## Forensic Workflow

### Step 1: Confirm OOM (not an app bug)

```bash
# Check kernel log for OOM kills in the crash time window
journalctl --since "2026-07-02 20:00:00" --until "2026-07-03 02:00:00" --no-pager | grep "Out of memory: Killed"
```

If you see `Out of memory: Killed process XXXXX (Hermes)` — it's OOM, not an Electron crash.

Also check for absence of Crashpad dumps:
```bash
find ~/.config/Hermes/Crashpad/ -name "*.dmp" 2>/dev/null
# Empty = no app-level crash, confirms external kill (SIGKILL from kernel)
```

### Step 2: Identify the Memory Hogs

```bash
# Full OOM kill list with process details
journalctl --since "TIME" --until "TIME+2h" --no-pager | grep -E "Out of memory: Killed"

# The kernel also prints the full process table at OOM time — look for it:
journalctl --since "TIME" --until "TIME+2h" --no-pager | grep -E "pid.*tgid.*total_vm.*rss"
```

Key fields in the OOM process table:
- `total_vm` — virtual memory (TB-scale for Electron/mmap'd models, misleading)
- `rss` — actual physical pages (pages, not kB — divide by 256 to get MB on 4K pages)
- `rss_anon` — anonymous heap (the real memory consumer)
- `oom_score_adj` — kernel's kill preference (higher = killed first)

### Step 3: Correlate with Session Activity

Find what the Hermes session was doing at crash time:

```bash
python3 -c "
import sqlite3, time
db = sqlite3.connect('/home/user/.hermes/state.db')
# Session time range
msgs = db.execute(\"SELECT id, role, timestamp, tool_name FROM messages WHERE session_id='SESSION_ID' ORDER BY id\").fetchall()
first_ts = msgs[0][2]
last_ts = msgs[-1][2]
print(f'Session: {time.strftime(\"%H:%M:%S\", time.localtime(first_ts))} - {time.strftime(\"%H:%M:%S\", time.localtime(last_ts))}')
# Find terminal commands that mention llama-*
for m in msgs:
    if m[3] == 'terminal':
        content = db.execute('SELECT content FROM messages WHERE id=?', (m[0],)).fetchone()[0]
        if content and 'llama' in content.lower():
            print(f'  [{time.strftime(\"%H:%M:%S\", time.localtime(m[2]))}] {content[:200]}')
"
```

### Step 4: Timeline Reconstruction

Match OOM kill timestamps to session message timestamps. Typical pattern:

```
20:34:47  OOM #1 — kills llama-perplexit (16.5 GB RSS)     ← first PPL run
20:35     Hermes restarts (PID change in ps)
20:37:17  Session starts
20:47:31  OOM #2 — kills chrome (collateral)
20:50:10  OOM #3 — kills cursor (collateral)
20:50:39  OOM #4 — kills Hermes (oom_score_adj=300) + llama-perplexit
20:59     Hermes restarts again (current PID)
```

### Step 5: Memory Budget Analysis

```bash
# Current system RAM
free -h

# Swap usage (critical — swap full = no headroom)
swapon --show

# Docker memory footprint
docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}' | sort -t$'\t' -k2 -rh | head -10

# All Electron/Chromium processes
ps aux | grep -E "[Hh]ermes|[Cc]hrome|[Cc]ursor|[Mm]attermost" | awk '{print $2, $6/1024 "MB", $11}'
```

### Why Hermes Gets Killed First

| Factor | Value | Effect |
|--------|-------|--------|
| `oom_score_adj` | 300 (max user-space) | Kernel prefers killing Hermes |
| Virtual memory | 1.4 TB (Electron address space) | Looks enormous to kernel OOM scorer |
| RSS | ~106 MB (small!) | But kernel scores by oom_score_adj + VM size, not just RSS |
| Swap exhaustion | 12.3/16 GB | No room for spikes → kernel panics and kills |

The OOM killer calculates a score combining `oom_score_adj` + process memory footprint. Electron's huge virtual memory mapping + `oom_score_adj=300` makes it the #1 target even when its actual RSS is tiny compared to `llama-perplexity`'s 16.5 GB.

## Mitigation Strategies

### 1. Run Heavy llama.cpp Tools Outside Hermes

```bash
# In a separate SSH session or tmux pane — NOT via Hermes terminal()
ssh pavel@jetson
/home/user/dev/llama.cpp/build/bin/llama-perplexity \
  -m model.gguf -f wiki.test.raw -c 512 -ngl 99
```

### 2. Reduce Memory Pressure Before Launching

```bash
# Stop non-essential Docker containers
docker stop difo-nginx-1 dify-api-1 dify-web-1 dify-worker-1 openhands 2>/dev/null

# Check available memory
free -h  # Need: model_size + 4GB headroom

# Check swap
swapon --show  # If USED > 50% of SIZE, don't launch
```

### 3. Reduce Model Memory Footprint

```bash
# CPU-only (no GPU layer offload = slower but different memory profile)
llama-perplexity -m model.gguf -f wiki.test.raw -c 128 -ngl 0

# Smaller batch/context
llama-perplexity -m model.gguf -f wiki.test.raw -c 128 -b 128
```

### 4. Protect Hermes from OOM Killer (per-session)

```bash
# Find Hermes main process PID
HERMES_PID=$(pgrep -f "Hermes --no-sandbox" | head -1)

# Make it unkillable by OOM (requires root)
sudo echo -100 > /proc/$HERMES_PID/oom_score_adj
# -100 = OOM killer will never target this process
# Note: resets on restart — not persistent
```

### 5. Increase Swap (persistent)

```bash
# Add 32GB swap file (Jetson has 121GB RAM, 16GB swap is too small for model work)
sudo fallocate -l 32G /swap2.img
sudo chmod 600 /swap2.img
sudo mkswap /swap2.img
sudo swapon /swap2.img
# Add to /etc/fstab for persistence
echo '/swap2.img none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Session Reference

- **Session ID:** `20260702_203717_b49469` (source: tui, 89 messages, 36 tool calls)
- **Task:** SuperQwen-AgentWorld-35B-A3B quantization pipeline (BF16 → F16 → imatrix → APEX I-Quality → PPL)
- **Crash cause:** Two `llama-perplexity` background processes (APEX + Q4_K_M PPL comparison) consumed 16.5 GB + 5.5 GB RSS simultaneously
- **System state:** 20+ Docker containers (~30-40 GB), 4 Electron apps, 12.3/16 GB swap used
- **Result:** 3 OOM waves in 16 minutes, Hermes killed twice (PID 3719365 at 20:50:39), 3 restarts total
