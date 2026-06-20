# VPS Tunnel Setup — <YOUR_VPS_IP>

## VPS Info
- IP: <YOUR_VPS_IP>
- OS: Debian x86_64, Linux 6.12
- SSH: root@<YOUR_VPS_IP> (key auth: ~/.ssh/id_ed25519)
- VPN: sing-box на порту 443 — НЕ ТРОГАТЬ
- Firewall: INPUT policy ACCEPT (нет блокировок)

## One-time VPS setup

```bash
# GatewayPorts — чтобы ssh -R слушал 0.0.0.0 (не только localhost)
sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config

# Keepalive — чтобы туннель не рвался при неактивности
cat >> /etc/ssh/sshd_config << 'EOF'
ClientAliveInterval 15
ClientAliveCountMax 4
EOF

systemctl reload sshd
```

## Tunnel from Jetson

```bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
    -o ServerAliveCountMax=3 -o TCPKeepAlive=yes \
    -o ExitOnForwardFailure=yes \
    -R 0.0.0.0:8643:localhost:8643 \
    root@<YOUR_VPS_IP> "while true; do sleep 30; done"
```

## Watchdog: /home/user/vps_watchdog.sh

Keeps the tunnel alive. Restarts on failure.

## App default URL

`http://<YOUR_VPS_IP>:8643` in Constants.kt + SettingsDataStore.kt

## Latency

Ping Jetson→VPS: ~0.3ms (VPS nearby, same region)
Phone cellular→VPS: depends on cellular network, typically 50-200ms connect time + API response time
