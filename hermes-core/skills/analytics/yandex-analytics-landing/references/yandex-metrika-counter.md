# Yandex Metrika Counter Creation (Official Docs)

Extracted from https://yandex.ru/support/metrica/ru/general/creating-counter

## Step 1 — Authorize

Login to Yandex account on metrika.yandex.ru.

## Step 2 — Add Counter

Click "Добавить счётчик" on the counters page.

## Step 3 — Basic Settings

### Required Fields

- **Имя счётчика** — displayed in counter list. If empty, uses site address.
- **Адрес сайта** — main domain. **NO protocol prefix** (no http:// or https://).
  - CAN include path: `example.com/category/` ✅
  - CANNOT include file: `example.com/page.html` ❌
  - CANNOT include fragment: `example.com#section` ❌
  - URL params (?...) are ignored
  - Cyrillic domains: use Cyrillic, not Punycode
- **Часовой пояс** — stats collected in this timezone. Historical data NOT recalculated on change.
- **Валюта** — default currency for revenue display.

### Additional Settings

- **Вебвизор, карта скроллинга, аналитика форм** — enables visit recording, click maps, link maps
- **Дополнительные адреса сайта** — for tracking multiple URLs with one counter
- **Принимать данные только с указанных адресов** — filters out data from other domains
- **Включая поддомены** — includes subdomains in filtering

### Code Settings (Дополнительные условия обработки данных)

- **Не сохранять полные IP-адреса** — anonymizes IPs (reduces geo accuracy)
- **GDPR agreement** — only if company registered in EU/Switzerland

### Before clicking "Продолжить"

- **Accept User Agreement** checkbox
- Click "Продолжить"

## Step 4 — Profile

Metrika uses profile data for optimal settings:

- Site type
- Industry (can select multiple)
- CMS (use "Без CMS" for static hosting)
- Roles in project (owner, analyst, etc.)

Different counters can have different role sets for the same user.

## Installing the Counter

After creation: Настройка → вкладка Счетчик → Скопировать

Insert code into `<head>` or `<body>`, as close to page start as possible.
`<noscript>` element MUST be inside `<body>`.

Counter appears on "Мои счетчики" page immediately. Data collection starts right away.

## Multi-domain Tracking

Two approaches:
1. **One counter for all** — common stats, composite goals, unified Webvisor
2. **Separate counters** — per-domain stats, separate goals

Recommendation: use both together for maximum coverage.
