#!/bin/bash
# Hermes Desktop GUI → Docker (host-сеть, порт 18648)
# Ждёт до 4 минут (инициализация gateway), затем запускает Desktop
set -e

ROOT="$(dirname "$0")/hermes-agent"

echo "============================================="
echo "  Hermes Desktop GUI → Docker (18648)"
echo "============================================="

# Ждать Docker (инициализация gateway — до 4 минут)
echo -n "⏳ Жду Docker"
for i in $(seq 1 120); do
  curl -sf http://localhost:18648/health > /dev/null 2>&1 && break
  echo -n "."
  sleep 2
done
echo ""

curl -sf http://localhost:18648/health > /dev/null 2>&1 || {
  echo "❌ Docker не отвечает. Запусти: docker compose up -d"
  exit 1
}
echo "✅ Docker отвечает"

cd "$ROOT"

# Первый запуск — установить зависимости
if [ ! -d "node_modules/react" ]; then
  echo "🔧 npm ci (первый раз)..."
  export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
  export GITHUB_SHA="sanitized-release"
  npm ci 2>&1 | tail -3
fi

# Песочница Electron
SANDBOX="node_modules/electron/dist/chrome-sandbox"
if [ -f "$SANDBOX" ] && [ "$(stat -c %U "$SANDBOX" 2>/dev/null)" != "root" ]; then
  sudo chown root:root "$SANDBOX" 2>/dev/null && sudo chmod 4755 "$SANDBOX" 2>/dev/null \
    && echo "✅ sandbox fixed" \
    || { echo "⚠️  --no-sandbox"; export ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox"; }
fi

export GITHUB_SHA="sanitized-release"

echo ""
echo "🚀 Запуск Desktop GUI..."
echo "   API:  http://localhost:18648"
echo ""

cd apps/desktop
exec npm start
