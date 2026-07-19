#!/usr/bin/env bash
# =============================================================================
# pre_implementation_gate.sh
# =============================================================================
# Pre-Flight Gate hook — вызывается перед Phase 6 (Implementation).
# Запускает orchestrator_gate.py. Если exit code != 0 — выводит ошибку
# и предлагает исправить проблемы перед продолжением.
#
# Usage:
#   ./pre_implementation_gate.sh                # human-readable
#   ./pre_implementation_gate.sh --json         # JSON output (passthrough)
# =============================================================================

set -euo pipefail

GATE_SCRIPT="${HOME}/.hermes/scripts/orchestrator_gate.py"
PYTHON_BIN="${HERMES_PYTHON:-python3}"

# Colours (optional, no-op if not a TTY)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m'  # No Colour
else
    RED='' GREEN='' YELLOW='' NC=''
fi

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  PRE-FLIGHT GATE — проверка перед Implementation${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Verify gate script exists
if [[ ! -f "$GATE_SCRIPT" ]]; then
    echo -e "${RED}[ERROR] Gate script not found: ${GATE_SCRIPT}${NC}"
    echo "        Make sure orchestrator_gate.py is installed."
    exit 2
fi

# Run the gate
set +e  # we want to capture the exit code
"$PYTHON_BIN" "$GATE_SCRIPT" "$@"
GATE_EXIT_CODE=$?
set -e

echo ""

if [[ $GATE_EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✅ ALL CHECKS PASSED — Implementation can proceed.${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  ❌ GATE FAILED — Implementation is BLOCKED.${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Review the failures in the report above."
    echo "  2. Fix each failed check:"
    echo "     • contracts  — start missing services"
    echo "     • ports      — resolve port conflicts"
    echo "     • env_vars   — set HERMES_HOME and/or NEO4J_PASSWORD"
    echo "     • isolation  — ensure HERMES_HOME directory exists"
    echo "     • observers  — restart dead observer processes"
    echo "     • research   — create a research artifact >500 bytes"
    echo "  3. Re-run:  ${GATE_SCRIPT}"
    echo "  4. Once all checks pass, proceed to Implementation."
    echo ""
    exit 1
fi
