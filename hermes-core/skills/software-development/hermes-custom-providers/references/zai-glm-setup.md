# z.ai (GLM) Provider Setup Details

Session transcripts from 2026-07-02 and 2026-07-08: configuring z.ai custom provider for GLM models in Hermes Agent, including rate-limiting diagnostics.

## API Endpoint

```
Base URL: https://api.z.ai/api/paas/v4 (default)
          https://api.z.ai/api/coding/paas/v4 (coding endpoint, via GLM_BASE_URL)
Auth:     Bearer {api_key}
Models:   GET /models
Chat:     POST /chat/completions (OpenAI-compatible)
```

**GLM_BASE_URL override**: The `zai` plugin has hardcoded `base_url="https://api.z.ai/api/paas/v4"`, but Hermes respects `GLM_BASE_URL` from `.env` at runtime. Confirmed in agent.log: `base_url=https://api.z.ai/api/coding/paas/v4`. The `env_vars` tuple in the plugin only lists key vars (`GLM_API_KEY`, `ZAI_API_KEY`, `Z_AI_API_KEY`) — `GLM_BASE_URL` is resolved by a separate config layer, not the plugin's `env_vars` tuple.

## Available Models (as of 2026-07-08)

| Model | Type | Notes |
|-------|------|-------|
| `glm-4.5` | Chat | Lightweight |
| `glm-4.5-air` | Chat | Fast |
| `glm-4.6` | Chat | Timeout issues observed |
| `glm-4.7` | Chat | **Recommended for regular chat** ✅ |
| `glm-5` | Reasoning | Thinking tokens, empty content |
| `glm-5-turbo` | Reasoning | Fast reasoning |
| `glm-5.1` | Reasoning | Thinking tokens, empty content |
| `glm-5.2` | Reasoning | `reasoning_effort: xhigh` produces both `reasoning_content` AND `content` |

## API Key Format

ZhipuAI keys use format: `{uuid}.{secret}` — e.g., `c101243a...yGGstD8pQ71YHQE6` (49 chars).

## Config

```yaml
custom_providers:
- name: zai
  base_url: https://api.z.ai/api/paas/v4
  api_key_env: GLM_API_KEY
  models:
    glm-4.5: {}
    glm-4.5-air: {}
    glm-4.6: {}
    glm-4.7: {}
    glm-5: {}
    glm-5-turbo: {}
    glm-5.1: {}
    glm-5.2: {}
```

## Rate Limiting (HTTP 429)

z.ai returns HTTP 429 with error code 1305 when the service is overloaded:

```json
{"error": {"code": "1305", "message": "The service may be temporarily overloaded, please try again later"}}
```

### Payload-size threshold

z.ai rate-limiting is **payload-size dependent**:

| Payload size | Typical result |
|-------------|----------------|
| ~1.4K tokens (small test) | HTTP 200 ✅ |
| ~6K tokens (light session) | May pass or 429 |
| ~70K tokens (medium session) | Usually 429 ❌ |
| ~167K tokens (zombie session) | Guaranteed 429 ❌ |

The threshold appears to be around 5K–10K input tokens. Sessions that exceed this get consistently rate-limited.

### Contributing factors

- **Large system prompts** (Plan2 preset ~16K tokens) make each request heavy — more likely to trigger rate limits
- **Token accumulation on retry**: each failed message stays in the conversation, so the 3rd retry has more tokens than the 1st, making it even MORE likely to be rate-limited
- **Multiple rapid retries**: Hermes retries 3× with exponential backoff (2s, 4s, 6s) — if the service stays overloaded, all 3 fail
- **Zombie sessions** (see below): sessions with `ended_at: NULL` and 300+ messages accumulate massive context (167K tokens) that's guaranteed to get 429 on every retry, eating rate limits until killed

### Zombie session 429 pattern

Old CLI sessions that were never properly closed (`ended_at: NULL` in state.db) are especially dangerous. When the Docker gateway or desktop GUI tries to resume them, the full context (hundreds of messages, 160K+ tokens) is sent to GLM → guaranteed 429. The session then sits in a retry loop eating rate limits.

