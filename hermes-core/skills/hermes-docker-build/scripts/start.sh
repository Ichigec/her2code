#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Hermes Portable — Unified Start Script
# ═══════════════════════════════════════════════════════════════
# Two deployment variants:
#
#   Variant A (compose):  docker-compose based, simple gateway+dashboard
#   Variant B (full):     docker run with full stack (LiteLLM, Neo4j, etc.)
#
# Usage:
#   ./start.sh                    # Default: compose (Variant A)
#   ./start.sh compose            # Variant A: docker-compose
#   ./start.sh full               # Variant B: full stack (gateway+dashboard+infra)
#   ./start.sh full --model M     # Variant B + local GGUF model
#   ./start.sh minimal            # Variant B: just gateway, no dashboard
#   ./start.sh gui                # Launch Desktop GUI (connects to running dashboard)
#   ./start.sh build              # Build Docker image
#   ./start.sh stop               # Stop all Hermes containers
#   ./start.sh litellm            # Start LiteLLM proxy (:4000 → :8092)
#   ./start.sh status             # Show status
#   ./start.sh logs [service]     # Show logs (gateway/dashboard/neo4j/litellm)
#   ./start.sh help               # Show this help
#
# LLM routing modes:
#   Direct:   Gateway → localhost:8092 (llama-server)         ← config.docker.yaml
#   Proxied:  Gateway → :4000 (LiteLLM) → :8092 + cloud APIs ← config.docker.litellm.yaml
#   Switch:   cp config/config.docker.litellm.yaml config/config.docker.yaml
#
# Environment variables (override defaults):
#   PORT_GW=18648         Gateway API port
#   PORT_DASH=9121        Dashboard port
#   HERMES_HOME=~/.hermes-docker   Data directory
#   DASH_TOKEN=sk-docker  Dashboard session token
#   HERMES_IMAGE=hermes-agent      Docker image name
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTABLE_DIR="$SCRIPT_DIR"

# Detect real user home (Hermes overrides $HOME)
REAL_HOME="${REAL_HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
[ -z "$REAL_HOME" ] && REAL_HOME="/home/$(whoami)"

# ── Defaults ──────────────────────────────────────────────────
PORT_GW="${PORT_GW:-18648}"
PORT_DASH="${PORT_DASH:-9121}"
HERMES_HOME="${HERMES_DOCKER_HOME:-$REAL_HOME/.hermes-docker}"
DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-docker-b}"
HERMES_IMAGE="${HERMES_IMAGE:-hermes-agent}"
CONTAINER_GW="hermes-gateway"
CONTAINER_DASH="hermes-dashboard"

# ── Helpers ───────────────────────────────────────────────────
log()  { echo -e "  $1"; }
ok()   { echo -e "  ✅ $1"; }
err()  { echo -e "  ❌ $1" >&2; }
wait_for() {
  local url="$1" name="$2" max="${3:-150}"
  echo -n "  ⏳ Ожидание $name"
  for i in $(seq 1 "$max"); do
    curl -sf "$url" >/dev/null 2>&1 && { echo ""; return 0; }
    sleep 2; echo -n "."
  done
  echo ""
  return 1
}

ensure_image() {
  if ! docker image inspect "$HERMES_IMAGE" >/dev/null 2>&1; then
    err "Образ '$HERMES_IMAGE' не найден."
    echo "  Соберите: ./start.sh build"
    exit 1
  fi
}

ensure_deps() {
  for cmd in docker curl; do
    command -v "$cmd" >/dev/null 2>&1 || { err "Не найден: $cmd"; exit 1; }
  done
}

