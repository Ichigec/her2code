# Offline Portable Package — Complete Deployment Pattern

> Pattern for creating a fully self-contained Hermes deployment package that
> runs on any machine without internet access. Tested 2026-07-08.

## Package structure

```
hermes_portable/                    ~25G total
├── deploy-offline-superqwen.sh     ← ONE-COMMAND launch (auto-detects arch)
├── start.sh                        ← Management (stop/status/gui)
├── models/
│   └── SuperQwen-APEX-I-Quality-v3.gguf   22G  ← GGUF (arch-independent)
├── llama.cpp/
│   ├── build/bin/llama-server              ARM64 native build
│   └── x64/                                x64 cross-compiled build
│       ├── llama-server
│       └── lib*.so*                        Shared libs (dereferenced symlinks)
├── docker/
│   └── hermes-agent-arm64.tar.gz           1.6G (gzip-compressed Docker image)
├── gui/
│   └── linux-arm64-unpacked/Hermes         687M (pre-built Electron)
├── config/
│   ├── config.docker.superqwen.yaml        Single-model config
│   ├── config.docker.3models.yaml          3-model config
│   └── config.docker.yaml                  Default config
└── scripts/                                18 helper scripts
```

## What must be pre-built offline

| Component | ARM64 | x64 | Notes |
|-----------|:-----:|:---:|-------|
| Docker image | ✅ `docker save \| gzip` | ❌ QEMU fails | Build on target x64 machine |
| GUI Electron | ✅ Pre-built binary | ❌ Needs GitHub download | Build on target x64 via `npm run pack` |
| llama-server | ✅ Native build | ✅ Cross-compiled (CPU-only) | See x64 cross-compile pitfalls below |
| GGUF model | ✅ Arch-independent | ✅ Same file | Works on both |

## deploy-offline-superqwen.sh — auto-architecture detection

The script detects architecture and uses the right binary:
```bash
ARCH="$(uname -m | sed 's/aarch64/arm64/;s/x86_64/x64/')"
GUI_BIN="$SCRIPT_DIR/gui/linux-${ARCH}-unpacked/Hermes"
MODEL_FILE="${MODEL_FILE:-$SCRIPT_DIR/models/SuperQwen-APEX-I-Quality-v3.gguf}"
LLAMA_BIN="$SCRIPT_DIR/llama.cpp/build/bin/llama-server"
[ -f "$LLAMA_BIN" ] || LLAMA_BIN="$SCRIPT_DIR/llama.cpp/x64/llama-server"
```

## Docker image save/load

```bash
# Save (on build machine, ~2-3 min for 4.65GB image):
docker save hermes-agent:latest | gzip > docker/hermes-agent-arm64.tar.gz
# Result: ~1.6GB compressed

# Load (on target machine):
docker load < docker/hermes-agent-arm64.tar.gz
```

## USB/exFAT drive pitfalls

USB flash drives are typically formatted as exFAT/FAT32 which do NOT support:
- Symlinks → `cp -r` fails with "Operation not permitted"
- Use `cp -rL` (dereference) to copy file contents instead of symlinks
- File permissions → chmod may not work, files may lose executable bit

```bash
# WRONG (exFAT):
cp -a llama.cpp/build /target/llama.cpp/build  # fails on symlinks

# RIGHT (exFAT):
cp -rL llama.cpp/build /target/llama.cpp/build  # dereferences symlinks
```

After copying, re-set executable bit:
```bash
chmod +x /target/llama.cpp/build/bin/llama-server
```
