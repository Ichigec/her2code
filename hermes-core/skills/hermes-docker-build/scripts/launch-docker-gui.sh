#!/bin/bash
# Запуск Docker Hermes GUI (изолированно от основного Hermes)
# Dashboard: http://localhost:9119, токен из /tmp/dashboard_token (sk-local)
#
# Использование:
#   bash scripts/launch-docker-gui.sh
#
# Принцип: env vars HERMES_DESKTOP_REMOTE_URL/TOKEN переопределяют
# connection.json. --user-data-dir изолирует кэш/сессии Docker GUI
# от основного GUI.

TOKEN=$(cat /tmp/dashboard_token 2>/dev/null || echo "sk-local")

HERMES_DESKTOP_REMOTE_URL=http://localhost:9119 \
HERMES_DESKTOP_REMOTE_TOKEN="$TOKEN" \
ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" \
/home/user/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes \
  --user-data-dir=/tmp/hermes-gui-docker
