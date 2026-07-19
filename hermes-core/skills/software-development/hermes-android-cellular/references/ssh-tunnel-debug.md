# SSH Tunnel Debug — полная диагностика

## Признаки проблем

| Симптом | Вероятная причина | Проверка |
|---------|-------------------|----------|
| `connection reset` | SSH туннель умер | `ss -tlnp | grep 8643` на Jetson |
| `502 Bad Gateway` | Прокси жив но бэкенд мёртв | `curl localhost:8643/health` |
| `401 Unauthorized` | Неверный ключ API | Проверить `.env` и `config.yaml` |
| `Empty reply from server` | Порт слушается но forwarding сломан | `ssh root@VPS "curl localhost:8643/health"` |
| `Connection refused` | Процесс не запущен | `pgrep -f "hermes gateway"` |
| `Remote end closed` | OpenCode+ не поддерживает не-SSE | Включить `stream: true` |

## Методичная диагностика (всегда в этом порядке)

```bash
# 1. Локальный health check
curl -s --max-time 5 http://localhost:8643/health

# 2. Проверить socat/прокси
ss -tlnp | grep 8643

# 3. Проверить SSH туннель
pgrep -f "ssh.*-R.*8643" | wc -l

# 4. Проверить VPS порт
ssh -o ConnectTimeout=5 root@<YOUR_VPS_IP> "ss -tlnp | grep 8643"

# 5. Проверить forwarding через VPS
ssh root@<YOUR_VPS_IP> "curl -s --max-time 3 http://127.0.0.1:8643/health"

# 6. Проверить извне (сотовая связь)
curl -s --max-time 5 http://<YOUR_VPS_IP>:8643/health

# 7. Проверить с телефона
adb shell /system/bin/curl -s -m 5 http://<YOUR_VPS_IP>:8643/health
```

## Stale sshd-session на VPS

Самая частая причина — после падения SSH туннеля sshd-session на VPS
остаётся висеть и блокирует порт. Новый туннель не может bind.

```bash
# Узнать PID
ssh root@VPS "ss -tlnp | grep 8643"

# Убить принудительно (kill недостаточно!)
ssh root@VPS "fuser -k 8643/tcp"

# Проверить что порт свободен
ssh root@VPS "ss -tlnp | grep 8643 || echo FREE"
```

## Множественные SSH процессы

Watchdog может наплодить туннели. Нужен ровно один.

```bash
# Сколько процессов?
pgrep -cf "ssh.*-R.*8643"

# Оставить только новейший
pids=$(pgrep -f "ssh.*-R.*8643" | sort -n)
latest=$(echo "$pids" | tail -1)
for pid in $pids; do
    [ "$pid" != "$latest" ] && kill "$pid" 2>/dev/null
done
```

⚠️ **Никогда не используй `pkill -f "ssh.*8643"`** — убьёт текущий терминал если
он содержит ssh в командной строке.

## Hermes Gateway не запускается

```bash
# Проверить логи
tail -20 /home/user/.hermes/logs/gateway.log

# Частая ошибка: "Port 8643 already in use"
# Причина: watchdog запустил unified_proxy на 8643 раньше Hermes
# Fix: убить ВСЁ на 8643, затем запустить Hermes
fuser -k 8643/tcp
sleep 2
hermes gateway run

# Другая частая ошибка: неверный ключ конфига
# Правильный ключ: platforms.api_server.port (НЕ api_server.port!)
hermes config set platforms.api_server.port 8648
```

## Android SharedPreferences не обновляются

После изменения дефолтов в коде, старые значения из SharedPreferences
переопределяют новые дефолты.

```bash
# Сбросить все настройки приложения
adb shell pm clear com.hermes.gui.debug

# Или удалить конкретный ключ через настройки в приложении
```
