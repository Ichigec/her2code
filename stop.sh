#!/usr/bin/env bash
# stop.sh - Stop Hermes Portable v4 containers

echo "Stopping Hermes Portable v4..."
docker stop hermes-gateway hermes-dashboard 2>/dev/null && echo "  Containers stopped" || echo "  No containers running"
docker rm hermes-gateway hermes-dashboard 2>/dev/null || true
echo "Done."
