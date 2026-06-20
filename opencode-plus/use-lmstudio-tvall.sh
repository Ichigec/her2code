#!/usr/bin/env bash
# Stop llama, refresh LiteLLM + OpenCode for LM Studio tvall (default) + llama alias in gateway.
set -euo pipefail

OPENCODE_PLUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== OpenCode+ — LM Studio tvall (llama off) ==="
echo ""

bash "$OPENCODE_PLUS_DIR/stop-llama.sh"

echo ""
echo "→ LM Studio: загрузите tvall43 в GUI и включите Local Server (:1234)"
if command -v lms >/dev/null 2>&1; then
    echo "   Проверка: lms ps && curl -s http://127.0.0.1:1234/v1/models | head"
else
    echo "   Проверка: curl -s http://127.0.0.1:1234/v1/models"
fi
echo ""

bash "$OPENCODE_PLUS_DIR/start-litellm-dual.sh"

echo ""
bash "$OPENCODE_PLUS_DIR/start-opencode-litellm.sh"
