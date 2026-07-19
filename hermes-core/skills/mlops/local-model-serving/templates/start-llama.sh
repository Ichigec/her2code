#!/bin/bash
# ============================================================================
# start-llama.sh - Launch 3 models on DGX Spark via direct llama-server
# No systemd, no llama-swap. Watchdog auto-restarts dead models (daemon).
# Auto-injects firewall rules for Docker -> host connectivity.
#
# Usage:
#   ./start-llama.sh          - start all 3 models + firewall + watchdog (daemon)
#   ./start-llama.sh start    - same
#   ./start-llama.sh stop     - stop all
#   ./start-llama.sh status   - show status
#   ./start-llama.sh test     - test for garbage tokens
#
# Copy and modify: change MODEL_* paths, PORT_* values, and aliases.
#
# KEY DESIGN DECISIONS (learned the hard way):
#   - setsid for daemon processes (NOT disown): setsid creates a new session,
#     fully preventing SIGHUP when the parent terminal/script exits.
#   - Watchdog writes to a FILE via heredoc (not inline bash -c '...'):
#     heredoc WITHOUT quotes on the delimiter expands variables AT WRITE TIME.
#     bash -c '...' with single quotes does NOT expand variables -> watchdog
#     restarts models with empty paths -> instant crash loop.
#   - iptables-nft does NOT work in Alpine containers on ARM64 DGX Spark.
#     Fall back to host iptables via sudo -n, or print manual instructions.
#
# CRITICAL: -c 262144 (256K context) is required for thinking models.
#    At 32K, reasoning tokens consume all output budget -> empty content.
# ============================================================================
set -euo pipefail

LLAMA_SERVER="/home/user/dev/llama.cpp/build/bin/llama-server"
PID_DIR="${HOME}/dev/llama/pids"
LOG_DIR="${HOME}/dev/llama/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
export GGML_CUDA_DISABLE_GRAPHS=1    # CRITICAL: stops CUDA graph leak on GB10 with qwen35moe

# Models (Q8_0 on qwen35moe SSM is BROKEN - use APEX or Q4_K_M)
MODEL_NEX="${HOME}/models/Huihui-Nex-N2-mini-abliterated-APEX-Quality.gguf"
MODEL_QWEN="${HOME}/models/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-APEX-I-Quality.gguf"
MODEL_WORLD="${HOME}/models/SuperQwen-APEX-I-Quality-v3.gguf"

PORT_NEX=8101
PORT_QWEN=8102
PORT_WORLD=8103

ALIAS_NEX="nex-n2-mini"
ALIAS_QWEN="qwen3.6-35b"
ALIAS_WORLD="agentworld"

# -- memlock check --
ML=$(ulimit -l 2>/dev/null || echo 0)
if [ "$ML" = "unlimited" ] || [ "${ML:-0}" -gt 100000000 ] 2>/dev/null; then
    MLOCK="--mlock"
else
    MLOCK=""
fi

kill_existing() {
    echo "=== Stopping llama-server ==="
    for pid in $(pgrep -x llama-server 2>/dev/null); do
        echo "  kill -9 PID $pid"
        kill -9 "$pid" 2>/dev/null || true
    done
    # Stop watchdog daemon
    if [ -f "$PID_DIR/watchdog.pid" ]; then
        wpid=$(cat "$PID_DIR/watchdog.pid" 2>/dev/null)
        kill "$wpid" 2>/dev/null || true
        rm -f "$PID_DIR/watchdog.pid"
    fi
    sleep 2
    pgrep -x llama-server >/dev/null 2>&1 && echo "  WARNING: survivors" || echo "  Stopped"
}

