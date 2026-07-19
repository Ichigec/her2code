# Portable v3 Packaging Pattern (2026-07-14)

Cleaner portable distribution structure with automated sanitization pipeline.
Developed during the hermes_portable_v3 session — an evolution of the V2
dual-arch portable pattern.

## Key improvement: reuse existing portable artifacts

**Before (V2):** Rebuilt Docker images and GUI binaries from scratch each time.

**After (V3):** Check if a previous portable version's Docker images and GUI
binaries are the same Hermes version. If so, just copy them.

```bash
# Check Hermes version
hermes --version  # → v0.16.0

# Check V2 docker image age + GUI binaries exist
ls -lh "/media/pavel/One Touch/hermes_portable_v2/docker/"
ls "/media/pavel/One Touch/hermes_portable_v2/gui-arm64/"
ls "/media/pavel/One Touch/hermes_portable_v2/gui-x64/"

# If same version → just copy (saves 30+ minutes of build time)
cp "$V2/docker/hermes-agent-arm64.tar.gz" "$V3/docker/"
cp "$V2/docker/hermes-agent-x64.tar.gz" "$V3/docker/"
cp -rL "$V2/gui-arm64" "$V3/gui-arm64"
cp -rL "$V2/gui-x64" "$V3/gui-x64"
```

**Verification:** `file gui-arm64/Hermes` → must show correct ELF architecture.
Docker image version can be checked via `docker inspect <image> --format '{{.Created}}'`.

## V3 directory structure

```
hermes_portable_v3/                    ~2.9G total
├── start-backend.sh                   # Docker backend launcher (auto-arch)
├── launch.sh                          # GUI launcher (auto-arch)
├── chat.sh                            # CLI curl-based chat
├── stop.sh / status.sh                # Container management
├── README.md / VERSION / .env.example
├── docker/                            # 2.3G — dual-arch Docker images
│   ├── hermes-agent-arm64.tar.gz     (1.6G)
│   ├── hermes-agent-x64.tar.gz       (810M)
│   └── docker-entrypoint.sh           # Telegram removal (sed-based)
├── gui-arm64/                         # 344M — pre-built ARM64 ELF
├── gui-x64/                           # 339M — pre-built x64 ELF
├── hermes-core/                       # 189M — sanitized ~/.hermes/ data
│   ├── agents/  skills/  hooks/  scripts/  gates/  plugins/  cron/
│   ├── config.yaml  persona.md  AGENTS.md
│   └── templates/                     # (if exists)
└── pip-packages/                      # 41M — 60 wheels for offline install
```

### Differences from V2

| Aspect | V2 | V3 |
|--------|----|----|
| Data layout | Flat in root | `hermes-core/` subdirectory |
| First-run data | Manual copy | Auto-copy on `start-backend.sh` first run |
| API key | Hardcoded in scripts | Auto-generated via `openssl rand -hex 32` |
| pip wheels | Not included | `pip-packages/` for offline CLI install |
| Scripts | start.sh (monolithic 890 lines) | 5 separate scripts (~60 lines each) |

## Automated PII sanitization pipeline

### Step 1: config.yaml — Python YAML recursive sanitizer

```python
import yaml, copy

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

sanitized = copy.deepcopy(config)

# 1. Remove Telegram platform entirely
if "gateway" in sanitized and "platforms" in sanitized["gateway"]:
    platforms = sanitized["gateway"]["platforms"]
    platforms.pop("telegram", None)

# 2. Recursively sanitize key/token/secret/password fields
def sanitize_recursive(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = k.lower()
            if any(word in kl for word in ["key", "token", "secret", "password", "pass"]):
                if isinstance(v, str) and len(v) > 5:
                    obj[k] = "CHANGEME"
            else:
                sanitize_recursive(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            sanitize_recursive(item, f"{path}[{i}]")

sanitize_recursive(sanitized)
```

### Step 2: Bulk sed pass across ALL text files

