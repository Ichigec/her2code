#!/usr/bin/env bash
# launch.sh - Hermes Portable v4 GUI Launcher
# Auto-selects correct binary based on host architecture

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_HOME="${REAL_HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
[ -z "$REAL_HOME" ] && REAL_HOME="$HOME"

PORT_DASH="${PORT_DASH:-9123}"
DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-docker-b}"
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64) ARCH="arm64" ;;
  x86_64|amd64)  ARCH="x64" ;;
  *) echo "ERROR: unsupported: $HOST_ARCH"; exit 1 ;;
esac

GUI_DIR="$SCRIPT_DIR/gui-$ARCH"
BIN="$GUI_DIR/Hermes"

if [ ! -f "$BIN" ]; then
  echo "ERROR: GUI binary not found: $BIN"
  exit 1
fi

echo "=========================================="
echo "  Hermes Portable v4 - GUI ($ARCH)"
echo "=========================================="
echo "  Dashboard: http://localhost:$PORT_DASH"
echo ""

# Check backend
if ! curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1; then
  echo "ERROR: Dashboard not responding on :$PORT_DASH"
  echo "  Start backend first: ./start-backend.sh"
  exit 1
fi
echo "  Backend OK"

# Kill old GUI
echo "  Cleaning old GUI processes..."
pgrep -f "gui-.*/Hermes" 2>/dev/null | while read pid; do kill "$pid" 2>/dev/null; done
sleep 1

# Clean locks
rm -f "$REAL_HOME/.config/Hermes/SingletonLock" \
      "$REAL_HOME/.config/Hermes/SingletonCookie" \
      "$REAL_HOME/.config/Hermes/SingletonSocket" 2>/dev/null || true

# Write connection.json -> DASHBOARD (not gateway!)
CONN_DIR="$REAL_HOME/.config/Hermes"
mkdir -p "$CONN_DIR"
printf '{"mode":"remote","remote":{"url":"http://localhost:%s","token":{"value":"%s"},"authMode":"token"},"profiles":{}}\n' \
    "$PORT_DASH" "$DASH_TOKEN" > "$CONN_DIR/connection.json"

echo "  Launching GUI..."
"$BIN" --disable-gpu --disable-software-rasterizer --no-sandbox
