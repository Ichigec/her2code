#!/bin/bash
# ============================================================================
# Offline Isolation Test — verifies a distribution works with NO internet
#
# Usage: sudo bash test-offline-isolation.sh [DIST_DIR] [IMAGES_DIR]
#
# What it does:
#   1. Blocks ALL outbound internet via iptables (allows localhost + Docker + LAN)
#   2. Logs every blocked connection attempt to /tmp/offline-blocked.log
#   3. Runs: docker load → pip install → npm extract → llama binary → compose up
#   4. Checks all services are healthy
#   5. Reports blocked connection count (MUST be 0 for fully offline)
#   6. Restores iptables + cleans up test containers
#
# Requires: sudo (root for iptables), Docker, python3
# ============================================================================
set -euo pipefail

LOG="/tmp/offline-test.log"
BLOCKED="/tmp/offline-blocked.log"
TEST_DIR="/tmp/offline-test-dist"
SEAGATE="${1:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"
IMAGES_DIR="${2:-${SEAGATE}/docker-images}"

echo "" | tee "$LOG"
echo "╔══════════════════════════════════════════════════╗" | tee -a "$LOG"
echo "║  OFFLINE ISOLATION TEST                          ║" | tee -a "$LOG"
echo "╚══════════════════════════════════════════════════╝" | tee -a "$LOG"

# ── 0. Save iptables state ──────────────────────────────────────────────────
iptables-save > /tmp/iptables-backup-$(date +%s).rules 2>/dev/null || true

# ── 1. Block internet (allow localhost + Docker + LAN) ──────────────────────
iptables -N OFFLINE_BLOCK 2>/dev/null || iptables -F OFFLINE_BLOCK
iptables -A OFFLINE_BLOCK -j LOG --log-prefix "OFFLINE_BLOCKED: " --log-level 4
iptables -A OFFLINE_BLOCK -j DROP

iptables -I OUTPUT 1 -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -I OUTPUT 2 -d 127.0.0.0/8 -j ACCEPT
iptables -I OUTPUT 3 -s 127.0.0.0/8 -j ACCEPT
iptables -I OUTPUT 4 -d 172.16.0.0/12 -j ACCEPT
iptables -I OUTPUT 5 -s 172.16.0.0/12 -j ACCEPT
iptables -I OUTPUT 6 -d 192.168.0.0/16 -j ACCEPT
iptables -I OUTPUT 7 -s 192.168.0.0/16 -j ACCEPT
iptables -I OUTPUT 8 -d 10.0.0.0/8 -j ACCEPT
iptables -I OUTPUT 9 -s 10.0.0.0/8 -j ACCEPT
iptables -I OUTPUT 10 -d 169.254.0.0/16 -j ACCEPT
iptables -A OUTPUT -j OFFLINE_BLOCK

echo "  ✅ Internet blocked" | tee -a "$LOG"

# ── 2. Start dmesg monitor ──────────────────────────────────────────────────
> "$BLOCKED"
( dmesg -w 2>/dev/null | grep --line-buffered "OFFLINE_BLOCKED" >> "$BLOCKED" ) &
MONITOR_PID=$!

# ── 3. Prepare test dir ─────────────────────────────────────────────────────
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"
cp -r "${SEAGATE}/codewar/"* "$TEST_DIR/" 2>/dev/null || true

