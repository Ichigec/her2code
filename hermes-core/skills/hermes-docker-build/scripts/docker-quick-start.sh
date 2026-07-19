#!/bin/bash
# Hermes Docker Quick Start — copy-paste ready
# Tested on Jetson ARM64, 2026-06-19

set -e
cd "${HER2CODE_DIR:-$HOME/dev/codemes/<SESSION_ID>/her2code}"

# 1. Fix base image SHA
docker pull ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie
SHA=$(docker inspect ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie --format='{{index .RepoDigests 0}}')
sed -i "1s|FROM .*|FROM $SHA AS uv_source|" hermes-agent/Dockerfile

# 2. Убедиться что ui-tui/ и web/ на месте (НЕ удалять, НЕ заменять заглушками!)
cd hermes-agent
if [ ! -f "ui-tui/package.json" ] || [ ! -f "web/package.json" ]; then
  echo "❌ ОШИБКА: ui-tui/ или web/ отсутствуют. Скопируйте из оригинального hermes-agent."
  echo "   cp -r /path/to/original/hermes-agent/ui-tui ."
  echo "   cp -r /path/to/original/hermes-agent/web ."
  exit 1
fi
cd ..

# 3. Build & start
cp config/.env.docker .env
echo 'DEEPSEEK_API_KEY=... # ADD YOUR KEY' >> .env
docker compose build hermes --no-cache
docker compose up -d
sleep 30
curl http://localhost:18648/health
echo "GUI: http://localhost:19119"
