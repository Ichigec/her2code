# Cellular Connectivity — Debugging History (June 2026)

## The Goal
Android app must connect to Jetson from cellular network (different subnet, ISP blocks inbound).

## Approaches Tried

### 1. Router Port Forwarding (FAILED)
- TP-Link router at 192.168.0.1, port 8643 TCP → 192.168.0.48:8643
- ISP blocks inbound on residential IP (<YOUR_HOME_IP>)
- Hairpin NAT prevents self-testing
- Verdict: ISP blocks — not fixable

### 2. cloudflared free (FAILED)
- QUIC blocked by ISP (UDP port 7844)
- HTTP2 mode: tunnel created, prechecks PASS, then dies silently (1033 "unable to resolve")
- Multiple instances conflict → stale tunnels
- Verdict: Unstable — dies within minutes even with `--protocol http2 --no-autoupdate`

### 3. serveo.net SSH reverse tunnel (FAILED)
- URL changes on every reconnect → app uses stale URL → 502
- Free tier warning page on first request → 502 on actual first request
- Phone HTTPS fails (old curl certs), HTTP works but tunnel dies
- Verdict: Unreliable — URL rotation is the killer

### 4. localhost.run SSH reverse tunnel (WORKED, but slow)
- Stable SSH connection
- Server in AWS Virginia → 1000ms+ latency
- URL changes on reconnect
- Verdict: Works but too slow for chat

### 5. Own VPS SSH reverse tunnel (FINAL SOLUTION ✅)
- VPS at <YOUR_VPS_IP> (Debian, sing-box VPN on :443 — don't touch)
- SSH key auth (no password)
- GatewayPorts yes on VPS
- Phone connects to http://<YOUR_VPS_IP>:8643
- Ping <1ms, permanent URL
- Keepalive: ServerAliveInterval=5, TCPKeepAlive=yes

## Tunnel Stability Saga

The SSH tunnel kept dying. Root causes found and fixed:

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| "Every second message fails" | OkHttp connection pool reuses closed sockets | `retryOnConnectionFailure(true)` |
| SSE "unexpected end of stream" | OkHttp can't retry streaming bodies | ChatRepository 2-retry loop |
| Watchdog spawns 5+ tunnels | Race in shell script | Python subprocess wrapper |
| paramiko doesn't forward data | `request_port_forward` needs handler | Use `ssh -R` via subprocess |
| Old sshd-sessions block port | Watchdog doesn't clean VPS | Kill stale sessions before restart |

## Phone VPN Interaction
Phone has sing-box VPN (tun1, UP) routing through the SAME VPS.
This is NOT a problem — traffic goes: phone → VPN → VPS → VPS:8643 (loopback) → SSH → Jetson.
VPN doesn't cause connectivity failures. Tunnel dying is the real cause.

## Testing Pattern
NEVER ask user to test. Test via ADB from phone:
```bash
ADB=/home/user/Android/Sdk/platform-tools/adb
# Phone on cellular (WiFi OFF, rmnet_data* = cellular)
$ADB shell "/system/bin/curl -s -m 5 http://<YOUR_VPS_IP>:8643/health"
# Must return {"status":"ok"} before declaring success
```

## Key Lesson
Always ASK about existing VPS before trying tunnel services.
User had VPS at <YOUR_VPS_IP> the whole time — ~20 hours wasted on cloudflared/serveo/localhost.run.
