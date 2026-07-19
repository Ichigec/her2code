# Session Audit: Cellular Connectivity Debugging (2026-06-13)

## Timeline
- **Duration**: ~2 дня
- **Messages**: 1374 (3 сессии)
- **Wasted**: ~16-25 часов на тупиковые решения
- **Final architecture**: 📱 → VPS:8643 → SSH → Hermes Gateway API (прямой)

## What Went Wrong

### 1. Over-engineering (80% времени)
Вместо простого `hermes gateway run` на 8643 построили:
```
socat → unified_proxy → LiteLLM/OpenCode+ routing → watchdog → SSH tunnel keeper
```
5 слоёв там, где нужен был 1.

### 2. Не читали конфиг
`platforms.api_server.port: 8643` уже был настроен. Но `AGENTS.md` не прочитан до начала задачи.

### 3. pkill убивал терминал
Каждый чистящий запуск → `pkill -f` → терминал падал → перезапуск → снова pkill → бесконечный цикл.

### 4. Фоновые процессы умирали
`terminal(background=true)` без `exec` → SIGTERM при закрытии сессии. 15+ watchdog'ов спавнились и конфликтовали.

### 5. Конфликт портов
8643 хотели: unified proxy, Hermes Gateway API, socat, tcp_proxy. Все боролись за один порт.

## What Worked

### Final Architecture
```
📱 → VPS:8643 → SSH → Jetson:8643 → Hermes Gateway API
```
Один процесс. Никаких прокси. Hermes сам маршрутизирует модели.

### Hermes Gateway Watchdog
```bash
while true; do
    if ! curl -s --max-time 3 http://localhost:8643/health | grep -q ok; then
        fuser -k 8643/tcp 2>/dev/null
        sleep 2
        ~/.hermes/hermes-agent/venv/bin/hermes gateway run &
    fi
    sleep 30
done
```

### Critical Commands
```bash
# Очистка stale VPS сессий
ssh root@<YOUR_VPS_IP> "fuser -k 8643/tcp"

# Проверка всей цепочки
curl localhost:8643/health && curl <YOUR_VPS_IP>:8643/health
```

## Preventive Measures (Implemented)

| Layer | What | File |
|-------|------|------|
| Pre-flight | Neo4j health, memory staleness | `hooks/preflight-check.py` |
| AGENTS.md | Auto-inject pitfalls + env | `hooks/inject-agents-md.py` |
| Skill router | 8-domain auto-load | `hooks/skill-router.py` |
| Workspace | Per-project AGENTS.md | `~/dev/codemes/*/AGENTS.md` |
| Neo4j | Vector search for skills | `embed_skills.py` |
