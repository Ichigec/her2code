# Cross-Architecture Migration Verification

Verify a migration plan against actual files on disk BEFORE presenting it as
final. Created 2026-07-06 after a verification session caught 5 errors in a
previously-generated ARM64→x86_64 plan.

## Why verification matters

Without verification, migration plans contain plausible-looking but incorrect
information:
- Docker image counts swapped (6 pull + 9 local vs actual 9 pull + 6 local)
- Non-existent images listed (OpenWebUI sidecars not in the dist)
- Sizes underestimated 3× (~5 GB vs actual ~15 GB Docker images)
- Hardcoded build args missed (CUDA_ARCH=121 in llamacpp Dockerfile)
- Partially-completed work not noticed (codewar-x86/ already had pip-packages)

## Quick verification (1 minute)

```bash
SEAGATE="/media/pavel/One Touch/hermes"

# ── 1. Wheel count and platform tags ──
echo "ARM64 wheels: $(ls "$SEAGATE/codewar/pip-packages/" | wc -l)"
echo "x86_64 wheels: $(ls "$SEAGATE/codewar-x86/pip-packages/" | wc -l)"
echo "ARM64 platform-specific: $(ls "$SEAGATE/codewar/pip-packages/" | grep aarch64 | wc -l)"
echo "x86_64 platform-specific: $(ls "$SEAGATE/codewar-x86/pip-packages/" | grep x86_64 | wc -l)"

# ── 2. Docker images: count, sizes, architecture ──
echo "Docker tars: $(ls "$SEAGATE/docker-images/"*.tar | wc -l)"
du -bc "$SEAGATE/docker-images/"*.tar | tail -1  # exact bytes, not rounded

# ── 3. llama-server binary architecture ──
cd /tmp && tar xzf "$SEAGATE/codewar/llm-stack/llama/llama-server-bin.tar.gz" 2>/dev/null
file /tmp/llama-server
# ARM64 dist: "ELF 64-bit LSB ... ARM aarch64"
# x86_64 dist: "ELF 64-bit LSB ... x86-64"

# ── 4. CUDA_ARCH in llamacpp Dockerfile ──
grep CUDA_ARCH "$SEAGATE/codewar/llm-stack/docker/llamacpp/Dockerfile"
# Output: "ARG CUDA_ARCH=121" → Blackwell/Jetson, needs override for x86_64

# ── 5. Compose files: actual service names ──
grep -E "^\s{2}[a-z_-]+:" \
  "$SEAGATE/codewar/llm-stack/compose/compose.agents-mesh.yml" \
  | grep -v "build:\|environment:\|volumes:\|ports:\|healthcheck:" \
  | sort -u

# ── 6. Directory sizes (exact, not rounded) ──
du -sh "$SEAGATE/codewar/" "$SEAGATE/codewar-x86/" \
       "$SEAGATE/docker-images/" "$SEAGATE/models/"
```

## Docker image architecture check (slow, loads images)

If you need to verify the architecture of each Docker image tar:

```bash
for f in "$SEAGATE/docker-images/"*.tar; do
  name=$(basename "$f")
  img=$(docker load -i "$f" 2>/dev/null | head -1 | sed 's/.*Loaded image: //')
  arch=$(docker inspect --format="{{.Architecture}}" "$img" 2>/dev/null || echo "??")
  echo "$name -> $arch"
done
```

All ARM64 dist images should show `arm64`. When building x86_64 versions,
verify they show `amd64`.

## Wheel platform comparison

Compare ARM64 and x86_64 wheel directories to find missing platform-specific wheels:

```bash
# Normalize names (replace aarch64→x86_64) and diff
comm -23 \
  <(ls "$SEAGATE/codewar/pip-packages/" \
    | sed 's/aarch64/x86_64/g; s/_aarch64\./_x86_64./g' \
    | sort) \
  <(ls "$SEAGATE/codewar-x86/pip-packages/" | sort)
```

If output is empty → all ARM64 wheels have x86_64 equivalents.
If output has entries → those packages are missing x86_64 versions.

Note: some wheel filenames differ slightly between platforms (e.g.
`manylinux2014_aarch64` vs `manylinux1_x86_64`), so the name normalization
isn't perfect. Cross-check any "missing" entries manually.

## Docker image list: dist vs daemon

The Docker daemon on the dev machine contains MANY images that are NOT in the
distribution. Do NOT use `docker images` as the source of truth for what's in
the dist — use the `docker-images/*.tar` directory.

```bash
# What's actually in the dist:
ls "$SEAGATE/docker-images/"*.tar | xargs -I{} basename {}

# What's in the daemon (includes runtime, OpenWebUI, experimental images):
docker images --format "{{.Repository}}:{{.Tag}}"

# Find images in daemon NOT in dist:
docker images --format "{{.Repository}}:{{.Tag}}" | while read img; do
  base=$(echo "$img" | tr '/:' '-')
  [ ! -f "$SEAGATE/docker-images/${base}.tar" ] && echo "NOT IN DIST: $img"
done
```

## CUDA_ARCH reference table

When building llama-server for a different architecture, override CUDA_ARCH:

| GPU Architecture | Example GPUs | sm_ value | CUDA_ARCH arg |
|-----------------|-------------|-----------|---------------|
| Blackwell | Jetson DGX Spark | sm_121 | 121 (current default) |
| Hopper | H100, H200 | sm_90 | 90 |
| Ada Lovelace | RTX 4090, L40S | sm_89 | 89 |
| Ampere | A100, A30 | sm_80 | 80 |
| Turing | RTX 2080, T4 | sm_75 | 75 |
| Multi-arch | unknown GPU | — | `89;90` (semicolon-separated) |

Override via buildx `--build-arg`:
```bash
docker buildx build --platform linux/amd64 --load \
  --build-arg CUDA_ARCH=89 \
  -t llama-x86-builder:latest \
  -f llm-stack/docker/llamacpp/Dockerfile .
```

Or edit the Dockerfile `ARG CUDA_ARCH=121` line directly.

## Verification checklist summary

- [ ] Wheel count matches (60 ARM64 = 60 x86_64)
- [ ] Platform-specific wheel count matches (14 aarch64 = 14 x86_64)
- [ ] Docker image count matches plan vs actual `.tar` files
- [ ] Docker image sizes verified with `du -bc` (exact bytes)
- [ ] llama-server binary architecture verified with `file`
- [ ] CUDA_ARCH value checked in llamacpp Dockerfile
- [ ] Compose service names match plan vs actual compose files
- [ ] No phantom images from `docker images` (OpenWebUI sidecars, runtime containers)
- [ ] Partially-completed target directories checked (codewar-x86/ may already exist)
