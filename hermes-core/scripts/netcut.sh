#!/bin/bash
# netcut.sh — Hermes internet kill switch (no root needed)
#
# Uses systemd IPAddressDeny/IPAddressAllow on a user scope.
# Requires Hermes to be launched via:
#   systemd-run --user --scope --unit=hermes hermes gui
#
# Usage:
#   netcut.sh on       — block external internet, keep local services
#   netcut.sh off      — restore internet
#   netcut.sh status   — show current state
#   netcut.sh toggle   — flip state (default)
#   netcut.sh check    — verify scope exists, show diagnostics

set -euo pipefail

UNIT="${HERMES_NETCUT_UNIT:-hermes.scope}"

# Local ranges to whitelist (IPv4 + IPv6)
ALLOW=(
  "127.0.0.0/8"
  "10.0.0.0/8"
  "172.16.0.0/12"
  "192.168.0.0/16"
  "::1/128"
  "fe80::/10"
  "fc00::/7"
)

build_allow_args() {
  local args=()
  for cidr in "${ALLOW[@]}"; do
    args+=("IPAddressAllow=$cidr")
  done
  printf '%s\0' "${args[@]}"
}

is_blocked() {
  local deny
  deny=$(systemctl --user show "$UNIT" -p IPAddressDeny --value 2>/dev/null || true)
  # "any" or "::/0 0.0.0.0/0" means blocked; empty means open
  [[ -n "$deny" && "$deny" != "" ]]
}

scope_exists() {
  systemctl --user is-active "$UNIT" &>/dev/null
}

do_on() {
  if ! scope_exists; then
    echo "ERROR: Unit $UNIT is not active." >&2
    echo "Launch Hermes with: systemd-run --user --scope --unit=hermes hermes gui" >&2
    exit 1
  fi

  # Build the set-property arguments
  local props=("IPAddressDeny=any")
  for cidr in "${ALLOW[@]}"; do
    props+=("IPAddressAllow=$cidr")
  done

  systemctl --user set-property --runtime "$UNIT" "${props[@]}"

  # Verify
  if is_blocked; then
    echo "🔒 Internet: BLOCKED"
    echo "   Local services (LiteLLM :4000, Neo4j :7687, MCP :8024) still accessible."
  else
    echo "⚠️  Rule set but verification failed. Check: systemctl --user show $UNIT" >&2
    exit 1
  fi
}

do_off() {
  if ! scope_exists; then
    echo "ERROR: Unit $UNIT is not active." >&2
    exit 1
  fi

  systemctl --user set-property --runtime "$UNIT" \
    IPAddressDeny= \
    IPAddressAllow=

  if is_blocked; then
    echo "⚠️  Failed to clear block. Check: systemctl --user show $UNIT" >&2
    exit 1
  else
    echo "🌐 Internet: OPEN"
  fi
}

do_status() {
  if ! scope_exists; then
    echo "❌ Unit $UNIT not active — Hermes not running in a scope."
    echo "   Start with: systemd-run --user --scope --unit=hermes hermes gui"
    exit 1
  fi

  if is_blocked; then
    echo "🔒 BLOCKED — external internet is cut off"
    echo "   Allowed: $(systemctl --user show "$UNIT" -p IPAddressAllow --value)"
    echo "   Denied:  $(systemctl --user show "$UNIT" -p IPAddressDeny --value)"
  else
    echo "🌐 OPEN — internet is unrestricted"
  fi
}

do_check() {
  echo "=== Netcut Diagnostics ==="
  echo "Unit: $UNIT"
  echo "Active: $(systemctl --user is-active "$UNIT" 2>/dev/null || echo 'no')"
  echo "cgroup: $(systemctl --user show "$UNIT" -p ControlGroup --value 2>/dev/null || echo 'n/a')"
  echo "IPAddressDeny: $(systemctl --user show "$UNIT" -p IPAddressDeny --value 2>/dev/null || echo 'n/a')"
  echo "IPAddressAllow: $(systemctl --user show "$UNIT" -p IPAddressAllow --value 2>/dev/null || echo 'n/a')"
  echo ""
  echo "Hermes PIDs in this scope:"
  local cg
  cg=$(systemctl --user show "$UNIT" -p ControlGroup --value 2>/dev/null || true)
  if [[ -n "$cg" && "$cg" != "" ]]; then
    local cgpath="/sys/fs/cgroup${cg}"
    if [[ -f "$cgpath/cgroup.procs" ]]; then
      wc -l < "$cgpath/cgroup.procs" | xargs echo "  Process count:"
    fi
  fi
}

case "${1:-toggle}" in
  on)     do_on ;;
  off)    do_off ;;
  status) do_status ;;
  toggle)
    if is_blocked; then do_off; else do_on; fi
    ;;
  check)  do_check ;;
  *)
    echo "Usage: netcut.sh [on|off|status|toggle|check]"
    echo "  on      — block external internet"
    echo "  off     — restore internet"
    echo "  status  — show current state"
    echo "  toggle  — flip state (default)"
    echo "  check   — diagnostics"
    exit 1
    ;;
esac
