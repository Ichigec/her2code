#!/usr/bin/env bash
# start-backend.sh — Hermes Portable: prepare volumes + docker compose up
# Template: copy into your portable folder, chmod +x, run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Real HOME (Hermes overrides $HOME to ~/.hermes/home)
REAL_HOME="${REAL_HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
[ -z "$REAL_HOME" ] && REAL_HOME="$HOME"

# ⚠️ CRITICAL: unset inherited HERMES_HOME from parent Hermes daemon!
# Without this, the script inherits ~/.hermes from the running Hermes Agent
# process, and docker compose mounts the WRONG volume.
unset HERMES_HOME DASH_HOME || true

# Settings
export PORT_GW="${PORT_GW:-18649}"
export PORT_DASH="${PORT_DASH:-9123}"
export HERMES_HOME="$REAL_HOME/.hermes-portable"
export DASH_HOME="$REAL_HOME/.hermes-portable-dash"
export HERMES_IMAGE="${HERMES_IMAGE:-hermes-agent}"
export HERMES_UID="$(id -u)"
export HERMES_GID="$(id -g)"
DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-portable-dash}"
export API_SERVER_KEY="${API_SERVER_KEY:-}"

echo "=========================================="
echo "  Hermes Portable — Backend"
echo "  Gateway:$PORT_GW  Dashboard:$PORT_DASH"
echo "  Data: $HERMES_HOME"
echo "=========================================="

# Check Docker
command -v docker &>/dev/null || { echo "ERROR: Docker not installed"; exit 1; }
docker info &>/dev/null 2>&1 || { echo "ERROR: Docker daemon not running"; exit 1; }

# Check/load image — auto-load from tarball if missing
if ! docker images --format '{{.Repository}}' | grep -q "^${HERMES_IMAGE}$"; then
    TARBALL="$SCRIPT_DIR/docker/hermes-agent-arm64.tar.gz"
    if [ -f "$TARBALL" ]; then
        echo "Loading image from tarball (~30 sec)..."
        docker load --input "$TARBALL"
        echo "OK: Image loaded"
    else
        echo "ERROR: Image '$HERMES_IMAGE' not found and no tarball at $TARBALL"
        exit 1
    fi
fi
echo "OK: Image '$HERMES_IMAGE' ready"

# Prepare directories
echo "Preparing data directories..."
mkdir -p "$HERMES_HOME/logs" "$HERMES_HOME/sessions"
mkdir -p "$DASH_HOME/logs" "$DASH_HOME/sessions"

# Config
[ ! -f "$HERMES_HOME/config.yaml" ] && cp "$SCRIPT_DIR/config/config.docker.yaml" "$HERMES_HOME/config.yaml"
cp "$HERMES_HOME/config.yaml" "$DASH_HOME/config.yaml"

# Gateway .env (WITH API_SERVER settings)
if [ ! -f "$HERMES_HOME/.env" ]; then
    [ -z "$API_SERVER_KEY" ] && API_SERVER_KEY="$(openssl rand -hex 32)"
    cat > "$HERMES_HOME/.env" <<EOF
API_SERVER_ENABLED=true
API_SERVER_KEY=$API_SERVER_KEY
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=$PORT_GW
EOF
    chmod 600 "$HERMES_HOME/.env"
    echo "OK: Gateway .env created"
else
    sed -i "s/^API_SERVER_PORT=.*/API_SERVER_PORT=$PORT_GW/" "$HERMES_HOME/.env"
    API_SERVER_KEY="$(grep '^API_SERVER_KEY=' "$HERMES_HOME/.env" | cut -d= -f2)"
fi

# Dashboard .env — NO API_SERVER settings! (prevents port conflict)
if [ ! -f "$DASH_HOME/.env" ]; then
    cat > "$DASH_HOME/.env" <<EOF
HERMES_DASHBOARD_SESSION_TOKEN=$DASH_TOKEN
EOF
    chmod 600 "$DASH_HOME/.env"
    echo "OK: Dashboard .env created"
fi

# Clean s6-log locks
rm -rf "$HERMES_HOME/logs/gateways" "$DASH_HOME/logs/gateways" 2>/dev/null || true

# Stop old containers
docker rm -f hermes-gateway hermes-dashboard 2>/dev/null || true

# Launch via compose
echo "Starting containers..."
cd "$SCRIPT_DIR/docker"
docker compose --env-file /dev/null up -d

# Wait for gateway (up to 2 min)
echo -n "Waiting for gateway"
for i in $(seq 1 60); do
    curl -sf "http://localhost:$PORT_GW/health" >/dev/null 2>&1 && { echo ""; echo "OK: Gateway ready"; break; }
    [ $i -eq 60 ] && { echo ""; echo "FAIL: Gateway timeout"; docker logs hermes-gateway --tail 20; exit 1; }
    sleep 2; echo -n "."
done

# Wait for dashboard (up to 3 MIN — s6-overlay cold start is slow!)
echo -n "Waiting for dashboard"
for i in $(seq 1 60); do
    curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1 && { echo ""; echo "OK: Dashboard ready"; break; }
    [ $i -eq 60 ] && { echo ""; echo "WARN: Dashboard not ready after 3 min (still loading?)"; }
    sleep 3; echo -n "."
done

echo "$API_SERVER_KEY" > "$SCRIPT_DIR/.api-key"
echo ""
echo "Backend ready! Now run: ./launch.sh"
