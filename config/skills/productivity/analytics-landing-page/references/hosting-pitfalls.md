# Hosting Options — What Works and What Doesn't

## Yandex Metrika Verification

### ❌ Does NOT work
| Method | Reason |
|--------|--------|
| `http://` (port 80) | Yandex requires HTTPS |
| `https://:8443` (non-standard port) | Yandex only checks port 443 |
| `*.trycloudflare.com` | Blocked as temporary/suspicious domain |
| `*.lhr.life` (localhost.run) | Blocked as temporary domain |
| `*.serveo.net` | Blocked as temporary domain |
| `*.nip.io` over HTTP | Needs HTTPS on port 443 |

### ✅ Works
| Method | URL format |
|--------|-----------|
| GitHub Pages | `https://<user>.github.io/<repo>/` |
| Netlify | `https://<site>.netlify.app/` |
| Vercel | `https://<site>.vercel.app/` |
| VPS + Let's Encrypt | `https://<domain>/` |
| Cloudflare Pages | `https://<site>.pages.dev/` |

## VPS HTTPS Setup (without 443 conflict)

If port 443 is occupied by VPN/proxy (sing-box, etc.):
1. **Do NOT touch the VPN.** Use GitHub Pages instead.
2. Cloudflared tunnel gives HTTPS URL but `trycloudflare.com` is blocked by analytics.
3. Cloudflared `--url` from Jetson behind VPN: QUIC often blocked, fails silently.

## gh CLI — Device Auth Flow

For headless servers without browser:
```bash
gh auth login --hostname github.com --git-protocol ssh
# → Shows code like "A626-AEE8"
# User visits https://github.com/login/device and enters code
# Process must stay alive while user enters code
```

Key: the `gh auth login` process must NOT exit before user enters the code.
Use background process or nohup to keep it alive.

## Jetpack-Specific Issues

- Jetson (aarch64): cloudflared works locally but QUIC blocked when behind VPN
- VPS (amd64): cloudflared works fine, downloads are fast
- `gh` binary: aarch64 download from GitHub can be very slow (timeout 30s+)
- VPS as build host is faster for downloads
