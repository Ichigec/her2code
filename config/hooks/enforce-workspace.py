#!/usr/bin/env python3
"""Enforce workspace boundaries — blocks write_file/patch/write outside allowed dirs.
post_tool_call hook. Matches: write_file, patch, terminal (file creation)."""

import json, os, sys, re
from pathlib import Path

HOME = Path.home()
ALLOWED_ROOTS = [
    HOME / "dev" / "codemes",          # workspace
    HOME / ".hermes",                   # config, skills, agents, hooks, scripts
    HOME / "tmp",                       # /tmp (via symlink or direct)
    Path("/tmp"),                       # /tmp
    HOME / "dev" / "Opencode",         # Android source (legacy, symlinked)
    HOME / "cursor",                    # OpenCode+ project
    HOME / "jupyterlab",               # Jupyter
]

def is_allowed(path_str: str) -> bool:
    path = Path(os.path.expanduser(path_str)).resolve()
    for root in ALLOWED_ROOTS:
        resolved_root = root.resolve()
        try:
            path.relative_to(resolved_root)
            return True
        except ValueError:
            continue
    return False

def main():
    try:
        payload = json.load(sys.stdin)
    except:
        return

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("write_file", "patch"):
        return

    params = payload.get("tool_params", {})
    path_str = params.get("path", "") or params.get("file_path", "")
    if not path_str:
        return

    if is_allowed(path_str):
        return  # OK — silent pass

    # BLOCKED
    allowed_list = "\n".join(f"  {r}" for r in ALLOWED_ROOTS)
    msg = (
        f"🚫 WORKSPACE VIOLATION: {path_str}\n\n"
        f"Write outside allowed directories.\n\n"
        f"Allowed roots:\n{allowed_list}\n\n"
        f"Action: move to ~/dev/codemes/<project>/ or ~/.hermes/<subdir>/"
    )
    print(json.dumps({"block": True, "reason": msg}, ensure_ascii=False))

if __name__ == "__main__":
    main()
