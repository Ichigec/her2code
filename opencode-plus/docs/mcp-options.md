# OpenCode+ — варианты подключения MCP

MCP в OpenCode — **платформенный слой (C4)**: внешние tool-серверы, не subagents. Конфигурация: `OPENCODE_MCP_SERVERS` (JSON) в [`../.env.opencode`](../../.env.opencode) и [`../docker/opencode/opencode.json`](../../docker/opencode/opencode.json).

## Сравнение вариантов

| Вариант | Конфиг | Сценарий |
| ------- | ------ | -------- |
| **1. Compose SSE (default mesh)** | `OPENCODE_MCP_SERVERS`: searchbox, clawcode-adapter, openhands-adapter | Agent-mesh, cross-delegation |
| **2. Локальный searchbox** | URL `http://searchbox:8090/sse` после `compose.searchbox.yml` | Поиск в промпте, standalone+ |
| **3. Host MCP (`mcp/`)** | `opencode.json`: `mcp.*.type=local`, stdio `python mcp/server.py` | Cursor-style, без Docker DNS |
| **4. Remote OAuth** | `mcp.sentry`, `context7` как в [`arch/comparison/configs/opencode.json`](../../arch/comparison/configs/opencode.json) | Внешние API |
| **5. Запрет self-loop** | **Не** добавлять `opencode-adapter` в MCP list | Cycle-guard (HTTP 429) |

## Рекомендация для OpenCode+ standalone

Минимальный набор — **только searchbox** (вариант 2). Mesh-адаптеры подключайте после `agent-mesh-demo-ru.sh`.

Пример минимального JSON в `opencode+/.env`:

```env
OPENCODE_MCP_SERVERS=[{"name":"searchbox","type":"sse","url":"http://searchbox:8090/sse"}]
```

Перезапуск: `bash opencode+/stop-all.sh && bash opencode+/start-opencode.sh`.

## Вариант 1 — Compose SSE (agent-mesh)

Default в [`../.env.opencode.example`](../../.env.opencode.example):

```json
[
  {"name":"searchbox","type":"sse","url":"http://searchbox:8090/sse"},
  {"name":"clawcode-adapter","type":"sse","url":"http://clawcode-adapter:8790/sse"},
  {"name":"openhands-adapter","type":"sse","url":"http://openhands-adapter:8791/sse"}
]
```

Требует `llm-stack-net` и сервисы из `compose.agents-mesh.yml`. Адаптеры дают делегирование в Claw/OpenHands без прямого доступа к их TUI.

## Вариант 2 — Searchbox only

Поднимите searchbox:

```bash
cd /path/to/repo
docker compose --env-file .env -f compose.searchbox.yml up -d
```

OpenCode в той же сети резолвит `searchbox:8090`.

## Вариант 3 — Host stdio MCP

Для процессов **вне** Docker DNS добавьте в кастомный `opencode.json` (не перезаписывая шаблон в образе без mount):

```json
{
  "mcp": {
    "local-tools": {
      "type": "local",
      "command": ["python", "mcp/server.py"],
      "cwd": "/workspace/project"
    }
  }
}
```

Удобно для скриптов на хосте; в нашем Docker-wrap чаще используют SSE внутри `llm-stack-net`.

## Вариант 4 — Remote OAuth

Скопируйте фрагменты из [`arch/comparison/configs/opencode.json`](../../arch/comparison/configs/opencode.json) (`mcp.sentry`, `context7`). Токены кэшируются в `OPENCODE_STATE_DIR`.

## Вариант 5 — Cycle-guard (обязательно)

**Никогда** не включайте `opencode-adapter` в `OPENCODE_MCP_SERVERS` для самого opencode — иначе LLM может вызвать себя рекурсивно.

Дополнительно: `X-Agent-Mesh-Depth` и `MAX_NESTED_AGENT_CALLS` в [`docs/agent-mesh.md`](../../docs/agent-mesh.md).

## Опциональный локальный конфиг

Если нужен overlay без правки корня репо, можно смонтировать `opencode+/configs/opencode.local.json` поверх шаблона (вручную в `compose.opencode.yml` — не включено по умолчанию).

## Troubleshooting MCP

| Симптом | Действие |
| ------- | -------- |
| MCP tools пустые | Проверить `docker logs opencode`, JSON в `OPENCODE_MCP_SERVERS` |
| `searchbox` connection refused | `compose.searchbox.yml up -d`, сеть `llm-stack-net` |
| HTTP 429 / loop | Убрать opencode-adapter из MCP; сбросить depth |
| OAuth expired | Очистить кэш в `~/.opencode`, переподключить provider |

См. [architecture-c1-c4.md](architecture-c1-c4.md) для размещения MCP в слое C4.