start_model() {
    local name="$1" model="$2" port="$3" alias="$4" extra_args="${5:-}"
    local logfile="${LOG_DIR}/${name}.log"
    local pidfile="${PID_DIR}/${name}.pid"

    echo "=== Start ${name} -> :${port} ==="
    [ -f "$model" ] || { echo "  Model not found: $model"; return 1; }
    echo "  $(du -h "$model" | cut -f1) - $(basename "$model")"

    # setsid: creates new session, prevents SIGHUP when parent exits.
    # --host 0.0.0.0 is REQUIRED for Docker containers to reach the server.
    # --no-mmap is MANDATORY for multi-model on DGX Spark unified memory.
    setsid "$LLAMA_SERVER" \
        -m "$model" \
        --alias "$alias" \
        -ngl 99 \
        -c 262144 \
        --cache-type-k q8_0 \
        --cache-type-v q8_0 \
        --no-mmap \
        --flash-attn on \
        -np 2 \
        $MLOCK \
        --host 0.0.0.0 \
        --port "$port" \
        --jinja \
        $extra_args \
        > "$logfile" 2>&1 &

    local pid=$!
    echo "$pid" > "$pidfile"
    disown "$pid" 2>/dev/null || true

    echo -n "  Loading"
    for i in $(seq 1 60); do
        if curl -sf "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
            echo ""; echo "  OK ${name} ($((i*2))s)"; return 0
        fi
        kill -0 "$pid" 2>/dev/null || { echo ""; echo "  DIED! $logfile"; tail -5 "$logfile"; return 1; }
        echo -n "."; sleep 2
    done
    echo ""; echo "  TIMEOUT"; return 1
}

test_model() {
    local name="$1" port="$2"
    local resp=$(curl -s "http://127.0.0.1:${port}/v1/completions" \
        -H "Content-Type: application/json" \
        -d '{"prompt":"What is 2+2?","max_tokens":16,"temperature":0}')
    echo "$resp" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    t = r['choices'][0]['text']
    s = t.strip()
    if set(s) <= set('/'): print('  GARBAGE: $name - / tokens (Q8_0 on SSM?)')
    elif not s: print('  EMPTY: $name - check chat template')
    else: print('  OK: $name - ' + repr(t[:60]))
except Exception as e: print('  ERROR: $name - ' + str(e))
" 2>&1 || true
}

inject_firewall_rules() {
    echo "=== Firewall rules (Docker -> host:8101-8103) ==="
    # iptables-nft does NOT work in Alpine containers on ARM64 DGX Spark
    # ("Failed to initialize nft: Protocol not supported").
    # Try host iptables via passwordless sudo first, fall back to instructions.
    if sudo -n true 2>/dev/null; then
        for port in 8101 8102 8103; do
            for net in 172.18.0.0/16 172.17.0.0/16; do
                sudo iptables -C ufw-user-input -s "$net" -p tcp --dport "$port" -j ACCEPT 2>/dev/null || \
                sudo iptables -I ufw-user-input 1 -s "$net" -p tcp --dport "$port" -j ACCEPT 2>/dev/null || true
            done
        done
        echo "  OK: iptables rules applied (host sudo)"
    else
        echo "  WARN: No passwordless sudo - skipping iptables."
        echo "  If Docker can't reach models, run manually:"
        echo "    sudo iptables -I ufw-user-input 1 -s 172.17.0.0/16 -p tcp --dport 8101:8103 -j ACCEPT"
    fi
}

start_watchdog() {
    # Watchdog as a separate daemon process.
    # CRITICAL: Write the watchdog script to a FILE via heredoc.
    # Heredoc WITHOUT quotes on the delimiter expands $VAR at WRITE TIME.
    # bash -c '...' with single quotes does NOT expand $VAR -> empty model paths
    # -> watchdog crashes models in an infinite loop. Use heredoc-to-file pattern.
    local wd_script="${PID_DIR}/watchdog.sh"

    cat > "$wd_script" <<WATCHDOG_EOF
#!/bin/bash
export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
export GGML_CUDA_DISABLE_GRAPHS=1    # CRITICAL: stops CUDA graph leak on GB10 with qwen35moe

PID_DIR="$PID_DIR"
LOG_DIR="$LOG_DIR"
LLAMA_SERVER="$LLAMA_SERVER"
MLOCK="$MLOCK"

declare -A MODELS=(
    ["nex"]="$MODEL_NEX|$PORT_NEX|$ALIAS_NEX|"
    ["qwen"]="$MODEL_QWEN|$PORT_QWEN|$ALIAS_QWEN|"
    ["world"]="$MODEL_WORLD|$PORT_WORLD|$ALIAS_WORLD|"
)

while true; do
    sleep 30
    for name in "\${!MODELS[@]}"; do
        pidfile="\${PID_DIR}/\${name}.pid"
        [ -f "\$pidfile" ] || continue
        pid=\$(cat "\$pidfile")
        if ! kill -0 "\$pid" 2>/dev/null; then
            echo "\$(date +%H:%M:%S) WARNING: \${name} dead, restarting..." >> "\${LOG_DIR}/watchdog.log"
            IFS="|" read model port alias extra <<< "\${MODELS[\$name]}"
            setsid "\$LLAMA_SERVER" -m "\$model" --alias "\$alias" -ngl 99 -c 262144 \\
                --cache-type-k q8_0 --cache-type-v q8_0 --no-mmap --flash-attn on -np 2 \$MLOCK \\
                --host 0.0.0.0 --port "\$port" --jinja \$extra \\
                > "\${LOG_DIR}/\${name}.log" 2>&1 &
            echo \$! > "\$pidfile"
            disown \$! 2>/dev/null || true
        fi
    done
done
WATCHDOG_EOF
    chmod +x "$wd_script"

    setsid bash "$wd_script" > /dev/null 2>&1 &
    echo $! > "$PID_DIR/watchdog.pid"
    disown $! 2>/dev/null || true
}

