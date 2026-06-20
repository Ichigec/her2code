# Yandex Direct Dynamic Parameters

Full list from https://yandex.ru/support/direct/ru/statistics/url-tags

## UTM Tags (Mandatory)

| Tag | Description | Example |
|-----|-------------|---------|
| `utm_source` | Traffic source | `yandex` |
| `utm_medium` | Channel type | `cpc` (search), `display` (media) |
| `utm_campaign` | Campaign | `{campaign_id}` or name |

## UTM Tags (Optional)

| Tag | Description | Example |
|-----|-------------|---------|
| `utm_content` | Ad identifier | `{position_type}.{position}` |
| `utm_term` | Keyword | `{keyword}` |

## Dynamic Parameters

| Parameter | Description | Values |
|-----------|-------------|--------|
| `{ad_id}` / `{banner_id}` | Ad ID | number |
| `{campaign_name}` | Campaign name | text, up to 255 chars |
| `{campaign_name_lat}` | Transliterated name | Latin, up to 255 chars |
| `{campaign_type}` | Campaign type | type1 (Performance), type6 (Search banner) |
| `{campaign_id}` | Campaign ID | number |
| `{creative_id}` | Creative ID | number |
| `{device_type}` | Device | desktop / mobile / tablet |
| `{keyword}` | Search phrase | text |
| `{position_type}` | Placement type | premium / other |
| `{source}` | Traffic source | yandex |

## Rules

- Order: utm_source → utm_medium → utm_campaign → utm_content → utm_term
- Latin characters, lowercase
- Separators: `_` or `-`
- Yandex may shorten `yandex` → `ya` in any utm_source value
- Cyrillic auto-encoded to UTF-8; URL max 4096 bytes