prepare_home() {
  mkdir -p "$HERMES_HOME/logs" "$HERMES_HOME/sessions"
  # Config — ALWAYS use config.docker.yaml (hardcoded, no template vars)
  local tmpl="$PORTABLE_DIR/config/config.docker.yaml"
  if [ -f "$tmpl" ]; then
    cp "$tmpl" "$HERMES_HOME/config.yaml"
  fi
  # .env with generated API key if not exists
  if [ ! -f "$HERMES_HOME/.env" ]; then
    local api_key
    api_key=$(openssl rand -hex 32)
    cat > "$HERMES_HOME/.env" <<EOF
API_SERVER_ENABLED=true
API_SERVER_KEY=$api_key
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=$PORT_GW
LLAMA_CPP_API_KEY=llama-cpp
EOF
    ok "Создан .env (API_SERVER_KEY сгенерирован)"
  else
    # Ensure LLAMA_CPP_API_KEY exists
    grep -q LLAMA_CPP_API_KEY "$HERMES_HOME/.env" 2>/dev/null || echo "LLAMA_CPP_API_KEY=llama-cpp" >> "$HERMES_HOME/.env"
  fi
  # ⚠️ Clean stale s6-log locks (gateway+dashboard share /opt/data volume)
  # Without this, gateway crash-loops: "s6-log: fatal: unable to lock ... Resource busy"
  rm -rf "$HERMES_HOME/logs/gateways" 2>/dev/null || true
  # Copy tui_gateway to persistent volume (needed for dashboard WebSocket)
  if [ ! -d "$HERMES_HOME/tui_gateway" ]; then
    local src=""
    for cand in "$PORTABLE_DIR/hermes-agent/tui_gateway" "$REAL_HOME/.hermes/hermes-agent/tui_gateway"; do
      [ -d "$cand" ] && src="$cand" && break
    done
    if [ -n "$src" ]; then
      cp -r "$src" "$HERMES_HOME/tui_gateway" 2>/dev/null || true
      log "Скопирован tui_gateway → $HERMES_HOME/tui_gateway"
    fi
  fi
}

# ═══════════════════════════════════════════════════════════════
# VARIANT A: docker-compose
# ═══════════════════════════════════════════════════════════════
start_compose() {
  ensure_deps
  ensure_image

  local compose_file="$PORTABLE_DIR/docker/docker-compose.yml"
  [ -f "$compose_file" ] || { err "Не найден $compose_file"; exit 1; }

  # Prepare data dir
  prepare_home

  # Export vars for compose
  export PORT_GW PORT_DASH HERMES_HOME DASH_TOKEN HERMES_IMAGE
  export API_SERVER_PORT="$PORT_GW"
  export HERMES_DISABLE_MESSAGING=1
  export GATEWAY_ALLOW_ALL_USERS=true

  # Source .env for API keys
  [ -f "$HERMES_HOME/.env" ] && set -a; . "$HERMES_HOME/.env"; set +a

  echo "🚀 Variant A: docker-compose"
  log "Gateway: :$PORT_GW  Dashboard: :$PORT_DASH"
  log "Data: $HERMES_HOME"

  cd "$PORTABLE_DIR/docker"
  docker compose -f docker-compose.yml up -d

  wait_for "http://localhost:$PORT_GW/health" "gateway" 150 || {
    err "Gateway не запустился"
    docker compose -f docker-compose.yml logs hermes --tail 20
    exit 1
  }
  ok "Gateway: http://localhost:$PORT_GW/health"

  # Dashboard
  start_dashboard_container

  echo ""
  ok "Variant A готов. Команды:"
  echo "  ./start.sh status     # статус"
  echo "  ./start.sh gui        # запустить GUI"
  echo "  ./start.sh stop       # остановить"
}

# ── LLM server functions ─────────────────────────────────────
start_llama_default() {
  # Try opencode+ start-llama-qwen.sh first (full MTP support)
  local script=""
  for cand in "$PORTABLE_DIR/models/start-llama.sh" "$REAL_HOME/cursor/opencode+/start-llama-qwen.sh"; do
    [ -f "$cand" ] && script="$cand" && break
  done
  if [ -n "$script" ] && [ -x "$REAL_HOME/dev/llama.cpp/build/bin/llama-server" ]; then
    # Already running?
    if curl -sf http://localhost:8092/v1/models >/dev/null 2>&1; then
      ok "llama-server уже работает на :8092"
      return
    fi
    echo "🧠 Запуск llama-server (Qwen3.6-35B-heretic, MTP)..."
    bash "$script" --daemon 2>/dev/null || true
    # Wait for ready
    for i in $(seq 1 60); do
      curl -sf http://localhost:8092/v1/models >/dev/null 2>&1 && break
      sleep 2
    done
    if curl -sf http://localhost:8092/v1/models >/dev/null 2>&1; then
      ok "llama-server готов на :8092"
    else
      log "⚠️ llama-server не ответил за 120с (возможно грузит модель)"
    fi
  else
    log "⚠️ llama-server не найден. Docker будет использовать облачный провайдер"
  fi
}

