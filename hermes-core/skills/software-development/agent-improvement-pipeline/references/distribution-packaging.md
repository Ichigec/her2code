# Distributable Packaging — Sanitization Checklist

Built from the codemes_apk packaging session (2026-06-13). Use when asked to produce a distributable version of an agent project.

## Structure

```
dist/
├── README.md                    # Full documentation
├── SETUP.md                     # Step-by-step setup
├── SEQUENCE.md                  # Sequence diagrams (ASCII art)
├── opencode-plus/               # OpenCode+ config (sanitized)
│   ├── configs/*.json
│   ├── .env.example
│   └── *.sh
├── hermes/                      # Hermes config (sanitized)
│   ├── config.yaml
│   ├── .env.example
│   └── agents/*.md
├── plugins/                     # All plugin source + tests
├── databases/                   # Empty DBs + schema.sql
├── mcp/                         # MCP server source
├── voice/                       # Voice proxy
├── android/*.apk                # APK
├── docs/
│   ├── architecture/
│   ├── research/
│   ├── plans/
│   ├── system-analysis/
│   └── vulnerabilities.md
└── skills/
```

## Sanitization Checklist

### 1. Secrets (absolute — zero tolerance)
- [ ] `grep -rn 'sk-[a-zA-Z0-9]\{20,\}' dist/` → 0 real matches (test fixtures with `sk-fake`, `sk-local`, `sk-abc...` are OK)
- [ ] All `.env` files replaced with `.env.example` — fake values only
- [ ] API keys: `sk-your-key-here`, `sk-fake...xxxx`, `***`
- [ ] Passwords: `changeme`, `your-password-here`
- [ ] Tokens: `your-bot-token-here`, `***`

### 2. Paths (all real paths → variables)
- [ ] `/home/<user>` → `${HOME}`
- [ ] Project paths → relative or `${HOME}/dev/<project>`
- [ ] Exceptions: research/archival docs may keep original paths as historical context

### 3. Databases (empty, schema only)
- [ ] SQLite: `.db` files contain only `CREATE TABLE` + indexes, zero data rows
- [ ] Neo4j: no dump needed (user creates fresh)
- [ ] Schema `.sql` files provided alongside empty `.db` files

### 4. Models (single provider, no paid APIs)
- [ ] OpenCode+ config: remove all paid model providers (DeepSeek, OpenAI, Anthropic)
- [ ] Keep only local/LiteLLM models (qwen, llama, gemma via llama.cpp or LM Studio)
- [ ] Default model: local inference path

### 5. Code (clean)
- [ ] No `__pycache__/` directories
- [ ] No `*.pyc` files
- [ ] No `.git/` directories
- [ ] No `node_modules/`
- [ ] No real `.env` files (only `.env.example`)

### 6. Documentation (complete)
- [ ] README.md: what, why, architecture diagram, usage
- [ ] SETUP.md: dependencies, install steps, health checks
- [ ] SEQUENCE.md: key flows as ASCII sequence diagrams
- [ ] Architecture docs from `docs/architecture/`

### 7. Verification commands
```bash
# Secrets check
grep -rn 'sk-[a-zA-Z0-9]\{20,\}' dist/ | grep -v 'sk-fake\|sk-local\|sk-your\|sk-test\|sk-example\|sk-abc\|sk-myk'

# Paths check
grep -rn '/home/' dist/ --include='*.yaml' --include='*.json' --include='*.env' --include='*.sh' --include='*.py' | grep -v '.git\|Binary\|cache\|__pycache__\|research\|historical'

# Size check
du -sh dist/

# File count
find dist -type f | wc -l
```

## Model: qwen3.6-heretic via OpenCode+ / LiteLLM

For distributions using OpenCode+ with local models:
- Provider: `litellm` with `baseURL: http://127.0.0.1:4000/v1`
- apiKey: `sk-local` (LiteLLM default)
- Models: `qwen3.6-35b-heretic` (llama.cpp), `tvall43-qwen3.6-35b-a3b-heretic` (LM Studio)
- Remove: all deepseek, openai, anthropic model entries
