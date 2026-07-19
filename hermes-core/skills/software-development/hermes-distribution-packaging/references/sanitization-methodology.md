# Hermes Stack Sanitization Methodology

> Reference for `hermes-distribution-packaging`.
> Learned during `<SESSION_ID>` — full 10-phase cycle sanitizing Hermes for GitHub publication.
> Result: 81MB, 3197 files, 0 PII findings.

## PII Discovery: What to look for

Run these grep patterns against the full `~/.hermes/` tree (and related dirs) to
find all personal data BEFORE sanitization:

### API Keys & Tokens

```bash
# OpenAI / Anthropic / DeepSeek keys (real, not test fixtures)
grep -rP 'sk-[a-zA-Z0-9_-]{30,}' ~/.hermes/ ~/dev/Opencode/ ~/cursor/ -l

# Bearer tokens / API server keys
grep -rP 'Bearer [A-Za-z0-9+/=_-]{20,}' ~/.hermes/ -l

# env var references (find which providers are configured)
grep -rE '(DEEPSEEK|OPENAI|ANTHROPIC|KIMI|BWS)_API_KEY' ~/.hermes/ -l

# Sudo password files
find ~/.hermes/ -name '.sudo_pass' -o -name '*.pass'
```

### IP Addresses & Hosts

```bash
# VPS / Public / Local IPs
grep -rP '\b(64\.188\.|95\.24\.|192\.168\.|10\.4\.)\d{1,3}\.\d{1,3}\b' ~/.hermes/ -l

# Tunnel URLs (lhr.life, trycloudflare, serveo)
grep -rP '[a-z0-9]+\.lhr\.life' ~/.hermes/ -l
grep -rP '[a-z0-9-]+\.trycloudflare\.com' ~/.hermes/ -l

# Hostnames and domains
grep -rP 'vpn\d?\.\w+\.\w+' ~/.hermes/ -l  # VPS hostnames
```

### Telegram / Messaging IDs

```bash
# Chat IDs (supergroups have negative IDs starting with -100)
grep -rP '\-100\d{7,}' ~/.hermes/ -l

# Direct message IDs (positive 9-digit)
grep -rP '\b\d{9}\b' ~/.hermes/cron/ ~/.hermes/skills/ -l

# Bot usernames
grep -rP '@\w+bot\b' ~/.hermes/ -l
```

### Personal Names & Paths

```bash
# Home directory paths
grep -r '/home/\w+/' ~/.hermes/ -l

# Git identity
grep -rE '(name\s*=\s*[A-Z]\w+|email\s*=\s*\w+@)' ~/.gitconfig 2>/dev/null

# GitHub usernames (in skills, memory, plans)
grep -rP 'github\.com/\w+/' ~/.hermes/skills/ -l

# Phone identifiers
grep -rP '\b[A-Z0-9]{16}\b' ~/.hermes/ -l  # Device PIDs
```

### Databases & Session Data

```bash
# Check DB sizes and row counts
for db in ~/.hermes/*.db; do
  echo "$db: $(du -sh "$db" | cut -f1)"
  sqlite3 "$db" "SELECT name FROM sqlite_master WHERE type='table'" 2>/dev/null
done

# Session dumps
find ~/.hermes/sessions/ -name '*.json' | wc -l
du -sh ~/.hermes/sessions/ 2>/dev/null

# Log files (may contain API keys in error messages)
find ~/.hermes/logs/ -name '*.log*' | wc -l
du -sh ~/.hermes/logs/ 2>/dev/null
```

## Sanitization: Replacement Table

