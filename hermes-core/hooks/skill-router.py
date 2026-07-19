#!/usr/bin/env python3
"""Extended skill router — coding, research, deploy, voice, graph, env patterns."""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path

_PATTERNS = {
    "coding": re.compile(r"\b(implement|refactor|debug|fix bug|feature|write test|build|unit test|pull request|migrate|optimize|create module|compile|failing test|stack trace|traceback|regression)\b", re.I),
    "research": re.compile(r"\b(research|investigate|analyze|survey|literature|paper|arxiv|deep analysis|study)\b", re.I),
    "voice": re.compile(r"\b(voice|audio|tts|stt|speech|microphone|speak|listen|transcribe|synthesize)\b", re.I),
    "graph": re.compile(r"\b(neo4j|graph|knowledge graph|cypher|ingest|embedding|vector|node|edge|FTS5)\b", re.I),
    "deploy": re.compile(r"\b(deploy|publish|release|ship|APK|install|adb install|npm publish|docker push|rollout)\b", re.I),
    "env": re.compile(r"\b(pavel|jetson|android|phone|adb|honor|cellular|vps|tunnel|ssh reverse)\b", re.I),
    "security": re.compile(r"\b(security|vulnerability|exploit|CVE|SAST|bandit|semgrep|gitleaks|OWASP|auth|injection)\b", re.I),
    "android": re.compile(r"\b(android|kotlin|compose|APK|gradle|build\.gradle|adb install)\b", re.I),
}

_SKILL_MAP = {
    "coding": ["plan", "test-driven-development", "requesting-code-review", "subagent-driven-development"],
    "research": ["research-loop"],
    "voice": ["voice-chat-integration", "hermes-voice-pipeline"],
    "graph": ["neo4j-knowledge-graph", "neo4j-agent-graph"],
    "deploy": ["deployment-operations"],
    "env": ["pavel-environment", "hermes-agent"],
    "security": ["secure-coding", "sast-audit"],
    "android": ["android-hermes-gui", "android-hermes-app", "voice-chat-integration"],
}

def main():
    if os.environ.get("HERMES_SKILL_ROUTER", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    try:
        payload = json.load(sys.stdin)
    except:
        return

    extra = payload.get("extra") or {}
    if not extra.get("is_first_turn", True):
        return

    msg = ""
    for key in ("user_message",):
        val = extra.get(key)
        if isinstance(val, str):
            msg = val
            break
    if not msg:
        return

    # Find matching domains
    matched = [domain for domain, pat in _PATTERNS.items() if pat.search(msg)]
    if not matched:
        return

    # Collect skills for matched domains
    skills = []
    seen = set()
    for domain in matched:
        for s in _SKILL_MAP.get(domain, []):
            if s not in seen:
                skills.append(s)
                seen.add(s)

    if not skills:
        return

    # Deduplicate per session
    session_id = payload.get("session_id") or ""
    marker_dir = Path(os.path.expanduser("~/.hermes/.skill-router"))
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id) or "default"
    marker = marker_dir / f"{safe}.done"
    if session_id and marker.exists():
        return

    nudge = (
        f"[SKILL ROUTER — domains: {', '.join(matched)}]\n"
        f"Load these skills before starting: {', '.join(skills)}. "
        "Use `skill_view(name)` for each. "
        "Check Neo4j education graph for known pitfalls in these domains. "
        "(Automated — not a user message.)"
    )
    print(json.dumps({"context": nudge}, ensure_ascii=False))

    if session_id:
        try:
            marker_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text("1", encoding="utf-8")
        except OSError:
            pass

if __name__ == "__main__":
    main()
