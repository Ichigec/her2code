---
name: secure-coding
description: "Secure-by-default while writing code: OWASP/CWE patterns + checkpoint self-audit."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [security, secure-coding, owasp, cwe, checkpoint, self-audit, defensive]
    related_skills: [sast-audit, sast-setup, requesting-code-review, test-driven-development]
---

# Secure Coding — secure-by-default + checkpoint self-audit

Write code that is safe the first time, and re-check it on every logical
milestone. This skill is the *while-you-write* half of the security pipeline;
`sast-audit` is the *before-you-commit* gate.

**Core principle:** security is cheapest at write-time. A parameterized query
costs nothing to write and everything to retrofit after a breach.

## When to Use

- During the **Implement** step of any feature that touches untrusted input,
  auth, secrets, files, subprocesses, network calls, serialization, or SQL.
- At every **checkpoint** — a logical milestone (a function/module done, before
  moving to the next unit, before a commit). Run the delta self-audit below.

**Skip for:** pure docs, comments, formatting-only changes.

## Secure-by-default checklist (OWASP Top 10 / CWE Top 25)

Keep these in mind as you type — not as an afterthought:

- **Injection (CWE-89/78/77/22):** SQL, OS command, path. Never concatenate
  untrusted input into a query, shell line, or filesystem path.
- **Authn / Authz (CWE-287/862):** verify identity and check authorization on
  every privileged action — not just at the UI layer. Deny by default.
- **Secrets in code (CWE-798):** no hardcoded API keys, passwords, tokens.
  Read from environment or a secret manager.
- **Cryptography (CWE-327/328/916):** use vetted libraries and modern
  algorithms. No MD5/SHA1 for security, no homemade crypto, no static IVs,
  use a CSPRNG (`secrets`, `crypto.randomBytes`), bcrypt/argon2 for passwords.
- **Insecure deserialization (CWE-502):** never `pickle.loads`, `yaml.load`
  (use `safe_load`), or `eval`/`exec` on untrusted data.
- **SSRF (CWE-918):** validate/allowlist outbound URLs built from user input.
- **XXE (CWE-611):** disable external entity resolution in XML parsers.
- **Path traversal (CWE-22):** normalize and confirm resolved paths stay inside
  an allowed base directory before reading/writing.
- **Race conditions / TOCTOU (CWE-367):** don't check-then-use on shared state;
  use atomic operations and proper locking.
- **Insecure defaults (CWE-1188):** ship closed — TLS verification on, debug
  off, permissive CORS/`0.0.0.0` binds only when intended.
- **Sensitive data in logs (CWE-532):** never log secrets, tokens, full PII, or
  raw request bodies.
- **Missing input validation (CWE-20):** validate type, length, range, and
  format at the trust boundary; prefer allowlists over denylists.
- **Error handling (CWE-755):** handle I/O / network / DB failures; fail closed,
  don't leak stack traces or internal detail to users.

## Safe patterns by language

### Python
```python
# SQL — parameterized, never f-string
cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))   # good
cur.execute(f"SELECT * FROM users WHERE id = {user_id}")        # BAD

# Subprocess — arg list, never shell=True with input
subprocess.run(["git", "checkout", branch], check=True)         # good
subprocess.run(f"git checkout {branch}", shell=True)            # BAD

# Secrets — env, not literals
API_KEY = os.environ["API_KEY"]                                 # good
token = secrets.token_urlsafe(32)                               # CSPRNG

# Deserialization — safe loaders only
data = json.loads(payload)                                      # good
data = yaml.safe_load(payload)                                  # good
data = pickle.loads(payload)                                    # BAD

# Path traversal — confine to a base dir
base = Path("/srv/data").resolve()
target = (base / user_path).resolve()
if not target.is_relative_to(base):
    raise ValueError("path escapes base")
```

### JavaScript / TypeScript
```javascript
// XSS — textContent, never innerHTML with user data
el.textContent = userInput;                                     // good
el.innerHTML = userInput;                                       // BAD

// SQL — parameterized
db.query("SELECT * FROM u WHERE id = $1", [id]);                // good

// Command — execFile with args, never string exec/template
execFile("convert", [src, dst]);                                // good
exec(`convert ${src} ${dst}`);                                  // BAD

// Secrets — env
const key = process.env.API_KEY;                                // good
```

### Shell
```bash
# Quote every expansion; avoid eval
cp -- "$src" "$dst"        # good
rm -rf $dir                # BAD (unquoted, no --)
eval "$user_input"         # BAD
```

### Docker
```dockerfile
# Pin versions, drop root, no secrets in layers
FROM python:3.12-slim
RUN useradd -m app
USER app                   # don't run as root
# Pass secrets at runtime (env/secret mount), never COPY them in
```

## Checkpoint discipline (the interim audit)

On every logical milestone — before you move to the next unit, and always
before a commit — do a fast self-audit of just the delta you wrote:

1. **Get the delta:** `git diff` (unstaged) or `git diff --cached` (staged).
2. **Scan added lines** against the checklist above. Focus on `^+` lines only —
   you own what you just added.
3. **Fix in place** any issue you spot before continuing. Don't accumulate a
   backlog of "I'll secure it later."
4. **Note assumptions** (e.g. "input already validated upstream") so the final
   `sast-audit` reviewer has context.

This is intentionally lightweight and discipline-based (not a per-edit hook) to
avoid noise. The heavier scanner pass and the independent reviewer happen once,
at the end, via `sast-audit`. Checkpoint audits catch most issues early; the
SAST gate catches what discipline missed.

## Red flags — never ship these

- String-built SQL / shell / paths from untrusted input
- `shell=True`, `os.system`, `eval`/`exec`, `pickle.loads` on external data
- Hardcoded credentials or tokens (even "temporary" ones)
- Disabled TLS verification (`verify=False`, `rejectUnauthorized: false`)
- `innerHTML` / `dangerouslySetInnerHTML` with user content
- Secrets or full PII written to logs

## Integration with other skills

- **sast-audit** — the mandatory pre-commit gate. Checkpoint audits are your
  first line; `sast-audit` runs scanners + an independent reviewer last.
- **sast-setup** — installs the scanners `sast-audit` prefers. Run once.
- **requesting-code-review** — broader quality + spec review; its Step 2
  security grep overlaps with the checkpoint audit here.
- **test-driven-development** — write tests for the security-relevant paths
  (rejected malicious input, authz denials) alongside the happy path.
