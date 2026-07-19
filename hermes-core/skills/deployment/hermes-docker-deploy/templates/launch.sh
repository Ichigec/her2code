#!/usr/bin/env bash
# launch.sh — Hermes Portable: create connection.json + launch Electron GUI
# Template: copy, edit GUI_DIR path if needed, chmod +x, run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_HOME="${REAL_HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
[ -z "$REAL_HOME" ] && REAL_HOME="$HOME"

PORT_DASH="${PORT_DASH:-9123}"
DASH_TOKEN=***  # must match start-backend.sh
GUI_DIR="$SCRIPT_DIR/gui"
BIN="$GUI_DIR/Hermes"

echo "=========================================="
echo "  Hermes Portable — GUI"
echo "=========================================="

# Check binary
[ ! -f "$BIN" ] && { echo "ERROR: GUI binary not found: $BIN"; exit 1; }

# Check backend
curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1 || {
    echo "ERROR: Dashboard not responding on :$PORT_DASH"
    echo "   Start backend first: ./start-backend.sh"
    exit 1
}

# Kill old GUI
old_pid=$(pgrep -f "linux-.*-unpacked/Hermes" 2>/dev/null || true)
[ -n "$old_pid" ] && { kill "$old_pid" 2>/dev/null || true; sleep 2; }

# Create connection.json
CONN_DIR="$REAL_HOME/.config/Hermes"
mkdir -p "$CONN_DIR"
cat > "$CONN_DIR/connection.json" <<JSONEOF
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:${PORT_DASH}",
    "token": {
      "value": "${DASH_TOKEN}"
    },
    "authMode": "token"
  },
  "profiles": {}
}
JSONEOF
echo "OK: connection.json -> localhost:$PORT_DASH"

# ARM64 flags: --disable-gpu is MANDATORY (Chromium GPU sandbox crashes on Jetson)
exec "$BIN" --disable-gpu --disable-software-rasterizer --no-sandbox
