#!/usr/bin/env bash
# Wire host llama → LiteLLM → Phoenix on this machine.
# Docker (llm-stack-net) can reach host port 1234 only, not 8092 — see README.
set -euo pipefail

OPENCODE_PLUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$OPENCODE_PLUS_DIR/.." && pwd)"

echo "=== OpenCode+ — connect llama to Phoenix ==="
echo "⚠ Сначала останавливаем ВСЁ на GPU (один llama, один порт)."
echo ""

bash "$OPENCODE_PLUS_DIR/stop-all.sh" 2>/dev/null || true
pkill -f llama-server 2>/dev/null || true
if command -v lms >/dev/null 2>&1; then
    lms unload 2>/dev/null || true
    if lms server status 2>/dev/null | grep -qi running; then
        echo "→ LM Studio server stop (освобождаем :1234) …"
        lms server stop 2>/dev/null || true
        sleep 2
    fi
fi
sleep 3

# На этом хосте Docker видит только host:1234 — один llama, без 8092
export LLAMA_CPP_PORT=1234
export LLAMA_CPP_API_BASE=http://host.docker.internal:1234/v1
bash "$OPENCODE_PLUS_DIR/start-llama-qwen.sh" --restart

echo ""
echo "→ Recreating LiteLLM (host.docker.internal:1234) …"
set -a
# shellcheck source=/dev/null
source "$PROJECT_ROOT/.env" 2>/dev/null || true
# shellcheck source=/dev/null
source "$PROJECT_ROOT/.env.llamacpp"
LLAMA_CPP_API_BASE="${LLAMA_CPP_API_BASE:-http://host.docker.internal:1234/v1}"
set +a
docker compose --env-file "$PROJECT_ROOT/.env" -f "$PROJECT_ROOT/compose.phoenix.yml" up -d --force-recreate litellm

echo ""
echo "→ Smoke: LiteLLM → llama …"
sleep 5
if curl -fsS -m 90 -H "Authorization: Bearer ${LITELLM_API_KEY:-sk-local}" \
    -H "Content-Type: application/json" \
    http://127.0.0.1:${LITELLM_HOST_PORT:-4000}/v1/chat/completions \
    -d '{"model":"qwen3.6-35b-heretic","messages":[{"role":"user","content":"ok"}],"max_tokens":5}' \
    | grep -q '"content"'; then
    echo "✓ LiteLLM → llama OK — traces should appear in Phoenix"
else
    echo "! Smoke failed — check: docker logs litellm --tail 50"
fi

echo ""
echo "  Phoenix UI:  http://127.0.0.1:${PHOENIX_HOST_PORT:-6006}"
echo "  LiteLLM:     http://127.0.0.1:${LITELLM_HOST_PORT:-4000}"
echo "  llama:       http://127.0.0.1:1234/v1"
echo ""
echo "  OpenCode via LiteLLM (Phoenix traces): OPENCODE_USE_LITELLM=1 in opencode+/.env"
echo "  Restart UI:  bash opencode+/stop-opencode.sh && bash opencode+/start-opencode.sh"
