"""
Project detection utility — identifies project type and structure.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def detect_project_type(workdir: str) -> str:
    """
    Detect project type by looking for marker files.

    Returns: 'python', 'kotlin', 'typescript', 'make', 'python-simple', or 'unknown'
    """
    wd = Path(workdir)

    markers = [
        ("python", ["pyproject.toml", "setup.py", "requirements.txt"]),
        ("kotlin", ["build.gradle.kts", "build.gradle"]),
        ("typescript", ["tsconfig.json", "package.json"]),
    ]

    for ptype, files in markers:
        for f in files:
            if (wd / f).exists():
                return ptype

    # Fallback heuristics
    if (wd / "Makefile").exists():
        return "make"

    # Check for any .py files in root or subdirectories
    py_files = list(wd.rglob("*.py"))
    if py_files:
        return "python-simple"

    return "unknown"


def get_changed_files(workdir: str) -> set[str]:
    """Get files changed since last commit via git diff."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=workdir,
            timeout=10,
        )
        if result.returncode == 0:
            return set(
                f.strip()
                for f in result.stdout.strip().split("\n")
                if f.strip()
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return set()


def get_git_commit(workdir: str) -> str:
    """Get HEAD commit hash."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=workdir,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return "unknown"


def get_test_file_for_source(source_path: str, workdir: str) -> Optional[str]:
    """
    Find corresponding test file for a source file.

    Convention: src/auth/login.py → tests/test_auth.py or tests/auth/test_login.py
    """
    wd = Path(workdir)
    source = Path(source_path)
    module_name = source.stem  # 'login' from 'login.py'

    # Strategy 1: tests/test_<module>.py
    candidates = list(wd.rglob(f"test_{module_name}.py"))
    if candidates:
        return str(candidates[0].relative_to(wd))

    # Strategy 2: tests/<parent_dir>/test_<module>.py
    parent = source.parent.name  # 'auth' from 'src/auth/login.py'
    candidates = list(wd.rglob(f"test_{parent}.py"))
    if candidates:
        return str(candidates[0].relative_to(wd))

    return None
