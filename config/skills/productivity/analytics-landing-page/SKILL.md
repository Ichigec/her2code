---
name: analytics-landing-page
description: "Create HTTPS-hosted landing pages with analytics (Yandex Metrika) for advertising Telegram channels. Covers UTM tracking, goal events, hosting pitfalls, and headless repo creation via gh device auth."
version: 1.0.0
author: Hermes Agent
platforms: [linux]
---

# Analytics Landing Page

Create a tracking-ready landing page for advertising a Telegram channel through Yandex Metrika, Google Analytics, or similar analytics platforms.

## When to Use

- User wants to advertise a Telegram channel/group with analytics
- Setting up Yandex Metrika counter with a landing page
- Need HTTPS landing page that passes analytics platform verification
- UTM tracking for ad campaigns

## Critical Pitfalls

### Yandex Metrika Verification
1. **HTTPS on port 443 is MANDATORY.** Yandex rejects non-standard ports (`:8443` fails).
2. **Temporary tunnel domains are BLOCKED.** `trycloudflare.com`, `lhr.life`, `serveo.net` — all blocked by Yandex as suspicious. Do NOT use them.
3. **nip.io works for DNS** but still needs proper HTTPS on port 443.
4. **HTTP (port 80) is NOT enough.** Yandex requires HTTPS.

### VPS Hosting
- If port 443 is occupied by VPN/proxy (sing-box, etc.) — **DO NOT touch it.** Find alternative hosting.
- Cloudflared tunnel from VPS works but `trycloudflare.com` subdomains are blocked by analytics platforms.
- Cloudflared from Jetson behind VPN often fails (QUIC blocked).

## Recommended Hosting (in priority order)

### 1. GitHub Pages — BEST
- Free HTTPS on port 443, permanent URL, Yandex accepts it.
- URL: `https://<user>.github.io/<repo>/`
- Requires: GitHub repo + SSH key or gh auth.

### 2. VPS with nginx + Let's Encrypt
- Only if port 443 is available.
- Use certbot with HTTP challenge on port 80.
- Requires real domain or nip.io.

### 3. Netlify / Vercel
- Free HTTPS, permanent URL.
- Requires account creation (interactive).

## GitHub Pages Workflow

### Headless Repo Creation (gh device auth)
When SSH key is set up but gh CLI needs auth:
```bash
# On remote server (VPS, etc.)
gh auth login --hostname github.com --git-protocol ssh
# → Shows one-time code, user enters at https://github.com/login/device
# Must keep process alive while user enters code!
```

After auth:
```bash
gh repo create <user>/<repo> --public --description "..."
git clone git@github.com:<user>/<repo>.git
cp landing-page-files/* <repo>/
cd <repo>
git add . && git commit -m "Landing page"
git push -u origin main
# Enable Pages: Settings → Pages → Source: main branch → Save
```

### If gh not available
Install on VPS (amd64):
```bash
curl -sL https://github.com/cli/cli/releases/latest/download/gh_VERSION_linux_amd64.tar.gz | tar xz -C /usr/local --strip-components=1
```

## Landing Page Template

Required elements for a Telegram channel landing page:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <!-- Metrika counter code — replace XXXXXXXX with actual ID -->
    <script>
       ym(XXXXXXXX, "init", {clickmap:true, trackLinks:true, webvisor:true});
    </script>
</head>
<body>
    <!-- CTA button with goal tracking + UTM pass-through -->
    <a href="https://t.me/channel"
       onclick="ym(XXXXXXXX, 'reachGoal', 'tg_subscribe'); return true;">
       Подписаться в Telegram
    </a>
    
    <!-- UTM capture script -->
    <script>
        const params = new URLSearchParams(window.location.search);
        const utm = {
            source: params.get('utm_source'),
            medium: params.get('utm_medium'),
            campaign: params.get('utm_campaign')
        };
        // Save to sessionStorage for multi-page flows
        if (utm.source) sessionStorage.setItem('utm_data', JSON.stringify(utm));
    </script>
</body>
</html>
```

## Yandex Metrika Setup Checklist

1. Create counter at [metrika.yandex.ru](https://metrika.yandex.ru)
2. Site address: `https://<actual-hosted-url>` (must be active, HTTPS port 443)
3. Enable: Webvisor, Click map
4. Copy counter ID (8 digits)
5. Replace `XXXXXXXX` in landing page HTML with counter ID
6. Create goal: JavaScript event → identifier `tg_subscribe`
7. Push updated HTML to hosting
8. Verify: open page, click CTA, check Metrika reports in ~5-10 minutes

## Ad Campaign UTM Structure

```
https://<landing>/?utm_source=yandex&utm_medium=cpc&utm_campaign=<name>&utm_content=<variant>&utm_term=<keyword>
```

Metrika auto-parses UTM params into Source → UTM report.

## Supporting Files

- `templates/landing-page.html` — full HTML template (replace CHANNEL_NAME, DESCRIPTION, topics, Metrika ID)
- `references/hosting-pitfalls.md` — what hosting options pass/fail Yandex verification, gh device auth details