start_llama_server() {
  local model_path="$1"
  local gpu_layers="${2:-41}"
  local llama_bin="$REAL_HOME/dev/llama.cpp/build/bin/llama-server"

  if curl -sf http://localhost:8092/v1/models >/dev/null 2>&1; then
    ok "llama-server уже работает на :8092"
    return
  fi

  if [ ! -x "$llama_bin" ]; then
    log "⚠️ llama-server не найден: $llama_bin"
    return
  fi

  nohup "$llama_bin" \
    --model "$model_path" \
    --port 8092 --host 0.0.0.0 \
    --n-gpu-layers "$gpu_layers" \
    --ctx-size 262144 --threads 20 \
    --alias "$(basename "$model_path" .gguf)" \
    > "$HERMES_HOME/logs/llama.log" 2>&1 &

  ok "llama-server PID $! → :8092"
  for i in $(seq 1 60); do
    curl -sf http://localhost:8092/v1/models >/dev/null 2>&1 && break
    sleep 2
  done
  curl -sf http://localhost:8092/v1/models >/dev/null 2>&1 \
    && ok "llama-server готов" \
    || log "⚠️ llama-server ещё грузит модель"
}

# ═══════════════════════════════════════════════════════════════
# VARIANT B: full stack (docker run)
# ═══════════════════════════════════════════════════════════════
start_full() {
  ensure_deps
  ensure_image
  prepare_home

  local model=""
  local gpu_layers=""
  local use_litellm=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model) model="$2"; shift 2 ;;
      --gpu-layers) gpu_layers="$2"; shift 2 ;;
      --litellm) use_litellm=true; shift ;;
      *) shift ;;
    esac
  done

  echo "🚀 Variant B: full stack (docker run)"

  # ── Optional: local model ──
  if [ -n "$model" ]; then
    if [ ! -f "$model" ]; then
      err "Файл модели не найден: $model"
      exit 1
    fi
    echo "🧠 Локальная модель: $model"
    start_llama_server "$model" "$gpu_layers"
  else
    # Try to start default llama-server from profile
    start_llama_default
  fi

  # ── LiteLLM Proxy (optional, --litellm flag) ──
  if [ "$use_litellm" = "true" ]; then
    start_litellm
    # Switch config to proxied mode
    local litellm_cfg="$PORTABLE_DIR/config/config.docker.litellm.yaml"
    if [ -f "$litellm_cfg" ]; then
      cp "$litellm_cfg" "$HERMES_HOME/config.yaml"
      log "Config → LiteLLM proxied mode (:4000)"
    fi
  fi

  # ── Gateway ──
  echo "📡 Запуск gateway..."
  docker rm -f "$CONTAINER_GW" 2>/dev/null || true

  docker run -d --name "$CONTAINER_GW" --restart unless-stopped \
    --network host \
    -v "$HERMES_HOME:/opt/data" \
    -e "API_SERVER_PORT=$PORT_GW" \
    -e HERMES_DISABLE_MESSAGING=1 \
    -e GATEWAY_ALLOW_ALL_USERS=true \
    "$HERMES_IMAGE" gateway run

  wait_for "http://127.0.0.1:$PORT_GW/health" "gateway" 90 || {
    err "Gateway не запустился"
    docker logs "$CONTAINER_GW" --tail 20
    exit 1
  }
  ok "Gateway: http://127.0.0.1:$PORT_GW/health"

  # ── Dashboard ──
  start_dashboard_container

  # ── Summary ──
  echo ""
  echo "╔════════════════════════════════════════════════╗"
  echo "║         Hermes Full Stack — ГОТОВО            ║"
  echo "╠════════════════════════════════════════════════╣"
  echo "║  Gateway:   http://127.0.0.1:$PORT_GW/health        ║"
  echo "║  Dashboard: http://127.0.0.1:$PORT_DASH              ║"
  echo "║  Token:     $DASH_TOKEN                        ║"
  echo "║  Data:      $HERMES_HOME"
  echo "╚════════════════════════════════════════════════╝"
  echo ""
  echo "  ./start.sh gui      # запустить GUI"
  echo "  ./start.sh stop     # остановить"
}

