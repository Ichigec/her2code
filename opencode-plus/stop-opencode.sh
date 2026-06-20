#!/usr/bin/env bash
# Stop native opencode web (host process, no Docker).
set -euo pipefail

OPENCODE_PLUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$OPENCODE_PLUS_DIR/.." && pwd)"
RUN_DIR="$OPENCODE_PLUS_DIR/.run"
WEB_PIDFILE="$RUN_DIR/opencode-web.pid"

# shellcheck source=lib/opencode-env.sh
source "$OPENCODE_PLUS_DIR/lib/opencode-env.sh"
load_opencode_env "$PROJECT_ROOT" OPENCODE_WEB_HOST_PORT
OPENCODE_WEB_HOST_PORT="${OPENCODE_WEB_HOST_PORT:-3400}"

stop_pid() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null || return 0
    kill "$pid" 2>/dev/null || true
    for _ in {1..10}; do
        kill -0 "$pid" 2>/dev/null || return 0
        sleep 0.5
    done
    kill -9 "$pid" 2>/dev/null || true
}

echo "→ Stopping native opencode web …"

if [ -f "$WEB_PIDFILE" ]; then
    stop_pid "$(cat "$WEB_PIDFILE" 2>/dev/null || true)"
    rm -f "$WEB_PIDFILE"
fi

# Fallback: any host opencode web on our port
pkill -f "opencode web.*--port[ =]${OPENCODE_WEB_HOST_PORT}" 2>/dev/null || true
pkill -f "opencode web.*--port ${OPENCODE_WEB_HOST_PORT}" 2>/dev/null || true

# Stop Docker opencode if still running (avoid port 3400 conflict on next start)
if docker info >/dev/null 2>&1 \
    && [ "$(docker inspect --format='{{.State.Status}}' opencode 2>/dev/null || echo missing)" = "running" ]; then
    echo "→ Stopping Docker opencode container …"
    bash "$PROJECT_ROOT/opencode-stop.sh" 2>/dev/null || \
        docker compose -p opencode -f "$PROJECT_ROOT/compose.opencode.yml" down 2>/dev/null || true
fi

echo "✓ opencode stopped"
