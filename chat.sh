#!/usr/bin/env bash
# chat.sh - Hermes Portable v4 CLI chat
# Simple curl-based chat through gateway API

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT_GW="${PORT_GW:-18649}"

# Get API key from .env
ENV_FILE="$SCRIPT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  API_KEY=$(grep '^API_SERVER_KEY=' "$ENV_FILE" | cut -d= -f2)
else
  echo "ERROR: .env not found. Run ./start-backend.sh first."
  exit 1
fi

[ -z "$API_KEY" ] && { echo "ERROR: API_SERVER_KEY empty in .env"; exit 1; }

# Check gateway
if ! curl -sf "http://localhost:$PORT_GW/health" >/dev/null 2>&1; then
  echo "ERROR: Gateway not responding on :$PORT_GW"
  echo "  Start backend first: ./start-backend.sh"
  exit 1
fi

echo "=========================================="
echo "  Hermes Portable v4 - CLI Chat"
echo "  Gateway: http://localhost:$PORT_GW"
echo "  Type 'exit' to quit"
echo "=========================================="
echo ""

while true; do
  printf "You: "
  read -r MSG || break
  [ "$MSG" = "exit" ] || [ "$MSG" = "quit" ] && break
  [ -z "$MSG" ] && continue

  echo -n "Hermes: "
  RESP=$(curl -sf "http://localhost:$PORT_GW/v1/chat/completions" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"hermes-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"$MSG\"}],\"max_tokens\":2000}" \
    2>&1)

  if echo "$RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    c = d.get('choices', [{}])[0]
    m = c.get('message', {}).get('content', '')
    print(m[:2000] if m else '(empty response)')
except Exception as e:
    print(f'(error: {e})')
" 2>/dev/null; then
    echo ""
  else
    echo "(request failed: $RESP)"
  fi
  echo ""
done

echo "Bye."
