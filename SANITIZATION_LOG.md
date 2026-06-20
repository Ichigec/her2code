# Sanitization Log — Hermes Stack

> **Date:** 2026-06-19  
> **PID:** `pavel_20260619_200039`  
> **Tool:** `sanitize.py` (included in this repo)  
> **Verdict:** ✅ 0 gitleaks findings, 0 PII remaining

## Summary

| Category | Count | Action |
|----------|:-----:|--------|
| 🔴 CRITICAL — Real API keys/passwords | 7 | Replaced with placeholders or deleted |
| 🟠 HIGH — Telegram IDs, Phone IDs, IPs | 20 | Replaced with placeholders |
| 🟡 MEDIUM — Paths, names, hardware | 29 | Replaced with `<YOUR_*>` or `/home/user/` |
| 🗄️ Databases cleared | 5 | Schema-only (data deleted) |
| 🗑️ Files deleted | 73 | Session dumps, logs, plans, personal skills |
| 📝 Files sanitized | 28+ | Regex replacements applied |
| ➕ Components added (round 2) | education-graph + claw-agent | Code only, no trained/collected data |

## Detailed Removal Log

### 🔴 CRITICAL: API Keys & Passwords

| # | Original | Replacement |
|---|----------|-------------|
| 1 | OpenAI API key `sk-proj-...Cr8A` in `litellm-dual.env` | `<YOUR_OPENAI_KEY>` (file excluded) |
| 2 | API Server key `<YOUR_API_SERVER_KEY>...rRv` in plans/sessions | Files deleted |
| 3 | Sudo password `<YOUR_SUDO_PASSWORD>` in `.sudo_pass` | File deleted |
| 4 | VLESS UUID `<YOUR_VLESS_UUID>` | `<YOUR_VLESS_UUID>` |
| 5 | DeepSeek API key ref in `config.yaml` | `<YOUR_DEEPSEEK_KEY>` |
| 6 | Bitwarden token ref in `config.yaml` | `<YOUR_BW_TOKEN>` |
| 7 | OpenAI key in session dumps (3 files) | Files deleted |

### 🟠 HIGH: Identifiers

| # | Original | Replacement |
|---|----------|-------------|
| 8 | Telegram chat `<YOUR_CHAT_ID>` | `<YOUR_CHAT_ID>` |
| 9 | Telegram DM `<YOUR_USER_ID>` | `<YOUR_USER_ID>` |
| 10 | Telegram bot `<YOUR_BOT_USERNAME>` | `<YOUR_BOT_USERNAME>` |
| 11 | Telegram channel `<YOUR_CHANNEL>` | `<YOUR_CHANNEL>` |
| 12 | VPS IP `<YOUR_VPS_IP>` | `<YOUR_VPS_IP>` |
| 13 | Public IP `<YOUR_PUBLIC_IP>` | `<YOUR_PUBLIC_IP>` |
| 14 | Home IP `<YOUR_HOME_IP>` | `<YOUR_HOME_IP>` |
| 15 | Local IP `<YOUR_LOCAL_IP>` | `<YOUR_LOCAL_IP>` |
| 16 | Router IP `<YOUR_ROUTER_IP>` | `<YOUR_ROUTER_IP>` |
| 17 | Phone subnet `10.4.x.x` | `<YOUR_PHONE_SUBNET>` |
| 18 | Phone ID `<YOUR_PHONE_ID>` | `<YOUR_PHONE_ID>` |
| 19 | VPS hostname `<YOUR_VPS_HOSTNAME>` | `<YOUR_VPS_HOSTNAME>` |
| 20 | WiFi SSID `<YOUR_WIFI_SSID>` | `<YOUR_WIFI_SSID>` |
| 21 | Hostname `<YOUR_HOSTNAME>` | `<YOUR_HOSTNAME>` |
| 22 | Tunnel `<YOUR_TUNNEL_URL>` | `<YOUR_TUNNEL_URL>` |
| 23 | Tunnel `<YOUR_TUNNEL_URL>` | `<YOUR_TUNNEL_URL>` |
| 24 | Tunnel `<YOUR_TUNNEL_URL>` | `<YOUR_TUNNEL_URL>` |
| 25 | Tunnel `*.trycloudflare.com` | `<YOUR_TUNNEL_URL>` |
| 26 | Telegram name `Павел` | `User` |

### 🟡 MEDIUM: Paths & Names

| # | Original | Replacement |
|---|----------|-------------|
| 27 | `{HOME}/.hermes/...` (~50 files) | `/home/user/.hermes/...` |
| 28 | `{HOME}/dev/...` | `/home/user/dev/...` |
| 29 | `{HOME}/cursor/...` | `/home/user/projects/...` |
| 30 | Git name `Pavel` | `User` |
| 31 | Git email `user@localhost` | `user@localhost` |
| 32 | GitHub `<YOUR_GITHUB_USER>` | `<YOUR_GITHUB_USER>` |
| 33 | Gitea user `pavel` | `user` |
| 34 | Systemd `User=pavel` | `User=user` |

### 🗄️ Databases (5)

| DB | Original | Action |
|----|----------|--------|
| `state.db` | 535 MB, 498 sessions, 25,052 messages | Deleted |
| `audit.db` | 229 KB, 15 tables | Deleted |
| `kanban.db` | 115 KB | Deleted |
| `metrics.db` | 49 KB | Deleted |
| `response_store.db` | 20 KB | Deleted |

### 🗑️ Deleted Directories & Files (73 items)

- `pavel-environment/` skill — 426 lines of personal environment specs
- `sing-box-vpn-setup.md` — VLESS UUID, IPs
- `.sudo_pass` — sudo password
- `sessions/` — 47 JSON dumps (~10 MB)
- `logs/` — 15 log files (~24 MB)
- `plans/` — 8 project plans
- `memories/MEMORY.md`, `USER.md` → templated
- `hermes-agent/apps/desktop/release/` — built Electron binary (280 MB)
- `hermes-agent/apps/desktop/dist/` — built JS bundles
- `hermes-agent/tests/` — test data with API key fixtures
- `hermes-agent/website/` — documentation site
- `opencode-android/.gradle/`, `build/` — Gradle cache
- All `__pycache__/`, `*.pyc` files

### 🚫 Explicitly Excluded (never copied)

- `~/.hermes/.env` — credential store (blocked by defense-in-depth)
- `~/.hermes/auth.json` — authentication data
- `~/.ssh/id_ed25519*` — SSH keys
- `~/.ssh/known_hosts` — host fingerprints
- `~/.gitconfig` — git identity
- `~/.hermes/bin/` — external binaries (cloudflared, tirith, uv, uvx)
- `*.apk` files — Android binaries
- `*.AppImage` — LM Studio binary
- LLM models (`~/models/`, `~/.lmstudio/models/`) — multi-GB

## Verification

Run these checks to verify sanitization:

```bash
# 0 findings expected in ALL of these:
gitleaks detect --no-git -v -s .
grep -r '/home/pavel' . -l          # → empty
grep -rP 'sk-proj-[A-Za-z0-9_-]{30,}' . -l  # → empty
grep -r '64\.188\.64\.52' . -l      # → empty
grep -r '<YOUR_PHONE_ID>' . -l     # → empty
grep -r '\<YOUR_CHAT_ID>' . -l      # → empty
grep -r '3957c617' . -l             # → empty
```

## Reproducibility

To re-run sanitization from source:

```bash
python3 sanitize.py
```

Configure replacements in `sanitize-config.yaml`.
