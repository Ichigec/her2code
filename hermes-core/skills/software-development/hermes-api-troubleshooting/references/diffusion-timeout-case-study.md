# DiffusionGemma Timeout Diagnosis — Case Study

Session: `20260714_224339_0e8a46` (July 14, 2026, 22:43 MSK)
Model: `diffusiongemma-abliterated` (BF16, enable_thinking=true, plan2 preset)

## Symptoms

- User sends request at 22:43:40
- Model responds after 168 seconds (slow, but works)
- After tool results, model takes 350 seconds (5 min 50 sec) for next response
- User sends "ты тут?" mid-turn (frustration signal)
- Response eventually arrives as another tool call — but session is effectively dead

## Diagnostic Pipeline

### Step 1: Reconstruct timeline from session DB

```
session_search(session_id="...") → message timestamps
Timeline:
  22:43:40 → user message
  22:46:28 → model response (+168s — prefill 15K+ tokens + generation)
  22:46:28 → tool results (instant)
  22:46:28 → user "ты тут?" (mid-turn, after tool results)
  22:52:18 → model response (+350s — THINKING OVERHEAD)
  22:52:18 → tool result (SIGINT again)
  22:52:18 → user "ау" (abandoned)
```

### Step 2: Check vLLM Docker logs

```bash
docker logs diffusiongemma --since "2026-07-14T19:40:00" --until "2026-07-14T19:55:00" 2>&1
```

Key metrics to look for:
- `Running: 0 reqs` gaps > 60s → model idle (not processing any request)
- `Committed: 0 tokens` with `Denoising steps: >0` → model IS generating, but all tokens are internal (thinking)
- `POST /v1/chat/completions` 200 OK → when responses actually delivered

### Step 3: Check gateway stability

```bash
journalctl --since "2026-07-14 22:40" --until "2026-07-14 22:55" --no-pager | grep -iE "hermes.*gateway|SIGKILL|signal"
```

In this case: `hermes-gateway.service: Sent signal SIGKILL` at 22:40:17 — gateway was killed and restarted 3 minutes before the session. TUI slash_worker runs independently but gateway restart can create state DB races.

### Step 4: Check LiteLLM proxy (if model routed through it)

```bash
docker logs litellm --since "..." --until "..." 2>&1 | grep -E "POST|error|timeout"
```

In this case: NO POST requests through LiteLLM — TUI worker goes DIRECT to vLLM at localhost:8000, bypassing LiteLLM entirely. This is valid per config (two provider entries for diffusiongemma: `vllm` direct + `local` via LiteLLM).

### Step 5: Identify root cause

Pattern: `enable_thinking: true` + massive system prompt (plan2 = ~15K tokens) + multi-turn context.

DiffusionGemma's thinking mode generates hidden reasoning tokens BEFORE visible output. With a 15K system prompt, the model reasons extensively about how to approach the task. Each "thinking canvas" costs ~10 seconds (256 tokens / 25 tok/s), and the model may use 5-10+ canvases for reasoning before the visible tool call.

**Proof from vLLM logs:**
```
Denoising steps: 20+, Committed: 0 tokens → model is "thinking" (generating internal tokens)
Denoising steps: 18, Committed: 256 tokens → model just emitted a visible canvas
```

The ratio of thinking canvases to output canvases can be 5:1 or higher with complex prompts.

## Root Cause Summary

| Factor | Contribution |
|--------|-------------|
| Thinking tokens (enable_thinking=true) | ~60% — hidden reasoning generation |
| Massive system prompt (plan2, 15K+ tokens) | ~25% — expensive prefill + KV-cache |
| Diffusion canvas overhead (48 steps per 256 tokens) | ~10% — pay for canvas regardless of output |
| Gateway restart (SIGKILL at 22:40:17) | ~5% — possible state DB race |

## Fix

1. **Immediate:** `enable_thinking: false` for non-reasoning tasks
2. **Config:** `--default-chat-template-kwargs '{"enable_thinking": false}'` in serve script
3. **Workflow:** Don't use heavy presets (plan2) on diffusion models — use AR models (deepseek, glm) for orchestration

## Verification

After fix, same prompt should respond in <60 seconds (not 350+). Verify with:
```bash
time curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"diffusiongemma-abliterated","messages":[{"role":"user","content":"проведи полную диагностику plan4"}],"chat_template_kwargs":{"enable_thinking":false}}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'tokens={d[\"usage\"][\"completion_tokens\"]}')"
```
