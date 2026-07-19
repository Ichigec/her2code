"""
Terminal utility — subprocess wrapper for gate tools.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass


@dataclass
class TerminalResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


def run(
    cmd: list[str] | str,
    workdir: str = ".",
    timeout: int = 120,
    env: dict | None = None,
) -> TerminalResult:
    """
    Run a shell command and return structured result.

    Args:
        cmd: command as list (preferred) or string
        workdir: working directory
        timeout: timeout in seconds
        env: environment variables (defaults to os.environ)

    Returns:
        TerminalResult with exit_code, stdout, stderr, duration_ms
    """
    if isinstance(cmd, str):
        cmd = ["bash", "-c", cmd]

    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
            env=env or None,
        )
    except subprocess.TimeoutExpired as e:
        return TerminalResult(
            command=" ".join(cmd),
            exit_code=-1,
            stdout=e.stdout or "",
            stderr=f"Command timed out after {timeout}s: {e.stderr or ''}",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except FileNotFoundError as e:
        return TerminalResult(
            command=" ".join(cmd),
            exit_code=-2,
            stdout="",
            stderr=f"Command not found: {e}",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except Exception as e:
        return TerminalResult(
            command=" ".join(cmd),
            exit_code=-3,
            stdout="",
            stderr=f"Unexpected error: {e}",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    return TerminalResult(
        command=" ".join(cmd),
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
