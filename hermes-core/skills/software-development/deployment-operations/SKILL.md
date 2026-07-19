---
name: deployment-operations
description: "CI/CD, monitoring, logging, alerts, and deployment decision tree (Docker vs artifact-only) — output docs/deployment/<slug>.md."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [deployment, cicd, monitoring, logging, alerts, operations, docker]
    related_skills: [github-pr-workflow, implementation-delivery, build-engineering-standards, continuous-improvement]
---

# Deployment & Operations

Phase 6 of the build lifecycle. Define how the change ships, how it is
observed in production, and what alerts fire when things break.

**Core principle:** if you cannot deploy, monitor, and debug it, it is not
done — even for library-only changes (document "artifact-only" explicitly).

## When to Use

- After Quality gate passes, before Iterate phase.
- When adding or changing CI/CD pipelines.
- When introducing new services, containers, or infrastructure.

## Deployment Decision Tree

**Always ask the user** how this change ships. Do not assume Docker.

```
1. Does this need to run as a long-lived service?
   NO  → artifact-only (library, CLI, npm package) — document publish steps
   YES → continue

2. Where does it run?
   a) Developer's machine only → local run docs + Makefile/scripts
   b) Shared server / VM → bare-metal or systemd unit docs
   c) Container platform → Docker + compose or orchestrator manifests
   d) CI-only (batch job, release pipeline) → GitHub Actions / equivalent
   e) Static site (landing page, docs, SPA) → GitHub Pages, Netlify, Vercel, or Cloudflare Pages (see Static Site Deployment below)

3. Does existing CI cover this change?
   NO  → add/update workflow; document in deployment doc
   YES → note which workflow and required checks

4. What observability is needed?
   - Structured logs (JSON) with correlation IDs
   - Metrics: latency, error rate, resource usage
   - Alerts: on SLO breach or error spike
```

Record the chosen path in `docs/deployment/<slug>.md` even when the answer
is "no deployment change — artifact-only, consumed as dependency."

## CI/CD

### GitHub Actions (common pattern)

- Workflow triggers: push to main, PR, release tag.
- Steps: lint → test → build → (optional) publish/deploy.
- Cache dependencies for speed.
- Fail fast; surface actionable error messages.

## Static Site Deployment

For landing pages, docs sites, SPAs, and other static content.

### GitHub Pages (recommended default)

Free, built-in HTTPS, permanent URL. No server maintenance.

**Deploy flow:**
```bash
# 1. Auth with gh CLI (device flow — user enters code at github.com/login/device)
ssh user@vps 'gh auth login --hostname github.com --git-protocol ssh'
# → copy one-time code, user enters it in browser
# → verify: gh auth status

# 2. Create repo and push
gh repo create USER/REPO --public --description '...'
gh repo clone USER/REPO
cp index.html REPO/
cd REPO && git add . && git commit -m "deploy" && git push origin main

# 3. Enable Pages
gh api repos/USER/REPO/pages --method POST -f 'source[branch]=main' -f 'source[path]=/'
```

**Pitfalls:**
- `gh auth login` device flow: keep the process ALIVE while user enters code. Each restart generates a new code. Don't kill before user finishes.
- SSH key must be added to GitHub account first.
- Pages build takes 10-30 seconds after push. Status check: `gh api repos/USER/REPO/pages | jq .status` → wait for `"built"`.
- GitHub Pages domain format for Yandex Metrika: `USER.github.io/REPO` (no `https://` prefix).

### VPS + nginx

For self-hosted static sites. See `references/static-site-nginx.md` for full details including nip.io domain tricks, SSH troubleshooting, and certbot setup.

Key pitfalls:
- Port 443 often used by VPN services (sing-box, etc.) — use 8443 with Let's Encrypt
- scp copies files with `0600` permissions → need `chmod 644` for nginx
- Cloudflare Tunnel (`cloudflared tunnel --url`) provides free HTTPS without touching port 443

### Compose / Makefile

- `make test`, `make build`, `make run` — document in feature README.
- Docker Compose: pin image tags; use `.env.example`.

### Integration with github-pr-workflow

When the change warrants a PR:
- Push branch, open PR, wait for CI green.
- Do not consider deployment phase complete until checks pass.

## Monitoring & Logging

### Structured Logging

```json
{"level":"info","msg":"request handled","correlation_id":"abc-123","duration_ms":42}
```

- Use correlation IDs across async boundaries and subagent calls.
- Log at boundaries: request in/out, external API calls, errors with stack.

### Metrics (when service runs in production)

| Metric | Purpose |
|--------|---------|
| Request latency (p50/p95/p99) | Performance SLOs |
| Error rate | Reliability |
| CPU / memory | Capacity planning |
| Queue depth | Backpressure |

### Alerts

- Alert on symptoms (high error rate, latency SLO breach), not every log line.
- Document alert routing and runbook link in deployment doc.

## Output

Save to: `docs/deployment/<slug>.md`

## Quick References

- **[Static Site — nginx + VPS](references/static-site-nginx.md)** — scp, nginx, permissions pitfall, nip.io, certbot, SSH fixes
- **[Static Site — GitHub Pages](references/static-site-github-pages.md)** — gh auth device flow, repo creation, Pages API, Yandex Metrika domain format
- **[Telegram Landing Template](templates/landing-page.html)** — dark HTML landing with Metrika counter + UTM tracking. Load `yandex-metrika-setup` skill for the full workflow.

See also: `yandex-metrika-setup` skill for the complete Metrika counter creation and ad tracking workflow.

## Template

```markdown
# Deployment: [Feature Name]

**Date:** YYYY-MM-DD
**Architecture:** [link to docs/architecture/<slug>.md]

## Deployment Model

- [ ] Artifact-only (library / package)
- [ ] Local development only
- [ ] Docker / Compose
- [ ] CI/CD pipeline only
- [ ] Production service

## Decision Rationale

[Why this model was chosen; user confirmation noted]

## Build & Publish

```bash
# Build
[exact commands]

# Publish / deploy
[exact commands or "N/A — merged to main"]
```

## CI/CD

| Workflow | Trigger | Checks |
|----------|---------|--------|
| `.github/workflows/...` | PR / push | lint, test, ... |

## Runtime Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `VAR` | [purpose] | [from .env.example] |

## Monitoring

- **Logs:** [where, format, retention]
- **Metrics:** [what is collected, where]
- **Dashboards:** [link or "N/A"]

## Alerts

| Alert | Condition | Action |
|-------|-----------|--------|
| [name] | [threshold] | [runbook step] |

## Rollback

[How to revert: git revert, previous image tag, feature flag]

## Verification

- [ ] CI green on PR
- [ ] Smoke test command documented
- [ ] Rollback path documented
```

## Gate Checklist

Before proceeding to Iterate:

- [ ] User asked about deployment model
- [ ] Decision documented (including artifact-only)
- [ ] CI changes identified or confirmed N/A
- [ ] Logging/monitoring noted or explicitly N/A for scope
- [ ] Document saved at `docs/deployment/<slug>.md`
