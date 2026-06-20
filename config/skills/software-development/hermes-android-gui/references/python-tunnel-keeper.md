# Python SSH Tunnel Keeper — Final Reliable Approach

After extensive failures with shell-based watchdogs (spawn too many processes, can't kill
themselves with pkill) and paramiko reverse forwards (don't actually forward data), the
**Python subprocess wrapper** approach is the only one that works reliably.

## The Problem

Shell watchdogs using `pkill -f "ssh.*-R.*8643"` kill their own terminal process.
Multiple iterations spawn 3-7 zombie SSH sessions. Cron-based watchdogs can't properly
clean up stale sshd-sessions on the VPS.

## The Solution: `tunnel_keeper.py`

```python
#!/usr/bin/env python3
"""SSH tunnel keeper — uses ssh -R with auto-restart."""
import subprocess, time

CMD = [
    "ssh", "-o", "StrictHostKeyChecking=no",
    "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=3",
    "-o", "TCPKeepAlive=yes", "-o", "ExitOnForwardFailure=yes",
    "-R", "0.0.0.0:8643:localhost:8643",
    "root@<YOUR_VPS_IP>",
    "while true; do sleep 30; done"
]

def test():
    try:
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "root@<YOUR_VPS_IP>", "curl -s --max-time 3 http://127.0.0.1:8643/health"],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0 and '"status":"ok"' in r.stdout
    except:
        return False

def main():
    proc = None
    while True:
        if proc is None or proc.poll() is not None:
            if proc:
                print(f"Tunnel died (rc={proc.returncode})", flush=True)
            print("Starting tunnel...", flush=True)
            proc = subprocess.Popen(CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(4)
            print("Tunnel OK" if test() else "Not healthy yet", flush=True)
        time.sleep(10)

if __name__ == "__main__":
    main()
```

## Key differences from previous approaches

| Approach | Result |
|----------|--------|
| Shell pkill + & | Killed terminal — unusable |
| Cron every 1m | Couldn't clean stale VPS sessions, spawned 3-7 processes |
| Watchdog script + $! PID tracking | Race condition — spawned before killing old |
| paramiko `request_port_forward` | Bound port but didn't forward data (empty reply) |
| **Python subprocess wrapper** | ✅ Works — clean lifecycle, health checking, single process |

## Setup on VPS

```bash
# On VPS (one-time):
sed -i 's/#GatewayPorts no/GatewayPorts yes/' /etc/ssh/sshd_config
systemctl reload sshd
echo 'ClientAliveInterval 15' >> /etc/ssh/sshd_config
echo 'ClientAliveCountMax 4' >> /etc/ssh/sshd_config
systemctl reload sshd
```

## Cleanup stale sessions

When things go wrong, manually clean stale sshd-sessions on VPS:
```bash
ssh root@<YOUR_VPS_IP> "ss -tlnp | grep 8643 | grep -oP 'pid=\K\d+' | xargs -r kill"
```
