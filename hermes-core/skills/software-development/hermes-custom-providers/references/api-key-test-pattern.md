# API Key Test Pattern

Always test API keys against the provider's endpoint BEFORE integrating with Hermes. This catches expired keys, wrong model names, and endpoint issues before Hermes's opaque error handling makes debugging harder.

## Step 1: Test key validity (models endpoint)

```python
import urllib.request, json, ssl

key = "YOUR_KEY"
url = "https://api.z.ai/api/paas/v4/models"  # for z.ai

req = urllib.request.Request(url, headers={"Authorization": f"Bearer ***})
with urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
    data = json.loads(resp.read())
    models = [m.get("id") for m in data.get("data", [])]
    print(f"Available: {models}")
```

- `HTTP 200` + model list → key is valid
- `HTTP 401` → key expired/wrong
- `HTTP 403` → permissions issue

## Step 2: Test chat completion (minimal)

```python
data = json.dumps({
    "model": "glm-5.2",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "say ok"}]
}).encode()

url = "https://api.z.ai/api/paas/v4/chat/completions"
req = urllib.request.Request(url, data=data,
    headers={"Authorization": f"Bearer ***, "Content-Type": "application/json"})

with urllib.request.urlopen(req, timeout=15) as resp:
    body = json.loads(resp.read())
    content = body["choices"][0]["message"].get("content", "")
    reasoning = body["choices"][0]["message"].get("reasoning_content", "")
    print(f"content: {content[:100]}")
    print(f"reasoning: {reasoning[:100]}")
    print(f"tokens: {body.get('usage', {})}")
```

- `HTTP 200` + content → model works
- `HTTP 200` + empty content + reasoning_content → reasoning model
- `HTTP 400` + `"Unknown Model"` → model name wrong
- `HTTP 400` + `"模型不存在"` → model not found (check model list from step 1)

## Step 3: Test Hermes integration

```bash
hermes chat -q "say ok" -m glm-5.2 --provider custom:zai
```

If `hermes model` is interactive-only, use `hermes chat -q` instead.

## Multiple endpoints to try

Some providers have multiple API endpoints. Test both:

| Provider | Endpoints |
|----------|-----------|
| ZhipuAI GLM | `https://api.z.ai/api/paas/v4`, `https://open.bigmodel.cn/api/paas/v4` |
