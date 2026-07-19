# Thinking Model Diagnosis & Fix Recipe

## Symptom

Agent switches to a local model (activated via `/agent plan3` or `/model custom:local:<name>`), seems to switch successfully, but user gets **no response** — not even "(empty)". The conversation looks stuck.

Actual root (discovered July 2026): the model IS responding, but ALL output tokens go to `reasoning_content`, leaving `content` empty. Hermes detects this as "thinking-only" and retries 5 times before giving up with `final_response = "(empty)"`.

## The Cascade

```
[Request] → llama-server (thinking ON)
  → response: content="" + reasoning_content="Thinking Process: 1. Analyze..."
  → Hermes: _is_thinking_only_message() = True
  → Thinking prefill retry #1: "continue..."
    → model: MORE reasoning, content=""
  → Thinking prefill retry #2: "continue..."
    → model: EVEN MORE reasoning, content=""
  → Empty content retry #1: retry whole request
    → model: MORE reasoning...
  → Empty content retry #2: retry
  → Empty content retry #3: retry
  → After 5 retries → "(empty)" → user sees nothing
```

Each retry adds previous reasoning to the context, making the model think even MORE. Never converges.

## Root Cause

Thinking models (Agents-A1 with `--jinja`, Qwen3.6 reasoning variants) default to `--reasoning auto`. This means the model generates its entire reasoning chain before producing content. Ratio measured: 568 tokens of reasoning for 33 chars of content (18:1) on "Say hi".

## Verified Evidence (July 2026, DGX Spark)

| Query | max_tokens | content | reasoning_content | Time | finish |
|-------|-----------|---------|-------------------|------|--------|
| "Say hi" | 10 | `""` | 42 chars | 0.5s | length |
| "Say hi" | 1000 | `""` | 3,498 chars | 30s | length |
| "Say hi" | 4000 | "Hi there! 👋" | 1,827 chars | 17.5s | stop |
| "Hi" + thinking OFF | 100 | "Hi!" | 0 chars | 0.6s | stop |

With thinking ON: model needs 568 tokens to produce "Hi there!".
With thinking OFF: model responds in 0.6s with direct content.

## Fix — Two Layers

### Layer 1: Server-level (REQUIRED)

Add `--reasoning off` to every llama-server instance:

```bash
llama-server -m model.gguf --alias agents-a1 -ngl 99 -c 262144 \
  --host 0.0.0.0 --port 8102 --jinja --reasoning off
```

Also update the watchdog script so restarted instances get the flag:

```bash
setsid "$LLAMA_SERVER" -m "$model" --alias "$alias" -ngl 99 -c 262144 \
  --host 0.0.0.0 --port "$port" --jinja --reasoning off $extra \
  > "$logfile" 2>&1 &
```

### Layer 2: Config-level (belt+suspenders)

In Hermes `config.yaml`, add `extra_body` to the `custom_providers` entry:

```yaml
custom_providers:
  - name: local
    base_url: http://localhost:4000/v1
    api_mode: chat_completions
    api_key: sk-local
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
    models:
      agents-a1-abliterated:
        context_length: 262144
```

## Verification Test

```bash
# End-to-end: LiteLLM → llama-server
curl -s --max-time 30 http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{"model":"agents-a1-abliterated","messages":[{"role":"user","content":"Say hi"}],"max_tokens":100}' \
  | python3 -c "
import sys,json
d = json.load(sys.stdin)
m = d['choices'][0]['message']
print(f'content=[{m.get(\"content\",\"\")}], reasoning_len={len(m.get(\"reasoning_content\",\"\"))}')"
# Expected with fix: content=[Hi there!], reasoning_len=0
# Expected without fix: content=[], reasoning_len=1827+
```

## The WRONG Fix

**Do NOT increase `-c` (context length) as a fix.** The pitfall previously read "increase context to 256K" — this does NOT solve the problem. The model still generates ALL tokens as reasoning, just within a larger budget. At 256K context, the model uses 568 tokens of reasoning for "Say hi". With a full Hermes system prompt (75K chars ≈ 20K tokens), the reasoning chain would be even longer, and the retry loop still amplifies it.

## Hermes Code Paths Involved

For future reference when debugging similar issues:

- `agent/conversation_loop.py:4364-4468` — Empty response retry logic
- `agent/conversation_loop.py:4340-4362` — Thinking prefill retry (×2)
- `run_agent.py:3190-3230` — `_is_thinking_only_message()` detection
- `agent/agent_runtime_helpers.py:991-1016` — `extract_reasoning()` — extracts `reasoning_content`
- `agent/chat_completion_helpers.py:864-870` — Copies `reasoning_content` from API response to message dict
- `agent/agent_init.py:135-136` — `_merge_custom_provider_extra_body()` — applies config-level `extra_body`
