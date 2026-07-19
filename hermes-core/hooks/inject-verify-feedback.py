#!/usr/bin/env python3
"""Deliver queued post-edit verification failures back to the model.

Companion to ``post-edit-verify.py``. Runs on ``pre_llm_call`` (fired once per
turn before the tool loop). If the current session has queued lint/test
failures, emit them as injected context (``{"context": ...}``) — the only
shell-hook channel that actually reaches the model — then clear the queue.

Because ``post_tool_call`` is observational, failures detected during a turn
surface at the start of the *next* turn. Fast and cheap when there is nothing
queued (one path stat).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    session_id = payload.get("session_id") or ""
    if not session_id:
        return

    qdir = Path(os.path.expanduser("~/.hermes/.verify-feedback"))
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id) or "default"
    qfile = qdir / f"{safe}.md"
    if not qfile.is_file():
        return

    try:
        text = qfile.read_text(encoding="utf-8").strip()
    except OSError:
        return
    finally:
        try:
            qfile.unlink()
        except OSError:
            pass

    if not text:
        return

    context = (
        "[POST-EDIT VERIFICATION — automated lint/test checks on files you "
        "edited last turn]\n"
        "These fast checks FAILED. Fix them before continuing, then re-run the "
        "checks to confirm green. Do not commit while these are failing.\n\n"
        f"{text}\n"
        "(Automated note from the post-edit verify hook — not a user message.)"
    )
    print(json.dumps({"context": context}, ensure_ascii=False))


if __name__ == "__main__":
    main()
