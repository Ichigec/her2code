#!/usr/bin/env python3
"""Observer Worker v3 — session-level analysis with activity-gate context.

Reads session context from a JSON file (written by observer-hook plugin),
spawns 4 observer subagents in parallel, each analyzing the FULL session.

Usage:
    observer_worker.py --session-id <sid> --context-file <path>
    observer_worker.py --session-id <sid>                    (queries Neo4j)
    observer_worker.py                                       (batch: pending sessions)
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

NEO4J_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"
NEO4J_AUTH = os.environ.get("NEO4J_AUTH", "neo4j:<YOUR_NEO4J_PASSWORD>")
HERMES_CLI = "/home/user/.hermes/hermes-agent/venv/bin/hermes"
_REAL_HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
LOCK_DIR = Path("/tmp/hermes_observer_locks")
OBSERVER_NAMES = ["auditor", "critic", "idea-generator", "knowledge-curator"]


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def neo4j_query(statement, params=None):
    payload = json.dumps({"statements": [{"statement": statement, "parameters": params or {}}]})
    try:
        r = subprocess.run(
            ["curl", "-s", "-u", NEO4J_AUTH, "-H", "Content-Type: application/json",
             "-d", payload, NEO4J_URL],
            capture_output=True, text=True, timeout=15
        )
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def acquire_lock(session_id: str) -> bool:
    """Try to acquire a lock for this session. Returns True if acquired."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / f"observer_{session_id}.lock"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(fd, str(os.getpid()).encode())
        return True
    except (BlockingIOError, OSError):
        return False


def get_pending_sessions():
    """Get sessions marked for observer review."""
    result = neo4j_query(
        "MATCH (s:Session) WHERE s.status = 'pending_observer_review' "
        "RETURN s.session_id AS sid, s.agent_preset AS preset, s.total_turns AS turns "
        "ORDER BY s.ended_at LIMIT 5"
    )
    try:
        return [{"session_id": r["row"][0], "preset": r["row"][1] or "unknown", "turns": r["row"][2] or 0}
                for r in result["results"][0]["data"]]
    except Exception:
        return []


def load_context(session_id: str, context_file: str | None = None) -> dict:
    """Load session context from JSON file or fall back to Neo4j query."""
    # Prefer context file from plugin (richer data)
    if context_file:
        try:
            data = json.loads(Path(context_file).read_text())
            if data.get("session_id") == session_id:
                return data
        except Exception:
            pass

    # Fallback: query Neo4j
    result = neo4j_query(
        "MATCH (s:Session {session_id: $sid}) "
        "RETURN s.agent_preset AS preset, s.total_turns AS turns, "
        "s.platform AS platform, s.msg_count AS msgs, "
        "s.tool_calls AS tools, s.input_tokens AS itok",
        {"sid": session_id}
    )
    try:
        data = result["results"][0]["data"]
        if data:
            row = data[0]["row"]
            return {
                "session_id": session_id,
                "agent_preset": row[0] or "unknown",
                "total_turns": row[1] or 0,
                "platform": row[2] or "tui",
                "message_count": row[3] or 0,
                "tool_call_count": row[4] or 0,
                "input_tokens": row[5] or 0,
            }
    except Exception:
        pass
    return {"session_id": session_id, "agent_preset": "unknown", "total_turns": 0,
            "platform": "tui", "message_count": 0, "tool_call_count": 0, "input_tokens": 0}


