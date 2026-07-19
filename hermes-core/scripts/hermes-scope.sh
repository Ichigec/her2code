#!/bin/bash
# hermes-scope.sh — launch Hermes inside a systemd user scope
#
# This wrapper enables /netcut (internet kill switch) by placing Hermes
# and all its child processes in a named systemd scope (hermes.scope).
# The IPAddressDeny/IPAddressAllow BPF filters attach to this scope.
#
# Usage:
#   hermes-scope.sh gui          # launch desktop GUI (most common)
#   hermes-scope.sh chat         # launch CLI chat
#   hermes-scope.sh gateway run  # launch gateway
#   hermes-scope.sh <any hermes args>
#
# After launch, use /netcut on|off|status inside Hermes to toggle internet.

UNIT="hermes.scope"

# Check if scope already exists
if systemctl --user is-active "$UNIT" &>/dev/null; then
  echo "⚠️  $UNIT is already active. Another Hermes instance is running in a scope." >&2
  echo "   To stop it: systemctl --user stop $UNIT" >&2
  echo "   Running without scope (netcut will not work)..." >&2
  exec hermes "$@"
fi

exec systemd-run --user --scope --unit=hermes --same-dir --collect hermes "$@"
