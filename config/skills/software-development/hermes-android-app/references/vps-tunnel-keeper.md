# VPS SSH Tunnel Keeper

## The problem

SSH reverse tunnels (`ssh -R`) die unpredictably:
- SSH connection drops (network hiccup)
- VPS sshd kills idle sessions
- Multiple tunnel processes accumulate (race conditions)
- Keepalive alone insufficient

## The solution: Bash watchdog (`tunnel_keeper.sh`)

Store at `/home/user/tunnel_keeper.sh`, run as background process.

### Why bash, not Python?

- **paramiko**: `request_port_forward()` establishes the tunnel but doesn't forward traffic. Incoming connections time out with "empty reply from server"
- **Python subprocess**: `pkill -f "ssh.*8643"` inside the Python script kills the script's own ssh process (the one connecting to VPS for health checks)
- **Bash**: `pgrep -f "ssh.*-R.*8643"` only matches the tunnel process (has `-R` flag), not the health-check ssh process

### The script

```bash
#!/bin/bash
while true; do
    if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
        root@<YOUR_VPS_IP> "curl -s --max-time 3 http://127.0.0.1:8643/health | grep -q ok" 2>/dev/null; then
        # Tunnel dead — cleanup and restart
        for pid in $(pgrep -f "ssh.*-R.*8643.*64.188"); do
            kill "$pid" 2>/dev/null
        done
        ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@<YOUR_VPS_IP> \
            "ss -tlnp | grep 8643 | grep -oP 'pid=\K\d+' | xargs -r kill" 2>/dev/null
        sleep 1
        ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
            -o ServerAliveCountMax=3 -o TCPKeepAlive=yes \
            -o ExitOnForwardFailure=yes -fN \
            -R 0.0.0.0:8643:localhost:8643 root@<YOUR_VPS_IP> 2>/dev/null
        sleep 2
    fi
    sleep 15
done
```

### Launch

```bash
chmod +x /home/user/tunnel_keeper.sh
# MUST use exec to avoid zombie shell process
exec /home/user/tunnel_keeper.sh
```

Can also be run as Hermes background process (`terminal background=true`).

### Why NOT `cron`?

Cron every 1-2 minutes is too slow. The tunnel can die and users see "connection error" for up to 2 minutes before cron fixes it. 15-second check loop catches failures fast.

### Verification

```bash
# From any machine
curl -s http://<YOUR_VPS_IP>:8643/health
# → {"status":"ok","platform":"opencode+","agent_count":10}

# From phone (via ADB, cellular connection)
adb shell "/system/bin/curl -s -m 5 http://<YOUR_VPS_IP>:8643/health"
```
