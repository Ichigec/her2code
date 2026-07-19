# OpenCode+ LiteLLM Proxy

OpenCode+ routes all chat/audio models through a local LiteLLM proxy on `http://127.0.0.1:4000/v1`.

| Artifact | Path |
|----------|------|
| LiteLLM config | `/home/user/cursor/first/docker/litellm/config.yaml` |
| Compose file | `/home/user/cursor/first/compose.phoenix.yml` |
| Start script | `/home/user/cursor/opencode+/start-litellm-dual.sh` |
| Env file used by compose | `/home/user/cursor/.env` |
| Env file that also holds keys | `/home/user/cursor/first/.env` |

**Critical env-file detail:** `compose.phoenix.yml` is started with `--env-file /home/user/cursor/.env`. If a key exists only in `/home/user/cursor/first/.env`, the LiteLLM container receives an empty value. Either copy the needed key into `/home/user/cursor/.env`, or ensure `start-litellm-dual.sh` exports it before `docker compose up`.

## Common failure: DeepSeek returns 401

Symptom: `deepseek-v4-pro` (or `deepseek-chat` / `deepseek-reasoner` / `deepseek-v4-flash`) is listed in `GET /v1/models`, but a chat request fails with:

```
Authentication Fails, Your api key: ****Cr8A is invalid.
```

The suffix `Cr8A` is the end of `OPENAI_API_KEY`, not `DEEPSEEK_API_KEY`. LiteLLM is sending the wrong key.

### Root causes

1. **Wrong provider prefix in `config.yaml`.** Using `model: openai/deepseek-*` plus an explicit `api_base: https://api.deepseek.com/v1` makes LiteLLM treat DeepSeek as a generic OpenAI-compatible endpoint and pull `OPENAI_API_KEY` instead of `DEEPSEEK_API_KEY`.
2. **Missing env var.** `compose.phoenix.yml` is started with `--env-file /home/user/cursor/.env`. If `DEEPSEEK_API_KEY` only exists in `/home/user/cursor/first/.env`, the LiteLLM container receives an empty key.

### Fix

In `first/docker/litellm/config.yaml`, write DeepSeek entries with the native provider:

```yaml
  - model_name: "deepseek-v4-pro"
    litellm_params:
      model: "deepseek/deepseek-v4-pro"
    model_info:
      mode: chat
```

Do the same for `deepseek-chat`, `deepseek-reasoner`, and `deepseek-v4-flash`.

Then ensure the key is in the env file that compose actually loads:

```bash
grep '^DEEPSEEK_API_KEY=' /home/user/cursor/.env || \
  grep '^DEEPSEEK_API_KEY=' /home/user/cursor/first/.env >> /home/user/cursor/.env
```

Restart:

```bash
cd /home/user/cursor/opencode+
bash start-litellm-dual.sh
```

### Verify

```bash
curl -s http://127.0.0.1:4000/v1/models -H 'Authorization: Bearer sk-local' | \
  python3 -c "import sys,json; print('\n'.join(m['id'] for m in json.load(sys.stdin).get('data',[])))"

curl -s http://127.0.0.1:4000/v1/chat/completions \
  -H 'Authorization: Bearer sk-local' \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4-pro","messages":[{"role":"user","content":"hi"}],"max_tokens":5}' \
  -w '\nHTTP %{http_code}\n'
```

Expected: HTTP 200 and `model: deepseek-v4-pro` in the response.

## General restart rule

After any change to `config.yaml` or `.env`, recreate the LiteLLM container:

```bash
cd /home/user/cursor/opencode+
bash start-litellm-dual.sh
```

Do not rely on `docker restart litellm`; config and env changes require a container recreate (`--force-recreate`).
