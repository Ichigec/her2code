# Git Deployment Workflow — Sanitization + Push to GitHub

> Tested 2026-06-22 on her2code project.

## Pre-push checklist

Run these BEFORE committing:

### 1. Scan for personal data

```bash
cd her2code/

# API keys (any sk-... pattern longer than 20 chars)
grep -rP "sk-[a-zA-Z0-9]{20,}" --include="*.md" --include="*.yaml" --include="*.yml" --include="*.sh" . | grep -v "sk-local\|sk-xxx\|placeholder\|CHANGEME"

# IP addresses (exclude localhost, 0.0.0.0, 255.255)
grep -rE "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" --include="*.md" --include="*.yaml" . | grep -v "127.0.0.1\|0.0.0.0\|localhost\|255.255"

# Personal paths
grep -r "/home/\w+" --include="*.md" --include="*.yaml" --include="*.sh" . | grep -v ".git/\|hermes-agent/"
```

### 2. Sanitize findings

Each finding:
```bash
# API keys → replace with ***
sed -i 's/sk-proj-[A-Za-z0-9]*/***/g' <file>

# Paths → use ~ instead of /home/user
sed -i 's|/home/\w+|~|g' <file>

# PIDs → replace with placeholder
sed -i 's/\w+_\d{8}_\d{6}/SANITIZED_PID/g' <file>

# VPS IPs → replace with VPS_IP
sed -i 's/64\.188\.\d+\.\d+/VPS_IP/g' <file>
```

### 3. Remove sanitization artifacts

```bash
rm -f sanitize.py sanitize-config.yaml SANITIZATION_LOG.md Makefile
rm -f "hermes@0.15.1" node sanitized-re  # placeholder files
```

### 4. Update .gitignore

```bash
cat >> .gitignore << 'EOF'
# Never commit
.env

# Local-only directories
opencode-android/
opencode-plus/
db/
infra/

# Obsolete files
status-proxy.py
EOF
```

### 5. Fix git submodule (if hermes-agent is tracked as submodule)

```bash
# If hermes-agent was added as plain directory, convert to submodule:
git rm --cached hermes-agent
git submodule add https://github.com/nousresearch/hermes-agent.git hermes-agent
```

### 6. Commit

```bash
git add -A
git commit -m "Cleanup: sanitize personal data, add docs, fix Docker GUI"
```

### 7. Push

```bash
# If repo exists on GitHub:
git remote add origin git@github.com:<user>/her2code.git
git push -u origin master

# If repo doesn't exist — create it first on GitHub, then push
```

## Common pitfalls

| Pitfall | Fix |
|---------|-----|
| Real API keys in skills/*.md | Check `config/skills/` — skills imported from host may contain real keys |
| `sk-proj-...Cr8A` in docs | These match `sk-[a-z]+` patterns. Replace with `***` |
| `/home/user` in scripts | Use `$HOME` or `~` |
| PID in docs | Replace with `SANITIZED_PID` |
| `changeme` passwords | Fine to keep — documented default |
| `hermes-agent` not as submodule | Convert via `git submodule add` |