| Category | Pattern | Replacement |
|----------|---------|-------------|
| OpenAI key | `sk-proj-[A-Za-z0-9_-]{20,}` | `<YOUR_OPENAI_KEY>` |
| API Server key | `Bearer [A-Za-z0-9+/=_-]{20,}` | `Bearer <YOUR_API_SERVER_KEY>` |
| Home paths | `/home/\w+/` | `/home/user/` |
| VPS IP | `64\.188\.64\.52` | `<YOUR_VPS_IP>` |
| Public IP | `95\.24\.31\.191` | `<YOUR_PUBLIC_IP>` |
| Local IP | `192\.168\.0\.\d+` | `<YOUR_LOCAL_IP>` |
| Router IP | `192\.168\.0\.1` | `<YOUR_ROUTER_IP>` |
| Phone subnet | `10\.4\.\d+\.\d+` | `<YOUR_PHONE_IP>` |
| Telegram chat | `<YOUR_TELEGRAM_CHAT_ID>` | `<YOUR_CHAT_ID>` |
| Telegram DM | `396480232` | `<YOUR_USER_ID>` |
| Telegram bot | `@Heracklbot` | `<YOUR_BOT_USERNAME>` |
| Telegram channel | `@raicomml` | `<YOUR_CHANNEL>` |
| Git name | `name\s*=\s*Pavel` | `name = User` |
| Git email | `\w+@jetson\.local` | `user@localhost` |
| GitHub user | `<GITHUB_USER>` | `<YOUR_GITHUB_USER>` |
| Phone ID | `<YOUR_DEVICE_ID>` | `<YOUR_PHONE_ID>` |
| VLESS UUID | `3957c617-0330-4453-bbe2-011a7cdfa0ad` | `<YOUR_VLESS_UUID>` |
| VPS hostname | `vpn1\.play2go\.cloud` | `<YOUR_VPS_HOSTNAME>` |
| WiFi SSID | `agent_builder_2g` | `<YOUR_WIFI_SSID>` |
| Tunnel URLs | `[a-z0-9]+\.lhr\.life` | `<YOUR_TUNNEL_URL>` |
| Sudo password | `03042026` | `<YOUR_SUDO_PASSWORD>` |
| Systemd user | `User=pavel` | `User=user` |

## What to DELETE (never copy)

| Item | Reason |
|------|--------|
| `~/.hermes/.env` | Credential store — blocked by defense-in-depth |
| `~/.hermes/auth.json` | Authentication data |
| `~/.ssh/id_ed25519*` | SSH private/public keys |
| `~/.ssh/known_hosts` | Host fingerprints with IPs |
| `~/.gitconfig` | Git identity |
| `~/.hermes/bin/` | External binaries (cloudflared, tirith, uv) |
| `~/.hermes/state.db` data | Session history (keep schema only) |
| `~/.hermes/sessions/*.json` | Session dumps |
| `~/.hermes/logs/*.log` | Logs (may leak keys in error messages) |
| `~/.hermes/plans/*.md` | Personal project plans |
| `~/.hermes/memories/MEMORY.md` | Agent memory (replace with template) |
| `~/.hermes/memories/USER.md` | User profile (replace with template) |
| `pavel-environment/` skill | Personal machine specs, Gitea, VPS |
| `sing-box-vpn-setup.md` | VLESS UUID, IPs |
| `.sudo_pass` | Sudo password |
| `*.apk` files | Binary artifacts |
| `apps/desktop/release/` | Built Electron binary (280MB) |
| `apps/desktop/dist/` | Built JS bundles |
| `tests/` directory | Test fixtures with fake API keys |
| `website/` directory | Documentation site |
| `opencode_claw/.compactor/` | Compactor logs with paths |

## Exclude rules for sanitize.py

```python
EXCLUDE_DIRS = {
    'venv', '__pycache__', '.git', 'node_modules', 'build', '.gradle',
    'logs', 'sessions', 'memories', 'plans', 'bin', '.ssh', 'tests',
    'website', 'release', 'dist'
}

EXCLUDE_FILES = {
    '.env', 'auth.json', '.sudo_pass', 'id_ed25519', 'id_ed25519.pub',
    'known_hosts', '*.apk', '*.pyc', '*.AppImage', '*.db'
}
```

## Verification checklist

After sanitization, all of these must return 0 hits:

