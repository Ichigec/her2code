# PII Sanitization — Second Pass Discoveries

These PII items survived the first sanitization pass and needed manual fixes:

## 1. SANITIZATION_LOG.md — документация с реальными значениями

Лог санитизации перечислял ЧТО удалено, но использовал оригинальные значения.
Все реальные IP, ключи, ID заменены на `<YOUR_*>` плейсхолдеры.

## 2. sanitize-config.yaml — hostname

`<YOUR_HOSTNAME>` остался в конфиге санитайзера. Заменён на `<YOUR_HOSTNAME>`.

## 3. Skills с частично скрытыми ключами

Файлы с `Bearer <YOUR_HARDCODED_TOKEN>...` (многоточие вместо полного ключа) не матчились regex'ом
`Bearer [A-Za-z0-9+/=_-]{10,}`. Нужен более широкий паттерн: `Bearer <YOUR_HARDCODED_TOKEN>[^ ]*`.

Затронутые файлы:
- `config/skills/software-development/hermes-android-gui/references/hermes-gateway-setup.md`
- `config/skills/software-development/hermes-android-app/references/dual-backend-architecture.md`

## 4. trycloudflare.com в skills

Не конкретные URL Павла, а документация о блокировке сервиса Яндексом.
Оставлены как есть — это знание о pitfalls, не PII.

## 5. Dockerfile — закешированный SHA

`FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:...` может быть недоступен.
Фикс: `docker pull` + `sed` для замены на актуальный SHA.

## Уроки для будущих прогонов

1. Всегда проверять SANITIZATION_LOG.md — он содержит оригиналы
2. Искать `Bearer` с частичным маскированием (`...` в середине ключа)
3. Проверять конфиги санитайзера (sanitize-config.yaml)
4. Не удалять `apps/desktop/` source — только `release/` и `dist/`
5. Не удалять `ui-tui/` и `web/` полностью — нужны заглушки для Dockerfile
