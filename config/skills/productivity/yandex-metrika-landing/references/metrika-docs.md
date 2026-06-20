# Yandex Metrika Counter Creation — Official Requirements

Extracted from https://yandex.ru/support/metrica/ru/general/creating-counter
Verified: 2026-06-19

## Domain Field Rules (critical)

- **NO protocol prefix** — `http://` or `https://` must NOT be included
- Path IS allowed: `example.com/category/` ✅
- File names NOT allowed: `example.com/page.html` ❌
- Fragments NOT allowed: `example.com#section` ❌
- URL parameters ignored: part after `?` is discarded
- Cyrillic domains: enter in Cyrillic, not Punycode

## URL Structure Reference

```
<host>/<path>?<params>#<fragment>
```

- `<host>` — domain
- `<path>` — hierarchical, separated by `/`
- `<params>` — after `?`, ignored in domain field
- `<fragment>` — after `#`, causes input error if included

## Counter Creation Steps

1. **Authorize** on Yandex
2. **Click "Add counter"** on the counters page
3. **Basic settings:**
   - Name (optional, defaults to domain)
   - Domain (required, format rules above)
   - Timezone + Currency
   - ☑ Webvisor, scroll map, form analytics
   - ☑ Accept only from specified addresses (security)
   - User Agreement checkbox
   - Click "Continue"
4. **Fill profile:** site type, industry, CMS, role(s)

## Limits

- One user: max 100,000 counters
- Counter active immediately after code installation
- Data collection starts instantly

## Metrika JS Init Options

```javascript
ym(COUNTER_ID, "init", {
    clickmap: true,              // Click map
    trackLinks: true,            // External link tracking
    accurateTrackBounce: true,   // Accurate bounce = <15s
    webvisor: true               // Session replay
});
```

## Goal Creation

- Type: JavaScript event
- Identifier: user-defined (e.g., `tg_subscribe`)
- Trigger: `ym(ID, 'reachGoal', 'goal_name')`

## Additional Settings

| Setting | When |
|---------|------|
| Anonymize IPs | Lower geo accuracy |
| GDPR agreement | Company in EU/Switzerland |
| Include subdomains | Own domain with subs |
| Multiple addresses | One counter for many sites |

## Direct Integration

Yandex Direct auto-links to Metrika under same account.
- Campaign → Strategy → «Метрика counters» → select counter + key goals
- Auto-optimization by conversions available
- UTM auto-marking or manual template with `{campaign_id}`, `{ad_id}`, `{keyword}`
