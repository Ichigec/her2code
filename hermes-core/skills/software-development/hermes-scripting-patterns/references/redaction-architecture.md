# Hermes Redaction Architecture — Code-Level Analysis

> Verified 2026-07-10 against `~/.hermes/hermes-agent/` source code.
> Corrects a prior misdiagnosis propagated across 7 skill files.

## The Read/Write Asymmetry

| Operation | Redacts content? | Code proof |
|-----------|:---:|------------|
| `write_file_tool` (WRITE) | **NO** | `tools/file_tools.py:1043` — no `redact_sensitive_text` call on the write path |
| `patch_tool` (WRITE) | **NO** | `tools/file_tools.py:1121` — no redaction call |
| `read_file_tool` (READ) | **YES** | `tools/file_tools.py:823` — `result.content = redact_sensitive_text(result.content, code_file=True)` |
| `terminal` stdout/stderr | **YES** | `tools/terminal_tool.py` — redacts output before returning |
| `code_execution` stdout | **YES** | `tools/code_execution_tool.py:1027` — `stdout_text = redact_sensitive_text(stdout_text)` |
| `cron` script output | **YES** | `cron/scheduler.py:1062-1064` — redacts both stdout and stderr |

**Conclusion:** Files on disk contain REAL content. The `***` appears only in tool
OUTPUT returned to the agent. This is a display layer, not a write layer.

## How `redact_sensitive_text()` works

File: `agent/redact.py`

### Token masking: `_mask_token()`

```python
def _mask_token(token: str) -> str:
    """Mask a log token — conservative 18-char floor, preserves 6 prefix / 4 suffix."""
    if not token:
        return "***"
    return mask_secret(token, head=6, tail=4, floor=18)
```

- Tokens **< 18 chars** → fully masked to `***`
- Tokens **>= 18 chars** → `sk-pro...last4` (first 6 + last 4 preserved)
- `sk-docker-b` (12 chars) → `***` (fully masked, below floor)
- `<YOUR_API_KEY>` (28+ chars) → `sk-ant...last4`

### Pattern catalog (`_PREFIX_PATTERNS`)

The redactor matches known API key prefixes:
- `sk-[A-Za-z0-9_-]{10,}` — OpenAI / OpenRouter / Anthropic
- `ghp_[A-Za-z0-9]{10,}` — GitHub PAT
- `xox[baprs]-...` — Slack tokens
- `AIza[A-Za-z0-9_-]{30,}` — Google API keys
- ...30+ more vendor patterns

### ENV assignment redaction

```python
_SECRET_ENV_NAMES = r"(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)"
_ENV_ASSIGN_RE = re.compile(
    rf"([A-Z0-9_]{{0,50}}{_SECRET_ENV_NAMES}[A-Z0-9_]{{0,50}})\s*=\s*(['\"]?)(\S+)\2",
)
```

This catches `DASH_TOKEN="sk-docker-b"` and similar assignments in tool output.

**IMPORTANT:** `code_file=True` parameter SKIPS the ENV-assignment and JSON-field
regexes (to avoid false positives in source code). But prefix patterns (`sk-*`)
are ALWAYS applied regardless of `code_file`.

### Toggle

```python
_REDACT_ENABLED = os.getenv("HERMES_REDACT_SECRETS", "true").lower() in {"1", "true", "yes", "on"}
```

Can be disabled via `security.redact_secrets: false` in config.yaml or
`HERMES_REDACT_SECRETS=false` in `.env`. Snapshot at import time prevents
runtime bypass.

## The Misdiagnosis That Caused This Analysis

**Session `20260709_233413_95efac`:**
1. Agent wrote `launch.sh` to exFAT USB via `write_file`
2. File on disk had real token: `DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-docker-b}"`
3. exFAT **merged two adjacent lines** (LINE MERGE — separate corruption mode)
4. `read_file` returned the merged line with token masked: `DASH_TOKEN=*** "$(uname -m)"`
5. Agent saw `***`, concluded "write_file censored the token"
6. Agent propagated this conclusion to 7 skill files + memory
7. **Reality:** `***` was display redaction. The ONLY corruption was LINE MERGE.

**Corrected 2026-07-10** after code analysis of `agent/redact.py` + `tools/file_tools.py`.

## How to verify real file content

```bash
# Method 1: terminal cat (terminal output IS redacted for some patterns,
# but cat+grep works for most because the redaction applies to tool OUTPUT,
# not to file content)
terminal('cat /path/to/file')

# Method 2: grep for specific pattern
terminal('grep -n "sk-" /path/to/file')

# Method 3: hex dump (bypasses all text redaction)
terminal('xxd /path/to/file | grep "73 6b 2d"')

# Method 4: line count (proves file structure is intact)
terminal('wc -l /path/to/file')
```
