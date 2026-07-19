#!/bin/bash
# ============================================================================
# PII Verification Test — Reusable template for any distribution
# Usage: bash test-pii.sh /path/to/distribution
# ============================================================================
# Excludes: self (test-pii.sh), binary dumps, .git, __pycache__
# Checks: personal paths, IPs, device IDs, Telegram, secrets, API keys,
#         memories/, pavel-environment/, codemes_1 refs, changeme defaults
# ============================================================================
set -euo pipefail

DIST_DIR="${1:-.}"
FAIL=0
TOTAL=0
PASSED=0

EXCLUDES="--exclude=*.dump --exclude=test-pii.sh --exclude-dir=.git --exclude-dir=__pycache__"

check() {
    local desc="$1"
    local cmd="$2"
    TOTAL=$((TOTAL + 1))
    local result
    result=$(bash -c "$cmd" 2>/dev/null | head -3)
    if [ -z "$result" ]; then
        echo "  ✅ $desc"
        PASSED=$((PASSED + 1))
    else
        echo "  ❌ $desc"
        echo "     $result"
        FAIL=1
    fi
}

echo "╔══════════════════════════════════════════════════╗"
echo "║  PII Verification                                ║"
echo "╚══════════════════════════════════════════════════╝"
echo "  Target: $DIST_DIR"
echo ""

# ── Personal paths ──────────────────────────────────────────────────────────
check "No /home/user/"         "grep -rl $EXCLUDES '/home/user/' '$DIST_DIR/'"
check "No /home/user (word)"    "grep -rl $EXCLUDES '/home/user' '$DIST_DIR/'"

# ── IP addresses (replace with your own) ────────────────────────────────────
check "No VPS IP"               "grep -rl $EXCLUDES '64\.188\.64\.52' '$DIST_DIR/'"

# ── Device IDs (replace with your own) ──────────────────────────────────────
check "No phone ID"             "grep -rl $EXCLUDES '<YOUR_DEVICE_ID>' '$DIST_DIR/'"

# ── Telegram (replace with your own) ────────────────────────────────────────
check "No Telegram chat_id"     "grep -rl $EXCLUDES '1003011121225' '$DIST_DIR/'"
check "No @raicomml"            "grep -rl $EXCLUDES '@raicomml' '$DIST_DIR/'"
check "No raicomml"             "grep -rl $EXCLUDES 'raicomml' '$DIST_DIR/'"

# ── Secrets ─────────────────────────────────────────────────────────────────
check "No .sudo_pass file"      "find '$DIST_DIR/' -name '.sudo_pass'"
check "No real .env"            "find '$DIST_DIR/' -name '.env' -not -name '*.example' -not -path '*/env/*'"
check "No auth.json"            "find '$DIST_DIR/' -name 'auth.json'"
check "No state.db"             "find '$DIST_DIR/' -name 'state.db*'"
check "No API keys (sk-)"       "grep -rlP $EXCLUDES 'sk-[a-zA-Z0-9]{20,}' '$DIST_DIR/'"
check "No __pycache__"          "find '$DIST_DIR/' -name '__pycache__'"

# ── Personal data directories ───────────────────────────────────────────────
check "No memories/"            "find '$DIST_DIR/' -path '*/memories/*' -type f"
check "No pavel-environment/"   "find '$DIST_DIR/' -path '*/pavel-environment/*' -type f"

# ── Naming (replace codemes_1 with your old dist name) ─────────────────────
check "No codemes_1 refs"       "grep -rl $EXCLUDES 'codemes_1' '$DIST_DIR/'"
check "No changeme (lowercase)" "grep -rl $EXCLUDES 'changeme' '$DIST_DIR/'"

# ── gitleaks (if available) ────────────────────────────────────────────────
if command -v gitleaks &>/dev/null; then
    check "gitleaks clean"      "gitleaks detect --source '$DIST_DIR/' --no-git -v 2>&1 | grep -i 'leak'"
else
    echo "  ℹ gitleaks not installed — skipping"
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "─── Summary ───"
echo "  Passed: $PASSED / $TOTAL"
if [ "$FAIL" -eq 0 ]; then
    echo "  ✅ ALL PII CHECKS PASSED"
    exit 0
else
    echo "  ❌ SOME CHECKS FAILED"
    exit 1
fi
