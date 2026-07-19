#!/usr/bin/env bash
# download-deps.sh - Download x64 dependencies on a machine WITH internet
# Run on any x64 machine with internet, then copy files to USB
#
# Produces:
#   downloads-x64/node_modules-x64.tar.gz  (~150-200M, native x64 node_modules)
#   downloads-x64/electron-v40.9.3-linux-x64.zip  (~115M, Electron binary)

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DL_DIR="$SCRIPT_DIR/downloads-x64"
mkdir -p "$DL_DIR"

echo "== Downloading x64 dependencies =="
echo "  Output: $DL_DIR"
echo ""

# 1. Electron x64
echo "[1/2] Electron v40.9.3 (x64)..."
ELECTRON_URL="https://github.com/electron/electron/releases/download/v40.9.3/electron-v40.9.3-linux-x64.zip"
if [ -f "$DL_DIR/electron-v40.9.3-linux-x64.zip" ]; then
    echo "  Already exists, skipping"
else
    curl -L -o "$DL_DIR/electron-v40.9.3-linux-x64.zip" "$ELECTRON_URL"
fi
echo "  OK"
echo ""

# 2. node_modules from hermes-agent
echo "[2/2] hermes-agent node_modules (x64)..."
if [ -f "$DL_DIR/node_modules-x64.tar.gz" ]; then
    echo "  Already exists, skipping"
else
    TMP_CLONE=$(mktemp -d)
    echo "  Cloning hermes-agent..."
    git clone --depth 1 https://github.com/NousResearch/hermes-agent.git "$TMP_CLONE/hermes-agent"

    echo "  Installing dependencies (npm ci)..."
    cd "$TMP_CLONE/hermes-agent"
    npm ci --no-audit --no-fund 2>&1 | tail -3

    echo "  Packaging..."
    cd "$TMP_CLONE"
    tar -czf "$DL_DIR/node_modules-x64.tar.gz" \
        hermes-agent/package.json \
        hermes-agent/package-lock.json \
        hermes-agent/node_modules \
        hermes-agent/apps \
        hermes-agent/ui-tui \
        hermes-agent/web

    cd "$SCRIPT_DIR"
    rm -rf "$TMP_CLONE"
fi
echo "  OK"

echo ""
echo "== Downloads complete =="
echo ""
ls -lh "$DL_DIR/"
echo ""
echo "  Copy these to hermes_portable_v1/ on USB"