**Detection**:

```bash
# Find zombie sessions with huge message counts
sqlite3 ~/.hermes/state.db "
  SELECT id, title, message_count, 
         printf('%.0f', input_tokens/1000) || 'K' as tokens,
         datetime(started_at, 'unixepoch', 'localtime') as started
  FROM sessions 
  WHERE ended_at IS NULL 
  ORDER BY message_count DESC 
  LIMIT 10
"
```

**Real example** (session `20260707_225015_6089b7`):

| Field | Value |
|-------|-------|
| Title | «Починка GUI после последних правок» |
| Started | July 7, 22:50 |
| Messages | 306 |
| Input tokens | 883K |
| API calls | 162 |
| Last success | July 8, 07:13 (API call #34) |
| Last attempt | July 8, 11:57 → 429 (167K tokens, 3 retries all failed) |
| Process | PID 2549897, CLI on pts/0, sleeping (ep_poll) |

**Fix**: kill the process and let the gateway clean up:
```bash
kill <PID>   # the zombie hermes CLI process
```
The session data stays in `state.db` — can resume later with `hermes --resume <id>` (but will hit 429 again unless switched to a different provider or compressed with `/compress`).

### Diagnostic commands

```bash
# Real-time: are requests failing?
grep "429\|RateLimitError" ~/.hermes/logs/agent.log | tail -20

# Deeper: error patterns with timestamps
grep -E "429|RateLimitError|error_type" ~/.hermes/logs/errors.log | tail -20

# Specific session's failures
grep "RateLimitError\|429" ~/.hermes/logs/agent.log | grep "YOUR_SESSION_ID"

# Check if Hermes auto-switched models
grep "Model switched in-place" ~/.hermes/logs/agent.log | tail -5
```

### Workarounds

1. **Wait and retry** — rate limits are temporary
2. **Use lighter agent preset** — fewer tokens = less likely to trigger 429
3. **Switch model/provider** — Hermes does this automatically if `fallback_providers` is set
4. **Use `glm-4.7`** — lighter model, less likely to be rate-limited

### Real example (session 20260708_113439)

```
11:36:21 ERROR — 3 retries failed, HTTP 429, tokens=~6,073
11:38:33 ERROR — 3 retries failed, HTTP 429, tokens=~6,075
11:48:06 ERROR — 3 retries failed, HTTP 429, tokens=~16,914  ← context grew!
11:52:26 INFO  — Model switched in-place: glm-5.2 (zai) → deepseek-v4-pro (deepseek)
```

Notice the token count grew from 6K to 17K because failed messages and tool calls accumulated in the conversation, making each subsequent request heavier.

## Testing

```python
import urllib.request, json, ssl

# Read key
with open(os.path.expanduser("~/.hermes/.env")) as f:
    for line in f:
        if "GLM_API_KEY" in line and not line.startswith("#"):
            key = line.strip().split("=", 1)[1]
            break

data = json.dumps({
    "model": "glm-4.7", "max_tokens": 30,
    "messages": [{"role": "user", "content": "Say OK"}]
}).encode()

req = urllib.request.Request(
    "https://api.z.ai/api/paas/v4/chat/completions",
    data=data,
    headers={"Authorization": f"Bearer ***, "Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as resp:
    print(json.loads(resp.read())["choices"][0]["message"]["content"])
```

## Pitfall: Reasoning Models and Empty Content

GLM-5.x models are reasoning models. They use `reasoning_tokens` for thinking and may return empty `content`. Response shows:

```json
{
  "choices": [{"message": {"content": "", "reasoning_content": "..."}}],
  "usage": {"completion_tokens": 50, "completion_tokens_details": {"reasoning_tokens": 45}}
}
```

For regular chat, use `glm-4.7`. For reasoning tasks, `glm-5.2` with `reasoning_effort: xhigh` produces both `reasoning_content` AND `content`.
