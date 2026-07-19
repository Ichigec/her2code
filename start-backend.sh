#!/usr/bin/env bash
# start-backend.sh - Hermes Portable v4 Backend Launcher
# Auto-detects architecture, loads Docker image, starts gateway + dashboard

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_HOME="${REAL_HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
[ -z "$REAL_HOME" ] && REAL_HOME="$HOME"

export PORT_GW="${PORT_GW:-18649}"
export PORT_DASH="${PORT_DASH:-9123}"
export HERMES_HOME="${HERMES_HOME:-$REAL_HOME/.hermes-portable}"
export DASH_HOME="${DASH_HOME:-$REAL_HOME/.hermes-portable-dash}"
export HERMES_UID="$(id -u)"
export HERMES_GID="$(id -g)"
export DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-portable-v4}"

# Auto-detect architecture
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64)
    export DOCKER_PLATFORM="linux/arm64"
    IMAGE_TAG="hermes-agent:latest"
    TARBALL="$SCRIPT_DIR/docker/hermes-agent-arm64.tar.gz"
    ;;
  x86_64|amd64)
    export DOCKER_PLATFORM="linux/amd64"
    IMAGE_TAG="hermes-agent:x64"
    TARBALL="$SCRIPT_DIR/docker/hermes-agent-x64.tar.gz"
    ;;
  *)
    echo "ERROR: Unsupported architecture: $HOST_ARCH"
    exit 1
    ;;
esac

echo "=========================================="
echo "  Hermes Portable v4 - Backend ($HOST_ARCH)"
echo "=========================================="
echo "  Gateway:   :$PORT_GW"
echo "  Dashboard: :$PORT_DASH"
echo "  HERMES_HOME: $HERMES_HOME"
echo ""

# Check Docker
if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker not found. Install Docker first."
  exit 1
fi

# Generate API_SERVER_KEY if .env not present
ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "==> First run: creating .env from .env.example..."
  if [ -f "$SCRIPT_DIR/.env.example" ]; then
    cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
  else
    touch "$ENV_FILE"
  fi
  # Generate real API key
  GEN_KEY=$(openssl rand -hex 32 2>/dev/null || echo "auto-generated-key-$(date +%s)")
  echo "API_SERVER_KEY=$GEN_KEY" >> "$ENV_FILE"
  echo "  Generated API_SERVER_KEY"
fi

# Load Docker image if not present
if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_TAG}$"; then
  echo "==> Loading Docker image: $IMAGE_TAG"
  if [ -f "$TARBALL" ]; then
    docker load -i "$TARBALL"
    # Handle tag naming
    if [ "$HOST_ARCH" = "x86_64" ] || [ "$HOST_ARCH" = "amd64" ]; then
      docker tag hermes-agent:latest hermes-agent:x64 2>/dev/null || true
    fi
  else
    echo "ERROR: Docker image not found: $TARBALL"
    exit 1
  fi
else
  echo "==> Docker image $IMAGE_TAG already loaded"
fi

# Prepare data directories
mkdir -p "$HERMES_HOME" "$DASH_HOME"

# Copy hermes-core on first run
if [ ! -f "$HERMES_HOME/config.yaml" ]; then
  echo "==> First run: copying hermes-core to $HERMES_HOME..."
  if [ -d "$SCRIPT_DIR/hermes-core" ]; then
    cp -rL "$SCRIPT_DIR/hermes-core/"* "$HERMES_HOME/" 2>/dev/null || true
    echo "  Copied agents, skills, hooks, scripts, gates, config"
  fi
fi

# Clean stale locks
rm -rf "$HERMES_HOME/logs/gateways" "$DASH_HOME/logs/gateways" 2>/dev/null || true

# Stop old containers
echo "==> Stopping old containers..."
docker stop hermes-gateway hermes-dashboard 2>/dev/null || true
docker rm hermes-gateway hermes-dashboard 2>/dev/null || true

# Source .env for keys
set -a
. "$ENV_FILE" 2>/dev/null || true
set +a

API_KEY="${API_SERVER_KEY:-$(openssl rand -hex 32)}"

# Start gateway
echo "==> Starting gateway on :$PORT_GW..."
docker run -d \
  --name hermes-gateway \
  --network host \
  --restart unless-stopped \
  -e HERMES_UID="$HERMES_UID" \
  -e HERMES_GID="$HERMES_GID" \
  -e HERMES_HOME="/opt/data" \
  -e API_SERVER_HOST=0.0.0.0 \
  -e API_SERVER_PORT="$PORT_GW" \
  -e API_SERVER_KEY="$API_KEY" \
  -e GATEWAY_ALLOW_ALL_USERS=true \
  -v "$HERMES_HOME:/opt/data" \
  "$IMAGE_TAG" gateway run

echo "  Gateway PID: $(docker inspect --format '{{.State.Pid}}' hermes-gateway 2>/dev/null)"

# Wait for gateway health
echo "==> Waiting for gateway..."
READY=0
for i in $(seq 1 60); do
  if curl -sf "http://localhost:$PORT_GW/health" >/dev/null 2>&1; then
    READY=1
    echo "  Gateway ready after ${i}s"
    break
  fi
  sleep 2
done
if [ "$READY" = "0" ]; then
  echo "  WARNING: Gateway not responding after 120s"
  echo "  Check: docker logs hermes-gateway"
fi

# Start dashboard
echo "==> Starting dashboard on :$PORT_DASH..."
docker run -d \
  --name hermes-dashboard \
  --network host \
  --restart unless-stopped \
  -e HERMES_UID="$HERMES_UID" \
  -e HERMES_GID="$HERMES_GID" \
  -e HERMES_HOME="/opt/data" \
  -e HERMES_DASHBOARD_SESSION_TOKEN="$DASH_TOKEN" \
  -e GATEWAY_HEALTH_URL="http://localhost:$PORT_GW/health" \
  -e PYTHONPATH="/opt/data" \
  -v "$DASH_HOME:/opt/data" \
  "$IMAGE_TAG" dashboard \
  --host 127.0.0.1 \
  --port "$PORT_DASH" \
  --insecure \
  --tui \
  --no-open \
  --skip-build

echo "  Dashboard PID: $(docker inspect --format '{{.State.Pid}}' hermes-dashboard 2>/dev/null)"

# Wait for dashboard
echo "==> Waiting for dashboard..."
READY=0
for i in $(seq 1 60); do
  if curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1; then
    READY=1
    echo "  Dashboard ready after ${i}s"
    break
  fi
  sleep 2
done
if [ "$READY" = "0" ]; then
  echo "  WARNING: Dashboard not responding after 120s"
  echo "  Check: docker logs hermes-dashboard"
fi

# Copy tui_gateway to dashboard container (fixes 95% hang)
TG_SRC="$HERMES_HOME/hermes-agent/tui_gateway"
if [ -d "$TG_SRC" ]; then
  tar -C "$HERMES_HOME/hermes-agent" -c tui_gateway/ 2>/dev/null | \
    docker exec -i hermes-dashboard tar -C /opt/data -x 2>/dev/null && \
    echo "  tui_gateway deployed to dashboard" || true
fi

echo ""
echo "=========================================="
echo "  Backend is UP!"
echo "  Gateway API:  http://localhost:$PORT_GW"
echo "  Dashboard:    http://localhost:$PORT_DASH"
echo "  API Key:      $API_KEY"
echo "  Dash Token:   $DASH_TOKEN"
echo "=========================================="
echo ""
echo "  Next: ./launch.sh    (to open GUI)"
echo "  Or:   ./chat.sh      (CLI mode)"
