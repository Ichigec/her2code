#!/bin/bash
# Observer worker fallback wrapper — runs worker, only prints if sessions found.
# Used by cron job c4e543ccefb2 as a fallback for the fire-and-forget hook.

OUTPUT=$(python3 /home/user/.hermes/scripts/observer_worker.py 2>&1)
EXIT_CODE=$?

# Only deliver output if there were pending sessions (non-empty output beyond the header)
if echo "$OUTPUT" | grep -q "pending session"; then
    echo "$OUTPUT"
fi
exit $EXIT_CODE
