# YAML Pitfall: `***` в docker-compose.yml

> Проблема и решение (2026-06-19)

## Симптом

```yaml
environment:
  - API_SERVER_KEY=***  - GATEWAY_ALLOW_ALL_USERS=true
```

После `write_file` или `patch` две переменные сливаются в одну строку.

## Причина

`***` — валидный YAML-синтаксис (альясы/якоря). Парсер YAML интерпретирует три звёздочки особым образом, и следующие за ними символы могут «приклеиться».

## Решение

```yaml
environment:
  - "API_SERVER_KEY=***"
  - GATEWAY_ALLOW_ALL_USERS=true
```

**Всегда использовать двойные кавычки** для значений с `***`.

## Исправление слитых строк

`sed` и `patch` не справляются — YAML-парсер в Hermes перезаписывает файл. Использовать Python:

```python
c = open('docker-compose.yml').read()
c = c.replace('API_SERVER_KEY=***      - GATEWAY', 'API_SERVER_KEY=***\n      - GATEWAY')
open('docker-compose.yml', 'w').write(c)
```
