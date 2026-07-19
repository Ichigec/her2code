# Offline USB Deployment — exFAT Pitfalls & Patterns

> Lessons from building a full offline Hermes package on an exFAT-formatted
> USB drive (2026-07-08). These constraints apply to ANY script or binary
> placed on exFAT/FAT32 external storage.

## exFAT Filesystem Constraints

exFAT (default for large USB drives, macOS-formatted drives) has four
silent failure modes that bite bash scripts and Docker workflows:

### 1. Heredoc corruption

Bash heredocs (`cat > file <<EOF ... EOF`) produce **silently corrupted
output** on exFAT. The EOF marker gets merged with the next line, or
content is truncated. `bash -n` passes (syntax looks fine in memory),
but the written file is broken.

**Fix:** Replace ALL heredocs with `printf`:
```bash
# WRONG (exFAT corrupts this):
cat > "$FILE" <<EOF
KEY=$VALUE
EOF

# RIGHT:
printf 'KEY=%s\n' "$VALUE" > "$FILE"
```

For multi-line config files, use multiple printf calls or a single
printf with `\n` separators:
```bash
printf '{"mode":"remote","remote":{"url":"http://localhost:%s","token":{"value":"%s"},"authMode":"token"},"profiles":{}}\n' \
    "$PORT" "$TOKEN" > "$CONN_FILE"
```

### 2. UTF-8 character corruption

Non-ASCII characters (Cyrillic, emoji, em-dashes `—`, box-drawing
characters `═`, checkmarks `✅`) get corrupted when written via
`write_file` or `cat` to exFAT. The bytes arrive as mojibake, which
can break bash parsing (e.g., unbalanced quotes from corrupted echo
strings).

**Fix:** Write scripts in **pure ASCII** when they target exFAT.
Use English-only messages, `==` instead of `✅`, `->` instead of `→`.

### 3. Symlink failure

exFAT does not support symlinks. `cp -a` silently drops them (on some
systems) or fails with "Operation not permitted". `node_modules/` from
npm/electron contains many symlinks (`libfoo.so -> libfoo.so.0`).

**Fix:** Use `cp -rL` (dereference) instead of `cp -a`:
```bash
# WRONG (symlinks fail on exFAT):
cp -a /source/node_modules /target/

# RIGHT (dereferences symlinks into real files):
cp -rL /source/node_modules /target/
```

For Docker-to-host extraction, use `tar` (preserves symlinks within
the tar stream, dereferences on extraction to exFAT):
```bash
docker run --rm --entrypoint tar "$IMAGE" \
    -cf - -C /opt/hermes apps/desktop node_modules \
    | tar -xf - -C "$BUILD_DIR"
```

### 4. Docker volume mount failure

`docker run -v /exfat/path:/container/path` fails or produces permission
errors because exFAT doesn't support POSIX permissions (uid/gid/mode).

**Fix:** Use `/tmp/` (ext4/tmpfs) for Docker build directories:
```bash
# WRONG (exFAT mount → permission denied):
BUILD_DIR="$SCRIPT_DIR/.build"
docker run -v "$BUILD_DIR:/out" ...

# RIGHT (/tmp is ext4):
BUILD_DIR="/tmp/hermes-build-$$"
docker run -v "$BUILD_DIR:/out" ...
```

## Cross-Architecture Docker Build (ARM64 → x64)

### QEMU SIGSEGV on Node.js

Cross-building x64 Docker images from ARM64 via QEMU/binfmt works for
`apt-get` and `pip`, but **crashes with SIGSEGV** on any Node.js
operation (npm install, npm run build, npx).

```
x86_64-binfmt-P: QEMU internal SIGSEGV {code=MAPERR, addr=0x20}
Segmentation fault (core dumped)
```

**Workaround:** Skip all npm/Node.js steps in the Dockerfile for
cross-builds. The resulting image has Python backend but no web UI:

```dockerfile
# Patch for cross-build: skip Node.js entirely
RUN true # npm+playwright skipped — QEMU SIGSEGV on x64 cross-build
RUN true # web+ui-tui build skipped — QEMU SIGSEGV
```

Also fix apt signature issues (QEMU doesn't verify GPG properly):
```dockerfile
RUN apt-get update --allow-insecure-repositories || \
    (echo 'Acquire::AllowInsecureRepositories "true";' > /etc/apt/apt.conf.d/99insecure && \
     apt-get update) && \
    apt-get install -y --allow-unauthenticated --no-install-recommends ...
```

And remove `node_modules` from chown (doesn't exist without npm install):
```dockerfile
RUN chmod -R a+rX /opt/hermes && \
    chown -R hermes:hermes /opt/hermes/.venv /opt/hermes/ui-tui /opt/hermes/gateway
    # NOTE: /opt/hermes/node_modules removed — not created in cross-build
```

### Image sizes

| Architecture | Image size | Compressed (tar.gz) |
|-------------|-----------|---------------------|
| ARM64 (native build) | 4.65 GB | 1.6 GB |
| x64 (QEMU cross-build, no npm) | 2.37 GB | 810 MB |

## Offline GUI Build from Docker Image

When no pre-built Electron binary exists for the target architecture,
build it on the target machine from source extracted out of the Docker
image:

1. Extract apps/desktop + node_modules from image via tar
2. Copy Electron binary from cache (`~/.cache/electron/electron-v*.zip`)
3. Run `npm run build && npm run pack` on the target machine
4. Copy result to `gui/`

**Key:** Build in `/tmp/` (not exFAT), use tar (not cp -a), set
`ELECTRON_SKIP_BINARY_DOWNLOAD=1` when cache is present.

## Package Structure for Full Offline Deployment

```
hermes_portable/
├── start-backend.sh          # Docker image load + container start
├── launch.sh                 # GUI launch (auto arch check + build)
├── chat.sh                   # CLI alternative (no Electron needed)
├── stop.sh                   # Teardown
├── docker/
│   ├── hermes-agent-arm64.tar.gz   # Docker image (per-arch)
│   └── hermes-agent-x64.tar.gz
├── docker/docker-compose.yml       # platform: directive mandatory
├── gui/
│   ├── Hermes                       # Pre-built binary (per-arch)
│   └── electron-v*-linux-*.zip     # Electron cache for offline build
├── config/
│   └── config.docker.yaml
└── .api-key                        # Generated by start-backend.sh
```

## docker-compose.yml: platform directive

Without `platform:`, Docker compose refuses to run mismatched images:
```
The requested image's platform (linux/arm64) does not match
the detected host platform (linux/amd64/v3)
```

**Fix:** Add platform to every service:
```yaml
services:
  hermes:
    image: ${HERMES_IMAGE:-hermes-agent}
    platform: ${DOCKER_PLATFORM:-linux/amd64}
    ...
```

The `DOCKER_PLATFORM` variable is set by the start script based on
`uname -m` detection.
