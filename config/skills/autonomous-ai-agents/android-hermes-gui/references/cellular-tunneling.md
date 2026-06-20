# Cellular Tunneling — Research & Testing Results

## Tested Solutions (June 2026, Jetson GB10 ARM64)

| # | Туннель | Стабильность | HTTPS с телефона | URL меняется | Примечание |
|---|---------|-------------|-------------------|-------------|------------|
| 1 | **Свой VPS (SSH -R)** | ⭐⭐⭐⭐⭐ | ✅ HTTP | ❌ Никогда | **РЕШЕНИЕ.** VPS <YOUR_VPS_IP>, GatewayPorts yes, keepalive. Пинг <1ms. |
| 2 | **localhost.run** (SSH) | ⭐⭐⭐⭐⭐ | ✅ Да | Редко | Запасной. URL привязан к SSH-ключу. |
| 3 | serveo.net (SSH) | ⭐⭐ | ❌ (TLS fail) | Всегда | 502 при реконнекте — URL меняется, старый URL в APK ломается. |
| 4 | cloudflared QUIC | ⭐ | N/A | Всегда | ISP блокирует QUIC (UDP). `timeout: no recent network activity` |
| 5 | cloudflared HTTP2 | ⭐ | ❌ (TLS fail) | Всегда | Умирает через минуты. |
| 6 | Tailscale userspace | N/A | N/A | N/A | Без sudo — только SOCKS5, входящие НЕ работают. |

## Current Architecture: unified_proxy.py

Один процесс управляет всем:
- Слушает порт 8643 напрямую (без socat)
- Встроенный `tunnel_thread()` — авто-перезапуск SSH reverse tunnel
- Маршрутизация: chat-модели → LiteLLM:4000, agent-модели → OpenCode+:8646

```
📱 → http://<YOUR_VPS_IP>:8643 → VPS → SSH → Jetson:8643 → unified_proxy.py
                                                               ├─ chat → LiteLLM:4000
                                                               └─ agent → OpenCode+:8646
```

## SSH Tunnel Pitfalls (из опыта)

| Проблема | Решение |
|----------|---------|
| Stale sshd-session блокирует порт на VPS | `fuser -k PORT/tcp` перед запуском нового туннеля |
| pkill убивает терминал | Использовать `kill PID` по конкретным процессам |
| Множественные watchdog'и конфликтуют | Один процесс: unified_proxy с встроенным tunnel_thread |
| Python subprocess умирает с родителем | bash-цикл с `exec` надёжнее |
| Туннель умирает от неактивности | ServerAliveInterval=5 + TCPKeepAlive=yes |
| VPN на телефоне (sing-box) | НЕ мешает — трафик идёт phone→VPN→VPS:8643 (loopback) |

## VPS SSH Tunnel — Full Setup

### На VPS (одноразово)
```bash
sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config
echo 'ClientAliveInterval 15' >> /etc/ssh/sshd_config
echo 'ClientAliveCountMax 4' >> /etc/ssh/sshd_config
systemctl reload sshd
```

### Keepalive chain
| Параметр | Где | Значение |
|----------|-----|----------|
| ServerAliveInterval | Jetson (клиент) | 5 сек |
| ServerAliveCountMax | Jetson (клиент) | 3 |
| TCPKeepAlive | Jetson (клиент) | yes |
| GatewayPorts | VPS (sshd_config) | yes |
| ClientAliveInterval | VPS (sshd_config) | 15 сек |
| ClientAliveCountMax | VPS (sshd_config) | 4 |

## Testing from Phone

```bash
# Через ADB (сотовая сеть телефона)
$ADB shell "/system/bin/curl -s -m 5 http://<YOUR_VPS_IP>:8643/health"
# Тест chat completions
$ADB shell "/system/bin/curl -s -m 40 -H 'Authorization: Bearer KEY' \
  -d '{\"model\":\"openai/qwen3.6-35b-heretic\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}]}' \
  http://<YOUR_VPS_IP>:8643/v1/chat/completions"
```

**Всегда тестировать через ADB перед тем как сказать пользователю «работает».**
