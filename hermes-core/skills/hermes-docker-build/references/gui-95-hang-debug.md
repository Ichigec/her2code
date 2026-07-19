# GUI 95% Hang — Root Cause & Debugging Recipe

> **Updated:** 2026-07-07 — added `mode=local` as a THIRD distinct cause.
> **Symptom:** Desktop GUI застревает на 95% ("Connecting to Hermes gateway...")

## ТРИ возможные причины (диагностика по порядку)

### Cause 1: `connection.json` mode=local (MOST COMMON)

GUI читает `~/.config/Hermes/connection.json`. Если `mode=local`, GUI пытается
spawn свой gateway вместо подключения к Docker dashboard → виснет на 95%.

**Проверка:**
```bash
cat ~/.config/Hermes/connection.json
# Если "mode": "local" — это причина
```

**Fix:** `start.sh gui` пишет remote `connection.json` автоматически. Или вручную:
```bash
cat > ~/.config/Hermes/connection.json << 'EOF'
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:9122",
    "token": {"value": "sk-docker-b"},
    "authMode": "token"
  },
  "profiles": {}
}
EOF
```

**Env vars НЕ работают** — `HERMES_DESKTOP_REMOTE_URL`/`HERMES_DESKTOP_REMOTE_TOKEN`
игнорируются GUI (проверено 2026-06-22 и 2026-07-07). Только `connection.json`.

### Cause 2: tui_gateway ModuleNotFoundError

Dashboard не может импортировать `tui_gateway` → WebSocket `/api/ws` → 500 → GUI виснет.

**Проверка:**
```bash
docker exec hermes-dashboard python3 -c "from tui_gateway.ws import handle_ws; print('OK')"
# Если ModuleNotFoundError — это причина
```

**Fix:** Скопировать `tui_gateway/` на persistent volume + `PYTHONPATH=/opt/data`.
См. `references/tui-gateway-module-fix.md`.

### Cause 3: Неправильный формат connection.json

Токен-строка вместо объекта или плоская структура → `decryptDesktopSecret()` возвращает `""` → 401.

**Проверка:**
```bash
cat ~/.config/Hermes/connection.json | python3 -c "
import sys,json; d=json.load(sys.stdin)
t = d.get('remote',{}).get('token','')
print('TOKEN OK' if isinstance(t, dict) and t.get('value') else 'TOKEN BROKEN')
"
```

**Fix:** Правильный формат — `token` как объект `{"value": "sk-docker-b"}`, НЕ строка.
Вложенная структура `remote.url`, НЕ плоская `url` на верхнем уровне.

## Диагностический flowchart

```
GUI висит на 95%
    │
    ├─ connection.json mode=local? ── ДА ──→ Write remote connection.json
    │                                         (start.sh gui делает это автоматически)
    │
    ├─ tui_gateway импортируется? ── НЕТ ──→ Copy tui_gateway to /opt/data
    │                                          + PYTHONPATH=/opt/data
    │
    └─ token в connection.json объект? ── НЕТ ──→ Переписать с {"value":"..."}
```

## Поток токена в Electron main process

```
resolveRemoteBackend() (main.cjs:4004)
  → env: HERMES_DESKTOP_REMOTE_URL + HERMES_DESKTOP_REMOTE_TOKEN  ← НЕ РАБОТАЕТ на практике
  → connection.json: readDesktopConnectionConfig() → config.remote.token
  → buildRemoteConnection(url, authMode, token, source)
    → {token, wsUrl: buildGatewayWsUrl(baseUrl, token)}
  
startHermes() → connection
  → hermes:api IPC handler → connection.token → fetchJson(url, token)
    → headers: {'X-Hermes-Session-Token': token}
```

## Ключевые функции (main.cjs)

| Функция | Строка | Роль |
|---------|--------|------|
| `readDesktopConnectionConfig()` | 3756 | Читает `parsed.remote` (не `parsed`) |
| `decryptDesktopSecret()` | 3702 | Требует `typeof secret === 'object'` |
| `buildGatewayWsUrl()` | connection-config.cjs:65 | Строит `ws://host/api/ws?token=...` |
| `resolveRemoteBackend()` | 4004 | Приоритет: profile → env → global |
| `fetchJson()` | 2321 | Шлёт `X-Hermes-Session-Token` header |