case "${1:-start}" in
    start)
        echo "=========================================="
        echo "  DGX SPARK - 3 MODELS (llama-server)"
        echo "=========================================="
        echo ""

        kill_existing
        free -h | head -2
        echo ""

        start_model "nex"   "$MODEL_NEX"   "$PORT_NEX"   "$ALIAS_NEX"   || exit 1
        start_model "qwen"  "$MODEL_QWEN"  "$PORT_QWEN"  "$ALIAS_QWEN"  || exit 1
        start_model "world" "$MODEL_WORLD" "$PORT_WORLD" "$ALIAS_WORLD" || exit 1

        echo ""
        echo "  ALL 3 MODELS RUNNING (daemon mode)"
        echo "  nex   -> :8101  coding, terminal"
        echo "  qwen  -> :8102  reasoning, analysis"
        echo "  world -> :8103  world simulation"
        echo ""
        free -h | head -2
        echo ""

        inject_firewall_rules
        echo ""

        echo "=== Auto-test ==="
        test_model "nex"   "$PORT_NEX"
        test_model "qwen"  "$PORT_QWEN"
        test_model "world" "$PORT_WORLD"
        echo ""

        echo "=== Watchdog (daemon) ==="
        start_watchdog
        echo "  OK: Watchdog started (PID $(cat "$PID_DIR/watchdog.pid"))"
        echo ""
        echo "  Script finished. Models running in background."
        ;;

    stop)
        kill_existing
        rm -f "$PID_DIR"/*.pid 2>/dev/null
        echo "=== Stopped ==="
        ;;

    status)
        echo "=== Status ==="
        for name in nex qwen world; do
            port_var="PORT_$(echo $name | tr a-z A-Z)"; port="${!port_var}"
            pidfile="${PID_DIR}/${name}.pid"
            if [ -f "$pidfile" ]; then
                pid=$(cat "$pidfile")
                if kill -0 "$pid" 2>/dev/null; then
                    if curl -sf "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
                        echo "  OK ${name}: PID $pid, :${port}"
                    else
                        echo "  WARN ${name}: PID $pid, :${port} - not responding"
                    fi
                else
                    echo "  DEAD ${name}: PID $pid"
                fi
            else
                echo "  -- ${name}: not started"
            fi
        done
        # Watchdog
        if [ -f "$PID_DIR/watchdog.pid" ]; then
            wpid=$(cat "$PID_DIR/watchdog.pid")
            kill -0 "$wpid" 2>/dev/null && echo "  OK watchdog: PID $wpid" || echo "  DEAD watchdog"
        else
            echo "  -- watchdog: not started"
        fi
        echo ""
        free -h | head -2
        ;;

    test)
        echo "=== Test ==="
        test_model "nex"   "$PORT_NEX"
        test_model "qwen"  "$PORT_QWEN"
        test_model "world" "$PORT_WORLD"
        ;;

    *)
        echo "Usage: $0 {start|stop|status|test}"
        exit 1
        ;;
esac
