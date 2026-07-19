# GUI Docker Testing Workflow — Complete Recipe

> Condensed from 2026-07-07 session. User corrected twice: "после первой и второй команды открывается локальное окружение, а не докер окружение."
> Root cause: `connection.json` must be switched to `remote` mode BEFORE launching GUI.

## Architecture recap

```
mode: "local" (default):
  Electron GUI ──WS──► Dashboard (:9120) ──► Gateway (:8643)
                         ↑ GUI spawn'ит сам     ↑ dashboard spawn'ит

mode: "remote":
  Electron GUI ──WS──► Dashboard B (:9121) ──► Gateway B (:18648)
                         ↑ уже запущен отдельно   ↑ уже запущен отдельно
```

GUI подключается к **Dashboard** (не к Gateway). Dashboard предоставляет `/api/ws` (WebSocket) и `/api/status`. Gateway — только REST API (`/health`, `/v1/chat/completions`).

## Предварительно: запустить Docker-окружение

```bash
# 1. Backend B (gateway на порту 18648)
HERMES_HOME=/tmp/hermes-backend2 \
  /home/user/.hermes-docker/hermes-agent/venv/bin/hermes gateway run &

# 2. Dashboard B (на порту 9121) — БЕЗ --skip-build если GUI был пересобран
cd ~/.hermes/hermes-agent && \
  HERMES_HOME=/tmp/hermes-backend2 \
  /home/user/.hermes-docker/hermes-agent/venv/bin/hermes dashboard \
  --port 9121 --host 127.0.0.1 --no-open &

# 3. Проверить что оба живы
curl -s http://127.0.0.1:18648/health
curl -s http://127.0.0.1:9121/api/status | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['gateway_state'])"
```

## КРИТИЧЕСКИЙ ШАГ: переключить connection.json в remote mode

**До запуска GUI** — иначе GUI откроется в local mode (локальный backend :8643):

```bash
# Сохранить текущий
cp ~/.config/Hermes/connection.json ~/.config/Hermes/connection.json.bak

# Переключить на Docker
cat > ~/.config/Hermes/connection.json << 'EOF'
{
  "mode": "remote",
  "remote": {
    "url": "http://127.0.0.1:9121",
    "token": {"value": "sk-docker-b"},
    "authMode": "token"
  },
  "profiles": {}
}
EOF
```

**Формат токена — объект, не строка!** `"token": {"value": "sk-local"}` — правильно. `"token": "sk-local"` — WRONG → `decryptDesktopSecret()` возвращает `""` → 401 на всех REST API.

## Запуск GUI

```bash
hermes gui --skip-build &
```

GUI читает `connection.json` при старте → видит `mode: "remote"` → подключается к Dashboard B (:9121) → Gateway B (:18648).

## Проверка

```bash
# Сообщение в GUI → ответ от Backend B
# Проверить логи Backend B:
tail -f /tmp/hermes-backend2/logs/agent.log
# Должны быть новые строки с "API call #"
```

## Возврат на локальное окружение

```bash
kill $(pgrep -f 'Hermes --no-sandbox') 2>/dev/null
echo '{"mode": "local"}' > ~/.config/Hermes/connection.json
hermes gui --skip-build &
```

## Dashboard launch flags

| Флаг | Зачем | Когда нужен |
|------|-------|-------------|
| `--port 9121` | Порт dashboard | Второй dashboard (основной на :9120) |
| `--host 127.0.0.1` | Bind | Локальный доступ |
| `--no-open` | Не открывать браузер | Всегда для второго dashboard |
| `--skip-build` | Пропустить web build | **НЕ работает после пересборки GUI** — web dist path меняется |
| `--tui` | Включить `/api/ws` WebSocket | Нужно для чата через GUI |
| `--insecure` | Token auth для remote desktop | Нужно для REST API из external clients |

## Pitfalls

### `--skip-build` fails after GUI rebuild

```
✗ --skip-build was passed but no web dist found at:
  .../release/linux-arm64-unpacked/resources/app.asar/dist
  Pre-build first: npm install --workspace web && npm run build -w web
  Or drop --skip-build to build automatically.
```

**Fix:** Убрать `--skip-build` после пересборки GUI. Или заранее: `npm run build -w web`.

### WS 403 Forbidden на Dashboard B

При `auth_required: false` (loopback), WS всё равно проверяет `?token=` query param.
GUI сам получает ticket через REST API и использует его для WS — ручной `curl` с любым токеном даст 403.
Это **ожидаемое поведение**, не баг. GUI работает через свой auth flow.

### `connection.json` leftover remote block

После тестирования в `connection.json` может остаться:
```json
{"mode": "local", "remote": {"url": "http://127.0.0.1:9121", ...}}
```
Mode = local, но remote блок указывает на Dashboard B. Это leftover — не влияет (mode=local игнорирует remote), но грязно. Очистить: `echo '{"mode": "local"}' > ~/.config/Hermes/connection.json`.