# ═══════════════════════════════════════════════════════════════
# VARIANT B: minimal (just gateway)
# ═══════════════════════════════════════════════════════════════
start_minimal() {
  ensure_deps
  ensure_image
  prepare_home

  echo "🚀 Variant B: minimal (gateway only)"

  docker rm -f "$CONTAINER_GW" 2>/dev/null || true

  docker run -d --name "$CONTAINER_GW" --restart unless-stopped \
    --network host \
    -v "$HERMES_HOME:/opt/data" \
    -e "API_SERVER_PORT=$PORT_GW" \
    -e HERMES_DISABLE_MESSAGING=1 \
    -e GATEWAY_ALLOW_ALL_USERS=true \
    "$HERMES_IMAGE" gateway run

  wait_for "http://127.0.0.1:$PORT_GW/health" "gateway" 90 || {
    err "Gateway не запустился"
    docker logs "$CONTAINER_GW" --tail 30
    exit 1
  }
  ok "Gateway: http://127.0.0.1:$PORT_GW/health"
  echo "  Данные: $HERMES_HOME"
  echo "  Остановка: ./start.sh stop"
}

# ═══════════════════════════════════════════════════════════════
# LiteLLM Proxy container
# ═══════════════════════════════════════════════════════════════
# Routes :4000 → host llama-server :8092 (qwen3.6-35b-heretic).
# arm64-native image (main-stable). НЕ v1.83.7-stable (amd64 QEMU SIGSEGV).
LITELLM_PORT="${LITELLM_PORT:-4000}"
LITELLM_IMAGE="${LITELLM_IMAGE:-ghcr.io/berriai/litellm-database:main-stable}"

start_litellm() {
  ensure_deps

  echo "🔀 LiteLLM Proxy (arm64-native)..."

  # Already running?
  if curl -sf "http://localhost:$LITELLM_PORT/health/readiness" >/dev/null 2>&1; then
    ok "LiteLLM уже запущен на :$LITELLM_PORT"
    return
  fi

  docker rm -f hermes-litellm 2>/dev/null || true

  local litellm_cfg="$PORTABLE_DIR/config/litellm/config.yaml"
  [ -f "$litellm_cfg" ] || { err "Нет $litellm_cfg"; exit 1; }

  # Pull arm64 image if not present
  if ! docker image inspect "$LITELLM_IMAGE" >/dev/null 2>&1; then
    log "Pull: $LITELLM_IMAGE (arm64)..."
    docker pull --platform linux/arm64 "$LITELLM_IMAGE" 2>&1 | tail -3
  fi

  docker run -d --name hermes-litellm --restart unless-stopped \
    --network host \
    -v "$litellm_cfg:/app/config.yaml:ro" \
    -v hermes_litellm_db:/app/db \
    -e LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-litellm-master-key}" \
    -e DATABASE_URL=sqlite:///app/db/litellm.db \
    -e LLAMA_CPP_API_BASE="${LLAMA_CPP_API_BASE:-http://127.0.0.1:8092/v1}" \
    -e LLAMA_CPP_API_KEY="${LLAMA_CPP_API_KEY:-llama-cpp}" \
    -e DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}" \
    -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    -e GLM_API_KEY="${GLM_API_KEY:-}" \
    "$LITELLM_IMAGE" \
    --config /app/config.yaml --port "$LITELLM_PORT" --host 0.0.0.0

  wait_for "http://localhost:$LITELLM_PORT/health/readiness" "LiteLLM" 30 || {
    err "LiteLLM не запустился"
    docker logs hermes-litellm --tail 20
    exit 1
  }
  ok "LiteLLM: http://localhost:$LITELLM_PORT/v1/models"

  # Verify model routing
  local models
  models=$(curl -sf "http://localhost:$LITELLM_PORT/v1/models" \
    -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-sk-litellm-master-key}" 2>/dev/null \
    | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin).get('data',[])]" 2>/dev/null || echo "")
  if echo "$models" | grep -q "qwen3.6-35b-heretic"; then
    ok "Модель qwen3.6-35b-heretic доступна через LiteLLM"
  else
    log "⚠️ qwen3.6-35b-heretic не найден в /v1/models — проверьте llama-server :8092"
  fi
}