```bash
find "$HC" -type f \( -name '*.md' -o -name '*.sh' -o -name '*.py' \
  -o -name '*.yaml' -o -name '*.yml' -o -name '*.json' -o -name '*.txt' \
  -o -name '*.ts' -o -name '*.js' -o -name '*.cjs' -o -name '*.toml' \
  -o -name '*.cfg' -o -name '*.conf' \) | while read f; do
  sed -i \
    -e 's|/home/user/|/home/user/|g' \
    -e 's|64\.188\.64\.52|<YOUR_VPS_IP>|g' \
    -e 's|95\.24\.31\.191|<YOUR_IP>|g' \
    -e 's|10\.4\.213\.|10.0.0.|g' \
    -e 's|<YOUR_DEVICE_ID>|<PHONE_ID>|g' \
    -e 's|<YOUR_TELEGRAM_CHAT_ID>|<CHAT_ID>|g' \
    -e 's|<YOUR_HARDCODED_TOKEN>[a-zA-Z0-9]*|CHANGEME|g' \
    -e 's|sk-proj-[A-Za-z0-9_-]\{20,\}|CHANGEME|g' \
    -e 's|Bearer [A-Za-z0-9+/=_\.*-]\{8,\}|Bearer CHANGEME|g' \
    "$f"
done
```

### Step 3: .env.example generation from real .env

```python
with open(".env", "r") as f:
    lines = f.read().split("\n")

out = []
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        out.append(line)  # keep comments + blanks
    elif "=" in stripped:
        key = stripped.split("=", 1)[0]
        out.append(f"{key}=CHANGEME")  # preserve key name, blank value
    else:
        out.append(line)

with open(".env.example", "w") as f:
    f.write("\n".join(out))
```

### Step 4: PII verification grep loop (iterative fix)

**Critical:** The first sanitization pass typically leaves 3-5 residual matches
in skill reference files, .curator_state, and cypher files. Run a grep scan,
fix remaining matches, re-scan until 0.

```bash
# Scan (exclude binaries + PLAN.md + test-pii.sh which contains patterns by design)
grep -rlP '/home/user/|64\.188\.64\.52|95\.24\.31\.191|1003011121225|<YOUR_DEVICE_ID>' \
  "$V3" --exclude='*.tar.gz' --exclude='*.whl' --exclude='PLAN.md' --exclude='test-pii.sh'

# Fix each remaining file with sed, then re-scan
# Expected: 0 matches after fix pass
```

**Known residual locations after first pass:**
- `skills/.curator_state` — contains source paths
- `skills/mlops/neo4j-knowledge-graph/references/*.cypher` — contains /home/user/
- `skills/software-development/hermes-distribution-packaging/scripts/test-pii.sh` — contains PII patterns as TEST STRINGS (by design, not a leak)
- `skills/software-development/hermes-distribution-packaging/references/*.md` — session docs with IP/chat IDs

## start-backend.sh first-run flow

The V3 start-backend.sh automates first-run onboarding:

1. **Check Docker** — exit if not installed
2. **Generate .env** — copy `.env.example` → `.env`, append `API_SERVER_KEY=$(openssl rand -hex 32)`
3. **Load Docker image** — `docker load` if image not present (auto-arch)
4. **Copy hermes-core** — `cp -rL hermes-core/* ~/.hermes-portable/` (only if config.yaml not present)
5. **Clean stale locks** — `rm -rf logs/gateways/`
6. **Start gateway** — `docker run --network host` with HERMES_UID/GID
7. **Wait for health** — poll `/health` for up to 120s
8. **Start dashboard** — separate container with `--insecure --tui --no-open --skip-build`
9. **Deploy tui_gateway** — `tar pipe` to dashboard container (fixes 95% GUI hang)

## Exclusion checklist for hermes-core

Always exclude from portable distribution:

| Item | Reason |
|------|--------|
| `state.db` (698M) | Session database — personal data |
| `.env` (24.8K) | Real API keys |
| `.sudo_pass` | sudo password |
| `auth.json` | Auth tokens |
| `channel_directory.json` | Telegram chat IDs |
| `observer_queue.jsonl` | Personal observer state |
| `observations/` | Personal observation history |
| `cron/output/` | Personal cron execution results |
| `skills/.curator_backups/` | 3M+ of backup tarballs |
| `skills/pavel-environment/` | Machine-specific environment docs |
| `__pycache__/` | Python bytecode cache |
| `.git/` | Git metadata |
| `node_modules/` | NPM deps (reinstalled on target) |
| `.venv/` | Python virtualenv |

## Verification protocol

| Check | Command | Expected |
|-------|---------|----------|
| Script syntax | `bash -n <script>` | OK for all 6 scripts |
| exFAT line merge | `head -20 <script> \| cat -n` | No merged lines |
| PII scan | `grep -rlP '<patterns>'` | 0 matches |
| Secret files | `find -name '.sudo_pass' -o -name 'auth.json' ...` | 0 matches |
| GUI ELF arch | `file gui-*/Hermes` | Correct arch per dir |
| pip wheels | `ls pip-packages/*.whl \| wc -l` | 60 wheels |
| Total size | `du -sh` | ~2.9G |
