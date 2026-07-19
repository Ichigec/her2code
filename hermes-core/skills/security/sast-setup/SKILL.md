---
name: sast-setup
description: "Install/verify SAST scanners (semgrep, bandit, pip-audit, gitleaks) — idempotent."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [security, sast, setup, install, semgrep, bandit, gitleaks, pip-audit]
    related_skills: [sast-audit, secure-coding]
---

# SAST Setup — install the security scanners

One-time, idempotent setup for the scanners `sast-audit` prefers. Without these
the audit still runs on grep fallback, but real scanners catch far more. Safe to
re-run: every step checks "already installed?" first.

**Core principle:** install once, idempotently. Never reinstall what's present.

## When to Use

- `sast-audit` reported "scanners absent" and you want the stronger pass.
- Setting up a new machine/container for the security pipeline.

## Step 1 — Check what's already present

```bash
for t in semgrep bandit pip-audit gitleaks trivy; do
  if command -v "$t" >/dev/null 2>&1; then
    printf '%-10s OK  (%s)\n' "$t" "$(command -v $t)"
  else
    printf '%-10s MISSING\n' "$t"
  fi
done
node -v >/dev/null 2>&1 && echo "npm audit  OK (built into npm)"
```

Only install the ones marked MISSING.

## Step 2 — Python tools (semgrep, bandit, pip-audit)

Prefer an isolated installer so these don't pollute project envs. Use whichever
is available, in order of preference:

```bash
# Best: uv (isolated per-tool installs)
if command -v uv >/dev/null 2>&1; then
  for t in semgrep bandit pip-audit; do command -v "$t" >/dev/null || uv tool install "$t"; done

# Next: pipx (isolated)
elif command -v pipx >/dev/null 2>&1; then
  for t in semgrep bandit pip-audit; do command -v "$t" >/dev/null || pipx install "$t"; done

# Fallback: pip --user (respect PEP 668; add --break-system-packages only if needed)
else
  python3 -m pip install --user semgrep bandit pip-audit \
    || python3 -m pip install --user --break-system-packages semgrep bandit pip-audit
fi
```

Note: `semgrep` is not supported on native Windows — use WSL or Docker
(`docker run --rm -v "$PWD:/src" semgrep/semgrep semgrep --config auto /src`).
`bandit` and `pip-audit` work cross-platform.

## Step 3 — gitleaks (secrets scanner, Go binary)

```bash
if ! command -v gitleaks >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew install gitleaks
  elif command -v go >/dev/null 2>&1; then
    go install github.com/gitleaks/gitleaks/v8@latest   # ensure $(go env GOPATH)/bin is on PATH
  else
    # Download the latest release binary for this OS/arch into ~/.local/bin
    mkdir -p "$HOME/.local/bin"
    OS=$(uname -s | tr '[:upper:]' '[:lower:]'); ARCH=$(uname -m)
    case "$ARCH" in x86_64) ARCH=x64;; aarch64|arm64) ARCH=arm64;; esac
    URL=$(curl -fsSL https://api.github.com/repos/gitleaks/gitleaks/releases/latest \
      | grep -oE "https://[^\"]*${OS}_${ARCH}\.tar\.gz" | head -1)
    [ -n "$URL" ] && curl -fsSL "$URL" | tar -xz -C "$HOME/.local/bin" gitleaks \
      && chmod +x "$HOME/.local/bin/gitleaks"
  fi
fi
```

Make sure `~/.local/bin` (and `$(go env GOPATH)/bin` if you used `go install`)
is on `PATH`.

## Step 4 — npm audit (built in)

`npm audit` ships with npm — no install needed. Just confirm Node is present
(`node -v`). It only applies to projects with a `package.json` / lockfile.

## Step 5 — trivy (optional: containers / IaC)

```bash
if ! command -v trivy >/dev/null 2>&1; then
  command -v brew >/dev/null 2>&1 && brew install trivy
  # or: see https://aquasecurity.github.io/trivy for apt/yum/binary installs
fi
```

## Step 6 — Verify

Re-run Step 1. Everything you intended to install should now read OK. Smoke-test
one scanner:

```bash
semgrep --version && bandit --version && pip-audit --version && gitleaks version
```

Then hand back to `sast-audit` (`/sast-audit`) — it will now use the real
scanners instead of the grep fallback.

## Pitfalls

- **PEP 668 "externally-managed-environment"** — prefer `uv`/`pipx`; only add
  `--break-system-packages` as a last resort.
- **Binary not found after install** — `~/.local/bin` or the Go bin dir isn't on
  `PATH`; add it and re-open the shell.
- **semgrep on Windows** — unsupported natively; use WSL or the Docker image.
- **Network-restricted environment** — installs need internet. If blocked, tell
  the user; `sast-audit` falls back to grep patterns automatically.
- **Don't reinstall** — every step is guarded by a `command -v` check; re-running
  is a no-op for already-present tools.