# ═══════════════════════════════════════════════════════════════
# Dashboard container (shared by both variants)
# ═══════════════════════════════════════════════════════════════
start_dashboard_container() {
  if curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1; then
    ok "Dashboard уже запущен на :$PORT_DASH"
    return
  fi

  echo "🖥️  Запуск Dashboard..."
  docker rm -f "$CONTAINER_DASH" 2>/dev/null || true

  docker run -d --name "$CONTAINER_DASH" --restart unless-stopped \
    --network host \
    -v "$HERMES_HOME:/opt/data" \
    -e HERMES_DASHBOARD_SESSION_TOKEN="$DASH_TOKEN" \
    -e PYTHONPATH=/opt/data \
    -e GATEWAY_HEALTH_URL="http://127.0.0.1:$PORT_GW/health" \
    "$HERMES_IMAGE" dashboard --host 127.0.0.1 --port "$PORT_DASH" \
    --insecure --tui --no-open --skip-build

  wait_for "http://localhost:$PORT_DASH/api/status" "dashboard" 90 || {
    err "Dashboard не запустился"
    docker logs "$CONTAINER_DASH" --tail 20
    exit 1
  }
  ok "Dashboard: http://localhost:$PORT_DASH/api/status"
}

# ═══════════════════════════════════════════════════════════════
# Desktop GUI
# ═══════════════════════════════════════════════════════════════
# connection.json — ЕДИНСТВЕННЫЙ надёжный способ переключить GUI
# в remote mode. Env vars HERMES_DESKTOP_REMOTE_URL НЕ работают
# (проверено 2026-06-22, GUI игнорирует их и читает connection.json).
CONNECTION_JSON="$REAL_HOME/.config/Hermes/connection.json"

start_gui() {
  local bin=""
  local arch=$(uname -m)
  # aarch64 → arm64, x86_64 → x64 (electron-builder naming)
  case "$arch" in
    aarch64|arm64) arch="arm64" ;;
    x86_64|amd64)  arch="x64" ;;
  esac
  for cand in \
    "$REAL_HOME/.hermes/hermes-agent/apps/desktop/release/linux-${arch}-unpacked/Hermes" \
    "$PORTABLE_DIR/hermes-agent/apps/desktop/release/linux-${arch}-unpacked/Hermes"; do
    [ -f "$cand" ] && bin="$cand" && break
  done

  if [ -z "$bin" ]; then
    err "GUI бинарник не найден (arch=$arch)"
    echo "  Установите: hermes setup  или  ./scripts/build-gui.sh"
    exit 1
  fi

  # ── Auto-detect dashboard port ──
  if ! curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1; then
    for p in 9122 9120 19119 9121; do
      if curl -sf "http://localhost:$p/api/status" >/dev/null 2>&1; then
        PORT_DASH="$p"
        log "Dashboard найден на :$PORT_DASH"
        break
      fi
    done
  fi

  if ! curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1; then
    err "Dashboard не отвечает"
    echo "  Запустите сначала: ./start.sh compose  (или full)"
    exit 1
  fi

  # ── Kill any running Hermes GUI (it rewrites connection.json on close) ──
  local old_pid
  old_pid=$(pgrep -f "release/linux-.*-unpacked/Hermes" 2>/dev/null || true)
  if [ -n "$old_pid" ]; then
    log "Останавливаю текущий GUI (PID $old_pid)..."
    kill $old_pid 2>/dev/null || true
    sleep 2
  fi

  # ── Write remote connection.json ──
  # Вложенная структура + токен как объект {value: "..."} — КРИТИЧНО
  mkdir -p "$(dirname "$CONNECTION_JSON")"
  printf '%s\n' \
    '{' \
    '  "mode": "remote",' \
    "  \"remote\": {" \
    "    \"url\": \"http://localhost:${PORT_DASH}\"," \
    '    "token": {' \
    "      \"value\": \"${DASH_TOKEN}\"" \
    '    },' \
    '    "authMode": "token"' \
    '  },' \
    '  "profiles": {}' \
    '}' > "$CONNECTION_JSON"

  ok "connection.json → remote :${PORT_DASH}"

  echo "🖥️  Запуск Desktop GUI..."
  echo "  Dashboard: http://localhost:${PORT_DASH}"
  echo "  Для возврата на локальный: echo '{\"mode\":\"local\"}' > ~/.config/Hermes/connection.json"
  echo ""

  ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" \
    "$bin" --no-sandbox
}

