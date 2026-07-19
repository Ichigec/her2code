# Docker containers accessing host llama-server ports through UFW+nftables

## Problem

Docker containers (LiteLLM on `llm-stack-net` bridge, 172.18.0.0/16) cannot
reach llama-server instances listening on host ports 8101-8103 (0.0.0.0).
Host itself can `curl localhost:8102` fine. DNS resolves (`host.docker.internal`
→ 172.17.0.1) but TCP connections time out.

## Root cause

On ARM64 Jetson with nftables backend:

1. `iptables-legacy` shows empty FORWARD with policy ACCEPT — **misleading**.
2. `iptables-nft` shows the real picture: FORWARD policy **DROP**, UFW chains
   active via nftables.
3. Docker bridge traffic from 172.18.0.0/16 to host IP (172.17.0.1) goes
   through **INPUT chain** (not FORWARD) because 172.17.0.1 is a local address
   on the host's docker0 interface.
4. INPUT (policy DROP) → ufw-before-input → ufw-not-local → ufw-user-input
   — no rule allows ports 8101-8103 from Docker subnets → dropped.

Also: alpine iptables in Docker returns `Failed to initialize nft: Protocol
not supported` on ARM64 — must use host's nft binary via nsenter.

## Fix

### Temporary (kernel only — lost on reboot)

```bash
# Via privileged Docker container with host nsenter:
docker run --rm --privileged --pid=host --network host --platform linux/arm64 \
  -v /usr:/host-usr:ro \
  -v /lib/aarch64-linux-gnu:/lib/aarch64-linux-gnu:ro \
  -v /lib/ld-linux-aarch64.so.1:/lib/ld-linux-aarch64.so.1:ro \
  alpine:latest sh -c '
NFT="/host-usr/sbin/nft"
nsenter -t 1 -n -- $NFT add rule ip filter INPUT \
    ip saddr 172.17.0.0/16 tcp dport {8101,8102,8103} accept
nsenter -t 1 -n -- $NFT add rule ip filter INPUT \
    ip saddr 172.18.0.0/16 tcp dport {8101,8102,8103} accept
nsenter -t 1 -n -- $NFT add rule ip filter DOCKER-USER \
    ip saddr 172.18.0.0/16 ip daddr 172.17.0.1 tcp dport {8101,8102,8103} accept
'
```

### Persistent (survives reboot)

```bash
sudo nft list ruleset > /etc/nftables.conf
```

Or via Docker if sudo unavailable:

```bash
docker run --rm --privileged --pid=host --network host --platform linux/arm64 \
  -v /usr:/host-usr:ro \
  -v /lib/aarch64-linux-gnu:/lib/aarch64-linux-gnu:ro \
  -v /lib/ld-linux-aarch64.so.1:/lib/ld-linux-aarch64.so.1:ro \
  -v /etc:/host-etc:rw \
  alpine:latest sh -c '
nsenter -t 1 -n -- /host-usr/sbin/nft list ruleset > /tmp/ruleset
cp /tmp/ruleset /host-etc/nftables.conf
'
```

## Verification

```bash
# From inside litellm container:
docker exec litellm python3 -c "
import socket
s = socket.socket(); s.settimeout(3)
s.connect(('host.docker.internal', 8102))
print('TCP OK')
s.close()
"

# Full chat test:
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-local" \
  -H "Content-Type: application/json" \
  -d '{"model":"agents-a1-abliterated","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

## Diagnostic commands

```bash
# Which iptables backend is Docker using?
docker run --rm --privileged --pid=host --network host --platform linux/arm64 \
  -v /usr:/host-usr:ro -v /lib/aarch64-linux-gnu:/lib/aarch64-linux-gnu:ro \
  -v /lib/ld-linux-aarch64.so.1:/lib/ld-linux-aarch64.so.1:ro \
  alpine:latest sh -c '
echo "=== iptables-legacy ==="
nsenter -t 1 -n -- /host-usr/sbin/xtables-legacy-multi iptables -L FORWARD -n | head -3
echo "=== iptables-nft ==="
nsenter -t 1 -n -- /host-usr/sbin/xtables-nft-multi iptables -L FORWARD -n | grep policy
'

# Check nftables INPUT chain
docker run --rm --privileged --pid=host --network host --platform linux/arm64 \
  -v /usr:/host-usr:ro \
  alpine:latest sh -c '
nsenter -t 1 -n -- /host-usr/sbin/nft list chain ip filter INPUT 2>&1 | head -5
'
```

## Key pitfalls

- `iptables-legacy` and `iptables-nft` see **different rule tables**.
  legacy shows ACCEPT; nft shows DROP. Always check both.
- Container traffic to `host.docker.internal` (→ 172.17.0.1) hits INPUT,
  not FORWARD, because the destination is a local address.
- Alpine `iptables` in Docker returns `Protocol not supported` on ARM64 —
  use host binary via `nsenter` + volume mounts.
- nftables rules added via `nft add rule` are **ephemeral** — lost on reboot.
  Save with `nft list ruleset > /etc/nftables.conf`.