# ── 4. TEST: Docker load ────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "TEST 1: Docker image load..." | tee -a "$LOG"
LOADED=0; FAILED=0
for tar in "$IMAGES_DIR"/*.tar; do
    [ -f "$tar" ] || continue
    echo -n "  $(basename $tar)... " | tee -a "$LOG"
    if docker load -i "$tar" &>/dev/null; then echo "✅" | tee -a "$LOG"; LOADED=$((LOADED+1))
    else echo "❌" | tee -a "$LOG"; FAILED=$((FAILED+1)); fi
done
echo "  Loaded: $LOADED, Failed: $FAILED" | tee -a "$LOG"

# ── 5. TEST: pip install (offline) ──────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "TEST 2: pip install hermes-agent (offline)..." | tee -a "$LOG"
python3 -m venv /tmp/offline-venv 2>/dev/null
source /tmp/offline-venv/bin/activate
if pip install --no-index --find-links "$TEST_DIR/pip-packages/" hermes-agent &>>"$LOG"; then
    echo "  ✅ $(hermes --version 2>/dev/null || echo 'installed')" | tee -a "$LOG"
else
    echo "  ❌ pip install failed" | tee -a "$LOG"
fi
deactivate 2>/dev/null || true

# ── 6. TEST: node_modules extraction ────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "TEST 3: node_modules extraction..." | tee -a "$LOG"
NM_TAR="$TEST_DIR/hermes-core/plugins/claw-neo4j/node_modules.tar.gz"
if [ -f "$NM_TAR" ]; then
    tar xzf "$NM_TAR" -C "$TEST_DIR/hermes-core/plugins/claw-neo4j/" 2>/dev/null
    echo "  ✅ $(ls "$TEST_DIR/hermes-core/plugins/claw-neo4j/node_modules/" 2>/dev/null | wc -l) packages" | tee -a "$LOG"
else
    echo "  ⚠ node_modules.tar.gz not found" | tee -a "$LOG"
fi

# ── 7. TEST: llama-server binary ────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "TEST 4: llama-server binary..." | tee -a "$LOG"
LLAMA_TAR="$TEST_DIR/llm-stack/llama/llama-server-bin.tar.gz"
if [ -f "$LLAMA_TAR" ]; then
    mkdir -p /tmp/offline-llama && tar xzf "$LLAMA_TAR" -C /tmp/offline-llama/ 2>/dev/null
    if /tmp/offline-llama/llama-server --help &>/dev/null; then
        echo "  ✅ binary works" | tee -a "$LOG"
    else
        echo "  ⚠ binary extracted but --help failed (may need CUDA)" | tee -a "$LOG"
    fi
else
    echo "  ⚠ llama-server-bin.tar.gz not found" | tee -a "$LOG"
fi

# ── 8. TEST: Docker compose up (offline) ────────────────────────────────────
echo "" | tee -a "$LOG"
echo "TEST 5: Docker compose up..." | tee -a "$LOG"

cd "$TEST_DIR"
cat > .env << 'EOF'
NEO4J_PASSWORD=testpass123
LITELLM_API_KEY=sk-test-offline
LITELLM_HOST_PORT=14000
PHOENIX_HOST_PORT=16006
EOF

docker network create offline-test-net 2>/dev/null || true

# Create modified compose files with non-conflicting ports/names
sed 's/llm-stack-net/offline-test-net/g; s/container_name: neo4j/container_name: offline-test-neo4j/; s/7474:7474/17474:7474/; s/7687:7687/17687:7687/' \
    llm-stack/compose/compose.neo4j.yml > /tmp/offline-compose-neo4j.yml
sed 's/llm-stack-net/offline-test-net/g; s/container_name: phoenix/container_name: offline-test-phoenix/g; s/container_name: phoenix-db/container_name: offline-test-phoenix-db/g; s/container_name: litellm/container_name: offline-test-litellm/g; s/container_name: litellm-db/container_name: offline-test-litellm-db/g; s/6006:6006/16006:6006/g; s/4317:4317/14317:4317/g; s/4318:6006/14318:6006/g; s/4000:4000/14000:4000/g; /openai-stack-relay/,/^$/d' \
    llm-stack/compose/compose.phoenix.yml > /tmp/offline-compose-phoenix.yml

NEO4J_PASSWORD=testpass123 docker compose -f /tmp/offline-compose-neo4j.yml up -d 2>>"$LOG" || true
docker compose -f /tmp/offline-compose-phoenix.yml up -d 2>>"$LOG" || true

# Wait for services
NEO4J_OK=false; PHOENIX_OK=false; LITELLM_OK=false
for i in $(seq 1 30); do
    docker exec offline-test-neo4j cypher-shell -u neo4j -p testpass123 "RETURN 1" &>/dev/null && NEO4J_OK=true && break
    sleep 2
done
for i in $(seq 1 45); do
    curl -sf http://127.0.0.1:16006 &>/dev/null && PHOENIX_OK=true && break
    sleep 2
done
for i in $(seq 1 30); do
    curl -sf http://127.0.0.1:14000/health &>/dev/null && LITELLM_OK=true && break
    sleep 2
done

echo "  Neo4j:   $([ "$NEO4J_OK" = true ] && echo '✅' || echo '❌')" | tee -a "$LOG"
echo "  Phoenix: $([ "$PHOENIX_OK" = true ] && echo '✅' || echo '❌')" | tee -a "$LOG"
echo "  LiteLLM: $([ "$LITELLM_OK" = true ] && echo '✅' || echo '❌ (port conflict on test machine is OK)')" | tee -a "$LOG"

# ── 9. Check blocked connections ────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "TEST 6: Blocked connections..." | tee -a "$LOG"
sleep 2
kill $MONITOR_PID 2>/dev/null || true
BLOCKED_COUNT=$(wc -l < "$BLOCKED" 2>/dev/null || echo "0")
echo "  Blocked connections: $BLOCKED_COUNT" | tee -a "$LOG"
if [ "$BLOCKED_COUNT" -gt 0 ]; then
    echo "  --- Details ---" | tee -a "$LOG"
    cat "$BLOCKED" | tee -a "$LOG"
fi

# ── 10. Cleanup ─────────────────────────────────────────────────────────────
docker compose -f /tmp/offline-compose-phoenix.yml down 2>/dev/null || true
docker compose -f /tmp/offline-compose-neo4j.yml down 2>/dev/null || true
docker network rm offline-test-net 2>/dev/null || true
rm -rf "$TEST_DIR" /tmp/offline-llama /tmp/offline-venv 2>/dev/null || true

# ── 11. Restore iptables ────────────────────────────────────────────────────
iptables -D OUTPUT -j OFFLINE_BLOCK 2>/dev/null || true
iptables -F OFFLINE_BLOCK 2>/dev/null || true
iptables -X OFFLINE_BLOCK 2>/dev/null || true
for i in $(seq 1 10); do iptables -D OUTPUT 1 2>/dev/null || true; done

# ── Summary ─────────────────────────────────────────────────────────────────
echo "" | tee -a "$LOG"
echo "╔══════════════════════════════════════════════════╗" | tee -a "$LOG"
echo "║  SUMMARY                                        ║" | tee -a "$LOG"
echo "╠══════════════════════════════════════════════════╣" | tee -a "$LOG"
echo "  Docker images:  $LOADED loaded, $FAILED failed" | tee -a "$LOG"
echo "  pip install:    $(grep -c '✅.*hermes\|✅.*installed\|✅.*Hermes' "$LOG" 2>/dev/null || echo 0) / 1" | tee -a "$LOG"
echo "  node_modules:   $(grep -c '✅.*packages' "$LOG" 2>/dev/null || echo 0) / 1" | tee -a "$LOG"
echo "  llama binary:   $(grep -c '✅.*binary works' "$LOG" 2>/dev/null || echo 0) / 1" | tee -a "$LOG"
echo "  Neo4j:          $([ "$NEO4J_OK" = true ] && echo '✅' || echo '❌')" | tee -a "$LOG"
echo "  Phoenix:        $([ "$PHOENIX_OK" = true ] && echo '✅' || echo '❌')" | tee -a "$LOG"
echo "  LiteLLM:        $([ "$LITELLM_OK" = true ] && echo '✅' || echo '⚠ (port conflict OK)')" | tee -a "$LOG"
echo "  Blocked conns:  $BLOCKED_COUNT" | tee -a "$LOG"
echo "║" | tee -a "$LOG"
if [ "$BLOCKED_COUNT" -eq 0 ]; then
    echo "║  ✅ FULLY OFFLINE — NO INTERNET NEEDED           ║" | tee -a "$LOG"
else
    echo "║  ⚠ SOME CONNECTIONS ATTEMPTED                   ║" | tee -a "$LOG"
fi
echo "╚══════════════════════════════════════════════════╝" | tee -a "$LOG"
echo ""
echo "Full log: $LOG"
echo "Blocked:  $BLOCKED"
