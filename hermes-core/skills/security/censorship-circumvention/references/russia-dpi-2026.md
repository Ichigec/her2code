# Russian DPI Circumvention (July 2026)

## TSPU Evolution Timeline

| Date | Event | Protocols Affected |
|------|-------|-------------------|
| 2024 | WireGuard loses ~88% connections | WG handshake fingerprint (fixed 148 bytes) |
| Dec 2025 | TSPU targets SOCKS5, VLESS, L2TP | Protocol fingerprints |
| Feb 2026 | 469 services + 385 protocols blocked | AI traffic analysis |
| Apr 2026 | Fake-TLS blocking (MTProto, VLESS) | JA3/JA4 ClientHello fingerprint |
| May 2026 | Partial blocking: VLESS, WG, XTLS/XHTTP, gRPC, Hysteria | Broad protocol attack |

**Source**: teleproxy#39, XTLS/Xray-core#5332, Zona.Media, vpnlab.io

## How TSPU Works (2026)

- **Client-side JA3/JA4 fingerprinting** of TLS ClientHello — classifies as "TELEGRAM_TLS" or "VPN_TLS"
- **Active probing**: DPI sends fake probe to server IP. If response fingerprints as VPN — IP blacklisted
- **DPI vendors**: VAS Experts, RDP.RU — deployed at all major ISPs
- **Mobile operators** more aggressive than home ISPs (MTS, Megafon, Beeline, T2, Yota)

## Protocol Effectiveness (July 2026)

| Protocol | DPI Resistance | Speed | Tunnel Type | Russia Status |
|----------|:---:|:---:|:---:|:---:|
| **VLESS + Reality** | Very High | Fast (TCP) | Proxy | ✅ Works with uTLS:randomized |
| **Hysteria2 + Salamander** | High | Fast (UDP/QUIC, Brutal CC) | Proxy | ✅ Works |
| **AmneziaWG 2.0** | High | Near-WG (92 Mbps) | Full VPN | ✅ Works |
| **ShadowTLS v3** | Medium | Medium (TCP) | Proxy | ⚠️ Partial |
| **WireGuard** | None | Fast (95 Mbps) | Full VPN | ❌ ~12% success |
| **OpenVPN + obfs4** | Medium | Slow (~25% OH) | Full VPN | ❌ Blocked |
| **Shadowsocks 2022** | Low | Medium | Proxy | ❌ Detectable |

## uTLS Fingerprint Strategy

The SINGLE most important client-side setting. Russian DPI fingerprint-ирует JA3/JA4 in TLS ClientHello.

Fingerprints ranked by stealth:
1. **`randomized`** — different ClientHello every connection, impossible to fingerprint
2. **`randomized_native`** — same but via Go crypto/tls (fewer library fingerprints)
3. **`qq`** — QQ browser, less commonly targeted
4. **`firefox`** — most common browser, high traffic volume makes blocking risky
5. **`chrome`** — already fingerprinted by TSPU, AVOID

Recommendation: start with `randomized`, fall back to `firefox` if latency issues.

## Client-Side TCP Fragmentation

When DPI blocks even randomized VLESS, add packet fragmentation:

- **Linux**: [zapret](https://github.com/bol-van/zapret) — splits TCP segments, defeats pattern matching
- **Windows**: [GoodbyeDPI](https://github.com/ValdikSS/GoodbyeDPI)
- **Android (no root)**: [NoDPI](https://github.com/ValdikSS/nodpi)

## Key Sources

- https://github.com/teleproxy/teleproxy/issues/39 — TSPU fake-TLS blocking (April 2026)
- https://github.com/XTLS/Xray-core/issues/5332 — TCP+Reality blocked, uTLS fix
- https://valebyte.com/en/blog/vps-for-vpn-in-russia-2026-what-works-after-youtube-blocks/ — protocol comparison
- https://dev.to/bivlked/amneziawg-20-self-host-an-obfuscated-wireguard-vpn-that-bypasses-dpi-4692 — AmneziaWG deep dive
- https://en.zona.media/article/2026/04/07/russian_internet_censorship_2026 — censorship timeline
- https://omnishield.io/unblock/ — обход РКН methods overview
- https://plisio.net/cybersecurity/vless-protocol — VLESS deep dive
- https://github.com/fscarmen/sing-box — multi-protocol deploy script (updated July 2026)
