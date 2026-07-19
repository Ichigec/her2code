# Self-Contained Portable Package (v1)

Verified pattern (2026-07-08): Docker image + GUI binary + scripts in ONE folder.
Nothing downloaded. Works on ARM64 (Jetson/DGX Spark).

## Package contents

```
hermes_portable_v1/                  ~1.9 GB
├── start-backend.sh                 # Prepare + docker compose up + health wait
├── launch.sh                        # connection.json + Electron launch
├── stop.sh                          # Cleanup
├── docker/
│   ├── docker-compose.yml           # 2 services (gateway + dashboard, separate volumes)
│   └── hermes-agent-arm64.tar.gz    # Docker image (1.6 GB compressed)
├── config/
│   └── config.docker.yaml           # Model/provider config
└── gui/                             # Pre-built Electron (ARM64)
    ├── Hermes                       # 187 MB ELF binary
    ├── *.pak, *.so, *.dat           # Chromium runtime files
    └── resources/
        └── app.asar                 # Electron app bundle
```

## Creating the package

### 1. Docker image

```bash
docker save hermes-agent:latest | gzip > docker/hermes-agent-arm64.tar.gz
# Verify: docker load --input docker/hermes-agent-arm64.tar.gz
```

### 2. GUI binary

```bash
# Source: host Hermes build output
cp -a ~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/ gui/
# The binary is at gui/Hermes (~187 MB ARM64 ELF)
# Must verify: file gui/Hermes → "ELF 64-bit LSB pie executable, ARM aarch64"
```

**⚠️ Copy the ENTIRE unpacked directory**, not just the `Hermes` binary. Chromium
needs `.pak`, `.so`, `.dat` files alongside the binary. Missing `libEGL.so` or
`icudtl.dat` → silent crash.

### 3. Config

```bash
cp config/config.docker.yaml config/
```

## First-run behavior

`start-backend.sh`:
1. Checks if Docker image exists → if not, auto-loads from tarball (`docker load`)
2. Creates `~/.hermes-portable/.env` with `API_SERVER_ENABLED=true` + random key
3. Creates `~/.hermes-portable-dash/.env` WITHOUT api_server settings
4. `docker compose up -d`
5. Waits for gateway health (2 min) then dashboard health (3 min)

## Dashboard cold-start timing (ARM64)

| Phase | Time | What happens |
|-------|------|-------------|
| s6-overlay init | 30-60s | UID change, skill sync, profile reconcile |
| Python import | 20-30s | Hermes modules loaded |
| Gateway health | 90-120s | API server starts on :18649 |
| Dashboard ready | 120-180s | Web UI + WebSocket on :9123 |

**Total cold start: up to 3 minutes.** The wait loop in start-backend.sh is
60 × 3s = 180s. Do NOT shorten — first boot will time out.

## ⚠️ Tool corruption when writing bash scripts

When using `write_file` or `patch` to create bash scripts containing token-like
strings (e.g., `${HERMES_DASHBOARD_SESSION_TOKEN:-sk-docker-b}`), the platform's
redaction layer can corrupt the value, replacing the middle with `...`:

```bash
# Written by tool:
export DASH_TOKEN="${DASH_TOK...r-b}"     # ← CORRUPTED

# Actual intent:
export DASH_TOKEN="${HE... # ← correct
```

**Symptom:** `bash -n` fails with "bad substitution" or script runs but DASH_TOKEN
is garbage.

**Fix:**
1. ALWAYS run `bash -n script.sh` after writing
2. If corrupted, re-write using simpler quoting or split the line
3. Alternative: use a variable that doesn't match token patterns:
   ```bash
   DT="sk-doc...NE_TOKEN:-$DT}"  # indirect, avoids pattern match
   ```

## Verification after package creation

```bash
# 1. All scripts pass syntax
bash -n start-backend.sh && bash -n launch.sh && bash -n stop.sh

# 2. Docker image loads
docker load --input docker/hermes-agent-arm64.tar.gz

# 3. GUI binary is ARM64
file gui/Hermes | grep -q "ARM aarch64"

# 4. Clean start from scratch
docker rm -f hermes-gateway hermes-dashboard
rm -rf ~/.hermes-portable ~/.hermes-portable-dash
./start-backend.sh   # should complete in ~3 min

# 5. Volumes are correct
docker inspect hermes-gateway --format '{{range .Mounts}}{{.Source}}{{println}}{{end}}'
# MUST show: /home/<user>/.hermes-portable (NOT /home/<user>/.hermes)
```
