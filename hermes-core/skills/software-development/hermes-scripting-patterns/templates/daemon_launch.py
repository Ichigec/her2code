#!/usr/bin/env python3
"""Double-fork daemon launcher for long-running commands under Hermes Agent.

USAGE: Edit CMD, LOG_DIR, WORKDIR below, then run:
    terminal(command="/venv/bin/python3 daemon_launch.py")
    → Returns daemon PID immediately. Process is orphaned to init (PID 1) and
      survives Hermes session restarts, timeouts, SIGTERM.

WHEN: Tasks that need 30+ hours (ML training, RL pipelines, batch processing).
      Hermes kills background processes after ~35 min even with background=true.
"""

import os, sys, subprocess, time

# ── CONFIGURE THESE ──────────────────────────────────────────────
CMD = [
    "/home/user/.hermes/hermes-agent/venv/bin/python3",
    "-u",
    "/path/to/your_script.py",
]
LOG_DIR = "/path/to/logs"
WORKDIR = "/path/to/workdir"
# ──────────────────────────────────────────────────────────────────

LOG = os.path.join(LOG_DIR, "daemon_%s.log" % time.strftime("%Y%m%d_%H%M%S"))


def daemonize():
    """Double-fork to fully detach from the parent session."""
    pid = os.fork()
    if pid > 0:
        print(f"Daemon PID: {pid}")
        print(f"Log: {LOG}")
        return  # parent exits

    os.setsid()  # new session, no controlling terminal

    pid2 = os.fork()
    if pid2 > 0:
        sys.exit(0)  # intermediate exits → grandchild orphaned to PID 1

    # We are the daemon now
    os.chdir(WORKDIR)
    os.umask(0)

    with open(LOG, "w") as log:
        log.write(f"[{time.ctime()}] Daemon starting (PID {os.getpid()})\n")
        log.write(f"Command: {' '.join(CMD)}\n")
        log.flush()
        result = subprocess.run(CMD, stdout=log, stderr=subprocess.STDOUT)
        log.write(f"\n[{time.ctime()}] Daemon finished (exit={result.returncode}).\n")


if __name__ == "__main__":
    daemonize()
