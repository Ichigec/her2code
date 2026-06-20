---
name: static-site-deploy
description: "Deploy static HTML/CSS sites publicly: serve via python3 http.server, expose via localhost.run or cloudflared tunnel."
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [static-site, deploy, tunnel, landing-page, localhost-run, cloudflared]
    platforms: [linux]
---

# Static Site Deploy

Quickly serve and publicly expose a static HTML/CSS site (landing page, demo, prototype) without nginx, Docker, or VPS configuration.

## When to Use

- User asks to create and host a landing page, promo page, or simple static site
- User wants a URL to share for a static HTML artifact
- User needs a quick public endpoint (for webhooks, analytics verification, etc.)

## Workflow

### 1. Create the static site

Write HTML/CSS/JS files into a directory. For landing pages with analytics, see `templates/landing-metrika.html`.

### 2. Serve locally

```bash
cd /path/to/site && python3 -m http.server 8080
```

Always use **background=true** — this is a long-lived server. Verify with curl:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
```

### 3. Expose publicly

**Primary: localhost.run** (most reliable — works through VPNs, no binary dependencies):

```bash
ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 \
    -R 80:localhost:8080 nokey@localhost.run
```

Output will contain: `https://<random-id>.lhr.life tunneled with tls termination`

- URL changes each restart (anonymous mode). For persistent domains, create an account at admin.localhost.run.
- First request after tunnel creation may return 502 — retry once, it resolves.

**Fallback: cloudflared** (faster, static domain possible, but BLOCKED by some VPNs):

```bash
cloudflared tunnel --url http://localhost:8080
```

## Pitfalls

| Issue | Symptom | Fix |
|-------|---------|-----|
| cloudflared behind VPN | `ERR Failed to dial a quic connection ... timeout: no recent network activity` | Use localhost.run instead |
| localhost.run 502 on first hit | `502 Bad Gateway` after tunnel just started | Retry once — the second request goes through |
| Port already in use | `Address already in use` | Pick another port (5000, 8888) — check with `ss -tlnp` |
| localhost.run host key | `Host key verification failed` | Use `-o StrictHostKeyChecking=accept-new` |

## Verification

After tunnel is up, verify from a separate context:

```bash
curl -s -o /dev/null -w "%{http_code}" https://<tunnel-url>/
# Expected: 200
```

## Templates

- `templates/landing-metrika.html` — Telegram channel landing page with Yandex Metrika integration, UTM tracking, and goal events.
