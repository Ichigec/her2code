#!/bin/bash
# Hermes Stack — быстрый запуск
# Использование: ./start.sh [desktop]
#
# Требования:
# 1. Docker (docker compose)
# 2. .env файл с API ключами (cp .env.example .env && nano .env)

set -e

# 1. Git init (нужен для сборки desktop)
if [ ! -d hermes-agent/.git ]; then
  cd hermes-agent && git init -q && git add -A && git commit -m "sanitized" -q && cd ..
fi

# 2. Docker (если не запущен)
curl -sf http://localhost:18648/health > /dev/null 2>&1 || {
  echo "🚀 Запуск Docker..."
  docker compose up -d
  echo -n "⏳ Инициализация (может занять 2-4 минуты при первом запуске)"
  for i in $(seq 1 90); do
    curl -sf http://localhost:18648/health > /dev/null 2>&1 && break
    sleep 2
    echo -n "."
  done
  echo ""
}

# 3. Проверка
curl -sf http://localhost:18648/health > /dev/null 2>&1 || {
  echo "❌ Docker не запустился. Проверь: docker compose logs hermes"
  exit 1
}
echo "✅ Docker API: http://localhost:18648"

# 4. Desktop GUI (опционально)
if [ "$1" = "desktop" ]; then
  echo "🖥️  Запуск Desktop GUI..."
  cd hermes-agent
  [ ! -d "node_modules/react" ] && npm ci 2>&1 | tail -3
  export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
  export GITHUB_SHA="sanitized-release"
  HERMES_DESKTOP_REMOTE_URL=http://localhost:18648 \
  HERMES_DESKTOP_REMOTE_TOKEN=*** \
    npm --prefix apps/desktop start
else
  echo ""
  echo "Готово. Команды:"
  echo "  curl http://localhost:18648/health"
  echo "  ./start.sh desktop   # запустить Desktop GUI"
fi
