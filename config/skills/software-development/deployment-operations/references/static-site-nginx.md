# Static Site Deployment (nginx + VPS)

Recurring pattern: deploy a single-page HTML site to a VPS with nginx.

## Quick Deploy

```bash
# 1. Copy to VPS
scp index.html root@<IP>:/var/www/html/index.html

# 2. ALWAYS fix permissions (scp gives 0600 = nginx 403!)
ssh root@<IP> "chmod 644 /var/www/html/index.html && chown www-data:www-data /var/www/html/index.html"

# 3. Configure nginx
ssh root@<IP> "cat > /etc/nginx/sites-available/site << 'EOF'
server {
    listen 80;
    server_name _;
    root /var/www/html;
    index index.html;
    location / { try_files \$uri \$uri/ =404; }
}
EOF
ln -sf /etc/nginx/sites-available/site /etc/nginx/sites-enabled/site
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx"
```

## Pitfalls

### scp sets 0600 — nginx returns 403
scp preserves restrictive source permissions (0600). nginx runs as www-data and can't read root's private files. **Always** `chmod 644` + `chown www-data` after scp.

Symptom: `curl http://IP/` → 403, nginx error log: `open() failed (13: Permission denied)`.

### Cloudflared tunnel fails behind VPN
cloudflared uses QUIC (UDP 7844) to Cloudflare edge. When the server routes through sing-box or similar VPN, QUIC packets are dropped with `timeout: no recent network activity`. 

**Fallback:** localhost.run (SSH-based, TCP 22, reliable through VPNs):
```bash
ssh -R 80:localhost:8080 nokey@localhost.run
# URL appears in output: https://<id>.lhr.life
```
**Trade-off:** URL changes on reconnect. For permanent URL use the VPS directly.

## Domain Workaround: nip.io

When a service (Yandex Metrika, LetsEncrypt, etc.) requires a domain name but you only have an IP:

```
<YOUR_VPS_IP>.nip.io  →  resolves to <YOUR_VPS_IP>
```

`nip.io` is a free wildcard DNS — any `IP.nip.io` resolves to that IP. Use it for:
- Yandex Metrika counter domain field
- SSL certificate validation via HTTP challenge
- Any service that rejects bare IP addresses

**No signup, no config, just works.** Add the nip.io hostname to nginx `server_name` so it responds to that Host header:
```nginx
server {
    listen 80;
    server_name <YOUR_VPS_IP>.nip.io <YOUR_VPS_IP>;
    ...
}
```

## SSH Troubleshooting

### Host key verification failed (no TTY)
After `ssh-keygen -R <host>` or on fresh VPS, add `-o StrictHostKeyChecking=accept-new`:
```bash
ssh -o StrictHostKeyChecking=accept-new root@<IP> "echo ok"
```

### Connection closed during KEX
Check routing first — `nc -zv <IP> 22` and `ip route get <IP>`. If port 22 is open but SSH fails at key exchange, the VPS may have changed host keys or be running fail2ban.
