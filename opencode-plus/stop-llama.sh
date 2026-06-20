#!/usr/bin/env bash
# Stop host llama-server only (free GPU for LM Studio).
set -euo pipefail

OPENCODE_PLUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$OPENCODE_PLUS_DIR/.run/llama.pid"

echo "=== OpenCode+ — stop llama.cpp ==="

if [ -f "$PIDFILE" ]; then
    pid="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "→ Stopping llama-server (pid=$pid) …"
        kill "$pid" 2>/dev/null || true
        for _ in {1..15}; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 1
        done
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PIDFILE"
fi

pkill -f 'llama-server' 2>/dev/null || true
if command -v fuser >/dev/null 2>&1; then
    fuser -k 8092/tcp 2>/dev/null || true
fi

sleep 2
if pgrep -f llama-server >/dev/null 2>&1; then
    echo "! llama-server still running" >&2
    pgrep -af llama-server | head -3 >&2
    exit 1
fi

echo "✓ llama.cpp stopped (VRAM free for LM Studio)"
