#!/bin/bash
# cloudflared watchdog — keeps tunnel alive, updates URL file
# Run: nohup /home/user/cf_watchdog.sh &

URL_FILE="/tmp/current_tunnel_url.txt"
LOG="/tmp/cf_watchdog.log"

while true; do
    if ! pgrep -f "cloudflared tunnel" > /dev/null; then
        echo "$(date): cloudflared dead, restarting..." >> "$LOG"
        cloudflared tunnel --protocol http2 --no-autoupdate \
            --url http://localhost:8643 2>&1 | tee /tmp/cf_stable.log &
        sleep 10
        URL=$(grep -oP 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' /tmp/cf_stable.log | tail -1)
        if [ -n "$URL" ]; then
            echo "$URL" > "$URL_FILE"
            echo "$(date): New URL: $URL" >> "$LOG"
        fi
    fi
    sleep 30
done
