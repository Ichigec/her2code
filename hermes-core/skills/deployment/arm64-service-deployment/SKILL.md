---
name: arm64-service-deployment
description: Deploy self-hosted services on ARM64 (Jetson) when official Docker images lack ARM64 support. Discovery pattern, binary fallback, Docker-for-dependencies strategy.
category: deployment
---

# ARM64 Service Deployment

Trigger: user asks to install/deploy a self-hosted service (Mattermost, GitLab, etc.) on Pavel's Jetson (ARM64/aarch64, Ubuntu 24.04).

## Discovery Pattern

1. **Check Docker first**: `docker pull <official-image>` — many services don't publish ARM64 manifests.
2. **Check official binary releases**: look at the project's downloads page / releases. Pattern for Mattermost: `https://releases.mattermost.com/{version}/mattermost-{version}-linux-arm64.tar.gz`.
3. **Check community ARM64 Docker images** as fallback, but prefer official binaries (newer, maintained).
4. **Build from source** as last resort (Go/Rust projects cross-compile well; Node/Python have less friction than C++).

## Standard Stack

- **Service binary**: direct download + extract to `~/<service>/`
- **Database**: Docker container (user has Docker group, no sudo needed for Docker)
- **Config**: edit JSON/YAML config in-place via `patch` tool
- **Runtime**: background process via `terminal(background=true, notify_on_complete=true)`

## PostgreSQL via Docker (reusable)

```bash
docker run -d --name <service>-postgres \
  -e POSTGRES_USER=<user> \
  -e POSTGRES_PASSWORD=<password> \
  -e POSTGRES_DB=<dbname> \
  -p 5432:5432 \
  postgres:16-alpine
```

Password changes: `docker exec <container> psql -U <user> -d <dbname> -c "ALTER USER <user> WITH PASSWORD '<new>';"`

## Pitfalls

- **`/opt/` needs root** — install under `~/` instead (Pavel has no sudo password).
- **Config `DataSource` format**: `postgres://user:pass@localhost:5432/dbname?sslmode=disable&connect_timeout=10&binary_parameters=yes` — MUST include port `:5432` when using Docker port mapping, the default config omits the port.
- **`SiteURL`**: set to `http://localhost:<port>` in config or the service will log warnings and some features break.
- **ARM64 binary naming**: varies by project — `linux-arm64`, `linux-aarch64`, `arm64`. Check the release page directly with `curl -sI` to probe before downloading.

## Verification

After starting the service:
```bash
curl -s http://localhost:<port>/api/v4/system/ping  # or equivalent health endpoint
ss -tlnp | grep <port>
```

## References

- `references/mattermost.md` — Mattermost-specific setup details and config structure.
