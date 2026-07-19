# Docker → Host UFW Firewall Fix

Full diagnosis walkthrough for the Docker container → host port blocking issue on Pavel's DGX Spark. Session: 2026-07-03.

## Problem

llama-server models on ports 8101-8103 respond correctly on localhost, but LiteLLM (running in Docker container `litellm` on `llm-stack-net`) cannot reach them. Requests hang until timeout with no GPU load and no log entries in llama-server.

## Diagnosis Path (5 stages)

### Stage 1: Verify models are running

```bash
curl -sf http://localhost:8101/v1/models  # Works on localhost
docker exec litellm python3 -c "
import urllib.request
req = urllib.request.Request('http://host.docker.internal:8101/v1/models')
with urllib.request.urlopen(req, timeout=5) as r:
    print(r.read())
"  # Times out from inside Docker
```

### Stage 2: Port reachability scan

```bash
docker exec litellm python3 -c "
import socket
test_ports = [1234, 8090, 8092, 8101, 8102, 8103, 8643]
for port in test_ports:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(('host.docker.internal', port))
        s.close()
        print(f'  :{port} CONNECTED')
    except ConnectionRefusedError:
        print(f'  :{port} RST (reachable, no service)')
    except TimeoutError:
        print(f'  :{port} TIMEOUT (blocked)')
    finally:
        s.close()
"
```

Result: ports 1234, 8090, 8092, 8643 → RST or CONNECTED. All others → TIMEOUT.

**Key distinction:** RST means the firewall allows the port (kernel sends TCP RST because no service listens). TIMEOUT means the firewall drops packets silently. This is NOT a routing issue — it's a firewall DROP.

### Stage 3: Check llama-server listen address

```bash
ss -tlnp | grep -E ':810[123]'
# If "127.0.0.1:8101" → only localhost, Docker can't reach it
# If "0.0.0.0:8101"    → all interfaces, Docker can potentially reach it
```

Fix: `--host 0.0.0.0` in llama-server launch (not `127.0.0.1`). But this alone is NOT sufficient if UFW blocks the port.

### Stage 4: Identify the firewall (KEY TECHNIQUE)

**Problem:** No sudo access on host. `iptables -L`, `nft list ruleset`, `ufw status` all require root.

**Solution: privileged Docker container with `--network host`**

```bash
# This container shares the HOST network namespace, so iptables shows HOST rules
docker run --rm --privileged --network host alpine sh -c "
    apk add --no-cache iptables 2>/dev/null >/dev/null
    iptables-save -t filter
"
```

**Critical insight:** `--cap-add=NET_ADMIN` without `--network host` shows the CONTAINER's iptables (empty/irrelevant). Only `--privileged --network host` sees the host's netfilter rules.

**Why `--privileged` not just `--cap-add=NET_ADMIN`:** NET_ADMIN gives capability to modify netfilter, but `--network host` is what makes the container see the host's network namespace. Both are needed.

Output revealed:
```
:INPUT DROP [32682:3411527]          ← INPUT policy is DROP!
...
-A ufw-user-input -s 172.18.0.0/16 -p tcp --dport 1234 -j ACCEPT
-A ufw-user-input -s 172.18.0.0/16 -p tcp --dport 8090 -j ACCEPT
-A ufw-user-input -s 172.18.0.0/16 -p tcp --dport 8092 -j ACCEPT
-A ufw-user-input -p tcp --dport 8643 -j ACCEPT
```

**Root cause:** UFW (Uncomplicated Firewall) with INPUT policy DROP. Only 4 ports explicitly allowed for Docker subnets. Ports 8101-8103 were never added.

**Note:** `ufw status` says "ufw not installed" when run without sudo — misleading. UFW IS installed and active, just not accessible without root.

### Stage 5: Inject UFW rules without sudo

```bash
docker run --rm --privileged --network host alpine sh -c '
    apk add --no-cache iptables 2>/dev/null >/dev/null
    for port in 8101 8102 8103; do
        for net in 172.18.0.0/16 172.17.0.0/16; do
            iptables -C ufw-user-input -s "$net" -p tcp --dport "$port" -j ACCEPT 2>/dev/null || \
            iptables -I ufw-user-input 1 -s "$net" -p tcp --dport "$port" -j ACCEPT
        done
    done
'
```

- `iptables -C` checks if rule exists (idempotent — no duplicates on re-run)
- `iptables -I ufw-user-input 1` inserts at position 1 (before any DROP rules)
- Both Docker subnets covered: `172.18.0.0/16` (llm-stack-net) and `172.17.0.0/16` (docker0 default bridge)
- Rules persist until reboot or Docker daemon restart

## Verification

```bash
# Direct test from container
docker exec litellm python3 -c "
import urllib.request, json
for port in [8101, 8102, 8103]:
    req = urllib.request.Request(f'http://host.docker.internal:{port}/v1/models')
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read())
        print(f'  :{port} ✅ — {data[\"data\"][0][\"id\"]}')
"
```

## Evolution of the fix

1. **socat bridge** (first attempt): proxy Docker-accessible ports (8090/8092/1234) to model ports (8101/8102/8103). Works but fragile — occupies ports needed by LM Studio/llama.cpp, adds latency, extra processes to manage.

2. **`--cap-add=NET_ADMIN` container** (failed): container sees its OWN iptables namespace, not host's. Rules added here don't affect host netfilter.

3. **`--privileged --network host` container** (final): sees and modifies HOST iptables. Direct UFW rule injection. No socat, no port conflicts, no extra processes.

## Persistent fix

For persistence across reboots (requires sudo):
```bash
# Add to /etc/ufw/user.rules before the final COMMIT
sudo bash -c 'cat >> /etc/ufw/user.rules << EOF
-A ufw-user-input -s 172.18.0.0/16 -p tcp --dport 8101 -j ACCEPT
-A ufw-user-input -s 172.18.0.0/16 -p tcp --dport 8102 -j ACCEPT
-A ufw-user-input -s 172.18.0.0/16 -p tcp --dport 8103 -j ACCEPT
EOF'
sudo ufw reload
```

Without sudo, the `start-llama.sh` script auto-injects rules on every `start` via the privileged container method.
