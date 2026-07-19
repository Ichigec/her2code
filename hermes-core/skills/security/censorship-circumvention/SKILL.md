---
name: censorship-circumvention
description: "Configure sing-box VPN servers to bypass DPI/censorship in Russia — VLESS Reality, Hysteria2, AmneziaWG, multi-protocol strategies, TSPU evasion."
version: 1.0.0
tags: [vpn, sing-box, vless, reality, hysteria2, censorship, dpi, russia, tspu]
---

# Censorship Circumvention (sing-box VPN)

## Overview

Configure and optimize sing-box VPN servers for censorship circumvention, primarily in Russia (TSPU/DPI). Covers protocol selection, stealth configuration, multi-protocol fallback, and DPI evasion techniques.

## Trigger Conditions

Load this skill when:
- User asks to configure, optimize, or troubleshoot a VPN/proxy server for Russia
- User asks about VLESS Reality, Hysteria2, AmneziaWG, or other circumvention protocols
- User mentions DPI, TSPU, РКН, censorship bypass
- User asks to add protocols to an existing sing-box server
- User asks «какой VPN работает в России», «обход блокировок»

## Workflow

### 1. Assess Current Setup

Check the VPS for existing sing-box config:

```bash
ssh root@<vps_ip> "cat /etc/sing-box/config.json && sing-box version && ss -tlnp | grep sing-box"
```

Reference the user's existing config document (if any) — often at `dev/sing-box-vpn-setup.md` or similar.

### 2. Research Current Threat Landscape

Russia's TSPU evolves rapidly. Before recommending configs, search for the latest:

```
web_search: "Russia DPI TSPU blocking VLESS Hysteria2 2026"
web_search: "sing-box Reality uTLS fingerprint bypass"
web_search: "обход блокировок РКН VPN протоколы"
```

Key threat intelligence sources:
- https://github.com/teleproxy/teleproxy/issues/39 — TSPU blocking patterns
- https://github.com/XTLS/Xray-core/issues/5332 — uTLS fix for Reality
- https://valebyte.com/en/blog/vps-for-vpn-in-russia-2026-what-works-after-youtube-blocks/ — protocol comparison

**When web_extract fails** (DuckDuckGo backend error), use raw curl:
```bash
curl -sL --max-time 15 -H 'User-Agent: Mozilla/5.0' '<URL>' | python3 -c "
import sys, re
html = sys.stdin.read()
text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
text = re.sub(r'<[^>]+>', ' ', text)
text = re.sub(r'&[a-z]+;', ' ', text)
text = re.sub(r'\s+', ' ', text)
print(text[:8000])
"
```

For GitHub raw content (README, configs): `curl -sL 'https://raw.githubusercontent.com/...'`

### 3. Protocol Selection

**Primary: VLESS + Reality (TCP, port 443)**
- Best stealth: indistinguishable from HTTPS to a real website
- `xtls-rprx-vision` flow for zero overhead
- Requires NO domain — uses borrowed SNI (e.g., `www.microsoft.com`)

**Secondary: Hysteria2 (UDP/QUIC, port 8443+)**
- Different transport — survives TCP-level blocking
- `salamander` obfuscation masks QUIC handshake
- Brutal congestion control maintains throughput under packet loss
- Port hopping: randomize port within range (e.g., 8443-8553)

**Tertiary: AmneziaWG 2.0 (UDP, full VPN tunnel)**
- WireGuard fork with protocol-level obfuscation
- Dynamic headers (H1-H4 random ranges), padding (S1-S4), CPS decoy packets
- ~92 Mbps vs WireGuard 95 Mbps (3% overhead)
- Full VPN tunnel — not just proxy

### 4. VLESS Reality: Critical Configuration

**Mandatory for Russia 2026:**

```json
{
  "type": "vless",
  "listen_port": 443,
  "users": [{
    "uuid": "<UUID>",
    "flow": "xtls-rprx-vision"
  }],
  "tls": {
    "enabled": true,
    "server_name": "www.microsoft.com",
    "reality": {
      "enabled": true,
      "handshake": {"server": "www.microsoft.com", "server_port": 443},
      "private_key": "<PRIVATE_KEY>",
      "short_id": ["<ID1>", "<ID2>", "<ID3>"],
      "max_time_difference": "5m"
    },
    "utls": {
      "enabled": true,
      "fingerprint": "randomized"
    }
  }
}
```

