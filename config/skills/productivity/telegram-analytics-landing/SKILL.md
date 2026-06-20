---
name: telegram-analytics-landing
description: "Deploy a landing page with Yandex Metrika tracking for Telegram group advertising — GitHub Pages + UTM + goal tracking."
tags: [telegram, yandex-metrika, landing, analytics, github-pages, utm]
---

# Telegram Analytics Landing Page

Create and deploy a landing page for tracking Telegram group ad campaigns with Yandex Metrika.

## Critical Constraints (User's Environment)

- **Yandex Metrika REQUIRES HTTPS on port 443** — HTTP and non-standard ports (8443, etc.) fail verification
- **Temporary domains are BLOCKED** by Yandex: trycloudflare.com, lhr.life, nip.io — don't use them
- **Sing-box on VPS port 443 — DO NOT TOUCH** (most critical service on User's VPS)
- **GitHub Pages is the go-to** for User: free HTTPS, accepted by Yandex, permanent URL
- **User's GitHub**: account `<YOUR_GITHUB_USER>`, SSH key `~/.ssh/id_ed25519`. gh CLI on VPS at `/usr/local/bin/gh` (amd64), authenticated via device flow

## Workflow

### 1. Create the landing page

Template: see `references/landing-template.html`. Key elements:
- Clean single-page design (dark theme preferred for tech channels)
- Telegram join button with `onclick="trackClick()"`
- Yandex Metrika counter placeholder (`XXXXXXXX` — replaced after counter creation)
- UTM parameter capture from URL
- Goal tracking: `ym(XXXXXXXX, 'reachGoal', 'tg_subscribe')`

### 2. Host on GitHub Pages

```bash
# SSH to VPS (gh CLI is there, authenticated for <YOUR_GITHUB_USER>)
ssh root@<YOUR_VPS_IP>

# Create repo
gh repo create <YOUR_GITHUB_USER>/REPO-NAME --public --description 'Landing for @channel'

# Clone and push
gh repo clone <YOUR_GITHUB_USER>/REPO-NAME
cp index.html REPO-NAME/
cd REPO-NAME
git add index.html
git commit -m 'Landing page'
git push origin main

# Enable Pages
gh api repos/<YOUR_GITHUB_USER>/REPO-NAME/pages \
  --method POST \
  -f 'source[branch]=main' \
  -f 'source[path]=/'
```

URL: `https://ichigec.github.io/REPO-NAME/` — wait 10-30s for first build.

### 3. Yandex Metrika setup (user does this)

1. Go to [metrika.yandex.ru](https://metrika.yandex.ru) → Add counter
2. Site address: `https://ichigec.github.io/REPO-NAME/`
3. Enable: Webvisor, Click map
4. Copy counter ID (8 digits, appears as `ym(XXXXXXXX, ...)`)
5. Create goal: JavaScript event, identifier `tg_subscribe`, name "Click Subscribe"

### 4. Insert counter ID

Replace `XXXXXXXX` (occurs 3 times in the template) with the actual counter ID:
1. `ym(XXXXXXXX, "init", ...` — counter initialization
2. `ym(XXXXXXXX, 'reachGoal', 'tg_subscribe')` — goal trigger
3. `<img src="https://mc.yandex.ru/watch/XXXXXXXX"` — noscript fallback

Commit and push the update.

### 5. Ad campaign UTM links

```
https://ichigec.github.io/REPO-NAME/?utm_source=yandex&utm_medium=cpc&utm_campaign=promo1
```

Optional UTM params: `utm_content`, `utm_term` — all captured and passed to Metrika.

## Pitfalls

- Never use VPS for Yandex Metrika hosting (port 443 occupied by sing-box)
- Cloudflared tunnel from VPS works but trycloudflare.com domains are blocked by Yandex
- Let's Encrypt on VPS works (HTTP challenge on port 80 → cert obtained) but HTTPS on non-443 port (8443) fails Yandex verification
- Don't ask User to create repos manually — use gh CLI on VPS
- GitHub Pages first build takes 10-30 seconds; expect 404 briefly
