# Russian DPI/Censorship Landscape — July 2026

Full research report from the session. Covers TSPU capabilities, protocol comparison, config recommendations.

## Threat Timeline

| Date | Event | Impact |
|------|-------|--------|
| 2024 | WireGuard loses ~88% connections | WG handshake fingerprint (fixed 148 bytes) |
| Dec 2025 | TSPU targets SOCKS5, VLESS, L2TP | Protocol-level fingerprinting |
| Feb 2026 | 469 VPN services + 385 protocols blocked | AI traffic analysis deployed |
| Apr 2026 | TSPU blocks fake-TLS (MTProto, partial VLESS) | JA3/JA4 ClientHello fingerprinting |
| May 2026 | Partial block of VLESS, WireGuard, XTLS, gRPC, Hysteria | Broad protocol attack |

## How TSPU Works (2026)

**Source: teleproxy/teleproxy#39 (Apr 2026)**

> Since April 1, 2026, Russian TSPU (state DPI, part of ASBI complex) has been intermittently blocking MTProxy fake-TLS connections, particularly on mobile operators (MTS, Megafon, Beeline, T2, Yota). Home ISPs may be less affected.

**Root cause: client-side detection.** DPI fingerprints the TLS ClientHello via JA3/JA4 hashing. Protocol classified as "TELEGRAM_TLS" by VAS Experts and RDP.RU DPI vendors.

**Server-side mitigations (partial):**
- Custom TLS backend (most effective)
- Real certificate behind proxy (nginx with valid cert)
- ServerHello fragmentation (split handshake into separate TCP segments)
- Wider encrypted data variation (±32 bytes)
- Port 443 only (non-standard ports are suspicious)

**Client-side workarounds (most effective):**
- zapret/zapret2 (Linux, Android root)
- GoodbyeDPI (Windows)
- NoDPI (Android, no root)
- TCP packet fragmentation defeats DPI pattern matching

## XTLS Reality Blocking (Nov 2025)

**Source: XTLS/Xray-core#5332**

> Reality suddenly stopped working. It looks like the protocol itself gets blocked by the government firewall. I suspect the firewall modifies TLS ClientHello during the connection, causing the Xray server to reject it.

**Fix:** Change uTLS fingerprint from `chrome` to `randomized` or `qq`. The firewall modifies/drops packets based on the known Chrome TLS fingerprint.

**Key observation:** "When connecting through the same ISP to another Xray server located in my country (Russia), using the same config except for the SNI, the VPN works without issues. This suggests that only servers outside Russia are affected."

## AmneziaWG 2.0

**Source: dev.to/bivlked (Mar 2026)**

WireGuard fork with protocol-level obfuscation:

- **Dynamic Headers (H1-H4):** Random values from ranges instead of fixed WireGuard message types (1-4)
- **Random Padding (S1-S4):** Breaks fixed-size signatures (init always 148 bytes → 148+S1)
- **CPS (Custom Protocol Signature):** Up to 5 decoy packets before handshake, can mimic QUIC Initial with allowlisted SNI
- **Junk Packets:** Jc random-sized packets before each handshake
- **Speed:** 92 Mbps vs WireGuard 95 Mbps (3% overhead)

Each server gets unique parameter set — no universal DPI signature.

## Protocol Comparison (Source: multiple)

| Protocol | DPI Resistance | Speed | Overhead | Tunnel Type | Russia Status (Jul 2026) |
|----------|:---:|:---:|:---:|:---:|--------|
| **XHTTP + Nginx** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~0% | Proxy | ✅ Best — real TLS + CDN + TLS v1.2 |
| VLESS + Reality (utls=randomized) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~0% | Proxy | ✅ Working |
| Hysteria2 + Salamander | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 5-15% | Proxy | ✅ Working (prefer :8443) |
| AmneziaWG 2.0 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ~12% | Full VPN | ✅ Working |
| ShadowTLS v3 | ⭐⭐⭐ | ⭐⭐⭐ | 10-15% | Proxy | ⚠️ Partial |
| WireGuard | ⭐ | ⭐⭐⭐⭐⭐ | ~4% | Full VPN | ❌ 12% success |
| OpenVPN + obfs4 | ⭐⭐ | ⭐⭐ | ~28% | Full VPN | ❌ Blocked |
| Shadowsocks 2022 | ⭐⭐ | ⭐⭐⭐ | Low | Proxy | ⚠️ Detectable |

## XHTTP Transport (New, Feb 2026)

XHTTP is a transport for VLESS that splits incoming and outgoing traffic into separate connections, defeating TLS-in-TLS detection.

### Advantages over VLESS Reality

| Aspect | XHTTP | VLESS Reality |
|--------|-------|---------------|
| TLS version | **TLS v1.2** (plus TLS v1.3) | TLS v1.3 only |
| Server fingerprint | Real Nginx (via reverse proxy) | uTLS library (detectable) |
| Traffic split | Separate rx/tx connections | Single connection |
| CDN support | ✅ Works through CDNs, domain fronting | ❌ Direct IP only |
| Browser dialer | ✅ Browser creates real TLS | ❌ uTLS simulator |
| Client requirement | v2rayNG/v2raN (not NekoBox) | NekoBox, any client |

### XHTTP Modes

- **packet-up:** Slowest, highest compatibility (works through almost any web server/CDN)
- **stream-up:** Fast, medium compatibility (specific web servers)
- **stream-one:** Full duplex, low compatibility (Nginx grpc_pass / Cloudflare gRPC)

### Important

