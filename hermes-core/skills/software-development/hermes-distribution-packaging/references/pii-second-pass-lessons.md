# PII Second Pass — Lessons from her2code Cycle

> Key finding: first sanitization pass misses 10-15% of PII.
> Always run a SECOND pass with explicit pattern search.

## PII missed in first pass (her2code, 2026-06-19)

| Category | Items missed | Root cause |
|----------|:-----------:|------------|
| Username (`pavel`) | 7 places in 4 files | Regex only matched `pavel_`, not standalone |
| API key (`<YOUR_HARDCODED_TOKEN>...`) | 1 in .kt file | Sanitizer didn't scan .kt files |
| PID | 3 in .puml files | .puml not in text_file_extensions |
| `changeme` runtime defaults | 5+ in compose/scripts | Only documented, not fixed in code |

## Second-pass verification commands

```bash
# Check for remaining usernames
grep -rn "pavel" --include="*.service" --include="*.sh" --include="*.md" \
  --include="*.py" --include="*.kt" . | grep -v "changeme\|/home/user\|<YOUR_"

# Check for API key patterns
grep -rPn 'sk-[a-zA-Z0-9_-]{20,}|[A-Za-z0-9+/=]{32,}' --include="*.kt" --include="*.py" .

# Check for real IPs
grep -rPn '64\.188\.64\.52|95\.24\.31\.191|10\.4\.\d+\.\d+' .

# Check for PID in non-.md files
grep -rn "pavel_202" --include="*.puml" --include="*.plantuml" .
```

## Security agent pattern (recommended)

For full cycle distributions, spawn 2 security agents BEFORE Phase 1:
- **Security Agent 1 (PII Monitor)**: scans git diff after every phase
- **Security Agent 2 (SAST Auditor)**: reviews all artifacts for security anti-patterns
