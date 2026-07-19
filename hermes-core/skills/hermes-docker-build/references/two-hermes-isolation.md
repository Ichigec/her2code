# Two Hermes Instances — Root Cause Analysis

> Дата: 2026-06-20

## Проблема

Два экземпляра Hermes (хост-установка + Docker-контейнер) не могут использовать
общую директорию `~/.hermes/`.

## Ресурсы, вызывающие конфликт

| Ресурс | Механизм конфликта | Симптом |
|--------|-------------------|---------|
| `config.yaml` | Чтение/запись обоими экземплярами. Docker-entrypoint модифицирует его (вырезает Telegram) — хост получает сломанный YAML | `YAML error at line 234`, дефолтный конфиг |
| `state.db` | SQLite WAL mode — два писателя создают блокировки | `database is locked`, потеря сессий |
| `logs/gateways/default/` | Два s6-log процесса пытаются писать в один lock-файл | `Resource busy`, dashboard restart loop |
| `skills/` | Оба экземпляра синхронизируют skills при старте | Дубликаты, конфликты |
| `gateway.pid` | Оба пишут PID в один файл | Неверный PID |

## Почему это НЕ баг

Hermes спроектирован как **один экземпляр на машину**. `~/.hermes/` — синглтон.
Docker-образ (`hermes-agent`) предполагает что это **единственный** Hermes на хосте.

## Решение: изолированная data-директория

```bash
mkdir -p ~/.hermes-docker
cp config.yaml.example ~/.hermes-docker/config.yaml
echo 'DEEPSEEK_API_KEY=*** > ~/.hermes-docker/.env
```

И в docker-compose: `~/.hermes-docker:/opt/data` (а не `~/.hermes`).

## Что это даёт

- Своя `state.db` — нет конфликтов сессий
- Свой `config.yaml` — можно безопасно модифицировать (Telegram и т.д.)
- Свои `logs/` — нет блокировок
- Свои `skills/` — независимая синхронизация
- Свой `.env` — отдельные API ключи

## Для конечного пользователя (GitHub)

Пользователь, клонирующий her2code/ с GitHub, НЕ имеет существующего `~/.hermes/`.
Он создаёт `~/.hermes-docker/` с нуля → никакого конфликта.
Проблема возникает ТОЛЬКО при попытке запустить Docker-копию на машине где уже работает основной Hermes.
