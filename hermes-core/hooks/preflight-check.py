#!/usr/bin/env python3
"""Pre-flight check: Neo4j health + memory staleness + skill freshness."""
import json, os, sys, time
from pathlib import Path

def main():
    try:
        payload = json.load(sys.stdin)
    except:
        return

    extra = payload.get("extra") or {}
    if not extra.get("is_first_turn", True):
        return

    session_id = payload.get("session_id") or ""
    marker = Path(os.path.expanduser(f"~/.hermes/.preflight/{session_id}.done"))
    if session_id and marker.exists():
        return

    warnings = []

    # Check Neo4j health
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "3", "http://localhost:7474"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0 or "neo4j" not in r.stdout.lower():
            warnings.append("⚠️ Neo4j не отвечает на :7474 — графовый поиск недоступен")
    except:
        warnings.append("⚠️ Neo4j health check failed")

    # Check memory staleness
    memory_file = Path(os.path.expanduser("~/.hermes/memories/MEMORY.md"))
    if memory_file.exists():
        age_days = (time.time() - memory_file.stat().st_mtime) / 86400
        if age_days > 30:
            warnings.append(f"⚠️ MEMORY.md не обновлялся {age_days:.0f} дней")

    # Check skill freshness
    skills_dir = Path(os.path.expanduser("~/.hermes/skills"))
    if skills_dir.exists():
        total = len(list(skills_dir.rglob("SKILL.md")))
        recent = sum(1 for f in skills_dir.rglob("SKILL.md") 
                    if (time.time() - f.stat().st_mtime) / 86400 < 90)
        if total > 0 and recent / total < 0.5:
            warnings.append(f"⚠️ {total-recent}/{total} навыков не обновлялись >90 дней")

    # Check Hermes Gateway health
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "3", "http://localhost:8643/health"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0 or "ok" not in r.stdout:
            warnings.append("⚠️ Hermes Gateway API (8643) не отвечает")
    except:
        pass

    if not warnings:
        return  # все хорошо — молчим

    note = "[PRE-FLIGHT CHECK]\n" + "\n".join(warnings) + "\n(Automated — not a user message.)"
    print(json.dumps({"context": note}, ensure_ascii=False))

    if session_id:
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("1")
        except OSError:
            pass

if __name__ == "__main__":
    main()
