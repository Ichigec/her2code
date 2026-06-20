---
name: yandex-metrika-landing
description: "Create a landing page for Telegram channel promotion with Yandex Metrika tracking, Yandex Direct UTM integration, and goal-based conversion tracking."
version: 1.0.0
author: Hermes Agent
tags: [yandex-metrika, landing-page, telegram, yandex-direct, utm, analytics]
---

# Yandex Metrika Landing Page for Telegram

Create an HTML landing page for promoting a Telegram channel/group with Yandex Metrika counter, goal tracking, and UTM support for Yandex Direct ads.

## When to Use

- User wants to promote a Telegram channel via Yandex Direct ads
- User needs a landing page with Yandex Metrika analytics
- User asks about UTM tracking, conversion goals, or Metrika integration for Telegram

## Architecture

```
Yandex Direct (ad) → Landing Page (with Metrika JS) → t.me/group (goal fires)
                          │
                    UTM params parsed
                    Metrika goal: tg_subscribe
```

## Step-by-step

### 1. Create the HTML landing page

Use `references/template.html` as the base. Copy and modify:

- Replace `CHANNEL_NAME` with the Telegram channel name
- Replace `CHANNEL_DESCRIPTION` with description
- Replace `CHANNEL_TAGS` with topic tags
- Replace `https://t.me/CHANNEL` with actual Telegram link

The template includes:
- Dark tech-themed design
- Hero section with channel info
- CTA button with Metrika goal tracking
- UTM parameter parsing and forwarding to Metrika
- Placeholder for counter ID (`XXXXXXXX`)

### 2. Host the landing page

**Preferred: GitHub Pages** (free HTTPS, permanent URL, Yandex-compatible)

```bash
# Create repo and push
gh repo create USER/REPO --public
git add index.html && git commit -m "Landing page"
git push origin main
gh api repos/USER/REPO/pages --method POST -f 'source[branch]=main' -f 'source[path]=/'
```

URL format: `https://USER.github.io/REPO/`

**Alternative: VPS with nginx + certbot** — see `references/vps-deploy.md`.

### 3. Create Yandex Metrika counter

**CRITICAL:** Enter the domain WITHOUT protocol prefix.

| Field | Value | Rule |
|-------|-------|------|
| **Имя счётчика** | Channel name | — |
| **Адрес сайта** | `user.github.io/repo/` | **NO `https://`!** |
| **Часовой пояс** | Москва (GMT+3) | — |
| **Валюта** | RUB | — |

Checkboxes:
- ☑ Вебвизор, карта скроллинга, аналитика форм
- ☑ Принимать данные только с указанных адресов
- ☑ Принять условия Пользовательского соглашения

**Шаг 4 (Profile):** Type=Лендинг, Industry=IT, CMS=Без CMS, Role=Владелец+Аналитик

### 4. Insert counter ID

Replace `XXXXXXXX` in `index.html` with the actual 8-9 digit counter ID. Occurs in 6 places in the template (comments + 4 code references).

### 5. Create the conversion goal

In Metrika: **Цели → Добавить цель → JavaScript-событие**
- Идентификатор: `tg_subscribe`
- Название: «Клик Подписаться в Telegram»

### 6. UTM setup for Yandex Direct

In Yandex Direct campaign settings → UTM-метки. Either:
- Enable auto-marking (simplest)
- Or use manual template: `?utm_source=yandex&utm_medium=cpc&utm_campaign={campaign_id}&utm_content={ad_id}&utm_term={keyword}`

Dynamic substitutions: `{campaign_id}`, `{ad_id}`, `{keyword}`, `{source}`, `{position_type}`

## Pitfalls

1. **Protocol prefix kills counter creation** — Yandex docs explicitly say NO `http://`/`https://` in the domain field. Path is OK (`domain.com/path/`). Files and fragments are NOT (`page.html`, `#section`).

2. **Temporary domains blocked** — `trycloudflare.com`, `lhr.life`, and similar tunnel domains are rejected by Yandex. Use permanent hosting (GitHub Pages, VPS with domain).

3. **CDN caching delays verification** — GitHub Pages uses Fastly CDN with 10-min cache. After pushing counter code, Yandex may serve stale version for up to 10 minutes. Use `curl -H 'Cache-Control: no-cache'` to verify, or wait.

4. **Non-standard HTTPS ports rejected** — Yandex only verifies on port 443. Port 8443 or custom ports won't pass.

5. **Counter creation failure ≠ site accessibility issue** — Yandex does NOT verify the site during counter creation. If creation fails, check: domain format (no protocol), adblocker off, browser incognito, User Agreement checkbox.

6. **hilogd on Honor/Huawei phones** — Android `Log.d()` suppressed. Use `Log.i()` for Metrika debug logs on Android.

## Metrika JS options reference

| Option | Effect |
|--------|--------|
| `clickmap: true` | Record all clicks → Click Map report |
| `trackLinks: true` | Track external link clicks (including t.me) |
| `accurateTrackBounce: true` | Bounce = visit < 15s (not 1 page) |
| `webvisor: true` | Session replay recordings |

## References

- `references/template.html` — Full HTML landing page template
- `references/metrika-docs.md` — Yandex Metrika official requirements (Russian)
