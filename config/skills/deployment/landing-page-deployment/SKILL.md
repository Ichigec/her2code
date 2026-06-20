---
name: landing-page-deployment
description: "Deploy a public landing page with HTTPS for Telegram channel advertising + Yandex Metrika analytics. Covers VPS nginx, Let's Encrypt, Cloudflare Tunnel, UTM tracking."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [deployment, web, analytics, telegram, nginx, cloudflare]
    related_skills: [deployment-operations]
---

# Landing Page Deployment

Deploy a static HTML landing page for Telegram channel advertising with
analytics tracking (Yandex Metrika). Covers HTTPS setup even when port 443
is occupied by another service (e.g. sing-box VPN).

## When to Use

- User wants to advertise a Telegram channel/group
- User asks for landing page + Yandex Metrika for ad tracking
- Need HTTPS landing page on a VPS with port 443 occupied
- Quick static site deployment for ad campaigns

## End-to-End Flow

### 1. Landing page HTML

Create `index.html` with:
- Dark theme (tech/AI vibe), centered card layout
- Channel name, description, topic tags
- CTA button linking to `https://t.me/<channel>`
- UTM parameter reading from URL (`utm_source`, `utm_medium`, `utm_campaign`)
- Yandex Metrika counter placeholder (`XXXXXXXX` — replace after user creates counter)
- Goal tracking: `ym(XXXXXXXX, 'reachGoal', 'tg_subscribe')` on CTA click
- Metrika JS snippet with webvisor, clickmap enabled

Use `templates/landing.html` as starting template — replace placeholders:
- `{{CHANNEL_TITLE}}`, `{{CHANNEL_NAME}}`, `{{CHANNEL_USERNAME}}`
- `{{CHANNEL_DESCRIPTION}}`, `{{EMOJI}}`
- `{{TAGS}}` — HTML span elements, e.g. `<span class="tag">🤖 AI</span>`
- `{{STATS}}` — HTML stat blocks
- `XXXXXXXX` — Yandex Metrika counter ID (3 occurrences)

### 2. Deploy to VPS (nginx)

```bash
# Install nginx
ssh root@<vps> "apt-get update -qq && apt-get install -y -qq nginx"

# Copy landing page
scp index.html root@<vps>:/var/www/html/index.html

# Fix permissions (crucial — scp creates 0600)
ssh root@<vps> "chmod 644 /var/www/html/index.html && chown www-data:www-data /var/www/html/index.html && chmod 755 /var/www/html"

# Configure nginx
ssh root@<vps> "
cat > /etc/nginx/sites-available/landing << 'EOF'
server {
    listen 80;
    server_name _;
    root /var/www/html;
    index index.html;
    location / { try_files \$uri \$uri/ =404; }
    location ~* \.(html)$ { add_header Cache-Control 'public, max-age=3600'; }
}
EOF
ln -sf /etc/nginx/sites-available/landing /etc/nginx/sites-enabled/landing
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
"
```

### 3. Get HTTPS

**Decision tree:**

```
Port 443 free?
  YES → certbot --nginx (standard Let's Encrypt)
  NO  → Is the 443 service touchable?
           YES → move it, certbot, move back
           NO  → Cloudflare Tunnel (Option A below)
                 OR non-standard port (Option B, Yandex won't accept)
```

**Option A: Cloudflare Tunnel (recommended when 443 occupied)**

```bash
# Install cloudflared on VPS
ARCH=$(ssh root@<vps> "dpkg --print-architecture")  # amd64 or arm64
URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}"
ssh root@<vps> "
curl -sL '$URL' -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
cloudflared --version
"

# Create systemd service for persistence
ssh root@<vps> "
cat > /etc/systemd/system/cloudflared-tunnel.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel for landing page
After=network.target
[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:80 --no-autoupdate
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now cloudflared-tunnel
"

# Get the URL
ssh root@<vps> "sleep 4 && grep -o 'https://[^ ]*trycloudflare.com' /var/log/cloudflared.log | tail -1"
```

The trycloudflare.com URL provides HTTPS via Cloudflare without touching VPS port 443.

**Option B: Non-standard port HTTPS (Let's Encrypt)**

```bash
# Use nip.io if no domain
DOMAIN="<IP>.nip.io"

ssh root@<vps> "
apt-get install -y -qq certbot
certbot certonly --webroot -w /var/www/html -d $DOMAIN \
  --non-interactive --agree-tos --register-unsafely-without-email
"
```

Then configure nginx with `listen 8443 ssl;` and cert paths.
**Pitfall:** Yandex Metrika rejects non-standard ports (:8443). Only use this
for testing or non-Yandex analytics.

### 4. Yandex Metrika setup

User must:
1. Go to [metrika.yandex.ru](https://metrika.yandex.ru) → Add counter
2. Site address: the HTTPS URL (must be port 443!)
3. Enable Webvisor + Click map
4. Copy counter ID (8 digits from `ym(XXXXXXXX, ...)`)
5. Tell agent to replace `XXXXXXXX` in the HTML

Agent then:
1. Replace `XXXXXXXX` with counter ID (3 occurrences in HTML)
2. Re-upload to VPS
3. User creates goal: JavaScript event, identifier `tg_subscribe`

### 5. UTM tracking

Ad links should include UTM parameters:
```
https://<landing-url>/?utm_source=yandex&utm_medium=cpc&utm_campaign=<name>
```

The landing page JS reads UTM from URL params and:
- Shows debug info on page
- Passes to Yandex Metrika via `ym(..., 'params', {...})`
- Saves to sessionStorage for multi-step tracking

## Pitfalls

1. **scp creates files with 0600 permissions** — nginx can't read them. Always `chmod 644` after scp.
2. **Yandex Metrika requires port 443** — non-standard ports like 8443 are silently rejected.
3. **nip.io domains**: Let's Encrypt may rate-limit these due to heavy usage. Cloudflare Tunnel is more reliable.
4. **trycloudflare.com URLs are temporary** — for production, use a named Cloudflare Tunnel or real domain.
5. **SSH host key issues**: `ssh-keygen -R <host>` clears old keys, then use `StrictHostKeyChecking=accept-new`.
6. **VPS vs Jetson architectures differ**: VPS is likely amd64, Jetson is aarch64. Binary downloads must match the target machine.
7. **Cloudflare Tunnel from Jetson may fail**: VPN routes (tun interfaces) can block QUIC. Run cloudflared on the VPS itself instead.

## User Preferences (User)

- **NEVER touch sing-box VPN on port 443** — it's the most critical service on the VPS
- Prefers fast action over deliberation — deploy first, explain after
- VPS at <YOUR_VPS_IP> (Debian 13), nginx for static hosting
- Landing page template at `/home/user/<YOUR_PROJECT>/index.html`

## Verification

```bash
# Check nginx
curl -s -o /dev/null -w "%{http_code}" http://<vps-ip>/

# Check Cloudflare Tunnel
curl -s --resolve "<domain>:443:<cf-ip>" https://<domain>/ | grep '<title>'

# From VPS itself
ssh root@<vps> "curl -s https://<trycloudflare-url>/ | grep '<title>'"
```
