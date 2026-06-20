#!/usr/bin/env bash
# Install opencode CLI on the host (no Docker).
set -euo pipefail

OPENCODE_PLUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$OPENCODE_PLUS_DIR/.." && pwd)"
# shellcheck source=lib/opencode-env.sh
source "$OPENCODE_PLUS_DIR/lib/opencode-env.sh"

load_opencode_env "$PROJECT_ROOT" OPENCODE_VERSION

if bin="$(oc_resolve_binary)" && [ -n "$bin" ]; then
    echo "✓ opencode already installed: $bin"
    "$bin" --version 2>/dev/null || "$bin" version 2>/dev/null || true
    exit 0
fi

echo "→ Installing opencode for ${EFFECTIVE_HOME} …"
if [ -n "${OPENCODE_VERSION:-}" ]; then
    OPENCODE_VERSION="${OPENCODE_VERSION}" curl -fsSL https://opencode.ai/install | bash
else
    curl -fsSL https://opencode.ai/install | bash
fi

bin="$(oc_resolve_binary)"
[ -n "$bin" ] || { echo "✗ install finished but opencode binary not found" >&2; exit 1; }
echo "✓ Installed: $bin"
