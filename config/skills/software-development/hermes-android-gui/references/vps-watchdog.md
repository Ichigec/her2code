# VPS Tunnel Watchdog

Скрипт авто-перезапуска SSH reverse tunnel к VPS. Запускать на Jetson.

## Файл: `/home/user/vps_watchdog.sh`

```bash
#!/bin/bash
# VPS tunnel watchdog — keeps SSH reverse tunnel alive
LOG="/tmp/vps_tunnel_watchdog.log"

while true; do
    if ! pgrep -f "ssh.*-R.*8643.*<YOUR_VPS_IP>" > /dev/null; then
        echo "$(date): Tunnel dead, restarting..." >> "$LOG"
        ssh -o StrictHostKeyChecking=no \
            -o ServerAliveInterval=5 \
            -o ServerAliveCountMax=3 \
            -o TCPKeepAlive=yes \
            -o ExitOnForwardFailure=yes \
            -R 0.0.0.0:8643:localhost:8643 \
            root@<YOUR_VPS_IP> "while true; do sleep 30; done" &
        echo "$(date): Started PID $!" >> "$LOG"
    fi
    sleep 30
done
```

## VPS настройка (один раз)

```bash
# GatewayPorts — разрешить внешние подключения к forwarded порту
sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config
# Keepalive на стороне сервера
echo 'ClientAliveInterval 15' >> /etc/ssh/sshd_config
echo 'ClientAliveCountMax 4' >> /etc/ssh/sshd_config
systemctl reload sshd
```

## Важно: чистить зомби-туннели

Watchdog может наплодить несколько ssh-процессов. Чистить периодически:
```bash
# Оставить только последний
LATEST=$(pgrep -f "ssh.*-R.*8643" | tail -1)
for pid in $(pgrep -f "ssh.*-R.*8643"); do
    [ "$pid" != "$LATEST" ] && kill $pid 2>/dev/null
done
```
