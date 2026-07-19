#!/usr/bin/env bash
# build-gui.sh — Сборка Hermes Desktop GUI из локальных файлов (офлайн/онлайн)
#
# Работает в двух режимах:
#   1. Офлайн: node_modules уже на месте (скопирован с донора той же архитектуры)
#   2. Онлайн: npm ci из кэша или сети (если node_modules отсутствует)
#
# Использование:
#   ./build-gui.sh                    # сборка unpacked-директории (--dir)
#   ./build-gui.sh --dist             # сборка AppImage/deb/rpm (--linux)
#   ./build-gui.sh --dir              # только unpacked (по умолчанию)
#   ./build-gui.sh --arch x64         # кросс-компиляция (нужен Docker x64)
#   ./build-gui.sh --skip-install     # пропустить проверку npm ci
#
# Требования:
#   - Node.js >= 22
#   - python3, make, g++ (для компиляции node-pty на Linux)
#   - git (для write-build-stamp, или задать GITHUB_SHA)
#
# Результат:
#   apps/desktop/dist/                          — frontend bundle (vite)
#   apps/desktop/build/install-stamp.json       — build stamp
#   apps/desktop/build/native-deps/             — node-pty .node бинарник
#   apps/desktop/release/linux-<arch>-unpacked/ — готовый бинарник Hermes
#
set -euo pipefail

# ── Разбор аргументов ──
MODE="--dir"
SKIP_INSTALL=false
ARCH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dist)  MODE="--dist";  shift ;;
    --dir)   MODE="--dir";   shift ;;
    --skip-install) SKIP_INSTALL=true; shift ;;
    --arch)  ARCH="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--dir|--dist] [--skip-install] [--arch <arch>]"
      echo "  --dir   Build unpacked directory only (default, fast)"
      echo "  --dist  Build AppImage/deb/rpm (slower)"
      echo "  --arch  Target architecture (arm64, x64) — for cross-compile use Docker"
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Определение путей ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="${HERMES_REPO_ROOT:-$(find /home -maxdepth 4 -path '*/hermes-agent/package.json' -not -path '*/node_modules/*' 2>/dev/null | head -1 | xargs dirname 2>/dev/null)}"

if [[ -z "$REPO_ROOT" || ! -f "$REPO_ROOT/package.json" ]]; then
  echo "❌ Не найден hermes-agent. Задайте HERMES_REPO_ROOT:"
  echo "   HERMES_REPO_ROOT=/path/to/hermes-agent $0"
  exit 1
fi

DESKTOP_DIR="$REPO_ROOT/apps/desktop"
echo "=== Build GUI ==="
echo "  Repo:     $REPO_ROOT"
echo "  Desktop:  $DESKTOP_DIR"
echo "  Mode:     $MODE"
echo "  Arch:     ${ARCH:-$(uname -m)}"
echo ""

# ── 1. Проверка node_modules ──
if [[ "$SKIP_INSTALL" == false ]]; then
  if [[ ! -f "$REPO_ROOT/node_modules/vite/package.json" ]]; then
    echo "⚠️  node_modules отсутствует. Пытаюсь npm ci..."
    cd "$REPO_ROOT"
    # Пробуем офлайн (из кэша), потом онлайн
    if ! npm ci --offline --prefer-offline 2>/dev/null; then
      echo "  Офлайн не удалось. Пробую онлайн..."
      npm ci
    fi
  else
    echo "✅ node_modules на месте"
  fi
fi

# ── 2. Проверка/компиляция node-pty ──
PTY_NODE="$REPO_ROOT/node_modules/node-pty/build/Release/pty.node"
if [[ ! -f "$PTY_NODE" ]]; then
  echo "⚠️  pty.node отсутствует. Компилирую node-pty..."
  echo "  (нужны: python3 make g++)"
  cd "$REPO_ROOT"
  npm rebuild node-pty
fi
echo "✅ node-pty: $(ls -la "$PTY_NODE" 2>/dev/null | awk '{print $5}') bytes"

# ── 3. Проверка Electron binary ──
ELECTRON_BIN="$REPO_ROOT/node_modules/electron/dist/electron"
if [[ ! -x "$ELECTRON_BIN" ]]; then
  echo "⚠️  Electron binary отсутствует. Пробую установить..."
  cd "$REPO_ROOT"
  # Пробуем из кэша
  if [[ -f "$HOME/.cache/electron/electron-v40.9.3-linux-${ARCH:-arm64}.zip" ]]; then
    echo "  Использую кэш: ~/.cache/electron/"
    npx electron install --cache "$HOME/.cache/electron"
  else
    echo "  Скачиваю Electron (нужен интернет)..."
    # Зеркало для РФ
    export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"
    npx electron install
  fi
fi
echo "✅ Electron: $(stat -c "%s" "$ELECTRON_BIN" 2>/dev/null) bytes"

# ── 4. Сборка ──
cd "$DESKTOP_DIR"

# GITHUB_SHA для write-build-stamp.cjs
export GITHUB_SHA="${GITHUB_SHA:-local-build}"

echo ""
echo "=== npm run build (tsc + vite + stage-native-deps) ==="
npm run build

echo ""
echo "=== electron-builder $MODE ==="
if [[ "$MODE" == "--dist" ]]; then
  if [[ -n "$ARCH" ]]; then
    npx electron-builder --linux --$ARCH
  else
    npx electron-builder --linux
  fi
else
  if [[ -n "$ARCH" ]]; then
    npx electron-builder --dir --$ARCH
  else
    npx electron-builder --dir
  fi
fi

# ── 5. Результат ──
echo ""
echo "=== Готово! ==="
UNPACKED="$DESKTOP_DIR/release/linux-${ARCH:-arm64}-unpacked"
if [[ -d "$UNPACKED" ]]; then
  echo "✅ Бинарник: $UNPACKED/Hermes"
  echo "   Размер: $(du -sh "$UNPACKED" | awk '{print $1}')"
  echo ""
  echo "   Запуск:"
  echo "   $UNPACKED/Hermes --no-sandbox"
  echo ""
  echo "   Или через hermes:"
  echo "   hermes gui --skip-build"
else
  echo "✅ Релиз: $DESKTOP_DIR/release/"
  ls -la "$DESKTOP_DIR/release/" 2>/dev/null | grep -E 'AppImage|deb|rpm'
fi
