# VPS Deployment for Landing Page

Alternative to GitHub Pages when user has their own VPS.

## Prerequisites

- SSH access to VPS (Debian/Ubuntu)
- Port 80 available
- Domain or nip.io for testing

## Quick Deploy (nginx)

```bash
# Install nginx
ssh root@VPS "apt-get install -y nginx"

# Copy landing page
scp index.html root@VPS:/var/www/html/index.html

# Fix permissions (scp may set 0600)
ssh root@VPS "chmod 644 /var/www/html/index.html && chown www-data:www-data /var/www/html/index.html"

# Configure site
ssh root@VPS "
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

## HTTPS via certbot (Let's Encrypt)

```bash
ssh root@VPS "
apt-get install -y certbot
certbot certonly --webroot -w /var/www/html -d DOMAIN \
  --non-interactive --agree-tos --register-unsafely-without-email

# Add HTTPS server block (if port 443 available)
# Or use alternative port 8443 if 443 is occupied:
cat >> /etc/nginx/sites-available/landing << 'EOF'
server {
    listen 8443 ssl;
    server_name _;
    ssl_certificate /etc/letsencrypt/live/DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN/privkey.pem;
    root /var/www/html;
    index index.html;
    location / { try_files \$uri \$uri/ =404; }
}
EOF
nginx -t && systemctl reload nginx
"
```

## HTTPS via Cloudflare Tunnel (when port 443 is occupied)

Use when sing-box/VPN occupies port 443. Cloudflare provides free HTTPS without touching port 443.

```bash
# Install cloudflared (amd64)
ssh root@VPS "
curl -sL 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64' \
  -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
"

# Run tunnel
ssh root@VPS "/usr/local/bin/cloudflared tunnel --url http://localhost:80"

# Systemd service for persistence
ssh root@VPS "
cat > /etc/systemd/system/cloudflared-tunnel.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel
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
```

**Pitfall:** `trycloudflare.com` domains are blocked by Yandex Metrika. Use only for testing, not for Metrika verification.

## nip.io for temporary domains

If no real domain: `IP.nip.io` resolves to `IP`. Example: `<YOUR_VPS_IP>.nip.io`.
Yandex Metrika may not verify nip.io domains — prefer real domains or GitHub Pages.
