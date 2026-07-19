# NekoBox Client Setup

## VLESS Reality Profile

Profile → Edit → fill:

| Tab | Field | Value |
|-----|-------|-------|
| Outbound | Type | VLESS |
| Outbound | Server | `<VPS_IP>` |
| Outbound | Port | `443` |
| Outbound | UUID | `<server UUID>` |
| Outbound | Flow | `xtls-rprx-vision` |
| Outbound | Encryption | `none` |
| Transport | Type | `tcp` |
| TLS | Security | `reality` |
| TLS | SNI | `www.microsoft.com` |
| TLS | **uTLS Fingerprint** | **`randomized`** |
| TLS | Public Key | `<reality public key>` |
| TLS | Short ID | `<first short_id>` |

Everything else: empty/disabled. OK.

**IMPORTANT**: uTLS fingerprint MUST be `randomized` — Russian TSPU fingerprint-ирует JA3/JA4. `chrome` уже детектится.

## Hysteria2 Profile (import link)

Copy this link → NekoBox → Profiles → Add from Clipboard:

```
hysteria2://<PASSWORD>@<VPS_IP>:9443?insecure=1&obfs=salamander&obfs-password=<SALAMANDER_PASS>&sni=www.microsoft.com&alpn=h3#VPS-HY2
```

URL-encode the salamander password: `+` → `%2B`, `=` → `%3D`, `/` → `%2F`.

Or manual setup:

| Field | Value |
|-------|-------|
| Name | `VPS-HY2` |
| Type | Hysteria2 |
| Server | `<VPS_IP>` |
| Port | `9443` |
| Password | `<hysteria2 password>` |
| SNI | `www.microsoft.com` |
| ALPN | `h3` |
| Obfuscation | Salamander |
| Obfs Password | `<salamander password>` |
| Allow Insecure | Yes |
| Bandwidth | 100/100 Mbps |

## Usage

1. Select profile → Connect button
2. Settings → System Proxy: ON
3. Verify: `curl -x socks5h://127.0.0.1:2080 --connect-timeout 10 http://ipv4.icanhazip.com`

Expected result: VPS IP.

## Strategy

- **Primary**: VLESS Reality (TCP, lowest latency)
- **Fallback**: Hysteria2 (UDP/QUIC, if TCP throttled/blocked)
- NekoBox supports automatic failover: Settings → Routing → Failover

## Troubleshooting

- No SOCKS port after connect → check NekoBox logs tab
- `curl` timeout but profile shows "Connected" → likely DPI throttling, switch to Hysteria2
- Short ID mismatch → server has 3 short_ids, client must use one of them
