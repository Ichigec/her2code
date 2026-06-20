---
name: hermes-android-cellular
description: "Развернуть cellular connectivity для Android Hermes: VPS туннель, SSH reverse, Hermes Gateway API, pitfalls."
version: 1.0.0
metadata:
  hermes:
    tags: [android, cellular, vps, tunnel, ssh, deployment]
    related_skills: [hermes-agent, voice-chat-integration, android-hermes-gui]
---

# Hermes Android Cellular — полная процедура развёртывания

## Архитектура

```
📱 Honor (сотовая) → VPS <YOUR_VPS_IP>:8643 → SSH → Hermes Gateway API (Jetson:8643)
```

## 1. Запуск Hermes Gateway на Jetson

```bash
# Убить старые процессы на порту 8643
fuser -k 8643/tcp

# Запустить Hermes Gateway (API server на 8643)
/home/user/.hermes/hermes-agent/venv/bin/hermes gateway run
```

## 2. SSH reverse tunnel Jetson → VPS

```bash
# Очистить stale сессии на VPS
ssh root@<YOUR_VPS_IP> "fuser -k 8643/tcp"

# Запустить туннель
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
    -o TCPKeepAlive=yes -fN \
    -R 0.0.0.0:8643:localhost:8643 root@<YOUR_VPS_IP>
```

## 3. Проверка

```bash
# Локально
curl http://localhost:8643/health

# Через VPS
curl http://<YOUR_VPS_IP>:8643/health

# С телефона
adb shell /system/bin/curl http://<YOUR_VPS_IP>:8643/health
```

## 4. Watchdog (держать туннель живым)

```bash
while true; do
    if ! curl -s --max-time 3 http://localhost:8643/health | grep -q ok; then
        echo "$(date) RESTART" >> /tmp/hermes_watchdog.log
        fuser -k 8643/tcp 2>/dev/null
        sleep 2
        /home/user/.hermes/hermes-agent/venv/bin/hermes gateway run &
    fi
    sleep 30
done
```

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| **Фоновые процессы умирают** | Hermes Gateway встроен в watchdog, не отдельный процесс |
| **pkill убивает терминал** | `kill <PID>` конкретно, не `pkill -f` |
| **Stale sshd-session на VPS** | `fuser -k 8643/tcp` на VPS перед новым туннелем |
| **Порт 8643 занят unified proxy** | Убить unified_proxy, запустить Hermes Gateway |
| **OpenCode+ step_start вместо текста** | Фильтр в SseClient на Android-клиенте |
| **AGENTS.md не читается** | Читать перед каждой задачей (универсальный + проектный) |
| **Hermes Gateway не видит конфиг порта** | Использовать `platforms.api_server.port` (НЕ `api_server.port`) |
| **Android хранит старые настройки** | `adb shell pm clear com.hermes.gui.debug` |
| **Watchdog плодит туннели** | Оставлять только новейший PID, убивать остальные |

## Диагностика

Полный debug-гайд: `references/ssh-tunnel-debug.md` — пошаговая диагностика
всех симптомов (connection reset, 502, 401, empty reply, connection refused).

## Связанные файлы

- `/home/user/dev/codemes/cellular-tunnel/AGENTS.md` — проектный контекст
- `/home/user/.hermes/config.yaml` — конфиг Hermes (api_server.port: 8643)
- `/home/user/.hermes/logs/gateway.log` — логи
- `references/session-audit-20260613.md` — полный аудит сессии разработки (уроки, таймлайн)