```bash
gitleaks detect --no-git -v -s her2code/
grep -r '/home/\w+/' her2code/ -l          # → empty
grep -rP 'sk-[a-zA-Z0-9_-]{30,}' her2code/ -l   # → empty (long keys)
grep -r '64\.188\.64\.52' her2code/ -l     # → empty
grep -r '<YOUR_DEVICE_ID>' her2code/ -l    # → empty
grep -r '\<YOUR_TELEGRAM_CHAT_ID>' her2code/ -l     # → empty
grep -r '3957c617' her2code/ -l            # → empty
grep -r '\w+@jetson\.local' her2code/ -l   # → empty
```

## her2code/ target structure

The final sanitized output should match this layout:

```
her2code/                    ← ≤100MB, clean
├── hermes-agent/            ← Core Python code (no venv, tests, release)
├── opencode-android/        ← Android client sources (no .gradle, build, APK)
├── opencode-plus/           ← OpenCode+ scripts + configs (no .env with keys)
├── config/                  ← User extensions
│   ├── agents/              ← Role definitions (14 .md)
│   ├── skills/              ← Skills (NO pavel-environment)
│   ├── hooks/               ← Pre/post hooks
│   ├── scripts/             ← Utility scripts
│   ├── plugins/             ← claw-neo4j, hermes-opencode
│   ├── mcp/education-graph/  ← Education + Codebase Graph MCP (18 files)
│   ├── claw-agent/           ← Claw + Composter agents (26 files, no .compactor data)
│   ├── cron/jobs.json.example
│   ├── .env.example
│   ├── config.yaml.example
│   └── compose.neo4j.yml
├── docs/architecture/       ← PlantUML diagrams + COMPONENTS.md
├── README.md                ← Quick Start (≤10 commands)
├── SANITIZATION_LOG.md      ← What was removed and why
├── sanitize.py              ← Reproducible sanitization script
├── sanitize-config.yaml     ← Declarative replacement config
├── Makefile                 ← make sanitize / verify / clean
└── LICENSE                  ← MIT
```

## Key lessons

1. **Size killers**: `apps/desktop/release/` (Electron binary, 280MB) and
   `state.db` (535MB session history) are the two biggest items to exclude.
   The core code alone is ~10MB.

2. **False positives**: API key patterns (`sk-ant-...`) in sanitize scripts
   and documentation are NOT real keys — they're descriptions of the format.
   But they trigger gitleaks. Either exclude docs from scanning or use
   broken patterns (`sk-ant-C...EME`) in documentation.

3. **Iteration limits**: Subagents hit tool-call limits (~56) when doing
   large-scale file operations. For sanitization of 18K files, run the
   sanitize.py script directly from the orchestrator terminal, not through
   a subagent.

4. **Documentation PII**: `SANITIZATION_LOG.md` and `README.md` will
   contain descriptions of what was removed — that's by design and
   acceptable. The actual PII values should only appear in the sanitization
   config/script, not in published documentation.

5. **Partially-hidden keys evade regex**: Keys written as `Bearer <YOUR_HARDCODED_TOKEN>...`
   (with ellipsis `...` or asterisks `***`) will NOT match `[A-Za-z0-9]{20,}`
   patterns. Use broader patterns for partial keys:
   ```bash
   grep -rP 'Bearer [A-Za-z0-9+/=_-]{5,}' . -l  # catches partial tokens
   sed -i 's|Bearer [A-Za-z0-9+/=_.*-]\{5,\}|Bearer <YOUR_KEY>|g'
   ```

6. **Self-sanitization gap**: The sanitizer's own files (`sanitize-config.yaml`,
   `SANITIZATION_LOG.md`, `Makefile`) are NOT processed by the sanitizer script.
   They must be cleaned separately with `sed` after the main sanitization run.
   Common leaks: hostname in config, PII values in log table, paths in Makefile.

7. **Skill reference files contain example tokens**: Skills like
   `hermes-gateway-setup.md`, `dual-backend-architecture.md` include code examples
   with `Authorization: Bearer <YOUR_HARDCODED_TOKEN>...` — these are documentation examples, not
   active credentials, but must still be replaced before publishing.

8. **trycloudflare.com is NOT PII**: The domain `trycloudflare.com` appears in
   skills as a service reference ("blocked by Yandex"), not as user-specific
   tunnel URLs. Only replace CONCRETE subdomains (`abc123.trycloudflare.com`),
   not the bare domain name.

