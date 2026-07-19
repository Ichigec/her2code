# VPS Reverse SSH Tunnel — Setup & Pitfalls

## Why VPS is the best solution

| Approach | Speed | Stability | URL | Verdict |
|----------|-------|-----------|-----|---------|
| **VPS SSH -R** | 0.3ms ping | TCP, never dies | Permanent | ✅ BEST |
| cloudflared | ~400ms | Dies minutes (QUIC blocked) | Changes | ❌ |
| serveo.net | ~200ms | URL changes on reconnect | Rotates | ❌ |
| localhost.run | ~1000ms | Stable but slow (AWS Virginia) | Changes | ⚠️ |
| ADB reverse | 0ms | USB only | localhost | ⚠️ fallback |

## VPS Setup

On VPS (<YOUR_VPS_IP>, Debian x86_64):
```bash
# 1. Enable GatewayPorts in sshd_config
sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config
systemctl reload sshd

# 2. Add Jetson's SSH public key
# (from Jetson: ssh-copy-id root@<YOUR_VPS_IP>)
```

On Jetson:
```bash
# Tunnel: VPS:8643 → Jetson:8643
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
    -R 0.0.0.0:8643:localhost:8643 root@<YOUR_VPS_IP> \
    "while true; do sleep 30; done"
```

App URL: `http://<YOUR_VPS_IP>:8643`

## VPS existing services (DO NOT TOUCH)

- sing-box VPN on :443 (pid 125197)
- sshd on :22
- No iptables firewall (policy ACCEPT)

## Watchdog approaches (from most to least reliable)

### Approach 1: tunnel_keeper.py (paramiko-based, RECOMMENDED)
Python script at `scripts/tunnel_keeper.py` — uses paramiko SSH client:
- Auto-reconnects on disconnect
- Cleans stale VPS sshd-sessions on restart
- Sends SSH keepalive every 10s via `transport.send_ignore()`
- Check: `pgrep -f tunnel_keeper`

### Approach 2: tunnel_keeper.sh (bash loop, simpler)
```bash
#!/bin/bash
# Check health via VPS curl, restart if dead
while true; do
    if ! ssh root@<YOUR_VPS_IP> "curl -s --max-time 3 http://127.0.0.1:8643/health | grep -q ok"; then
        # Clean stale sessions ON VPS before starting new tunnel
        ssh root@<YOUR_VPS_IP> "ss -tlnp | grep 8643 | grep -oP 'pid=\K\d+' | xargs -r kill"
        # Kill local zombie tunnels (explicit PID, not pkill)
        for pid in $(pgrep -f "ssh.*-R.*8643.*64.188"); do kill "$pid" 2>/dev/null; done
        sleep 1
        # Start fresh
        ssh -fN -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
            -o ExitOnForwardFailure=yes -R 0.0.0.0:8643:localhost:8643 root@<YOUR_VPS_IP>
    fi
    sleep 15
done
```

### Pitfall: pkill killing the terminal
`pkill -f "ssh.*8643"` can match the SSH command in the CURRENT terminal pipeline.
Use explicit `pgrep -f "ssh.*-R.*8643.*64.188"` with the `-R` flag in the pattern to be specific.
Or better: iterate `for pid in $(pgrep ...); do kill $pid; done` — safe, explicit kill per PID.

## Testing cellular from the agent's side

Phone is on cellular (rmnet_data* interface, WiFi OFF). ADB over USB provides shell access.
`adb shell curl http://<YOUR_VPS_IP>:8643/health` IS testing cellular — the HTTP request
goes over the phone's mobile data connection.

## The "tunnel storm" anti-pattern

On 2026-06-13, the agent wasted ~20 hours trying 7+ tunneling services in sequence:
cloudflared → serveo → localhost.run → pinggy → bore → ngrok → frp → back to cloudflared...

ROOT CAUSE: the user HAD a VPS (<YOUR_VPS_IP>) but never mentioned it until the end.
The agent should have ASKED if the user has any public server before exploring
external services.

LESSON: Before trying ANY external tunneling service, ask: "Do you have a VPS or
public server we can use?" One SSH reverse tunnel to a VPS beats all free services.
