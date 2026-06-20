# Build Instructions — Hermes Stack

> Как собрать Docker-образ Hermes Agent и запустить стек.

## Проблема

Стандартный `hermes-agent/Dockerfile` использует закешированный SHA базового образа:

```dockerfile
FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:b3c543b6c4...
```

Этот SHA может быть недоступен (истёк, удалён, не поддерживает ARM64).

## Решение 1: Обновить SHA (рекомендуется)

```bash
# 1. Найти актуальный образ
docker pull ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie

# 2. Получить новый SHA
docker inspect ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie \
  --format='{{index .RepoDigests 0}}'

# 3. Заменить первую строку в Dockerfile
sed -i "1s|FROM .*|FROM $(docker inspect ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie --format='{{index .RepoDigests 0}}') AS uv_source|" \
  hermes-agent/Dockerfile
```

## Решение 2: Использовать floating tag (проще, но менее воспроизводимо)

```bash
# Заменить SHA на floating tag
sed -i '1s|FROM .*|FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie AS uv_source|' \
  hermes-agent/Dockerfile
```

## Сборка

```bash
# После исправления Dockerfile:
docker compose build hermes --no-cache

# Или напрямую:
cd hermes-agent
docker build -t hermes-agent .
```

## Запуск

```bash
# Скопировать и настроить .env
cp config/.env.docker .env
nano .env   # добавить DEEPSEEK_API_KEY=*** или OPENAI_API_KEY=***# Запустить
docker compose up -d

# Проверить
curl http://localhost:18648/health
# → {"status": "ok"}
```

## Без Docker

Если Docker не нужен — Hermes уже работает на хосте:

```bash
hermes gateway run
# → http://localhost:8648/health
```

## Примечания

- **ARM64 (Jetson):** образ `astral-sh/uv` должен поддерживать `linux/arm64`
- **x86_64:** проблем с SHA обычно нет, но `--platform linux/amd64` может потребоваться
- **Образ > 2 ГБ:** первый билд тянет все зависимости
- **Neo4j:** запускается отдельно, не требует пересборки:
  ```bash
  docker compose -f config/compose.neo4j.yml up -d
  ```
