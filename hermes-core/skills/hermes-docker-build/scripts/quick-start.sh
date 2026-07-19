#!/bin/bash
# Hermes Stack — быстрый запуск
# Использование: ./start.sh [desktop]
set -e
HER2CODE="$(dirname "$0")"
PORT=18648

if [ ! -d "$HER2CODE/hermes-agent/.git" ]; then
  cd "$HER2CODE/hermes-agent" && git init -q && git add -A && git commit -m "sanitized" -q && cd "$HER2CODE"
fi

if ! curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then
  echo "🚀 Запуск Docker..."
  docker compose -f "$HER2CODE/docker-compose.yml" up -d
  echo -n "⏳ Инициализация"
  for i in $(seq 1 90); do
    curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1 && break
    sleep 2 && echo -n "."
  done
  echo ""
fi

curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1 || { echo "❌ Docker не запустился"; exit 1; }
echo "✅ Docker: http://localhost:$PORT"

if [ "$1" = "desktop" ]; then
  echo "🖥️  Запуск Desktop GUI..."
  cd "$HER2CODE/hermes-agent"
  export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
  export GITHUB_SHA="sanitized-release"
  export HERMES_DESKTOP_REMOTE_URL="http://localhost:$PORT"
  export HERMES_DESKTOP_REMOTE_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-local}"
  [ ! -d "node_modules/react" ] && npm ci 2>&1 | tail -3
  SANDBOX="node_modules/electron/dist/chrome-sandbox"
  [ -f "$SANDBOX" ] && [ "$(stat -c %U "$SANDBOX" 2>/dev/null)" != "root" ] && \
    sudo chown root:root "$SANDBOX" 2>/dev/null && sudo chmod 4755 "$SANDBOX" 2>/dev/null || \
    export ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox"
  cd apps/desktop && npm start
else
  echo "  curl http://localhost:$PORT/health"
  echo "  ./start.sh desktop"
fi
