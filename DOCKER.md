# Docker Deployment Guide — Hermes Stack

> Пошаговая инструкция разворачивания всего стека Hermes в Docker.

## Быстрый старт (5 минут)

```bash
# 1. Клонировать репозиторий
git clone <repo-url> && cd her2code

# 2. Скопировать и настроить конфигурацию
cp config/.env.docker .env
cp config/config.yaml.example ~/.hermes/config.yaml

# 3. Отредактировать .env — добавить API-ключ
nano .env  # DEEPSEEK_API_KEY=sk-... или OPENAI_API_KEY=sk-...

# 4. Запустить стек
docker compose up -d

# 5. Проверить
curl http://localhost:18648/health
# → {"status": "ok"}

# 6. Neo4j Browser (графовая БД)
open http://localhost:7474  # логин: neo4j, пароль: changeme
```

## Состав стека

| Сервис | Порт | Назначение |
|--------|:----:|------------|
| **hermes** | 18648 | AI Agent Gateway + REST API |
| **proxy** | 18648 | Прокси (добавляет /api/status для Desktop GUI) |
| **neo4j** | 7474, 7687 | Графовая БД (отдельный запуск) |
## Пошаговая настройка

### Шаг 1: Конфигурация

Создайте `~/.hermes/config.yaml` из шаблона:

```bash
mkdir -p ~/.hermes
cp config/config.yaml.example ~/.hermes/config.yaml
```

Настройте провайдера LLM в `~/.hermes/config.yaml`:

```yaml
model:
  default: deepseek-v4-pro
  provider: deepseek
```

### Шаг 2: Переменные окружения

Файл `.env` в корне `her2code/`:

```bash
# Обязательно — хотя бы один ключ
DEEPSEEK_API_KEY=sk-your-deepseek-key
# или
OPENAI_API_KEY=sk-your-openai-key
# или
ANTHROPIC_API_KEY=sk-ant-your-key

# Опционально
NEO4J_PASSWORD=changeme          # пароль Neo4j
API_SERVER_KEY=sk-local           # ключ API-сервера Hermes
```

### Шаг 3: Neo4j (опционально)

Neo4j поднимается автоматически. Для инициализации Education Graph:

```bash
# После запуска стека, инициализировать схему
docker exec hermes-neo4j cypher-shell -u neo4j -p changeme \
  -f /import/education_graph.cypher
```

### Шаг 4: MCP-серверы

После запуска Hermes подключит MCP-серверы автоматически согласно `config.yaml`:

- **claw-graph** — каталог инструментов в Neo4j
- **education-graph** — knowledge graph (сущности, факты)
- **graph-tool** — гибридный поиск + графовые операции
- **searchbox** — 15 поисковых движков (требует Docker-контейнер `openwebui-searchbox`)

### Шаг 5: Проверка работоспособности

```bash
# Health check
curl http://localhost:18648/health

# Список моделей
curl -H "Authorization: Bearer *** http://localhost:18648/v1/models"

# Тестовый запрос
curl -X POST http://localhost:18648/v1/chat/completions \
  -H "Authorization: Bearer sk-local" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-pro","messages":[{"role":"user","content":"Hello"}]}'

# Neo4j
curl http://localhost:7474
```

## Профили разворачивания

### Минимальный (только Hermes API)

```bash
docker compose up -d
```

### Development (с локальным llama.cpp)

```bash
# Запустить llama.cpp отдельно
cd opencode-plus && ./start-llama-direct.sh

# Затем Hermes в Docker (использует llama.cpp на host)
docker compose up hermes dashboard -d
```

## Устранение неполадок

| Симптом | Решение |
|---------|---------|
| `hermes` не стартует | Проверить `docker compose logs hermes` |
| `401 Unauthorized` | Проверить `API_SERVER_KEY` в `.env` и заголовке `Authorization` |
| Neo4j не отвечает | `docker compose logs neo4j`, проверить память |
| MCP не подключается | Проверить пути в `config.yaml` → `mcp_servers` |
| Нет API-ключа | Отредактировать `.env`, перезапустить: `docker compose restart` |

## Остановка и очистка

```bash
# Остановить
docker compose down

# Остановить и удалить данные Neo4j
docker compose down -v

# Полная очистка (осторожно!)
docker compose down -v
rm -rf ~/.hermes/state.db ~/.hermes/audit.db
```

## Обновление

```bash
git pull
docker compose build --no-cache hermes
docker compose up -d
```

## Безопасность

- **API_SERVER_KEY** обязателен при `API_SERVER_HOST=0.0.0.0`
- **Dashboard** слушает только `127.0.0.1` — для удалённого доступа используйте SSH-туннель:
  ```bash
  ssh -L 9119:localhost:9119 user@host
  ```
- **Neo4j** слушает только `127.0.0.1` — не exposed наружу
- Смените `changeme` на стойкий пароль при production-разворачивании
