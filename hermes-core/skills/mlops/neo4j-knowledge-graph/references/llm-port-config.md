# LLM Server Ports Configuration

## Known Ports

The local llama.cpp servers run on the following ports by default:

| Port | Model Alias | Purpose |
|------|-------------|---------|
| 8101 | `nex-n2-mini` | Coding, terminal tasks |
| 8102 | `agents-a1` | Reasoning, analysis (VLM) |
| 8103 | `agentworld` | Environment simulations |

## Scripts and Their Expected Ports

### `knowledge-curator-ingest-llm.py`
- **Default:** `http://127.0.0.1:8092/v1`
- **Fallback:** NONE
- **Usage:** Always set `LLAMA_URL` explicitly or use `curator-daily.sh`

### `curator-daily.sh`
- **Auto-detects:** 8092 → 8102 → 8103 → 8101
- **Health check:** Tests content generation before using a port
- **Recommended:** Use this wrapper for cron jobs

## Troubleshooting

### "Connection refused" on port 8092
1. Check if any llama-server is running: `ps aux | grep llama-server`
2. Test available ports: `for p in 8101 8102 8103; do curl -s http://127.0.0.1:$p/v1/models && echo " Port $p OK"; done`
3. Set the environment variable: `export LLAMA_URL="http://127.0.0.1:8102/v1"`

### "Failed to fit params to device memory"
The model is too large for GPU memory with `n_gpu_layers=99`. This occurs when:
- Multiple llama-server instances are already running
- GPU memory is fragmented or insufficient

**Solution:** Kill unused servers or start with fewer GPU layers (not recommended for quality).

## Verification

```bash
# Check if a port responds
curl -sf http://127.0.0.1:8102/v1/models

# Quick content test
curl -sf http://127.0.0.1:8102/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"OK"}],"max_tokens":5,"temperature":0}'
```

## Cron Configuration

**Correct:**
```bash
0 2 * * * /home/user/.hermes/scripts/curator-daily.sh
```

**Incorrect (will fail silently if port 8092 is down):**
```bash
0 2 * * * python3 /home/user/.hermes/scripts/knowledge-curator-ingest-llm.py
```
