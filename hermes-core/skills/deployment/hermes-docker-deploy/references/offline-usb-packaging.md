# Offline USB Packaging — Full Stack Portable Deployment

Session 20260708. Packaging Hermes + model + binary for offline x64/ARM64 machines.

## Package Structure

```
hermes_portable_v1/               ~2.3G (without model) or ~25G (with GGUF)
├── start-backend.sh              ← Docker gateway+dashboard launcher
├── launch.sh                     ← Electron GUI launcher
├── stop.sh                       ← Stop everything
├── docker/
│   ├── hermes-agent-arm64.tar.gz  (1.6G)  ← ARM64 Docker image
│   ├── hermes-agent-x64.tar.gz    (810M)  ← x64 Docker image (no web UI)
│   └── docker-compose.yml         ← with platform: directive
├── gui/
│   └── Hermes                     (195M)  ← Electron binary (arch-specific!)
├── config/
│   └── config.docker.yaml         ← model/provider config
├── models/                        ← (optional, 22G)
│   └── *.gguf
└── llama.cpp/                     ← (optional, for local LLM)
    ├── build/bin/llama-server     ← ARM64
    └── x64/llama-server           ← x64
```

## GGUF Model — Architecture Independent

GGUF files work on BOTH ARM64 and x64 — the same 22G file runs on either arch.
No need to package separate models per architecture.

## x64 Docker Image Limitations

Cross-compiling from ARM64 → x64 via QEMU:
- ✅ apt-get (with `--allow-unauthenticated`)
- ✅ Python pip/uv install
- ❌ `npm install` → SIGSEGV (`x86_64-binfmt-P: QEMU internal SIGSEGV`)
- ❌ `npm run build` → same SIGSEGV
- ❌ Playwright install → SIGSEGV

**Workaround:** Skip ALL Node.js steps in Dockerfile. Gateway + API work fine.
Dashboard starts but has no web UI assets. For full x64 Docker image, build
natively on an x64 machine.

## Architecture Auto-Detection Pattern

All three scripts use the same pattern:
```bash
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64) ARCH="arm64"; IMAGE_TAG="hermes-agent:arm64"; TARBALL="hermes-agent-arm64.tar.gz" ;;
  x86_64|amd64)  ARCH="x64";   IMAGE_TAG="hermes-agent:amd64"; TARBALL="hermes-agent-x64.tar.gz" ;;
esac
```

## heredoc-free Script Pattern for exFAT

Never use `cat <<EOF` on exFAT — use printf:
```bash
# .env generation
printf 'API_SERVER_ENABLED=true\nAPI_SERVER_KEY=%s\nAPI_SERVER_PORT=%s\n' "$KEY" "$PORT" > .env

# connection.json generation
printf '{"mode":"remote","remote":{"url":"http://localhost:%s","token":{"value":"%s"},"authMode":"token"},"profiles":{}}\n' \
  "$PORT_DASH" "$DASH_TOKEN" > connection.json
```

## Verification Checklist (before declaring "done")

1. `bash -n script.sh` passes on BOTH source and target
2. Binary `file` command matches target architecture
3. Docker image `--format '{{.Architecture}}'` matches target
4. Dashboard `/api/status` returns 200
5. Gateway `/health` returns 200
6. Model responds to chat completion through gateway
7. GUI window appears (xwininfo, not wmctrl — wmctrl false-negatives)

## Known Issues

- **x64 GUI binary not available offline:** Electron download requires GitHub
  access. For x64 machines, build locally: `cd hermes-agent && npm ci && npm run pack -- --linux`
- **x64 Docker image has no web UI:** npm steps skipped during cross-compile.
  Gateway API works, dashboard serves but has no embedded web assets.
- **start.sh path mismatch:** start.sh searches for GUI binary in
  `$PORTABLE_DIR/hermes-agent/apps/desktop/release/` but on USB it's in
  `$PORTABLE_DIR/gui/linux-arm64-unpacked/`. Must add USB path as first candidate.
