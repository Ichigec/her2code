# Portable v1 Clean Package — Self-Contained Deployment

A minimal, self-contained Hermes portable package that includes Docker
image tarball, pre-built GUI, configs, and launch scripts. Nothing is
downloaded at runtime — only Docker itself must be pre-installed.

Verified working 2026-07-08 on ARM64 (Jetson Orin / DGX Spark).

## Package structure

```
hermes_portable_v1/                 ~2 GB
├── start-backend.sh                Docker launcher (auto-loads tarball)
├── launch.sh                       GUI launcher (ARM64 flags built-in)
├── stop.sh                         Stop everything
├── README.md                       User instructions
├── docker/
│   ├── docker-compose.yml          2 services: gateway + dashboard
│   └── hermes-agent-arm64.tar.gz   Docker image (1.6 GB)
├── config/
│   └── config.docker.yaml          Hermes config (provider, model)
└── gui/                            Pre-built Electron (ARM64, 345 MB)
    ├── Hermes                      Binary
    ├── resources/
    │   └── app.asar
    ├── libEGL.so libGLESv2.so libvulkan.so.1
    └── locales/ icudtl.dat *.pak
```

## start-backend.sh responsibilities

1. Detect `REAL_HOME` via `getent passwd` (Hermes overrides `$HOME`)
2. **`unset HERMES_HOME DASH_HOME`** — prevent inheritance from parent Hermes
3. Export all vars: `PORT_GW=18649`, `PORT_DASH=9123`, `HERMES_UID/GID`
4. Check Docker daemon running
5. If image not loaded → `docker load --input docker/hermes-agent-arm64.tar.gz`
6. Create `~/.hermes-portable/` and `~/.hermes-portable-dash/`
7. Generate gateway `.env` with `API_SERVER_ENABLED=true`, random key, correct port
8. Generate dashboard `.env` WITHOUT any `API_SERVER_*` vars
9. `docker compose up -d` (NO `--env-file` flag — not universally supported)
10. Wait for gateway health (up to 2 min) then dashboard (up to 5 min)

## launch.sh responsibilities

1. Kill stale GUI process (`pgrep -f "linux-.*-unpacked/Hermes"`)
2. Create `~/.config/Hermes/connection.json` pointing to `localhost:9123`
3. Launch with ARM64-mandatory flags: `--disable-gpu --disable-software-rasterizer --no-sandbox`
4. Token in connection.json is `sk-docker-b` (must match `DASH_TOKEN` in start-backend.sh)

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| `unset HERMES_HOME` at top | Parent Hermes exports it → wrong volume mount |
| No `--env-file` flag | Older Docker versions don't support it |
| Dashboard wait = 5 min | s6-overlay first boot is slow on ARM64 |
| Separate dashboard volume | Prevents s6-log lock + .env bleed-through |
| `HERMES_UID=$(id -u)` | Default 10000 locks host user out of volume |
| `API_SERVER_ENABLED=true` in .env | Without it, gateway won't start API server |
| Port 9123 (not 9122) | Host Hermes auto-restarts on :9122 |

## Creating the package from scratch

```bash
# 1. GUI: copy from working Hermes install
cp -a ~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked gui/

# 2. Docker image: save from working Docker
docker save hermes-agent:latest | gzip > docker/hermes-agent-arm64.tar.gz

# 3. Config: use existing docker config
cp config/config.docker.yaml config/

# 4. Scripts: see start-backend.sh, launch.sh, stop.sh above
```

## Cross-machine deployment

When copying to another ARM64 machine (e.g. `paulpk`):

```bash
# On target machine:
cd /path/to/hermes_portable_v1
chmod +x *.sh
./start-backend.sh    # loads tarball, creates volumes, starts containers
./launch.sh           # opens GUI window
```

Only Docker needs to be pre-installed. Everything else is in the folder.
