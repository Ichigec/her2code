#!/bin/bash
# Voice Proxy auto-restart wrapper — keeps voice_proxy.py alive
# Run: bash /home/user/dev/Opencode/voice_proxy_watchdog.sh

HERMES_VENV="$HOME/.hermes/hermes-agent/venv"
PROXY_SCRIPT="$HOME/dev/Opencode/voice_proxy.py"

while true; do
    if ! curl -s http://localhost:8647/health > /dev/null 2>&1; then
        echo "[Watchdog] Starting voice proxy..." 
        source "$HERMES_VENV/bin/activate"
        python3 "$PROXY_SCRIPT" &
        sleep 3
    fi
    sleep 10
done
