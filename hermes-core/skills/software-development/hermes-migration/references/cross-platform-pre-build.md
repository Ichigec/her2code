# Cross-Platform Pre-Building: ARM64 → x86_64 (Offline)

## Discovery (2026-07-06, Jetson ARM64)

Three critical findings proven on Pavel's Jetson (ARM64, NVIDIA GB10, CUDA 13):

1. `pip download --platform manylinux2014_x86_64` downloads x86_64 wheels on ARM64 — WORKS
2. `docker pull --platform linux/amd64` pulls amd64 images on ARM64 — WORKS
3. `docker buildx build --platform linux/amd64 --load` builds amd64 images via QEMU — WORKS

This means ALL x86_64 artifacts can be prepared on the ARM64 Jetson while it has
internet, then carried to an air-gapped x86_64 machine.

## Prerequisites on Jetson

```bash
# QEMU for buildx cross-platform builds
sudo apt install qemu-user-static

# Verify
docker buildx ls | grep linux/amd64
# Should show: linux/arm64, linux/amd64, linux/amd64/v2, ...

# Verify pip cross-download
pip download --platform manylinux2014_x86_64 --python-version 312 \
  --only-binary=:all: cryptography -d /tmp/test 2>&1 | grep -q 'manylinux.*x86_64' \
  && echo "✅ pip cross-download works"
```

## Artifacts to pre-build

| # | Artifact | Command | Time | Output |
|---|----------|---------|------|--------|
| 1 | pip wheels (14 aarch64→x86_64) | `pip download --platform manylinux2014_x86_64` | 30s | 60 whl, 38 MB |
| 2 | Docker pull images (9) | `docker pull --platform linux/amd64` + `save` | 15 min | 9 .tar, ~12.5 GB |
| 3 | Docker local-build (6) | `docker buildx build --platform linux/amd64 --load` | 20 min | 6 images, ~2.5 GB |
| 4 | llama-server x86_64 | `docker buildx build` with CUDA Dockerfile + CUDA_ARCH override | 15 min | binary, ~50 MB |

## Full script: pre-build all x86_64 artifacts

```bash
#!/bin/bash
# Run on Jetson ARM64 WITH internet
# Output goes to ./x86_64-dist/ — copy to target machine
set -euo pipefail

OUT="./x86_64-dist"
mkdir -p "$OUT"/{pip-packages,docker-images,llama}

echo "=== 1/4: Python wheels for x86_64 ==="
pip download --platform manylinux2014_x86_64 --python-version 312 \
  --only-binary=:all: hermes-agent -d "$OUT/pip-packages/"

echo "=== 2/4: Docker pull images for amd64 ==="
PULL_IMAGES=(
  "neo4j:5-community"
  "arizephoenix/phoenix:latest"
  "postgres:16-alpine"
  "python:3.12-slim"
  "python:3.12-alpine"
  "alpine:latest"
  "ghcr.io/berriai/litellm-database:v1.83.7-stable"
  "nvidia/cuda:13.0.0-devel-ubuntu24.04"
  "nvidia/cuda:13.0.0-runtime-ubuntu24.04"
)
for img in "${PULL_IMAGES[@]}"; do
  echo "  $img..."
  docker pull --platform linux/amd64 "$img"
  docker save "$img" -o "$OUT/docker-images/$(echo $img | tr '/:' '-').tar"
done

echo "=== 3/4: Docker local-build images (buildx --platform amd64) ==="
# Build each of the 9 local images via buildx
# Example for one:
docker buildx build --platform linux/amd64 --load \
  -t voice-assistant-opencode:local \
  -f llm-stack/docker/Dockerfile.opencode .
docker save voice-assistant-opencode:local \
  -o "$OUT/docker-images/voice-assistant-opencode-local.tar"
# ... repeat for other 8

echo "=== 4/4: llama-server for x86_64 ==="
cat > /tmp/Dockerfile.llama-x86 << 'DOCKEREOF'
FROM nvidia/cuda:13.0.0-devel-ubuntu24.04
RUN apt-get update && apt-get install -y git cmake build-essential
RUN git clone --depth 1 https://github.com/ggml-org/llama.cpp /src
RUN cd /src && cmake -B build -DGGML_CUDA=ON \
  && cmake --build build -j$(nproc) --target llama-server
DOCKEREOF
docker buildx build --platform linux/amd64 --load \
  -t llama-x86-builder:latest -f /tmp/Dockerfile.llama-x86 .
docker run --rm -v "$OUT/llama:/out" llama-x86-builder:latest \
  cp /src/build/bin/llama-server /out/

echo "=== DONE ==="
echo "Output: $OUT/"
du -sh "$OUT/"
echo "Copy this directory to the target x86_64 machine."
```

## What CANNOT be pre-verified

| Pre-built? | Can verify on Jetson? | Must verify on target |
|:---:|:---:|:---:|
| pip wheels | ✅ (file exists, correct platform tag) | ❌ |
| Docker pull images | ✅ (correct architecture in manifest) | ✅ (actually runs, CUDA works) |
| Docker local-build | ✅ (build succeeds via QEMU) | ✅ (actually runs, GPU passthrough) |
| llama-server binary | ⚠️ (file exists, ELF header says x86_64) | ✅ (loads models, CUDA inference) |
| GGUF models | ✅ (universal format) | ❌ |
| Neo4j dump | ✅ (universal format) | ❌ |
| Configs/skills | ✅ (text, universal) | ❌ |

## Known issues

- **QEMU performance**: docker buildx on ARM64 emulating x86_64 is SLOW (5-10× slower
  than native). A 2-minute native build becomes 10-20 minutes.
- **CUDA images via QEMU**: the CUDA devel image can be pulled and used as a build
  base, but `nvidia-smi` inside QEMU-emulated containers will NOT work (no GPU access).
- **llama-server cross-compilation alternative**: instead of Docker buildx, use a
  proper cross-compilation toolchain (`aarch64-linux-gnu-gcc` targeting x86_64).
  Faster but more complex to set up.
- **docker save image tag must match**: `docker save python:3.12-slim-bookworm`
  fails with `reference does not exist` if local image is tagged `python:3.12-slim`.
  Use `docker images` to check exact tags before saving.
