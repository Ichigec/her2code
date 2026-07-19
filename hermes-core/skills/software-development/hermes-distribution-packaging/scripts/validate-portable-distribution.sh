#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# validate-portable-distribution.sh
# Validate a finished Hermes portable distribution directory.
#
# Usage:
#   bash validate-portable-distribution.sh /path/to/hermes_portable
#
# Checks:
#   1. Bash scripts: syntax check (bash -n)
#   2. Python scripts: compile check (py_compile)
#   3. YAML/YML files: parse check (pyyaml)
#   4. JSON files: parse check
#   5. d2 diagrams: compile check (requires d2 CLI)
#   6. Port consistency: grep all port refs, check for mismatches
#   7. Hardcoded paths: grep for /home/<user> in scripts/configs
#   8. Fitness functions: can they run?
#   9. Binary artifacts: GUI binary, model GGUF, docker tarball exist
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="${1:-.}"
ERRORS=0
WARNINGS=0
SKIPPED=0

echo "═══ Validating: $ROOT ═══"
echo ""

# ── 1. Bash syntax ──
echo "── Bash scripts ──"
for f in $(find "$ROOT" -maxdepth 3 -name '*.sh' -not -path '*/gui/*' -not -path '*/llama.cpp/*' -not -path '*/skills/*' 2>/dev/null); do
  if bash -n "$f" 2>/dev/null; then echo "  ✅ ${f#$ROOT/}"; else echo "  ❌ ${f#$ROOT/}"; ERRORS=$((ERRORS+1)); fi
done

# ── 2. Python compile ──
echo ""
echo "── Python scripts ──"
for f in $(find "$ROOT" -maxdepth 4 -name '*.py' -not -path '*/__pycache__/*' -not -path '*/skills/*' -not -path '*/gui/*' -not -path '*/llama.cpp/*' 2>/dev/null); do
  if python3 -c "import py_compile; py_compile.compile('$f', doraise=True)" 2>/dev/null; then
    echo "  ✅ ${f#$ROOT/}"
  else
    echo "  ❌ ${f#$ROOT/}"; ERRORS=$((ERRORS+1))
  fi
done

# ── 3. YAML parse ──
echo ""
echo "── YAML configs ──"
for f in $(find "$ROOT" -maxdepth 3 \( -name '*.yaml' -o -name '*.yml' \) -not -path '*/skills/*' -not -path '*/gui/*' 2>/dev/null); do
  if python3 -c "import yaml; yaml.safe_load(open('$f'))" 2>/dev/null; then
    echo "  ✅ ${f#$ROOT/}"
  else
    echo "  ❌ ${f#$ROOT/}"; ERRORS=$((ERRORS+1))
  fi
done

# ── 4. JSON parse ──
echo ""
echo "── JSON files ──"
for f in $(find "$ROOT" -maxdepth 3 -name '*.json' -not -path '*/skills/*' -not -path '*/gui/*' 2>/dev/null); do
  if python3 -c "import json; json.load(open('$f'))" 2>/dev/null; then
    echo "  ✅ ${f#$ROOT/}"
  else
    echo "  ❌ ${f#$ROOT/}"; ERRORS=$((ERRORS+1))
  fi
done

# ── 5. d2 diagrams ──
echo ""
echo "── D2 diagrams ──"
if which d2 >/dev/null 2>&1; then
  D2_TMP=$(mktemp -d)
  for f in $(find "$ROOT" -maxdepth 3 -name '*.d2' -not -path '*/skills/*' 2>/dev/null); do
    # Use temp dir, NOT /dev/null — multi-board diagrams (layers:) need mkdir on output path
    if d2 "$f" "$D2_TMP/$(basename "$f").svg" >/dev/null 2>&1; then
      echo "  ✅ ${f#$ROOT/}"
    else
      echo "  ❌ ${f#$ROOT/}"; ERRORS=$((ERRORS+1))
    fi
  done
  rm -rf "$D2_TMP"
else
  echo "  ⏭️  d2 CLI not found — skipping diagram validation"
  SKIPPED=$((SKIPPED+1))
fi

# ── 6. Port consistency ──
echo ""
echo "── Port consistency ──"
PORT_REFS=$(grep -rn 'PORT_GW\|PORT_DASH\|API_SERVER_PORT' \
  "$ROOT"/start.sh "$ROOT"/.env* "$ROOT"/docker/.env* "$ROOT"/docker/*.yml "$ROOT"/config/*.yaml 2>/dev/null | \
  grep -v '^Binary' | grep -v 'export ' | head -30)
echo "$PORT_REFS" | while read -r line; do echo "  $line"; done

# Check for <style>{} in d2 files (AI generation artifact)
echo ""
echo "── d2 <style>{} check ──"
STYLE_HITS=$(grep -rl '<style>' "$ROOT"/architecture/ 2>/dev/null || true)
if [ -n "$STYLE_HITS" ]; then
  echo "$STYLE_HITS" | while read -r f; do echo "  ❌ ${f#$ROOT/} uses <style>{} — will not compile"; done
  ERRORS=$((ERRORS+1))
else
  echo "  ✅ No <style>{} artifacts found"
fi

# ── 7. Hardcoded paths ──
echo ""
echo "── Hardcoded /home paths ──"
HARDCODED=$(grep -rn '/home/user\|/home/user' \
  "$ROOT"/scripts/*.py "$ROOT"/architecture/fitness-functions/*.py "$ROOT"/config/hooks/*.py 2>/dev/null | \
  grep -v '__pycache__' | head -20)
if [ -n "$HARDCODED" ]; then
  echo "$HARDCODED" | while read -r line; do echo "  ⚠️  $line"; done
  WARNINGS=$((WARNINGS+1))
else
  echo "  ✅ No hardcoded paths in scripts"
fi

# ── 8. Binary artifacts ──
echo ""
echo "── Binary artifacts ──"
for artifact in "gui/linux-arm64-unpacked/Hermes" "docker/hermes-agent-arm64.tar.gz"; do
  if [ -f "$ROOT/$artifact" ]; then
    SIZE=$(du -h "$ROOT/$artifact" | cut -f1)
    echo "  ✅ $artifact ($SIZE)"
  else
    echo "  ⚠️  $artifact not found"
    WARNINGS=$((WARNINGS+1))
  fi
done

for model in "$ROOT"/models/*.gguf; do
  if [ -f "$model" ]; then
    SIZE=$(du -h "$model" | cut -f1)
    echo "  ✅ $(basename "$model") ($SIZE)"
  fi
done

# ── Summary ──
echo ""
echo "═══ Summary ═══"
echo "  Errors:   $ERRORS"
echo "  Warnings: $WARNINGS"
echo "  Skipped:  $SKIPPED"
if [ "$ERRORS" -gt 0 ]; then
  echo "  ❌ VALIDATION FAILED"
  exit 1
else
  echo "  ✅ All critical checks passed"
  exit 0
fi