## Second-pass additions: education graph + claw agent

After the initial sanitization, verify that ALL functional components are
included — not just the core Hermes agent. The user may need to remind you.

### Education Graph (`graph_tool/`)

Source: `~/cursor/first/graph_tool/` (excluded from `~/.hermes/` scope)

Copy these files WITHOUT `venv/`, `node_modules/`, or trained graph data:

```
config/mcp/education-graph/
├── mcp/
│   ├── education-server.mjs    # Neo4j MCP: education entities
│   ├── codebase-server.mjs     # Neo4j MCP: codebase structure
│   ├── mcp-server.mjs          # Generic MCP bridge
│   ├── neo4j_client.js         # Neo4j driver
│   ├── search.js               # Hybrid search endpoint
│   ├── rrf.js                  # Reciprocal Rank Fusion
│   └── package.json
├── python/
│   ├── graph/
│   │   ├── init_education.py   # Graph initialization
│   │   └── education_graph.cypher  # Neo4j schema
│   ├── education/
│   │   ├── education_agent.py  # Education agent logic
│   │   ├── security_validator.py
│   │   └── triple_extractor.py
│   ├── hybrid_searcher.py      # Vector + keyword search
│   └── requirements.txt
├── README.md
└── ANALYSIS.md
```

### Claw Agent (`opencode_claw/`)

Source: `~/cursor/opencode+/opencode_claw/`

Copy documentation, schemas, and diagrams — WITHOUT `.compactor/` data
(`log.jsonl`, `registry/`, `sessions/`, `summaries/`):

```
config/claw-agent/
├── AGENTS.md                   # 33KB compactor runbook (5-axis taxonomy)
├── Knowledge.md, PLAN.md       # Companion docs
├── schemas/                    # 8 JSON validation schemas
├── diagrams/                   # 10 PlantUML diagrams
└── .compactor/                 # Empty template structure
    ├── README.md
    ├── drafts/   (empty)
    ├── knowledge/ (empty)
    ├── registry/  (empty)
    ├── sessions/  (empty)
    └── summaries/ (empty)
```

### Claw AGENTS.md path sanitization

The claw `AGENTS.md` hardcodes paths like `/home/user/cursor/first/` in
scan scope documentation and code examples. All must be replaced:

```bash
sed -i \
  -e 's|/home/user/cursor/first/|/home/user/projects/|g' \
  -e 's|/home/user/|/home/user/|g' \
  config/claw-agent/AGENTS.md
```

## Complete verification (22 patterns)

After sanitization, ALL of these must return 0 files (excluding `.git/`,
`__pycache__/`, `*.png`, `*.jpg`):

```bash
# Paths
grep -rPl '/home/\w+/' . | grep -v '.git/' | grep -v __pycache__
# API keys (real, long)
grep -rPl 'sk-[a-zA-Z0-9_-]{30,}' . | grep -v '.git/'
# API keys (partial with ellipsis)
grep -rPl 'Bearer [A-Za-z0-9+/=_-]{5,}' . | grep -v '.git/'
# IPs
grep -rPl '64\.188\.64\.52|95\.24\.31\.191|95\.24\.32\.220|192\.168\.0\.(48|1)' .
# Phone IDs
grep -rPl '<YOUR_DEVICE_ID>|10\.4\.213\.' .
# Telegram
grep -rPl '\<YOUR_TELEGRAM_CHAT_ID>|396480232|@Heracklbot|@raicomml' .
# VLESS UUID / hostnames / WiFi
grep -rPl '3957c617-0330|vpn1\.play2go\.cloud|<YOUR_HOSTNAME>|agent_builder_2g' .
# Email / GitHub / sudo
grep -rPl 'pavel@jetson\.local|<GITHUB_USER>|03042026' .
# Tunnel URLs (concrete subdomains, not bare service domain)
grep -rPl '[a-z0-9]{8,}\.lhr\.life|[a-z0-9-]{8,}\.trycloudflare\.com' .
```
