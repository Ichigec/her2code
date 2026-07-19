#!/bin/bash
# gui-recover.sh — full clean restart of Hermes Desktop GUI
# Usage: bash ~/.hermes/skills/deployment/hermes-gui-launch/scripts/gui-recover.sh
set -e

ARCH=$(uname -m | sed 's/aarch64/arm64/;s/x86_64/x64/')
BIN="$HOME/.hermes/hermes-agent/apps/desktop/release/linux-${ARCH}-unpacked/Hermes"
DASH_TOKEN=$(grep '^HERMES_DASHBOARD_SESSION_TOKEN=' "$HOME/.hermes-portable-dash/.env" | cut -d= -f2)

echo "==> Checking dashboard :9123..."
if ! curl -sf http://localhost:9123/api/status >/dev/null 2>&1; then
  echo "✗ Dashboard not running. Start backend first:"
  echo "  cd ~/dev/hermes_portable && REAL_HOME=$HOME bash ./start.sh full --3models"
  exit 1
fi
echo "  ✅ Dashboard alive"

echo "==> Killing old GUI processes..."
ps -eo pid,args | grep "release/linux-.*-unpacked/Hermes" | grep -vE "grep|zygote|chrome-sandbox" \
  | awk '{print $1}' | while read pid; do kill "$pid" 2>/dev/null; done
sleep 2

echo "==> Cleaning stale scopes..."
for s in $(systemctl --user list-units --all 'app-org.chromium.Chromium-*.scope' --no-legend 2>/dev/null | awk '{print $1}'); do
  systemctl --user stop "$s" 2>/dev/null
done

echo "==> Removing singleton locks..."
rm -f "$HOME/.config/Hermes/SingletonLock" "$HOME/.config/Hermes/SingletonCookie" "$HOME/.config/Hermes/SingletonSocket" 2>/dev/null

echo "==> Writing connection.json → dashboard :9123..."
# CRITICAL: Electron rewrites connection.json to mode:local on close.
# Must re-write to remote mode EVERY time before launch.
mkdir -p "$HOME/.config/Hermes"
cat > "$HOME/.config/Hermes/connection.json" <<EOF
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:9123",
    "token": { "value": "${DASH_TOKEN}" },
    "authMode": "token"
  },
  "profiles": {}
}
EOF

echo "==> Launching Hermes Desktop..."
# ARM64 Jetson: --disable-gpu is REQUIRED, not optional.
# Without it, Chromium GPU sandbox crashes (error_code=1002 → FATAL).
nohup "$BIN" --disable-gpu --disable-software-rasterizer --no-sandbox >/tmp/hermes-gui.log 2>&1 &
GUI_PID=$!
echo "  PID: $GUI_PID"

echo "==> Waiting for window..."
# NOTE: wmctrl -l can return empty even when the window exists.
# Cross-check with: xwininfo -root -tree 2>/dev/null | grep -i hermes
for i in $(seq 1 15); do
  sleep 1
  if xwininfo -root -tree 2>/dev/null | grep -qi '"Hermes"'; then
    echo "  ✅ Window visible after ${i}s"
    exit 0
  fi
done

echo "  ⚠️  No window after 15s. Check ~/.hermes/logs/desktop.log"
exit 1
