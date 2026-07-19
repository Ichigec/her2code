# Silent empty response: diagnostic checklist

When phone shows no response but "sent" indicator, the root cause is almost always
cloud API key failure (401/429), NOT infrastructure.

## Symptoms

- App logcat: `SSE: [DONE] after 5 lines`, `ChatVM: Done: responseText length=0`
- Server-side: `completion_tokens: 0`, empty delta content
- No explicit error in the app UI — just silence

## Diagnostic path (in order — stop when you find the issue)

### 1. Health check
```bash
curl -s http://localhost:8643/health  # native Gateway
# Should return {"status":"ok","platform":"hermes-agent"}
```

### 2. Gateway logs for model errors
```bash
docker logs hermes-gateway --tail 50 2>/dev/null | grep -i "error\|fail\|connection\|auth"
# Or for native: tail -50 /home/user/.hermes-native-gateway/logs/gateway.log | grep -i error
```

### 3. Test models directly through LiteLLM
```bash
for m in deepseek-chat glm-5.2 gpt-4.1-mini; do
  echo -n "$m: "
  curl -s -m 5 http://localhost:4000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer *** \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":10}"
  echo
done
```

### 4. Check LiteLLM logs
```bash
docker logs litellm --tail 20 | grep -i "auth\|401\|429\|500"
```

## Common failures

| Symptom | LiteLLM HTTP | Root cause | Fix |
|---------|-------------|------------|-----|
| Empty SSE, tokens=0 | 401 | DEEPSEEK_API_KEY lost/expired | Add key to litellm-config.yaml |
| Empty SSE, tokens=0 | 429 | GLM rate limit (5h window) | Wait or switch model |
| Empty SSE, tokens=0 | 500 | OPENAI_API_KEY missing | Add key to config |
| Connection reset | timeout | SSH tunnel / socat dead | Check systemd services |

## If ALL cloud models fail

Fallback to local vLLM — check what's running:
```bash
nvidia-smi --query-compute-apps=pid,name --format=csv,noheader
# If vLLM is running: curl localhost:8000/v1/models
```

Then add vLLM as primary provider in Gateway config and restart.
