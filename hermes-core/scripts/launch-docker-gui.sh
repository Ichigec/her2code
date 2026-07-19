#!/bin/bash
# Запуск Docker Hermes GUI (изолированно от основного Hermes)
# Dashboard: http://localhost:9119, токен: sk-local

HERMES_DESKTOP_REMOTE_URL=http://localhost:9119 HERMES_DESKTOP_REMOTE_TOKEN=sk-local ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" /home/user/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes   --user-data-dir=/tmp/hermes-gui-docker