**Why each parameter matters:**

| Parameter | Setting | Rationale |
|-----------|---------|-----------|
| `utls.fingerprint` | `"randomized"` | **CRITICAL.** Russian DPI fingerprints JA3/JA4 of TLS ClientHello. `chrome` is already fingerprinted. `randomized` changes the fingerprint every connection. Alternatives: `randomized_native`, `firefox`, `qq` |
| `short_id` | 3+ values | Rotation when one is compromised without regenerating keys |
| `max_time_difference` | `"5m"` | Clock skew between VPS and client — `1m` is too tight |
| `server_name` | Real, foreign, non-redirecting domain | `www.microsoft.com` is reliable; `dl.google.com` has encrypted post-ServerHello (bonus) |
| Port | `443` ONLY | Non-standard TLS ports are inherently suspicious to DPI |

**uTLS fingerprint priority (stealthiest first):**
1. `randomized` — maximum stealth, different ClientHello each time
2. `randomized_native` — same but via Go crypto/tls (less library fingerprint)
3. `firefox` — most common browser, less targeted than Chrome
4. `qq` — niche browser, unlikely to be fingerprinted
5. `chrome` — CURRENTLY FINGERPRINTED by TSPU (avoid)

### 5. Hysteria2: Configuration

```json
{
  "type": "hysteria2",
  "listen_port": 8443,
  "up_mbps": 100,
  "down_mbps": 100,
  "users": [{"password": "<32-byte-base64>"}],
  "tls": {
    "enabled": true,
    "server_name": "www.microsoft.com",
    "alpn": ["h3"],
    "min_version": "1.3",
    "certificate_path": "/etc/sing-box/fullchain.pem",
    "key_path": "/etc/sing-box/privkey.pem"
  },
  "obfs": {
    "type": "salamander",
    "password": "<16-byte-base64>"
  }
}
```

**Port hopping (optional, added via server-level config):**
```json
// In sing-box top-level config:
"services": [{
  "type": "port_hopping",
  "tag": "hysteria2-hop",
  "inbound": "hysteria2-in",
  "ports": "8443-8553",
  "interval": "30s"
}]
```

Generate passwords:
```bash
openssl rand -base64 32  # user password
openssl rand -base64 16  # salamander obfs password
```

### 6. Multi-Protocol Architecture

Run ALL protocols under ONE sing-box process:

```
VPS :443  → VLESS Reality (TCP, uTLS randomized)
VPS :8443 → Hysteria2 (UDP/QUIC, Salamander obfs)
VPS :8443 → nginx fallback (real HTTPS for active probing)
```

**DNS (sing-box config):**
```json
{
  "dns": {
    "servers": [
      {"type": "udp", "tag": "dns-google", "server": "8.8.8.8"},
      {"type": "udp", "tag": "dns-cf", "server": "1.1.1.1"}
    ],
    "strategy": "ipv4_only"
  }
}
```

**Route (all traffic → direct):**
```json
{
  "route": {
    "final": "direct",
    "default_domain_resolver": {"server": "dns-google", "strategy": "ipv4_only"}
  }
}
```

**IPv6 must be disabled on VPS:**
```bash
sysctl -w net.ipv6.conf.all.disable_ipv6=1
sysctl -w net.ipv6.conf.default.disable_ipv6=1
```

### 7. Client-Side Tools (Extra Protection)

When DPI blocks even Reality on some ISPs, client-side TCP fragmentation helps:

| OS | Tool | Notes |
|----|------|-------|
| Linux | [zapret](https://github.com/bol-van/zapret) | TCP packet fragmentation, defeats DPI pattern matching |
| Windows | [GoodbyeDPI](https://github.com/ValdikSS/GoodbyeDPI) | Same approach |
| Android (no root) | [NoDPI](https://github.com/ValdikSS/nodpi) | Local VPN-based fragmentation |

### 8. Verification

After configuration changes:

```bash
# On VPS:
sing-box check -c /etc/sing-box/config.json
systemctl restart sing-box
ss -tlnp | grep sing-box  # should show :443 and :8443
journalctl -u sing-box -n 30 --no-pager | grep -E 'error|warn|reality|hysteria'
```

```bash
# From client (via SOCKS5 proxy):
curl -x socks5h://127.0.0.1:2080 --connect-timeout 20 http://ipv4.icanhazip.com
# Expected: VPS IP (<YOUR_VPS_IP>)

curl -x socks5h://127.0.0.1:2080 -o /dev/null -w "%{http_code}\n" https://api.telegram.org
# Expected: 200 or 302
```

### 9. Quick Deploy Alternative

For rapid multi-protocol deployment, the [fscarmen/sing-box](https://github.com/fscarmen/sing-box) script (updated July 2026) installs 11 protocols in one command:

```bash
bash <(wget -qO- https://raw.githubusercontent.com/fscarmen/sing-box/main/sing-box.sh) -k
```

After install: `sb -d` (config editor), `sb -n` (node list), `sb -r` (add/remove protocols).

## XHTTP Transport (VLESS) — New Anti-DPI Technology (2026)

**XHTTP** is a transport for VLESS (not a separate protocol) designed specifically to bypass advanced DPI systems. It evolved from Xray's SplitTunnel/meek concept.

### Why XHTTP Matters

| Feature | XHTTP | VLESS Reality | 
|---------|-------|---------------|
| TLS version | **TLS v1.2** (RKN blocks TLS v1.3 to hosting providers) | TLS v1.3 only |
| Server fingerprint | **Real Nginx fingerprint** via reverse proxy | uTLS library (can be detected) |
| Traffic split | **Separate rx/tx connections** — breaks TLS-in-TLS detection | Single connection |
| CDN/proxy compatibility | ✅ Works through CDNs, domain fronting | ❌ Direct IP only |
| QUIC support | ✅ Can use QUIC for one direction, TCP for the other | ❌ |
| Client dialer | ✅ Browser dialer for perfect fingerprint | ❌ |

### Three Modes

| Mode | Speed | Compatibility | Use Case |
|------|-------|---------------|----------|
| `packet-up` | Slowest | Highest — works through almost any web server/CDN | Maximum stealth, high-latency OK |
| `stream-up` | Fast | Medium — specific web servers | Best balance for CDN use |
| `stream-one` | Full duplex | Low — Nginx `grpc_pass` or Cloudflare gRPC | Direct connection, Reality-like |

### Architecture (XHTTP + Nginx)

```
Client (v2rayNG/v2raN)
  │
  ├─ TCP:443 → Nginx (real Let's Encrypt HTTPS, TLS v1.2)
  │                └─ grpc_pass → Xray (VLESS + XHTTP, :7443)
  │
  └─ Fallback: VLESS Reality (direct, if Nginx is filtered)
```

### Implementation

**Server (Xray-core):**
```json
{
  "inbounds": [{
    "listen": "127.0.0.1",
    "port": 7443,
    "protocol": "vless",
    "settings": {
      "clients": [{"id": "<UUID>"}]
    },
    "streamSettings": {
      "network": "xhttp",
      "xhttpSettings": {
        "mode": "stream-up",
        "path": "/xhttp"
      },
      "security": "none"
    }
  }]
}
```

**Nginx frontend (port 443):**
```nginx
server {
    listen 443 ssl http2;
    server_name <your-domain>;
    ssl_certificate /etc/letsencrypt/live/<domain>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<domain>/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    root /var/www/html;  # Real site for cover

    location /xhttp {
        grpc_pass grpc://127.0.0.1:7443;
        grpc_set_header Host $host;
    }
}
```

### Important Caveats

- **NOT supported by official sing-box** — requires **Xray-core** (server) and **v2rayNG/v2raN** (client), or the **sing-box-lx** (Leadaxe) / **sing-box-extended** (shtorm-7) fork
- **NekoBox does NOT support XHTTP** — use v2raN (desktop) or v2rayNG (Android) instead
- **Under active development** — server and client versions must match exactly
- **Not compatible with XTLS-Vision** — protection comes from XMUX multiplexing instead
- **Can be used with XTLS-Reality** (forces stream-one mode)

### References

- Habr article: [A brief overview of XHTTP for VLESS](https://habr.com/en/articles/990208/)
- Xray examples: https://github.com/XTLS/Xray-examples/tree/main/VLESS-XHTTP3-Nginx
- sing-box-lx (XHTTP fork): https://github.com/Leadaxe/sing-box-lx

## Russian Entry VPS + Foreign Exit Architecture

**Concept:** Use a cheap Russian VPS as the entry point (no DPI scans domestic traffic), which tunnels to the foreign VPS (<YOUR_VPS_IP>) as the exit.

```
Клиент → [РФ VPS entry] → [Foreign VPS exit] → Internet
         ^ DPI не сканирует внутрироссийский трафик
```

### Why It Works

1. **Domestic traffic is NOT filtered** by TSPU at the protocol layer — only cross-border traffic is inspected
2. **Any protocol works** for the РФ→foreign hop — even Shadowsocks or plain WireGuard
3. **Foreign VPS IP stays hidden** from DPI — only the domestic VPS is visible
4. **Entry VPS can be cheap** — 300-500 RUB/mo (Timeweb, RUVDS, Beget, FirstVDS)

### Implementation

```bash
# On РФ VPS (entry) — simple sing-box or xray with outbound to foreign
# On Foreign VPS (<YOUR_VPS_IP>) — existing sing-box, unchanged

# WireGuard tunnel between them for backend transport
```

## CDN Fronting for VLESS

Route VLESS traffic through Cloudflare or other CDN to mask the origin IP:

```
Client → Cloudflare CDN → VPS (origin)
SNI: www.example.com     реальный IP скрыт
```

**When to use:** When the VPS IP (`<YOUR_VPS_IP>`) itself is being DPI-targeted. The CDN IP pool is too large to block without collateral damage.

**Limitations:** Cloudflare prohibits VPN/proxy use of its CDN. Works unofficially through WebSocket transport with Cloudflare's proxy enabled (`orange cloud`).

## DPI Probe Monitoring

The number of `REALITY: processed invalid connection` log entries indicates how aggressively your server is being probed by TSPU.

**Baseline:** <100/day = normal scanning  
**Elevated:** 100-500/day = active interest  
**Critical:** 500+/day = targeted, IP likely in DPI database  

If critical: rotate keys, change IP, or move to CDN fronting / Russian entry VPS.

**Mitigation with fail2ban:**
```bash
cat > /etc/fail2ban/filter.d/sing-box-reality.conf << 'EOF'
[Definition]
failregex = .*REALITY: processed invalid connection from <HOST>:\d+
ignoreregex =
EOF

cat > /etc/fail2ban/jail.d/sing-box.conf << 'EOF'
[sing-box-reality]
enabled = true
logpath = /var/log/syslog
filter = sing-box-reality
maxretry = 50
findtime = 600
bantime = 3600
action = iptables-allports[name=REALITY]
EOF
```

## Multiplexing (XMUX / Smux)

**Multiplexing merges multiple proxy streams into one TLS connection**, which:
- Masks TLS-in-TLS patterns that DPI uses to detect proxies
- Reduces connection overhead (one TLS handshake for many streams)
- Works with VLESS Reality (add `multiplex` block to client outbound)

```json
"multiplex": {
  "enabled": true,
  "protocol": "smux",
  "max_streams": 32
}
```

**Important:** NekoBox does not support multiplexing. Use sing-box client or Xray-based client.

**Pitfalls**

1. **uTLS `chrome` is fingerprinted** — TSPU JA3/JA4 hashing identifies Chrome TLS fingerprints. Always use `randomized` or at minimum `firefox`. The Xray-core issue #5332 (Nov 2025) documents: "Russians DPI has received an update that blocks FakeTLS. Set uTLS to randomized."

2. **ServerHello not fragmented** — sing-box Reality doesn't fragment ServerHello by default. If DPI matches on the full response, consider running nginx behind Reality on a fallback port with real TLS cert to make the server look legitimate during active probing.

3. **Single shortId = no rotation** — when DPI identifies and blocks one shortId, you need to change it and update all clients. Have 3+ shortIds configured so you can rotate clients individually.

4. **Hysteria2 without Salamander = detectable QUIC** — the QUIC handshake has recognizable patterns. Always enable `obfs.type: "salamander"`.

5. **Non-port-443 = suspicious** — DPI flags TLS on non-standard ports. Always use 443 for Reality.

6. **IPv6 on VPS = silent failures** — some requests resolve to IPv6 and then hang. Disable IPv6 entirely on the VPS (`sysctl disable_ipv6` + `dns.strategy: ipv4_only`).

7. **web_extract fails with DuckDuckGo backend** — when researching, use raw `curl` with User-Agent + Python HTML stripping. See Step 2 above.

8. **Cross-protocol contamination** — when DPI identifies ONE protocol on an IP (e.g., VLESS Reality), it starts degrading ALL protocols (including Hysteria2) on the same IP, even on different ports/transports. Mitigation: multi-IP architecture (Russian entry VPS), CDN fronting, or IP rotation.

9. **Hysteria2 on port 9443 is suspicious** — avoid isolated non-standard UDP ports. Prefer `8443` UDP (adjacent to HTTPS Nginx) or port hopping range `8443-8553`. UDP on 9443 with no adjacent TCP service flags DPI.

10. **DPI probes accumulate** — 800+/day REALITY invalid connections means the IP is actively tracked. Mitigate with fail2ban, rotate keys every 2-4 weeks, or switch to XHTTP architecture.

## Server-Side Validation & Restart

After any config change, always validate before restart:

```bash
sing-box check -c /etc/sing-box/config.json
systemctl restart sing-box
systemctl status sing-box

# Verify ports
ss -tlnp | grep sing-box   # TCP
ss -ulnp | grep sing-box   # UDP
```

**Rollback:**
```bash
cp /etc/sing-box/config.json.bak.latest /etc/sing-box/config.json
systemctl restart sing-box
```

## NekoBox Client Setup

### VLESS Reality Profile
- TLS Security: `Reality`
- uTLS Fingerprint: **`randomized`** (не `chrome` — РКН fingerprint-ит)
- SNI: `www.microsoft.com` (or `www.apple.com`)
- See [`references/nekobox-setup.md`](references/nekobox-setup.md) for step-by-step profile configuration

### Hysteria2 Share Link
```
hysteria2://PASSWORD@IP:8443?insecure=1&obfs=salamander&obfs-password=OBFS_PASS&sni=www.microsoft.com&alpn=h3#Name
```

## sing-box 1.13.0+ Migration Pitfalls

These config validation errors cost 3+ iterations — always check before `systemctl restart`:

1. **`dns` outbound type REMOVED in 1.13.0** — do NOT include `{"type": "dns", "tag": "dns-out"}` in outbounds. DNS works through route rules.
2. **`transport.type: "tcp"` is NOT valid for VLESS inbound** — VLESS is always TCP. Remove the `transport` block entirely.
3. **`utls` is CLIENT-ONLY** — server-side Reality inbound does NOT accept `utls` field. Configure uTLS fingerprint on the CLIENT (NekoBox, v2rayNG, sing-box client).

## Protocol Comparison (Russia, July 2026)

| Protocol | DPI Resistance | Speed | Status |
|----------|:---:|:---:|--------|
| **XHTTP + Nginx** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ Best option — real TLS, CDN, TLS v1.2 |
| VLESS + Reality (utls=randomized) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ Working |
| Hysteria2 + Salamander | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ Working (prefer :8443 not :9443) |
| AmneziaWG 2.0 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ Working |
| ShadowTLS v3 | ⭐⭐⭐ | ⭐⭐⭐ | ⚠️ Partial |
| Shadowsocks 2022 | ⭐⭐ | ⭐⭐⭐ | ⚠️ Detectable |
| WireGuard | ⭐ | ⭐⭐⭐⭐⭐ | ❌ 12% success |
| OpenVPN + obfs4 | ⭐⭐ | ⭐⭐ | ❌ Blocked |

## References

- User's existing VPN setup: `dev/sing-box-vpn-setup.md` (VLESS Reality, NekoBox client, VPS <YOUR_VPS_IP>)
- Full research report (July 2026): `references/russia-dpi-landscape-2026-07.md`
- Real-time TSPU blocking: https://github.com/teleproxy/teleproxy/issues/39
- XTLS Reality blocking fix: https://github.com/XTLS/Xray-core/issues/5332
- sing-box official docs: https://sing-box.sagernet.org/configuration/
