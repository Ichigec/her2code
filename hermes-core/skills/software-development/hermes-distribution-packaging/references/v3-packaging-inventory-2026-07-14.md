# V3 Packaging Inventory — July 14, 2026

Full audit of `~/.hermes/` conducted 2026-07-14 for hermes_portable_v3.
Supersedes `packaging-inventory-2026-07.md` (counts have grown).

## Current Hermes version

```
Hermes Agent v0.16.0 (2026.6.5)
upstream 46e87b14, local beeb744a (+7 carried commits)
Python 3.11.15, OpenAI SDK 2.45.0
```

## Profile structure (discovered this session)

```
~/.hermes/                          <- HERMES_HOME (top level)
├── agents/         (32 .md)        <- HERE, not under profiles/
├── skills/         (131 SKILL.md)  <- HERE, not under profiles/
├── hooks/          (10)
├── scripts/        (32)
├── gates/          (60 files)
├── plugins/        (3 dirs)
├── cron/           (2 job dirs + output/)
├── config.yaml     (11.8K)         <- real keys, Telegram, personal
├── .env            (24.8K)         <- REAL API KEYS
├── persona.md      (2.5K)          <- plan2 ref, personal workflow
├── AGENTS.md       (17K)           <- /home/user/, IPs, phone IDs
├── state.db        (698M)          <- EXCLUDE
├── .sudo_pass                      <- EXCLUDE
├── channel_directory.json          <- EXCLUDE (Telegram chat IDs)
├── auth.json                       <- EXCLUDE
├── observer_queue.jsonl            <- EXCLUDE
├── observations/                   <- EXCLUDE
└── home/.hermes/profiles/
    └── codewar/                    <- profile name is env-specific, NOT "1"
        ├── config.yaml             <- profile-specific config
        └── .env                    <- profile-specific keys
```

## Inventory comparison (July 6 → July 14)

| Component | July 6 | July 14 | Change |
|-----------|--------|---------|--------|
| agents/ | 31 | 32 | +1 |
| skills/ (SKILL.md) | ~80 est. | 131 | +51 (significant growth) |
| hooks/ | 8 | 10 | +2 |
| scripts/ | 30 | 32 | +2 |
| gates/ | full system | 60 files | stable |
| plugins/ | 3 | 3 | stable |
| state.db | 323M | 698M | +375M (growing — more reason to exclude) |

## V3 target structure

```
hermes_portable_v3/
├── start-backend.sh       # Docker backend (auto-arch, from V2)
├── launch.sh              # GUI launcher (auto-arch, from V2)
├── chat.sh                # CLI fallback
├── stop.sh / status.sh
├── README.md / VERSION / .env.example
├── docker/                # 2.4G (REUSED from V2 — same version)
│   ├── hermes-agent-arm64.tar.gz  (1.6G)
│   └── hermes-agent-x64.tar.gz    (810M)
├── gui-arm64/             # 344M (REUSED from V2)
├── gui-x64/               # 339M (REUSED from V2)
├── hermes-core/           # ~50M sanitized
│   ├── agents/  skills/  hooks/  scripts/
│   ├── gates/  plugins/  cron/  templates/
│   ├── config.yaml  persona.md  AGENTS.md
└── pip-packages/          # ~40M wheels for offline install
```

Estimated total: ~3.5G

## V2 assets verified reusable

- Docker image `hermes-agent:latest` built 2026-07-07 (v0.16.0) — matches current version
- V2 Docker tarballs dated July 9 — same image
- V2 GUI binaries (ARM64 + x64) — pre-built from same codebase
- Only ARM64 binary exists on host (`linux-arm64-unpacked`); x64 was cross-built for V2

## PII sources to exclude (verified 2026-07-14)

| Path | Contents |
|------|----------|
| `.sudo_pass` | Actual sudo password |
| `channel_directory.json` | Telegram chat_id: <YOUR_TELEGRAM_CHAT_ID> |
| `auth.json` | Auth tokens |
| `observer_queue.jsonl` | Observer state |
| `observations/` | Personal observation history (172K) |
| `cron/output/` | Personal cron execution results |
| `state.db` | 698M sessions DB |
| `.env` | 24.8K real API keys |
| `config.yaml` | 11.8K with real settings, Telegram config |

## Scripts with potential secrets (grep sk- found)

- `scripts/launch-docker-gui.sh` — check for hardcoded tokens
- `scripts/claw-discovery.py` — check for API keys
- `scripts/embed_skills.py` — check for API keys

All must pass through PII sanitization before packaging.
