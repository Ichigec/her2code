#!/usr/bin/env bash
# status.sh - Check Hermes Portable v4 status

PORT_GW="${PORT_GW:-18649}"
PORT_DASH="${PORT_DASH:-9123}"

echo "=== Hermes Portable v4 Status ==="

echo -n "Gateway   :$PORT_GW  "
if curl -sf "http://localhost:$PORT_GW/health" >/dev/null 2>&1; then
  echo "UP"
else
  echo "DOWN"
fi

echo -n "Dashboard :$PORT_DASH  "
if curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1; then
  echo "UP"
else
  echo "DOWN"
fi

echo ""
echo "Containers:"
docker ps --filter "name=hermes-" --format "  {{.Names}}  {{.Status}}  {{.Ports}}" 2>/dev/null || echo "  Docker not available"
