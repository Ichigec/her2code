#!/usr/bin/env bash
# Knowledge Curator v2 — Daily Pipeline
# Runs: paper-collector → paper-deep-read → knowledge-curator-ingest
#
# Cron: 0 2 * * * /home/user/.hermes/scripts/curator-daily.sh
# Manual: bash /home/user/.hermes/scripts/curator-daily.sh [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="/home/user/.hermes/hermes-agent/venv/bin/python3"
LOG_DIR="/home/user/.hermes/logs"
DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/curator-$DATE.log"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Knowledge Curator v2 Daily Pipeline ==="
echo "Date: $DATE"
echo "Started: $(date)"
echo ""

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo "MODE: DRY RUN (no LLM/Neo4j writes)"
fi

# Check prerequisites
echo "── Prerequisites ──"

# Check Neo4j
if curl -sf -u neo4j:<YOUR_NEO4J_PASSWORD> http://127.0.0.1:7474 > /dev/null 2>&1; then
    echo "  ✓ Neo4j running"
else
    echo "  ✗ Neo4j NOT running — aborting"
    exit 1
fi

# Check Qwen (llama.cpp) — try preferred port 8092, then fall back to 8101-8103
LLM_AVAILABLE=false
LLAMA_URL=""
for port in 8092 8102 8103 8101; do
    if curl -sf -m 5 "http://127.0.0.1:${port}/v1/models" > /dev/null 2>&1; then
        # Quick health check — ensure model actually generates content
        test_resp=$(curl -sf -m 30 "http://127.0.0.1:${port}/v1/chat/completions" \
            -H 'Content-Type: application/json' \
            -d '{"messages":[{"role":"user","content":"OK"}],"max_tokens":50,"temperature":0}' 2>/dev/null || true)
        test_content=$(echo "$test_resp" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('choices',[{}])[0].get('message',{}).get('content',''))" 2>/dev/null || true)
        if [ -n "$test_content" ]; then
            LLM_AVAILABLE=true
            LLAMA_URL="http://127.0.0.1:${port}/v1"
            model_name=$(curl -sf -m 5 "http://127.0.0.1:${port}/v1/models" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['data'][0]['id'])" 2>/dev/null || echo "?")
            echo "  ✓ LLM running on :${port} (model: ${model_name})"
            break
        else
            echo "  ⚠ :${port} responds but generates empty content (reasoning-only?), skipping"
        fi
    fi
done
if [ "$LLM_AVAILABLE" = false ]; then
    echo "  ⚠ No usable LLM found on ports 8092/8101-8103 — paper deep-read will be skipped"
fi
export LLAMA_URL
export LLAMA_MAX_TOKENS="${LLAMA_MAX_TOKENS:-4000}"

# Check pdftotext
if which pdftotext > /dev/null 2>&1; then
    echo "  ✓ pdftotext available"
else
    echo "  ⚠ pdftotext NOT available — install poppler-utils"
fi

echo ""

# Phase A: Collect papers
echo "── Phase A: Paper Collector ──"
if [ "$LLM_AVAILABLE" = true ] || [ -n "$DRY_RUN" ]; then
    python3 "$SCRIPT_DIR/paper-collector.py" $DRY_RUN --days=1 --top=10
    echo "  ✓ Paper collection complete"
else
    echo "  ⊘ Skipped (no LLM)"
fi

echo ""

# Phase B: Deep-read papers
echo "── Phase B: Paper Deep Reader ──"
if [ "$LLM_AVAILABLE" = true ] && [ -z "$DRY_RUN" ]; then
    python3 "$SCRIPT_DIR/paper-deep-read.py" --top=5
    echo "  ✓ Deep read complete"
elif [ -n "$DRY_RUN" ]; then
    python3 "$SCRIPT_DIR/paper-deep-read.py" --dry-run --top=5
    echo "  ✓ Dry run complete"
else
    echo "  ⊘ Skipped (no LLM)"
fi

echo ""

# Phase C: Scan markdown artifacts (existing pipeline)
echo "── Phase C: Markdown Ingestion ──"
if [ "$LLM_AVAILABLE" = true ] && [ -z "$DRY_RUN" ]; then
    timeout 3600 python3 "$SCRIPT_DIR/knowledge-curator-ingest-llm.py" || echo "  ⚠ Timed out after 1h (normal for large scans)"
elif [ -n "$DRY_RUN" ]; then
    python3 "$SCRIPT_DIR/knowledge-curator-ingest-llm.py" --dry-run
else
    echo "  ⊘ Skipped (no LLM)"
fi

echo ""
echo "── Pipeline Complete ──"
echo "Finished: $(date)"
echo "Log: $LOG_FILE"

# Health summary
ENTITY_COUNT=$(curl -sf -u neo4j:<YOUR_NEO4J_PASSWORD> \
    -H 'Content-Type: application/json' \
    -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN count(ke) AS c"}]}' \
    http://127.0.0.1:7474/db/neo4j/tx/commit | python3 -c "import json,sys; print(json.load(sys.stdin)['results'][0]['data'][0]['row'][0])" 2>/dev/null || echo "?")

PAPER_COUNT=$(curl -sf -u neo4j:<YOUR_NEO4J_PASSWORD> \
    -H 'Content-Type: application/json' \
    -d '{"statements":[{"statement":"MATCH (p:Paper) RETURN count(p) AS c"}]}' \
    http://127.0.0.1:7474/db/neo4j/tx/commit | python3 -c "import json,sys; print(json.load(sys.stdin)['results'][0]['data'][0]['row'][0])" 2>/dev/null || echo "?")

REL_COUNT=$(curl -sf -u neo4j:<YOUR_NEO4J_PASSWORD> \
    -H 'Content-Type: application/json' \
    -d '{"statements":[{"statement":"MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS c"}]}' \
    http://127.0.0.1:7474/db/neo4j/tx/commit | python3 -c "import json,sys; print(json.load(sys.stdin)['results'][0]['data'][0]['row'][0])" 2>/dev/null || echo "?")

echo ""
echo "── Health ──"
echo "  KnowledgeEntities: $ENTITY_COUNT"
echo "  Papers: $PAPER_COUNT"
echo "  Relationships: $REL_COUNT"