def spawn_observer(name: str, ctx: dict) -> str:
    """Spawn a single observer via hermes CLI with rich session context."""
    session_id = ctx["session_id"]
    agent_file = _REAL_HERMES_HOME / "agents" / f"{name}.md"
    if not agent_file.exists():
        return f"SKIP (no {name}.md)"

    preset = ctx.get("agent_preset", "unknown")
    turns = ctx.get("total_turns", 0)
    msgs = ctx.get("message_count", 0)
    tools = ctx.get("tool_call_count", 0)
    itok = ctx.get("input_tokens", 0)

    # Rich prompt: full session context so observer sees the big picture
    prompt = (
        f"Session analysis for {name} observer.\n"
        f"\n"
        f"Session: {session_id}\n"
        f"Agent preset: {preset}\n"
        f"Stats: {msgs} messages, {tools} tool calls, {turns} LLM turns, "
        f"{itok} input tokens\n"
        f"\n"
        f"INSTRUCTIONS:\n"
        f"1. Use session_search(session_id='{session_id}') to read the FULL "
        f"conversation — all messages, tool calls, tool results.\n"
        f"2. Focus on the ENTIRE session arc, not individual turns:\n"
        f"   - What was the goal? Was it achieved?\n"
        f"   - What went wrong and how was it fixed?\n"
        f"   - Were there patterns of inefficiency (repeated mistakes, loops)?\n"
        f"   - What ideas emerged that could improve Hermes itself?\n"
        f"   - What knowledge was created or referenced?\n"
        f"3. Write findings to Neo4j at {NEO4J_URL} (auth neo4j:<YOUR_NEO4J_PASSWORD>):\n"
        f"   - Auditor → CREATE (:AuditFinding {{session_id, severity, finding, "
        f"evidence, recommendation, timestamp}})\n"
        f"   - Critic → CREATE (:CriticFinding {{session_id, category, finding, "
        f"root_cause, preventive, timestamp}})\n"
        f"   - Idea Generator → CREATE (:Idea {{session_id, category, idea, "
        f"potential_value, timestamp}}) + (:Mutation {{...}})\n"
        f"   - Knowledge Curator → MERGE (:KnowledgeEntity {{name, type, "
        f"description, confidence, source}})\n"
        f"4. Follow your agent definition in {agent_file}.\n"
        f"5. Write 3-7 findings, be specific and actionable. "
        f"Reference exact messages/turns as evidence.\n"
    )

    try:
        r = subprocess.run(
            [HERMES_CLI, "chat", "-q", prompt, "--yolo",
             "-m", "deepseek-v4-pro", "--provider", "deepseek",
             "--source", "observer"],
            capture_output=True, text=True, timeout=180,
            env={**os.environ, "HERMES_NO_COLOR": "1",
                 "HERMES_OBSERVER_SUBAGENT": "1",
                 "HERMES_SESSION_SOURCE": "observer"}
        )
        return "ok" if r.returncode == 0 else f"FAIL (rc={r.returncode})"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def process_session(ctx: dict) -> dict:
    """Spawn all 4 observers in parallel for a session."""
    sid = ctx["session_id"]
    print(f"  [{_ts()}] Session: {sid}")
    print(f"    preset={ctx.get('agent_preset')}, turns={ctx.get('total_turns')}, "
          f"msgs={ctx.get('message_count')}, tools={ctx.get('tool_call_count')}, "
          f"tok={ctx.get('input_tokens')}")

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(spawn_observer, name, ctx): name
            for name in OBSERVER_NAMES
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = f"EXCEPTION: {e}"
            print(f"    [{name}] → {results[name]}")

    return results


def mark_done(session_id: str) -> None:
    neo4j_query(
        "MATCH (s:Session {session_id: $sid}) "
        "SET s.status = 'observer_reviewed', s.observer_processed_at = $ts",
        {"sid": session_id, "ts": _ts()}
    )


def main():
    parser = argparse.ArgumentParser(description="Observer Worker v3")
    parser.add_argument("--session-id", "-s", help="Process a specific session")
    parser.add_argument("--context-file", "-c", help="JSON context file from observer-hook plugin")
    args = parser.parse_args()

    print(f"[{_ts()}] Observer Worker v3 starting...")

    if args.session_id:
        sid = args.session_id
        if not acquire_lock(sid):
            print(f"  Session {sid} already being processed (lock held). Skipping.")
            return
        try:
            ctx = load_context(sid, args.context_file)
            results = process_session(ctx)
            print(f"  Results: {results}")
            mark_done(sid)
        finally:
            pass
    else:
        # Batch mode — process pending sessions
        sessions = get_pending_sessions()
        if not sessions:
            print("  No pending sessions.")
            return
        print(f"  {len(sessions)} pending session(s)")
        for s in sessions:
            sid = s["session_id"]
            if not acquire_lock(sid):
                print(f"  Session {sid} locked. Skipping.")
                continue
            try:
                ctx = load_context(sid)
                ctx.update(s)  # merge Neo4j data
                results = process_session(ctx)
                print(f"  Results: {results}")
                mark_done(sid)
            finally:
                pass


if __name__ == "__main__":
    main()