# ═══════════════════════════════════════════════════════════════
# Build Docker image
# ═══════════════════════════════════════════════════════════════
build_image() {
  ensure_deps
  local ctx=""
  for cand in \
    "$HOME/.hermes/hermes-agent" \
    "$PORTABLE_DIR/hermes-agent" \
    "$PORTABLE_DIR/../hermes-agent"; do
    [ -f "$cand/Dockerfile" ] && ctx="$cand" && break
  done
  if [ -z "$ctx" ]; then
    err "Dockerfile не найден. Укажите путь: HERMES_BUILD_CTX=/path ./start.sh build"
    exit 1
  fi

  echo "🔨 Сборка Docker образа из $ctx..."
  cd "$ctx"

  # Fix base image SHA
  if docker pull ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie >/dev/null 2>&1; then
    local sha
    sha=$(docker inspect ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie --format='{{index .RepoDigests 0}}' 2>/dev/null)
    if [ -n "$sha" ]; then
      sed -i "1s|FROM .*|FROM $sha AS uv_source|" Dockerfile 2>/dev/null || true
      log "Base image SHA: ${sha:0:40}..."
    fi
  fi

  docker build -t "$HERMES_IMAGE" .
  ok "Образ собран: $HERMES_IMAGE"
}

# ═══════════════════════════════════════════════════════════════
# Stop
# ═══════════════════════════════════════════════════════════════
stop_all() {
  echo "🛑 Остановка..."
  docker stop "$CONTAINER_DASH" 2>/dev/null && docker rm "$CONTAINER_DASH" 2>/dev/null || true
  docker stop "$CONTAINER_GW" 2>/dev/null && docker rm "$CONTAINER_GW" 2>/dev/null || true
  docker stop hermes-litellm 2>/dev/null && docker rm hermes-litellm 2>/dev/null || true
  # Also try compose down
  if [ -f "$PORTABLE_DIR/docker/docker-compose.yml" ]; then
    cd "$PORTABLE_DIR/docker" && docker compose down 2>/dev/null || true
  fi
  ok "Остановлено"
}

