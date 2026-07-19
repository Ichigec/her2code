# Russia DPI Landscape (2026)

Research notes from July 2026 deep dive. Sources cited inline.

## Threat Model: TSPU

ТСПУ (Technical Means of Countering Threats) — DPI boxes at every major Russian ISP.

### Timeline

| Date | Event | What's blocked |
|------|-------|----------------|
| 2024 | WireGuard loses ~88% connections | WG handshake fingerprint (fixed 148 bytes) |
| Dec 2025 | TSPU attacks SOCKS5, VLESS, L2TP | Protocol fingerprints |
| Feb 2026 | 469 VPN services + 385 protocols blocked | AI traffic analysis |
| Apr 2026 | TSPU blocks fake-TLS | JA3/JA4 fingerprint of ClientHello |
| May 2026 | VLESS, WireGuard, XTLS/XHTTP, gRPC, Hysteria partially blocked | Mass protocol attack |

### Detection Mechanism (April 2026)

**Source:** [teleproxy#39](https://github.com/teleproxy/teleproxy/issues/39)

> "Since April 1, 2026, Russian TSPU has been intermittently blocking MTProxy fake-TLS connections. Root cause: DPI fingerprints the TLS ClientHello via JA3/JA4 hashing. The protocol is classified as 'TELEGRAM_TLS' by both VAS Experts and RDP.RU DPI vendors."

**Source:** [XTLS/Xray-core#5332](https://github.com/XTLS/Xray-core/issues/5332)

> "Russians DPI has received an update that blocks FakeTLS. Set uTLS to `randomized` or `qq`. DPI modifies the TLS ClientHello during connection — server logs show 'failed to read client hello'."

### Counter-measures

1. **uTLS fingerprint randomization** (CLIENT-SIDE): `randomized`, `randomized_native`, `firefox`, `qq` — changes JA3/JA4 every connection
2. **Reality dest to real HTTPS**: nginx with Let's Encrypt cert → DPI active probing sees legitimate website
3. **Salamander obfuscation** (Hysteria2): masks QUIC handshake
4. **Port 443 only**: non-standard ports are suspicious
5. **Multi-protocol**: TCP (VLESS) + UDP (Hysteria2) — if one transport is targeted, the other works

## Protocol Comparison (Russia 2026)

| Protocol | DPI Resistance | Speed | Transport | Tunnel | Status |
|----------|:---:|:---:|:---:|:---:|:---:|
| VLESS + Reality | ⭐⭐⭐⭐⭐ | Fast | TCP | Proxy | ✅ Works |
| Hysteria2 + Salamander | ⭐⭐⭐⭐ | Fast (Brutal) | UDP/QUIC | Proxy | ✅ Works |
| AmneziaWG 2.0 | ⭐⭐⭐⭐ | 92 Mbps | UDP (obf.) | Full VPN | ✅ Works |
| ShadowTLS v3 | ⭐⭐⭐ | Medium | TCP | Proxy | ⚠️ Partial |
| WireGuard | ⭐ (12%) | 95 Mbps | UDP | Full VPN | ❌ Blocked |
| OpenVPN + obfs4 | ⭐⭐ | Slow (~25%) | TCP/UDP | Full VPN | ❌ Blocked |
| Shadowsocks | ⭐ | Medium | TCP | Proxy | ⚠️ Detectable |

**Sources:**
- [Valebyte: VPS for VPN in Russia 2026](https://valebyte.com/en/blog/vps-for-vpn-in-russia-2026-what-works-after-youtube-blocks/)
- [AmneziaWG 2.0 deep dive](https://dev.to/bivlked/amneziawg-20-self-host-an-obfuscated-wireguard-vpn-that-bypasses-dpi-4692)
- [OmniShield: обход РКН 2026](https://omnishield.io/unblock/)
- [Zona.Media: censorship 2026](https://en.zona.media/article/2026/04/07/russian_internet_censorship_2026)
- [VLESS Protocol Deep Dive](https://plisio.net/cybersecurity/vless-protocol)
- [XTLS Reality config](https://github.com/XTLS/Xray-examples/blob/main/VLESS-TCP-XTLS-Vision-REALITY/REALITY.ENG.md)

## Client-Side Tools

When server-side measures are insufficient — add TCP fragmentation on client:

| Tool | Platform | Mechanism |
|------|----------|-----------|
| [zapret](https://github.com/bol-van/zapret) | Linux | TCP packet fragmentation |
| [GoodbyeDPI](https://github.com/ValdikSS/GoodbyeDPI) | Windows | TCP packet fragmentation |
| [NoDPI](https://github.com/ValdikSS/nodpi) | Android (no root) | TCP packet fragmentation |

## fscarmen/sing-box (Quick Deploy Alternative)

One-command multi-protocol installer with 11 protocols:
```bash
bash <(wget -qO- https://raw.githubusercontent.com/fscarmen/sing-box/main/sing-box.sh) -k
```
Supports: Reality, Hysteria2, TUIC, ShadowTLS, Trojan, SS-2022, VMess, VLESS, AnyTLS, NaiveProxy. Auto-certificates, auto-subscriptions for all clients.
