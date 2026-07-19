# HERMES_UID/GID Environment Variable Leakage

> Discovered 2026-06-22. When the parent shell has `HERMES_UID`/`HERMES_GID` exported,
> they silently leak into `docker run` commands, triggering slow chown on container boot.

## Problem

When the host shell has `export HERMES_UID=1000` and `export HERMES_GID=1000`,
these variables are passed into `docker run` even WITHOUT explicit `-e` flags:

```bash
# This command was supposed to start WITHOUT UID remap:
env -u HERMES_UID -u HERMES_GID docker run ... hermes-agent dashboard ...

# But the container STILL showed:
#   HERMES_UID=1000
#   HERMES_GID=1000
```

The container then runs the stage2 chown hook (3-5 minutes on Jetson ARM64).

## Diagnosis

```bash
# Check what the container actually received
docker inspect <container> --format '{{json .Config.Env}}' | python3 -m json.tool | grep -E "UID|GID"
```

## Solution

To skip UID remap (fast boot, no chown — useful for testing):

```bash
env -u HERMES_UID -u HERMES_GID docker run ...
```

For production (accept one-time chown, then instant subsequent boots):

```bash
docker run -e HERMES_UID=1000 -e HERMES_GID=1000 ...
```

## chown Timing

| Scenario | First boot | Subsequent boots |
|----------|:----------:|:----------------:|
| `HERMES_UID=1000` set | ~4 min (chown .venv) | Instant (skipped) |
| `HERMES_UID` unset | Instant | Instant |

The stage2 hook checks `venv_owner == actual_hermes_uid` and skips chown when they match.

## Root cause in stage2-hook.sh

```bash
HERMES_UID="${HERMES_UID:-${PUID:-}}"
...
venv_owner=$(stat -c %u "$INSTALL_DIR/.venv" 2>/dev/null || echo "")
if [ -n "$venv_owner" ] && [ "$venv_owner" != "$actual_hermes_uid" ]; then
    chown -R hermes:hermes "$INSTALL_DIR/.venv" ...  # SLOW
fi
```
