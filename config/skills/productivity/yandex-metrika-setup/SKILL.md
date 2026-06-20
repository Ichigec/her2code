---
name: yandex-metrika-setup
description: "Create Yandex Metrika counters, set up landing pages for Telegram channel ads, configure UTM tracking and goals. Covers domain requirements, blocked domains, common errors and workarounds."
version: 1.0.0
tags: [yandex, metrika, analytics, landing, telegram, advertising, utm]
---

# Yandex Metrika Setup

Create a Yandex Metrika counter for tracking Telegram channel advertising. Includes landing page deployment (GitHub Pages is the default), UTM tracking, goal setup, and common pitfalls.

## When to Use

- User wants to advertise a Telegram channel/group and track conversions
- User asks to "создать Яндекс Метрику" or "счётчик для рекламы"
- Setting up analytics for a static landing page
- Troubleshooting Metrika counter creation errors

## Architecture

```
Реклама (Яндекс.Директ) → Лендинг (с Метрикой + UTM) → Кнопка → Telegram-группа
```

A landing page is REQUIRED — Telegram doesn't allow embedding Metrika code directly. The landing page hosts the Metrika counter code and a CTA button to the Telegram group.

## Step-by-Step

### 1. Deploy the Landing Page

**Default: GitHub Pages** (free, HTTPS, no auth required after first setup, permanent URL).

Alternative: VPS + nginx (but HTTPS on port 443 conflicts with sing-box/VPN services — use port 8443 or Cloudflare Tunnel).

Use the template at `references/landing-template.html`. Replace:
- `<YOUR_CHANNEL>` → actual Telegram group handle
- Channel description text
- `XXXXXXXX` → Metrika counter ID (after creation)

### 2. Create Yandex Metrika Counter

Go to [metrika.yandex.ru](https://metrika.yandex.ru) → **Добавить счётчик**.

**CRITICAL — Domain format:**
```
✅ ichigec.github.io/<YOUR_PROJECT>/
❌ https://ichigec.github.io/<YOUR_PROJECT>/
```
Yandex docs explicitly say: *«Префикс схемы/протокола (http://, https://) указывать не следует»*. Enter the bare domain + optional path. No protocol, no file names, no `#` fragments or `?` parameters.

**Settings:**
- Имя: channel name (e.g., `raicomml`)
- Часовой пояс: Москва (GMT+3)
- ☑ Вебвизор, карта скроллинга, аналитика форм
- Дополнительные адреса: leave empty (one site)

**The counter is created IMMEDIATELY** — Yandex does NOT verify site accessibility during creation. Verification is a separate step after installing the code.

### 3. Install Counter Code

After creation, Yandex shows the counter code block (`ym(XXXXXXXX, "init", {...})`). Copy the 8-digit counter ID and paste it into the landing page HTML (replacing `XXXXXXXX` in the template).

### 4. Create Goal "Click to Telegram"

In counter settings → **Цели** → **Добавить цель**:
- Тип: JavaScript-событие
- Идентификатор: `tg_subscribe`
- Название: «Клик Подписаться»

The template already has `onclick="ym(XXXXXXXX, 'reachGoal', 'tg_subscribe')"` on the CTA button.

### 5. UTM Tracking

Add UTM parameters to ad links:
```
https://landing-url/?utm_source=yandex&utm_medium=cpc&utm_campaign={campaign_name}&utm_content={ad_name}&utm_term={keyword}
```

The template reads UTM from URL, passes to Metrika via `ym(XXXXXXXX, 'params', {...})`, and stores in sessionStorage.

## Pitfalls

### Domain-blocked services (DO NOT USE)
| Service | Reason |
|---------|--------|
| `trycloudflare.com` | Blocked by Yandex as temporary/suspicious domain |
| `lhr.life` (localhost.run) | Unstable, may be blocked |
| `nip.io` with non-standard HTTPS port | Yandex only checks standard ports |

### Common errors

**"Не удалось выполнить операцию" при создании счётчика:**
1. **Protocol prefix** — most likely cause. Remove `https://` from the domain field.
2. **Ad blocker** — disable uBlock/AdBlock for `metrika.yandex.ru`.
3. **Session issue** — try incognito mode or re-login to Yandex.
4. **Browser bug** — try a different browser or Ctrl+F5.

**Site verification after creation:**
Yandex does NOT verify the site during counter creation. If you see "счётчик не проверен" later, it means the counter code isn't detected on the page. Wait ~5 minutes after deploying, then use the built-in checker at Настройка → Проверка счетчика.

### VPS deployment (alternative)
If using VPS instead of GitHub Pages:
- Port 80: nginx for HTTP
- Port 443: often occupied by sing-box/VPN — **DO NOT TOUCH**
- HTTPS workaround: Let's Encrypt cert via HTTP challenge on port 80, serve on port 8443
- Cloudflare Tunnel: `cloudflared tunnel --url http://localhost:80` from VPS gives HTTPS

### gh CLI auth (GitHub Pages deployment)
When deploying to GitHub Pages programmatically:
- SSH key must be added to GitHub account
- `gh auth login` device flow: run process persistently, capture one-time code, user enters at `github.com/login/device`
- Don't kill the process before user enters the code — each restart generates a new code
- After auth: `gh repo create`, `git push`, `gh api repos/:owner/:repo/pages --method POST`

## References
- `references/landing-template.html` — base HTML template with Metrika + UTM
- `references/metrika-domain-rules.md` — Yandex documentation excerpts on domain format
