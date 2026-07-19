# PII Blind Spots — Second-Pass Sanitization (2026-06-20)

During the her2code security audit (PID: <SESSION_ID>), 2 security agents
found PII that the first sanitization pass missed.

## Blind Spot 1: Systemd Service Files

**Files affected:** `opencode-plus/systemd/opencode-plus.service`, `opencode-plus/systemd/README.md`

**Missed patterns:**
```
Group=pavel          → Group=user
Environment=USER=pavel → Environment=USER=user
Environment=LOGNAME=pavel → Environment=LOGNAME=user
от пользователя pavel → от пользователя user
sudo -u pavel bash   → sudo -u user bash
```

**Root cause:** `sanitize-config.yaml` Category 4 only replaced `\bpavel_` (pavel+underscore), not standalone `pavel`. The systemd service had `User=pavel` → `User=user` fixed on line 14 but `Group`, `USER`, `LOGNAME` were missed.

**Verification regex:**
```bash
grep -rn '\bpavel\b' --include='*.service' --include='*.sh' --include='*.md' . | grep -v '/home/user\|changeme\|<YOUR_\|---'
```

## Blind Spot 2: PlantUML Diagrams

**Files affected:** `docs/architecture/*.puml`

**Missed pattern:**
```
' PID: <SESSION_ID> → ' PID: her2code
```

**Root cause:** `sanitize-config.yaml` Category 12 only targets `.md` files. `.puml` is not in `text_file_extensions`.

**Verification regex:**
```bash
grep -rn 'PID:.*pavel' --include='*.puml' .
```

## Blind Spot 3: Android Kotlin Source

**File affected:** `opencode-android/app/src/main/java/com/hermes/gui/data/settings/SettingsDataStore.kt:32`

**Missed pattern:**
```kotlin
const val DEFAULT_API_KEY = "<YOUR_HARDCODED_TOKEN>"
```
→ `const val DEFAULT_API_KEY = "***"`

**Severity:** CRITICAL — real API token baked into compiled APK.

**Root cause:** Android source is binary-incompatible with regex sanitizers. Must be manually reviewed.

## Blind Spot 4: Python Runtime Defaults

**Files affected:** Multiple in `config/scripts/`, `config/mcp/`, `infra/`

**Missed pattern:**
```python
auth=("neo4j", "changeme")         → auth=("neo4j", os.getenv("NEO4J_PASSWORD", ""))
NEO4J_PASSWORD:?Set NEO4J_PASSWORD           → NEO4J_PASSWORD:?Set NEO4J_PASSWORD
```

**Severity:** CRITICAL — well-known default password if user deploys without overriding.

## Blind Spot 5: UID Exposure

**File affected:** `opencode-plus/systemd/opencode-plus.service:22`

**Missed pattern:**
```
XDG_RUNTIME_DIR=/run/user/1000
```
UID 1000 is the first non-root user on most Linux systems.

## Verification Checklist (Post-Sanitization)

```bash
# 1. API keys (MUST return 0)
grep -rP 'sk-proj-[A-Za-z0-9_-]{30,}' her2code/
grep -rP 'sk-ant-api03-[A-Za-z0-9_-]{30,}' her2code/
grep -rP 'Bearer <YOUR_HARDCODED_TOKEN>' her2code/

# 2. Real IPs (MUST return 0)
grep -rP '64\.188\.64\.52|95\.24\.31\.191' her2code/

# 3. Username in non-documentation files (MUST return 0)
grep -rn '\bpavel\b' her2code/ --include='*.service' --include='*.sh' | grep -v '/home/user\|#'

# 4. Runtime defaults (MUST use :? not :-)
grep -rn ':-changeme' her2code/ --include='*.yml' --include='*.yaml' --include='*.py'

# 5. PID in non-markdown files
grep -rn 'pavel_20260619' her2code/ --include='*.puml'
```