- NOT supported by official sing-box — requires **Xray-core** (server) or **sing-box-lx**/**sing-box-extended** fork
- NekoBox does NOT support XHTTP — use v2raN/v2rayNG instead
- Versions must match exactly between client and server

**Source:** [Habr article](https://habr.com/en/articles/990208/), [Xray examples](https://github.com/XTLS/Xray-examples/tree/main/VLESS-XHTTP3-Nginx), [sing-box-lx](https://github.com/Leadaxe/sing-box-lx)

## Cross-Protocol Contamination

**Observation:** When TSPU identifies ONE protocol on an IP (e.g., VLESS Reality via DPI probes), it starts degrading ALL protocols running on that same IP — including Hysteria2 on a different port/transport.

**Evidence:** The VPS (<YOUR_VPS_IP>) shows 827+ REALITY invalid connections/day from DPI probe IPs. Hysteria2 (UDP) drops simultaneously even though it uses a completely different transport.

**DPI Probe IPs (observed):**
- `64.62.156.0/24` — DPI scanning infrastructure
- `52.36.131.235` — AWS (DPI probe relay)
- `151.248.89.73` — Russian DPI
- `85.11.167.46` — Russian DPI
- `199.30.231.5` — DPI probe
- `23.105.4.153` — DPI probe
- `172.232.108.36` — DPI probe
- `192.121.71.242` — DPI probe

**Mitigation:**
1. Russian entry VPS (domestic traffic not scanned) → foreign exit
2. CDN fronting (VPS IP hidden behind CDN)
3. IP rotation every 2-4 weeks
4. fail2ban to ban DPI probe IPs (maxretry=50, findtime=600, bantime=3600)

## Hysteria2 Port Strategy

**Do NOT use port 9443** — it's isolated with no adjacent TCP service, making it suspicious:

| Port | Traffic | Next to | Suspicion Level |
|------|---------|---------|:---:|
| 9443 UDP | Hysteria2 | Nothing | 🚩 HIGH |
| 8443 UDP | Hysteria2 | Nginx HTTPS (8443 TCP) | ✅ LOW |
| 443 UDP | QUIC | Nginx/sing-box (443 TCP) | ✅ LOW (but may conflict) |

**Port hopping (optional, sing-box 1.13+):**
```json
"services": [{
  "type": "port_hopping",
  "tag": "hysteria2-hop",
  "inbound": "hysteria2-in",
  "ports": "8443-8553",
  "interval": "30s"
}]
```

## Russian Entry VPS Strategy

**Concept:** Domestic VPS entry → tunnel to foreign VPS exit.

**Why it works:** TSPU does not scan domestic protocol traffic — only cross-border connections are inspected.

**Implementation options:**
1. Simple Shadowsocks on РФ VPS → WireGuard tunnel to foreign VPS
2. sing-box on РФ VPS with outbound pointing to foreign VPS
3. VLESS Reality on РФ VPS masquerading as Russian website

**Cost:** 300-500 RUB/month (Timeweb, RUVDS, Beget, FirstVDS)

## DPI Probe Volume Monitoring

Scale for "REALITY: processed invalid connection" count (24h):

| Count | Status | Action |
|-------|--------|--------|
| <100 | ✅ Normal scanning | None |
| 100-500 | ⚠️ Active interest | Consider rotation prep |
| 500+ | 🚨 Targeted | Rotate keys, change IP, or deploy Russian entry VPS |

## Current Deployed Setup (VPS <YOUR_VPS_IP>, Jul 2026)

| Protocol | Port | Status |
|----------|------|--------|
| VLESS Reality (utls=randomized) | 443 TCP | ✅ Working |
| Hysteria2 + Salamander | 8443 UDP | ✅ Working |
| Nginx (Let's Encrypt) | 80/8443 TCP | ✅ Present (coexists) |

- sing-box 1.13.9 (stock — no XHTTP)
- UUID: `3957c617-0330-4453-bbe2-011a7cdfa0ad`
- Reality SNI: `www.microsoft.com`, 3 short IDs
- Hysteria2 password: 32-char base64
- DNS: 8.8.8.8 + 1.1.1.1, IPv4 only
- DPI probe rate: 800+/day (critical level — IP heavily tracked)

## Key Sources

| # | Title | URL | Key Info |
|---|-------|-----|----------|
| 1 | TSPU blocking fake-TLS | https://github.com/teleproxy/teleproxy/issues/39 | JA3/JA4 detection |
| 2 | XTLS Reality blocked | https://github.com/XTLS/Xray-core/issues/5332 | uTLS randomized fix |
| 3 | VPS for VPN Russia 2026 | https://valebyte.com/en/blog/vps-for-vpn-in-russia-2026-what-works-after-youtube-blocks/ | Protocol comparison |
| 4 | AmneziaWG 2.0 deep dive | https://dev.to/bivlked/amneziawg-20-self-host-an-obfuscated-wireguard-vpn-that-bypasses-dpi-4692 | Technical details |
| 5 | VLESS Reality Guide 2026 | https://github.com/T4lpv/vless-reality-anti-censorship-guide | Architecture |
| 6 | VLESS Protocol Deep Dive | https://plisio.net/cybersecurity/vless-protocol | VLESS Reality still works |
| 7 | NexTunnel protocol comparison | https://nextunnel.com/en/blog/reality-vs-hysteria2-vs-trojan-2026 | Reality vs H2 vs Trojan benchmarks |
| 8 | fscarmen/sing-box | https://github.com/fscarmen/sing-box | Multi-protocol deploy script |
| 9 | sing-box-lx (XHTTP fork) | https://github.com/Leadaxe/sing-box-lx | XHTTP + AmneziaWG 2.0 |
| 10 | sing-box-extended | https://github.com/shtorm-7/sing-box-extended | Extended builds with XHTTP |
| 11 | XHTTP for VLESS overview | https://habr.com/en/articles/990208/ | XHTTP technology explanation |
