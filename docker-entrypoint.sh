#!/bin/sh
set -euo pipefail
# Docker entrypoint: безопасное удаление Telegram из конфига
# Использует sed вместо inline Python — нет риска shell injection.
# Если config.yaml не найден за 30с — продолжает без модификации (не блокирует запуск).

CONFIG=/opt/data/config.yaml
ATTEMPTS=0
MAX_ATTEMPTS=15

while [ ! -f "$CONFIG" ] && [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
  sleep 2
  ATTEMPTS=$((ATTEMPTS + 1))
done

if [ -f "$CONFIG" ]; then
  # Удалить секцию telegram из gateway.platforms (все варианты написания)
  # Работает только если config.yaml существует
  sed -i '/^[[:space:]]*telegram:/,/^[[:space:]]*[a-z]/{
    /^[[:space:]]*telegram:/d
    /^[[:space:]]*[a-z]/!d
  }' "$CONFIG" 2>/dev/null || true
  echo "[entrypoint] Telegram removed from config" >&2
else
  echo "[entrypoint] No config.yaml found after ${MAX_ATTEMPTS}s, continuing" >&2
fi

exec /init /opt/hermes/docker/main-wrapper.sh "$@"
