---
name: yandex-analytics-landing
description: "Landing page setup for Yandex Metrika + Direct — counter creation, UTM tracking, hosting that doesn't block YandexBot, full testing checklist."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, any]
metadata:
  hermes:
    tags: [yandex, metrika, direct, analytics, landing, utm, deployment]
---

# Yandex Metrika + Direct Landing Page Setup

End-to-end setup: landing page → Metrika counter → Direct UTM → ad approval.

## When to Use

- Creating a landing page for Yandex Direct ads
- Setting up Yandex Metrika counter for conversion tracking
- Debugging "Страница перехода не отображается" (Direct moderation rejection)
- Debugging "Не удалось выполнить операцию" (Metrika counter creation failure)

## Pre-flight Checklist (MANDATORY — read before deploying)

1. **Read Yandex docs FIRST**, not after hitting errors:
   - Metrika counter: https://yandex.ru/support/metrica/ru/general/creating-counter
   - Direct URL tags: https://yandex.ru/support/direct/ru/statistics/url-tags
2. **Requirements deduced from docs:**
   - HTTPS on port 443 (Metrika blocks non-standard ports like :8443)
   - No protocol prefix in "Адрес сайта" field
   - Page must respond to YandexBot UA with HTTP 200
   - UTM: `utm_source`, `utm_medium`, `utm_campaign` — mandatory

## Step 1: Metrika Counter Creation (4 steps)

### Step 3 — Основные настройки

| Field | Value | Rule |
|-------|-------|------|
| **Имя** | project name | |
| **Адрес сайта** | `domain.ru/path/` | **NO https://** — prefix causes validation error |
| **Часовой пояс** | Moscow (GMT+3) | |
| **Валюта** | RUB | |

**Additional settings:** ☑ Вебвизор, ☑ Принимать данные только с указанных адресов.

**Before clicking "Продолжить":** ☑ Accept terms (Пользовательское соглашение).

### Step 4 — Профиль

Fill profile: site type, industry, CMS (use "Без CMS" for static hosting), roles.

### After creation

Copy counter code → insert in `<head>` of landing page. Counter activates immediately.

## Step 2: Landing Page Hosting — Compatibility Matrix

**CRITICAL: test with YandexBot UA before declaring done.**

| Hosting | YandexBot | HTTPS | Setup |
|---------|:---------:|:-----:|-------|
| GitHub Pages | ❌ BLOCKED | ✅ | Fastly CDN drops YandexBot connections |
| VPS (nginx) | ✅ | ❌ | Needs HTTPS cert + domain |
| trycloudflare.com | ❌ BLOCKED | ✅ | Temporary domain rejected by Yandex |
| localhost.run (lhr.life) | ⚠️ Unstable | ✅ | Tunnels die; not for production |
| Netlify | ✅? | ✅ | Needs account; untested with YandexBot |
| Vercel | ✅? | ✅ | Needs GitHub login; untested |

**Test command:**
```bash
curl -s --max-time 10 \
  -H "User-Agent: Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)" \
  https://domain.ru/ \
  -o /dev/null -w "HTTP %{http_code}\n"
# MUST return HTTP 200. 000 or 403 = hosting blocks YandexBot → Direct will reject.
```

## Step 3: UTM Tags for Yandex Direct

### Required UTM tags (from Yandex docs)

```
?utm_source=yandex&utm_medium=cpc&utm_campaign={campaign_id}
```

### Optional UTM tags

```
&utm_content={ad_id}&utm_term={keyword}
```

### Yandex Direct dynamic parameters

| Parameter | Value |
|-----------|-------|
| `{campaign_id}` | Campaign ID (number) |
| `{ad_id}` | Ad ID (number) |
| `{keyword}` | Search phrase |
| `{device_type}` | desktop / mobile / tablet |
| `{campaign_name}` | Campaign name (text) |

### UTM rules (from Yandex docs)

- Order: source → medium → campaign → content → term
- Latin characters, lowercase
- Separators: `_` or `-`
- ⚠️ Yandex may shorten `yandex` → `ya` in utm_source values

## Step 4: Metrika Counter Code Template

```html
<!-- Yandex.Metrika counter -->
<script type="text/javascript">
   (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
   m[i].l=1*new Date();
   for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
   k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
   (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");

   ym(XXXXXXXX, "init", {
        clickmap:true,
        trackLinks:true,
        accurateTrackBounce:true,
        webvisor:true
   });
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/XXXXXXXX" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
```

### Goal tracking on CTA button

```html
<a href="https://t.me/channel"
   onclick="ym(XXXXXXXX, 'reachGoal', 'goal_id'); return true;">
   Button text
</a>
```

Then create goal in Metrika: Цели → JavaScript-событие → `goal_id`.

## Pitfalls

1. **GitHub Pages blocks YandexBot** — Fastly CDN drops connections with YandexBot/3.0 UA. Never use GH Pages for Yandex Direct landing pages. Always test with the YandexBot UA curl command above.

2. **trycloudflare.com blocked** — temporary Cloudflare tunnel domains are rejected by Yandex Metrika and likely Direct too. Use proper hosting.

3. **Non-standard HTTPS ports** — Metrika and Direct only check port 443. Serving HTTPS on :8443 will fail.

4. **https:// prefix in counter creation** — Yandex docs explicitly say NOT to include protocol prefix in "Адрес сайта" field. Enter `domain.ru/path/` not `https://domain.ru/path/`.

5. **Useless searches for Russian docs** — SearxNG returns irrelevant Yandex portal pages for Russian-language queries. For Yandex documentation, use direct `curl` to known URL paths instead of search engines.

6. **Announcing "ready" too early** — A page that loads in a browser may still be invisible to YandexBot. Always verify with ALL stakeholders: browser UA, YandexBot UA, and the actual Metrika/Direct interfaces.

7. **Looping on GitHub auth** — gh CLI device auth is fragile in headless/remote shells. Skip after 2 failed attempts; ask the user to create the repo manually (30 seconds) or use a different hosting.

## Testing Checklist (before telling user "done")

- [ ] Page loads: `curl -s https://domain/` → HTTP 200
- [ ] YandexBot: `curl -s -H "User-Agent: ...YandexBot..." https://domain/` → HTTP 200
- [ ] Counter code present: `curl -s https://domain/ | grep 'ym(XXXXXXXX'`
- [ ] User tested counter creation in Metrika UI
- [ ] User tested ad submission in Direct UI

## Reference Files

- [`references/yandex-metrika-counter.md`](references/yandex-metrika-counter.md) — Metrika counter creation steps from official docs
- [`references/yandex-direct-utm.md`](references/yandex-direct-utm.md) — Direct URL parameters and dynamic UTM tags
