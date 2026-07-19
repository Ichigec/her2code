#!/usr/bin/env python3
"""Post-edit verification hook (post_tool_call).

After a ``write_file`` / ``patch`` tool call, run the project's *fast* checks
(lint + a targeted test) on the edited file and queue any failures so the
companion ``inject-verify-feedback.py`` (pre_llm_call) can feed them back to
the model on its next turn.

``post_tool_call`` is observational in Hermes — its stdout is ignored — so the
feedback is delivered out-of-band via a per-session queue file under
``~/.hermes/.verify-feedback/`` rather than from this script's stdout.

Scope / safety:
- Only acts on write_file / patch with a resolvable file path.
- Only runs inside a git repository (skips scratch/temp files to avoid noise).
- Lint is always run (fast). A single *targeted* test file is run when one can
  be located (never the whole suite).
- Toggle off entirely with ``HERMES_POST_EDIT_VERIFY=0``.
- Toggle targeted tests off with ``HERMES_POST_EDIT_TESTS=0``.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

LINT_TIMEOUT = 25
TEST_TIMEOUT = 60
MAX_OUTPUT_CHARS = 4000


def _falsey(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in {"0", "false", "no", "off"}


def _find_git_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, f"(timed out after {timeout}s)"
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return 127, str(exc)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _lint(path: Path, repo: Path) -> str | None:
    ext = path.suffix.lower()
    if ext == ".py":
        if shutil.which("ruff"):
            rc, out = _run(["ruff", "check", str(path)], repo, LINT_TIMEOUT)
            if rc not in (0, 124, 127) and out:
                return f"ruff check:\n{out}"
        else:
            rc, out = _run([sys.executable, "-m", "py_compile", str(path)], repo, LINT_TIMEOUT)
            if rc not in (0, 124) and out:
                return f"py_compile:\n{out}"
    elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        eslint = repo / "node_modules" / ".bin" / "eslint"
        if eslint.is_file():
            rc, out = _run([str(eslint), str(path)], repo, LINT_TIMEOUT)
            if rc not in (0, 124) and out:
                return f"eslint:\n{out}"
    return None


def _find_test_target(path: Path, repo: Path) -> Path | None:
    name = path.name
    if re.match(r"^test_.*\.py$", name) or re.match(r".*_test\.py$", name):
        return path
    if path.suffix.lower() != ".py":
        return None
    stem = path.stem
    candidates = [f"test_{stem}.py", f"{stem}_test.py"]
    # Sibling first, then common test dirs (bounded — no full-repo rglob).
    search_dirs = [path.parent]
    for d in ("tests", "test"):
        td = repo / d
        if td.is_dir():
            search_dirs.append(td)
    for base in search_dirs:
        for cand in candidates:
            direct = base / cand
            if direct.is_file():
                return direct
        if base != path.parent:
            for cand in candidates:
                for hit in base.rglob(cand):
                    if hit.is_file():
                        return hit
    return None


def _pytest_cmd() -> list[str] | None:
    """Return a runnable pytest invocation, or None if pytest isn't installed.

    Guards against ``python -m pytest`` returning a generic non-zero
    "No module named pytest" — which would otherwise be reported as a
    spurious test failure.
    """
    if shutil.which("pytest"):
        return ["pytest"]
    rc, _ = _run([sys.executable, "-c", "import pytest"], Path.cwd(), 10)
    if rc == 0:
        return [sys.executable, "-m", "pytest"]
    return None


def _test(path: Path, repo: Path) -> str | None:
    if _falsey("HERMES_POST_EDIT_TESTS"):
        return None
    if path.suffix.lower() != ".py":
        return None
    target = _find_test_target(path, repo)
    if target is None:
        return None
    base = _pytest_cmd()
    if base is None:
        return None
    rc, out = _run(base + ["-q", "-x", str(target)], repo, TEST_TIMEOUT)
    if rc not in (0, 124) and out:
        return f"pytest {target.relative_to(repo)}:\n{out}"
    if rc == 124:
        return f"pytest {target.relative_to(repo)}: {out}"
    return None


def _queue(session_id: str, path: Path, failures: list[str]) -> None:
    qdir = Path(os.path.expanduser("~/.hermes/.verify-feedback"))
    qdir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id) or "default"
    body = "\n\n".join(failures)
    if len(body) > MAX_OUTPUT_CHARS:
        body = body[:MAX_OUTPUT_CHARS] + "\n…(truncated)"
    entry = f"### Edited `{path}`\n{body}\n"
    with open(qdir / f"{safe}.md", "a", encoding="utf-8") as fh:
        fh.write(entry)


def main() -> None:
    if _falsey("HERMES_POST_EDIT_VERIFY"):
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("tool_name") not in ("write_file", "patch"):
        return
    tin = payload.get("tool_input") or {}
    raw = tin.get("path") if isinstance(tin, dict) else None
    if not raw or not isinstance(raw, str):
        return

    cwd = payload.get("cwd") or os.getcwd()
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        p = Path(cwd) / p
    try:
        p = p.resolve()
    except OSError:
        return
    if not p.is_file():
        return

    repo = _find_git_root(p.parent)
    if repo is None:
        return

    failures: list[str] = []
    try:
        lint = _lint(p, repo)
        if lint:
            failures.append(lint)
        test = _test(p, repo)
        if test:
            failures.append(test)
    except Exception:
        return

    if failures:
        _queue(payload.get("session_id") or "", p, failures)


if __name__ == "__main__":
    main()