# ═══════════════════════════════════════════════════════════════
# Status
# ═══════════════════════════════════════════════════════════════
show_status() {
  echo "════════════════════════════════════════════════════"
  echo "  Hermes Portable — Status"
  echo "════════════════════════════════════════════════════"

  echo ""
  echo "── Gateway (:${PORT_GW}) ──"
  local gw=$(curl -sf "http://localhost:$PORT_GW/health" 2>/dev/null)
  if [ -n "$gw" ]; then
    echo "  ✅ $gw"
  else
    echo "  ❌ Не отвечает"
  fi

  echo ""
  echo "── Dashboard (:${PORT_DASH}) ──"
  local dash=$(curl -sf "http://localhost:$PORT_DASH/api/status" 2>/dev/null)
  if [ -n "$dash" ]; then
    echo "$dash" | python3 -c "
import sys, json
try:
  d = json.load(sys.stdin)
  print(f'  ✅ version={d.get(\"version\",\"?\")} gw_running={d.get(\"gateway_running\",\"?\")} sessions={d.get(\"active_sessions\",\"?\")}')
except: print('  ⚠️ Не удалось распарсить')
" 2>/dev/null || echo "  ✅ отвечает"
  else
    echo "  ❌ Не отвечает"
  fi

  echo ""
  echo "── Containers ──"
  docker ps --filter "name=hermes-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  Нет"

  echo ""
  echo "── LiteLLM (:${LITELLM_PORT:-4000}) ──"
  local llm=$(curl -sf "http://localhost:${LITELLM_PORT:-4000}/health/readiness" 2>/dev/null)
  if [ -n "$llm" ]; then
    echo "  ✅ Ready"
    # Show available models
    curl -sf "http://localhost:${LITELLM_PORT:-4000}/v1/models" \
      -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-sk-litellm-master-key}" 2>/dev/null \
      | python3 -c "import sys,json; [print(f'    • {m[\"id\"]}') for m in json.load(sys.stdin).get('data',[])]" 2>/dev/null || true
  else
    echo "  ❌ Не запущен (./start.sh litellm)"
  fi

  echo ""
  echo "── llama-server (:8092) ──"
  local llama=$(curl -sf "http://localhost:8092/v1/models" 2>/dev/null)
  if [ -n "$llama" ]; then
    echo "$llama" | python3 -c "import sys,json; [print(f'    • {m[\"id\"]}') for m in json.load(sys.stdin).get('data',[])]" 2>/dev/null || echo "  ✅ работает"
  else
    echo "  ❌ Не запущен"
  fi

  echo ""
  echo "── Data ──"
  echo "  HERMES_HOME: $HERMES_HOME"
  [ -d "$HERMES_HOME" ] && echo "  Размер: $(du -sh "$HERMES_HOME" 2>/dev/null | cut -f1)" || echo "  Не существует"

  echo ""
  echo "── Image ──"
  docker image inspect "$HERMES_IMAGE" --format "  ✅ {{.RepoTags}} ({{.Size}} bytes, created {{.Created}})" 2>/dev/null || echo "  ❌ Образ не найден"

  echo "════════════════════════════════════════════════════"
}

# ═══════════════════════════════════════════════════════════════
# Logs
# ═══════════════════════════════════════════════════════════════
show_logs() {
  local svc="${1:-gateway}"
  case "$svc" in
    gw|gateway) docker logs "$CONTAINER_GW" --tail 50 -f ;;
    dash|dashboard) docker logs "$CONTAINER_DASH" --tail 50 -f ;;
    neo4j) docker logs neo4j --tail 50 -f 2>/dev/null || err "neo4j не найден" ;;
    litellm) docker logs litellm --tail 50 -f 2>/dev/null || err "litellm не найден" ;;
    *) err "Неизвестный сервис: $svc"; echo "  Доступно: gateway, dashboard, neo4j, litellm" ;;
  esac
}

# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
case "${1:-compose}" in
  compose|a)
    start_compose
    ;;
  full|b)
    shift
    start_full "$@"
    ;;
  minimal|min)
    start_minimal
    ;;
  gui|desktop)
    start_gui
    ;;
  litellm|llm)
    start_litellm
    ;;
  build)
    build_image
    ;;
  stop|down)
    stop_all
    ;;
  status|st)
    show_status
    ;;
  logs)
    shift
    show_logs "$@"
    ;;
  help|-h|--help)
    sed -n '3,30p' "$0"
    ;;
  *)
    echo "Неизвестная команда: $1"
    echo "Использование: ./start.sh [compose|full|minimal|gui|build|stop|status|logs|help]"
    exit 1
    ;;
esac
