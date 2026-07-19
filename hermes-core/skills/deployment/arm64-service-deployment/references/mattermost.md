# Mattermost on ARM64

## Binary

Official ARM64 builds published at `https://releases.mattermost.com/{version}/mattermost-{version}-linux-arm64.tar.gz`.

Latest tested: **11.6.0** (April 2026, 430 MB).

## Directory Structure

```
~/mattermost/
  bin/mattermost       # server binary
  config/config.json   # main configuration
  client/              # React frontend SPA
  logs/                # server logs
  templates/           # email templates
  i18n/                # translations
```

## Database Setup

```bash
docker run -d --name mattermost-postgres \
  -e POSTGRES_USER=mmuser \
  -e POSTGRES_PASSWORD=*** \
  -e POSTGRES_DB=mattermost \
  -p 5432:5432 \
  postgres:16-alpine
```

## Config Changes (config/config.json)

Key settings to change from defaults:

```json
{
  "ServiceSettings": {
    "SiteURL": "http://localhost:8065",
    "ListenAddress": ":8065"
  },
  "SqlSettings": {
    "DriverName": "postgres",
    "DataSource": "postgres://mmuser:mmuser_password@localhost:5432/mattermost?sslmode=disable&connect_timeout=10&binary_parameters=yes"
  }
}
```

**Critical**: Default config uses database `mattermost_test` — change to `mattermost`. Default config omits port — add `:5432`.

## Start Command

```bash
cd ~/mattermost && ./bin/mattermost server
```

Runs on port 8065. Web UI at `http://localhost:8065`.

## Health Check

```bash
curl -s http://localhost:8065/api/v4/system/ping
# → {"status":"OK"}
```

## First Access

On first load, Mattermost prompts to create an admin account (email + password). No CLI bootstrap needed.

## Version Check

```bash
./bin/mattermost version
# → Version: 11.6.0, Build Date: Mon Apr 6 15:40:07 UTC 2026
```

## Official Docker Image Gap

`mattermost/mattermost-team-edition` has NO `linux/arm64/v8` manifest. The binary is available on the release server, just not packaged into a multi-arch Docker image. Community images (zefhemel/mattermost-arm64) are from 2021 — avoid.
