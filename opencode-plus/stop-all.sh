#!/usr/bin/env bash
# Stop native opencode + host llama-server.
set -euo pipefail

OPENCODE_PLUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$OPENCODE_PLUS_DIR/.run/llama.pid"

echo "=== OpenCode+ — stop ==="

bash "$OPENCODE_PLUS_DIR/stop-opencode.sh"
bash "$OPENCODE_PLUS_DIR/stop-llama.sh" 2>/dev/null || true

echo "✓ Done"
