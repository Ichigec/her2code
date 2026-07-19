# Portable v2: Dual-Architecture Package (Pre-Built Binaries)

> **(2026-07-09):** Evolution of the v1 pattern. Pre-builds BOTH GUI binaries
> (ARM64 + x64) on the Jetson, so the target machine needs ZERO build tools.

## Why v2?

The v1 pattern shipped a single ARM64 GUI binary. On x64 machines, the user
had to build from source on-site (needs Node.js 22, npm, build-essential,
network for npm ci). The v2 pattern eliminates all of that.

## Key Technique: electron-builder --dir --x64 on ARM64

`npx electron-builder --dir --x64` run on the Jetson (ARM64) produces a
working x86-64 ELF binary. This is a packaging step, not a build step —
no QEMU needed. See `hermes-gui-launch` ->
`references/cross-arch-offline-build.md` Method 1.

## Package Layout

```
hermes_portable_v2/                  ~3.0 GB (fully self-contained)
├── start-backend.sh                 Auto-arch: loads arm64 or x64 Docker tar.gz
├── launch.sh                        Auto-arch: picks gui-arm64/ or gui-x64/
├── chat.sh                          CLI chat via python3 urllib (arch-independent)
├── stop.sh                          Stop containers + GUI
├── requirements.md                  Human-readable instructions
├── config/
│   └── config.docker.yaml           Provider/model config
├── docker/
│   ├── hermes-agent-arm64.tar.gz    ~1.6 GB (full, with web UI)
│   └── hermes-agent-x64.tar.gz      ~810 MB (gateway only, no web UI — QEMU limitation)
├── gui-arm64/
│   └── Hermes                       Pre-built ARM64 binary (~344 MB)
└── gui-x64/
    └── Hermes                       Pre-built x64 binary (~339 MB, cross-compiled on Jetson)
```

## auto-arch Detection Pattern

Both `start-backend.sh` and `launch.sh` use the same pattern:

```bash
ARCH=$(uname -m)
case "$ARCH" in
  aarch64|arm64) GUI_DIR="gui-arm64"; DOCKER_TAR="hermes-agent-arm64.tar.gz" ;;
  x86_64|amd64)  GUI_DIR="gui-x64";   DOCKER_TAR="hermes-agent-x64.tar.gz"  ;;
esac
```

## launch.sh Key Differences from v1

1. **No `exec`** — v1 used `exec "$BIN"` which replaced the shell with the
   binary. If the binary was wrong-arch, the user dropped into a root shell
   with no error message. v2 runs `"$BIN" &` and checks exit code.

2. **Binary arch validation** — `file "$BIN" | grep -q "$(uname -m)"` before
   launching, exits with clear message if mismatch.

3. **`set -u` without `set -e`** — `-e` killed the script when `grep`/`read`
   returned non-zero (e.g., empty pipe). v2 uses only `set -u`.

## x64 Docker Image Limitation (QEMU)

The x64 Docker image cross-built via `docker buildx --platform linux/amd64`
**lacks web UI** because QEMU SIGSEGV's on `npm install`. The gateway and
dashboard API work fine. The dashboard serves but `/` returns no frontend.

**Impact:** GUI connects to dashboard (:9123) which proxies to gateway (:18649).
Chat works through WebSocket. Only the browser-based dashboard UI is blank.

**If full web UI is needed on x64:** build the Docker image natively on the
x64 machine (`docker build -t hermes-agent .`). Requires Node.js 22 on x64.

## chat.sh: CLI Fallback

v2 includes `chat.sh` — a pure Python3 (urllib) CLI chat client that connects
to the gateway API directly. No curl dependency, no Node.js. Works on any
architecture, any distro with Python3 (which is essentially all of them).

```bash
python3 -c "
import urllib.request, json
req = urllib.request.Request(
    'http://localhost:18649/v1/chat/completions',
    json.dumps({...}).encode(),
    {'Content-Type':'application/json', 'Authorization':f'Bearer {key}'})
print(urllib.request.urlopen(req, timeout=120).read().decode())
"
```

## Script Writing for exFAT (STILL CRITICAL)

All v2 scripts on the USB drive must be **pure ASCII** (no Cyrillic, no emoji,
no em-dashes). Write to `/tmp` first, verify with `bash -n`, then `cp` to USB.

The `chat.sh` script was rewritten 3 times because inline Python with UTF-8
broke bash syntax on exFAT. Final version uses `python3 -c` with ASCII-only
arguments.
