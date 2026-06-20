#!/usr/bin/env bash
# Rebuild llama.cpp with CUDA for GB10 (sm_121) and verify MTP (--spec-type draft-mtp).
# Does not modify global git config.
set -euo pipefail

OPENCODE_PLUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$OPENCODE_PLUS_DIR/.." && pwd)"
# shellcheck source=lib/env.sh
source "$OPENCODE_PLUS_DIR/lib/env.sh"

_LL_ENV_KEYS=(
    LMSTUDIO_MODELS_DIR
    LLAMA_CPP_DIR
    LLAMA_CPP_SERVER_BIN
)

load_llama_env "$PROJECT_ROOT" "${_LL_ENV_KEYS[@]}"

LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-${EFFECTIVE_HOME}/dev/llama.cpp}"
LLAMA_CPP_SERVER_BIN="${LLAMA_CPP_SERVER_BIN:-$LLAMA_CPP_DIR/build/bin/llama-server}"
CUDA_NVCC="${CUDA_NVCC:-/usr/local/cuda-13.2/bin/nvcc}"

if [ ! -d "$LLAMA_CPP_DIR/.git" ]; then
    cat <<EOF >&2
llama.cpp repo not found: $LLAMA_CPP_DIR
  (effective home: ${EFFECTIVE_HOME:-$HOME}, uid=$(id -u))

Clone first:
  mkdir -p "$(dirname "$LLAMA_CPP_DIR")"
  git clone https://github.com/ggml-org/llama.cpp "$LLAMA_CPP_DIR"

Or run as the repo owner (recommended):
  sudo -u pavel bash $OPENCODE_PLUS_DIR/rebuild-llama-mtp.sh
EOF
    exit 1
fi

if [ ! -x "$CUDA_NVCC" ]; then
    echo "CUDA nvcc not found: $CUDA_NVCC (set CUDA_NVCC if installed elsewhere)" >&2
    exit 1
fi

echo "=== Rebuild llama.cpp for MTP (draft-mtp) ==="
echo "→ Repo: $LLAMA_CPP_DIR"
echo "→ nvcc: $CUDA_NVCC"

cd "$LLAMA_CPP_DIR"
git fetch --tags --prune origin
# MTP (PR #22673) is on master; latest release tag may lag behind.
if git rev-parse --verify origin/master >/dev/null 2>&1; then
    echo "→ Checkout origin/master (includes draft-mtp after PR #22673)"
    git checkout origin/master
elif git rev-parse --verify master >/dev/null 2>&1; then
    echo "→ Checkout master"
    git checkout master
else
    LATEST_TAG="$(git for-each-ref --sort=-creatordate --count=1 \
        --format='%(refname:short)' refs/tags/ 2>/dev/null || true)"
    if [ -n "$LATEST_TAG" ]; then
        echo "→ Checkout tag: $LATEST_TAG"
        git checkout "$LATEST_TAG"
    else
        echo "→ No origin/master or tags; staying on current branch" >&2
    fi
fi

rm -rf build
cmake -S . -B build \
    -DGGML_CUDA=ON \
    -DGGML_CCACHE=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_COMPILER="$CUDA_NVCC" \
    -DCMAKE_C_COMPILER=/usr/bin/gcc-12 \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++-12 \
    -DCMAKE_CUDA_ARCHITECTURES="121-real;121-virtual" \
    -DLLAMA_BUILD_TESTS=OFF

cmake --build build --config Release -j"$(nproc)"

echo ""
echo "=== Smoke tests ==="
"$LLAMA_CPP_SERVER_BIN" --version || true

if ! llama_help_has_draft_mtp "$LLAMA_CPP_SERVER_BIN"; then
    cat <<EOF >&2

✗ llama-server --help does not list draft-mtp.

You need a build that includes MTP speculative decoding (PR #22673):
  https://github.com/ggml-org/llama.cpp/pull/22673

Try a newer tag/master after the PR is merged, or cherry-pick the branch, then re-run:
  bash $OPENCODE_PLUS_DIR/rebuild-llama-mtp.sh
EOF
    exit 1
fi

echo "✓ draft-mtp found in --help"
echo "✓ Binary: $LLAMA_CPP_SERVER_BIN"
echo ""
echo "Next: bash $OPENCODE_PLUS_DIR/start-llama-qwen.sh --daemon"
echo "      bash $OPENCODE_PLUS_DIR/start-all.sh"
