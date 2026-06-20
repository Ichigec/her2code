#!/usr/bin/env python3
"""AGENTS.md injector — inserts project conventions into first turn context."""
import json, os, sys
from pathlib import Path

def main():
    try:
        payload = json.load(sys.stdin)
    except:
        return

    extra = payload.get("extra") or {}
    # Only on first turn
    if not extra.get("is_first_turn", True):
        return

    session_id = payload.get("session_id") or ""
    marker = Path(os.path.expanduser(f"~/.hermes/.agents-md-inject/{session_id}.done"))
    if session_id and marker.exists():
        return

    # Read universal AGENTS.md
    universal = Path(os.path.expanduser("~/.hermes/AGENTS.md"))
    context_parts = []

    if universal.exists():
        content = universal.read_text()
        # Extract only Known Pitfalls + Environment (most valuable)
        pitfalls_section = extract_section(content, "Known Pitfalls")
        env_section = extract_section(content, "Environment")
        if pitfalls_section:
            context_parts.append("## AGENTS.md — Known Pitfalls\n" + pitfalls_section)
        if env_section:
            context_parts.append("## AGENTS.md — Environment\n" + env_section)

    # Check workspace projects
    workspace = Path(os.path.expanduser("~/dev/codemes"))
    if workspace.exists():
        for proj in workspace.iterdir():
            if proj.is_dir():
                agents_md = proj / "AGENTS.md"
                if agents_md.exists():
                    proj_content = agents_md.read_text()
                    pitfalls = extract_section(proj_content, "Known Pitfalls")
                    if pitfalls:
                        context_parts.append(f"## {proj.name}/AGENTS.md — Pitfalls\n" + pitfalls)

    if not context_parts:
        return

    injected = "\n\n---\n\n".join(context_parts)
    note = "[AUTO-INJECTED — AGENTS.md project conventions. Not a user message.]\n\n"
    print(json.dumps({"context": note + injected}, ensure_ascii=False))

    if session_id:
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("1")
        except OSError:
            pass

def extract_section(text: str, heading: str) -> str:
    """Extract a markdown section by heading."""
    import re
    pattern = rf'##\s+{heading}\s*\n(.*?)(?=\n##\s|\Z)'
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""

if __name__ == "__main__":
    main()
