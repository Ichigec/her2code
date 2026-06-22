#!/bin/bash
# Hermes Stack — быстрый запуск Docker + опционально GUI
# Использование:
#   ./start.sh              # только Docker (gateway + dashboard)
#   ./start.sh gui          # Docker + Desktop GUI (изолированно)

set -e

PORT_GW=18648
PORT_DASH=9119
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 1. Docker Gateway ──
start_gateway() {
  if curl -sf "http://localhost:${PORT_GW}/health" > /dev/null 2>&1; then
    echo "✅ Gateway уже запущен на :${PORT_GW}"
    return
  fi
  echo "🚀 Запуск Docker Gateway..."
  docker compose up -d
  echo -n "⏳ Ожидание gateway (первый запуск: 2-5 минут)"
  for i in $(seq 1 150); do
    curl -sf "http://localhost:${PORT_GW}/health" > /dev/null 2>&1 && break
    sleep 2
    echo -n "."
  done
  echo ""
  curl -sf "http://localhost:${PORT_GW}/health" > /dev/null 2>&1 || {
    echo "❌ Gateway не запустился. Логи: docker compose logs hermes"
    exit 1
  }
  echo "✅ Gateway: http://localhost:${PORT_GW}"
}

# ── 2. Docker Dashboard ──
start_dashboard() {
  if curl -sf "http://localhost:${PORT_DASH}/api/status" > /dev/null 2>&1; then
    echo "✅ Dashboard уже запущен на :${PORT_DASH}"
    return
  fi
  echo "🚀 Запуск Docker Dashboard..."

  # Check if tui_gateway is on persistent volume
  if ! docker exec hermes-dashboard ls /opt/data/tui_gateway/ws.py > /dev/null 2>&1; then
    echo "   Копирование tui_gateway на persistent volume..."
    tar -C "$SCRIPT_DIR/hermes-agent" -c tui_gateway/ 2>/dev/null | \
      docker exec -i hermes-dashboard tar -C /opt/data -x 2>/dev/null || {
        # Fallback: copy from host
        tar -C "$HOME/.hermes/hermes-agent" -c tui_gateway/ | \
          docker exec -i hermes-dashboard tar -C /opt/data -x 2>/dev/null || true
      }
  fi

  docker rm -f hermes-dashboard 2>/dev/null || true
  docker run -d --name hermes-dashboard --network host \
    --volumes-from hermes-test \
    -e HERMES_UID=1000 -e HERMES_GID=1000 \
    -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
    -e PYTHONPATH=/opt/data \
    hermes-agent dashboard --host 127.0.0.1 --port "$PORT_DASH" \
      --insecure --tui --no-open --skip-build

  echo -n "⏳ Ожидание dashboard (первый запуск: 2-5 минут)"
  for i in $(seq 1 150); do
    curl -sf "http://localhost:${PORT_DASH}/api/status" > /dev/null 2>&1 && break
    sleep 2
    echo -n "."
  done
  echo ""
  curl -sf "http://localhost:${PORT_DASH}/api/status" > /dev/null 2>&1 || {
    echo "❌ Dashboard не запустился. Логи: docker logs hermes-dashboard"
    exit 1
  }
  echo "✅ Dashboard: http://localhost:${PORT_DASH}"
}

# ── 3. Desktop GUI ──
start_gui() {
  local BIN="$HOME/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes"
  if [ ! -f "$BIN" ]; then
    echo "❌ GUI бинарник не найден: $BIN"
    echo "   Установи Hermes GUI: hermes setup"
    exit 1
  fi

  # Проверить что dashboard готов
  curl -sf "http://localhost:${PORT_DASH}/api/status" > /dev/null 2>&1 || {
    echo "❌ Dashboard не отвечает на :${PORT_DASH}. Запусти сначала: ./start.sh"
    exit 1
  }

  echo "🖥️  Запуск Desktop GUI (изолированно)..."
  echo "   Dashboard: http://localhost:${PORT_DASH}"
  echo "   Data dir:  /tmp/hermes-gui-docker"

  HERMES_DESKTOP_REMOTE_URL="http://localhost:${PORT_DASH}" \
  HERMES_DESKTOP_REMOTE_TOKEN=*** \
  ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" \
    "$BIN" --user-data-dir=/tmp/hermes-gui-docker &
  GUI_PID=$!
  echo "   PID: $GUI_PID"
}

# ── Main ──
case "${1:-}" in
  gui|desktop)
    start_gateway
    start_dashboard
    start_gui
    ;;
  dashboard|dash)
    start_dashboard
    ;;
  gateway|gw)
    start_gateway
    ;;
  stop)
    echo "🛑 Остановка..."
    docker stop hermes-dashboard 2>/dev/null || true
    docker compose down 2>/dev/null || true
    echo "✅ Остановлено"
    ;;
  status)
    echo "=== Gateway ==="
    curl -sf "http://localhost:${PORT_GW}/health" 2>/dev/null || echo "  Не отвечает"
    echo "=== Dashboard ==="
    curl -sf "http://localhost:${PORT_DASH}/api/status" 2>/dev/null | \
      python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  version={d[\"version\"]} gw_running={d[\"gateway_running\"]} sessions={d[\"active_sessions\"]}')" 2>/dev/null || echo "  Не отвечает"
    ;;
  *)
    start_gateway
    start_dashboard
    echo ""
    echo "Готово. Команды:"
    echo "  ./start.sh status     # статус"
    echo "  ./start.sh gui        # запустить Desktop GUI"
    echo "  ./start.sh stop       # остановить"
    ;;
esac
