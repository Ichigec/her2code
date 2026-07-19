#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# build-gui.sh — Build Electron GUI from Docker image + cached Electron zip
# Works WITHOUT internet: extracts source from Docker, uses local Electron cache.
# See: hermes-gui-launch skill -> references/cross-architecture-offline-deploy.md
# ═══════════════════════════════════════════════════════════════
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Hermes GUI — Build from Docker image"
echo "=========================================="

# ── Checks ──
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not installed"; exit 1; }
command -v node  >/dev/null 2>&1 || { echo "ERROR: node not installed: sudo apt install nodejs"; exit 1; }
command -v npm   >/dev/null 2>&1 || { echo "ERROR: npm not installed: sudo apt install npm"; exit 1; }

# ── Detect architecture ──
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64) ARCH="arm64" ;;
  x86_64|amd64)  ARCH="x64" ;;
  *) echo "ERROR: unsupported arch: $HOST_ARCH"; exit 1 ;;
esac

# ── Find Docker image ──
IMAGE_TAG=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep hermes-agent | head -1)
[ -z "$IMAGE_TAG" ] && { echo "ERROR: Docker image hermes-agent not found. Run start-backend.sh first"; exit 1; }
echo "  Image: $IMAGE_TAG ($ARCH)"

# ── Find Electron zip cache ──
ELECTRON_ZIP=""
for z in "$SCRIPT_DIR/gui/electron-v"*"linux-${ARCH}.zip" \
         "$SCRIPT_DIR/electron-v"*"linux-${ARCH}.zip" \
         "$HOME/.cache/electron/electron-v"*"linux-${ARCH}.zip"; do
    if [ -f "$z" ]; then ELECTRON_ZIP="$z"; break; fi
done

if [ -n "$ELECTRON_ZIP" ]; then
    echo "  Electron cache: $(basename "$ELECTRON_ZIP")"
    mkdir -p "$HOME/.cache/electron"
    cp "$ELECTRON_ZIP" "$HOME/.cache/electron/" 2>/dev/null || true
    export ELECTRON_SKIP_BINARY_DOWNLOAD=1
else
    echo "  WARNING: Electron zip not in cache — will try to download (needs network)"
fi

# ── Extract source from Docker image ──
BUILD_DIR="$SCRIPT_DIR/.build-gui"
echo ""
echo "  Extracting source from Docker image..."
rm -rf "$BUILD_DIR" 2>/dev/null || true
mkdir -p "$BUILD_DIR/hermes-agent"

docker run --rm -v "$BUILD_DIR/hermes-agent:/out" --entrypoint sh "$IMAGE_TAG" -c '
    cp -a /opt/hermes/apps/desktop /out/apps/desktop &&
    cp -a /opt/hermes/ui-tui /out/ui-tui 2>/dev/null; true &&
    cp -a /opt/hermes/web /out/web 2>/dev/null; true &&
    cp -a /opt/hermes/package.json /out/package.json 2>/dev/null; true &&
    cp -a /opt/hermes/package-lock.json /out/package-lock.json 2>/dev/null; true &&
    cp -a /opt/hermes/node_modules /out/node_modules 2>/dev/null; true
' 2>/dev/null || true

[ -f "$BUILD_DIR/hermes-agent/apps/desktop/package.json" ] || {
    echo "ERROR: Failed to extract apps/desktop from image"
    rm -rf "$BUILD_DIR"
    exit 1
}
echo "  OK: source extracted"

# ── Build ──
echo ""
echo "  Building (tsc + vite + electron-builder)..."
cd "$BUILD_DIR/hermes-agent/apps/desktop"
export GITHUB_SHA="local-offline-build"

if [ ! -d "../../node_modules/vite" ]; then
    echo "  npm ci (may need network)..."
    npm ci --prefer-offline 2>&1 | tail -3 || {
        echo "ERROR: npm ci failed (network needed for dependencies)"
        cd "$SCRIPT_DIR"
        exit 1
    }
fi

echo "  npm run build..."
npm run build 2>&1 | tail -3 || { echo "ERROR: build failed"; cd "$SCRIPT_DIR"; exit 1; }

echo "  npm run pack..."
npm run pack 2>&1 | tail -3 || { echo "ERROR: pack failed"; cd "$SCRIPT_DIR"; exit 1; }

# ── Copy result ──
RELEASE_DIR="$BUILD_DIR/hermes-agent/apps/desktop/release/linux-${ARCH}-unpacked"
if [ -d "$RELEASE_DIR" ]; then
    BACKUP_DIR="$SCRIPT_DIR/gui-backup-$(date +%s)"
    [ -d "$SCRIPT_DIR/gui" ] && mv "$SCRIPT_DIR/gui" "$BACKUP_DIR"
    cp -a "$RELEASE_DIR" "$SCRIPT_DIR/gui"
    echo ""
    echo "  OK: Binary built: $SCRIPT_DIR/gui/Hermes"
    echo "  Old gui backed up: $BACKUP_DIR"
else
    echo "ERROR: Binary not found in $RELEASE_DIR"
    cd "$SCRIPT_DIR"
    exit 1
fi

cd "$SCRIPT_DIR"
rm -rf "$BUILD_DIR" 2>/dev/null || true

echo ""
echo "=========================================="
echo "  GUI built! Now run: ./launch.sh"
echo "=========================================="
