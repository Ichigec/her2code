# Unified Proxy Dead End — Lessons Learned

## What we tried
A Python HTTP proxy (unified_proxy.py) on port 8643 that routed:
- Chat models (qwen3.6-35b-heretic, etc.) → LiteLLM :4000
- Agent models (hermes-agent, general, build...) → OpenCode+ :8646

Goal: one endpoint, smart routing, no need for client-side switching.

## Why it failed

| Problem | Detail |
|---------|--------|
| **Background process death** | `terminal(background=true)` processes die silently. The proxy exits and no one knows. |
| **Watchdog interference** | Multiple watchdog loops restart competing processes on the same port. |
| **pkill kills terminal** | `pkill -f pattern` from foreground shell kills the shell itself. |
| **socat fragility** | socat 8643→8647 dies and doesn't restart. Needs separate watchdog. |
| **401 Unauthorized** | LiteLLM key routing works intermittently. Error logging was absent. |
| **502 Bad Gateway** | Proxy exception handler masks real errors. No way to debug without adding logging. |
| **Stale SSH sessions** | VPS sshd-sessions hold port 8643. New tunnel can't bind until old sessions are force-killed with `fuser -k`. |
| **Port conflict** | Hermes Gateway API also wants port 8643. Can't run both without moving ports. |

## What actually works
**Hermes Gateway API on port 8643 directly.** No proxy, no routing, no socat.
One `hermes gateway run` process. One SSH tunnel. One endpoint.

## Watchdog anti-pattern
```bash
# THIS IS BAD — pkill kills the terminal
pkill -f "ssh.*-R.*8643"

# THIS IS BETTER — kill specific PID
kill $(ss -tlnp | grep 8643 | grep -oP 'pid=\K\d+')

# THIS IS SAFEST — fuser on VPS (doesn't affect local terminal)
ssh root@VPS "fuser -k 8643/tcp"
```

## Key takeaway
**Never chain background processes with watchdog loops.** One process, one responsibility.
If it dies, the watchdog restarts it. Don't have watchdog A restart watchdog B.
