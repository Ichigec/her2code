#!/usr/bin/env bash
# build-gui-offline.sh - Build GUI from pre-downloaded node_modules-x64.tar.gz
# NO INTERNET NEEDED. Requires Node.js 22 + build-essential.
#
# Looks for node_modules-x64.tar.gz next to this script or in downloads-x64/
# Looks for electron-v*.zip next to this script or in downloads-x64/

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  x86_64|amd64)  ARCH="x64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "ERROR: unsupported arch: $HOST_ARCH"; exit 1 ;;
esac

echo "== Hermes GUI Build - OFFLINE ($ARCH) =="

# Find node_modules tar.gz
NM_TAR=""
for f in "$SCRIPT_DIR/node_modules-x64.tar.gz" \
         "$SCRIPT_DIR/downloads-x64/node_modules-x64.tar.gz" \
         "$SCRIPT_DIR/node_modules.tar.gz"; do
    if [ -f "$f" ]; then NM_TAR="$f"; break; fi
done

if [ -z "$NM_TAR" ]; then
    echo "ERROR: node_modules tar.gz not found"
    echo "  Download on a machine with internet: ./download-deps.sh"
    exit 1
fi
echo "  Dependencies: $(basename "$NM_TAR") ($(du -h "$NM_TAR" | cut -f1))"

# Build in /tmp (NOT on exFAT USB)
BUILD_DIR="/tmp/hermes-build-$$"
echo "  Build dir: $BUILD_DIR"

echo ""
echo "Step 1: Extract dependencies..."
rm -rf "$BUILD_DIR" 2>/dev/null
mkdir -p "$BUILD_DIR"
tar -xzf "$NM_TAR" -C "$BUILD_DIR"

if [ -d "$BUILD_DIR/hermes-agent" ]; then
    SRC_ROOT="$BUILD_DIR/hermes-agent"
elif [ -f "$BUILD_DIR/package.json" ]; then
    SRC_ROOT="$BUILD_DIR"
else
    echo "ERROR: unexpected tar.gz structure"
    rm -rf "$BUILD_DIR"
    exit 1
fi
echo "  OK"

# Electron cache
echo ""
echo "Step 2: Electron..."
ELECTRON_ZIP=""
for z in "$SCRIPT_DIR/electron-v"*"linux-${ARCH}.zip" \
         "$SCRIPT_DIR/downloads-x64/electron-v"*"linux-${ARCH}.zip" \
         "$SCRIPT_DIR/gui/electron-v"*"linux-${ARCH}.zip"; do
    [ -f "$z" ] && ELECTRON_ZIP="$z" && break
done

if [ -n "$ELECTRON_ZIP" ]; then
    echo "  Cache: $(basename "$ELECTRON_ZIP")"
    mkdir -p "$HOME/.cache/electron"
    cp "$ELECTRON_ZIP" "$HOME/.cache/electron/" 2>/dev/null || true
    export ELECTRON_SKIP_BINARY_DOWNLOAD=1
else
    echo "  WARN: no Electron cache"
fi

# Build
echo ""
echo "Step 3: Build..."
cd "$SRC_ROOT/apps/desktop"
export GITHUB_SHA="local-offline-build"

echo "  npm run build..."
if ! npm run build 2>&1 | tail -10; then
    echo ""
    echo "ERROR: build failed"
    echo "  1. Node version (need v22, have: $(node --version))"
    echo "  2. node-pty arch (try: cd $SRC_ROOT && npm rebuild node-pty)"
    echo "  3. Missing tools: sudo apt install build-essential python3"
    cd "$SCRIPT_DIR"
    rm -rf "$BUILD_DIR"
    exit 1
fi

echo "  npm run pack..."
if ! npm run pack 2>&1 | tail -10; then
    echo "ERROR: pack failed"
    cd "$SCRIPT_DIR"
    rm -rf "$BUILD_DIR"
    exit 1
fi

# Copy result
echo ""
echo "Step 4: Copy binary..."
RELEASE_DIR="$SRC_ROOT/apps/desktop/release/linux-${ARCH}-unpacked"
if [ -d "$RELEASE_DIR" ]; then
    if [ -d "$SCRIPT_DIR/gui" ]; then
        mv "$SCRIPT_DIR/gui" "$SCRIPT_DIR/gui-backup-$(date +%s)" 2>/dev/null || true
    fi
    cp -r "$RELEASE_DIR" "$SCRIPT_DIR/gui"
    echo "  OK: $SCRIPT_DIR/gui/Hermes"
else
    echo "ERROR: binary not found in $RELEASE_DIR"
fi

cd "$SCRIPT_DIR"
rm -rf "$BUILD_DIR" 2>/dev/null

echo ""
echo "== Done! Run: ./launch.sh =="
