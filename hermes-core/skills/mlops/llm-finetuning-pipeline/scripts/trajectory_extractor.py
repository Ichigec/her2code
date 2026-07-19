#!/usr/bin/env python3
"""
trajectory_extractor.py — Extracts code-editing trajectories from Hermes state.db
for fine-tuning data generation.

Usage:
    python3 trajectory_extractor.py [--min-tools 20] [--output ~/dev/training_data/trajectories]

Output:
    {output}/{session_id}.json  — one trajectory per file
    {output}/summary.json       — index of all trajectories
    {output}/stats.json         — aggregate statistics

Each trajectory JSON contains:
    - session_id, title, model, cwd, started_at
    - trajectory_type: bug_fix_with_debugging | feature_implementation | code_edit | other
    - n_code_changes: count of patch + write_file operations
    - code_changes[]: list of {tool, path, old_string, new_string}
    - steps[]: full trajectory (user_request → reasoning → tool_call → tool_result → ...)
    - final_result: last assistant response

The state.db path is hardcoded to /home/user/.hermes/state.db because HERMES_HOME
overrides ~ to /home/user/.hermes/home/, making os.path.expanduser('~/.hermes/state.db')
resolve to the wrong (empty) database. Always use the absolute path.
"""

import sqlite3
import json
import os
import re
from datetime import datetime
from pathlib import Path
from argparse import ArgumentParser

# CRITICAL: must be absolute — HOME is overridden by Hermes
DB_PATH = "/home/user/.hermes/state.db"
DEFAULT_OUTPUT = os.path.expanduser("~/dev/training_data/trajectories")
MIN_TOOL_CALLS = 20
CODE_TOOLS = {"patch", "write_file", "read_file", "terminal", "search_files", "execute_code", "list", "glob"}


def extract_session_trajectory(conn, session_id):
    """Extract one session as a structured trajectory."""
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, source, model, cwd,
               started_at, ended_at, tool_call_count, message_count
        FROM sessions WHERE id = ?
    """, (session_id,))
    row = cur.fetchone()
    if not row:
        return None

    sid, title, source, model, cwd, started, ended, tc_count, mc_count = row

    cur.execute("""
        SELECT id, role, content, tool_call_id, tool_calls, tool_name,
               timestamp, reasoning, reasoning_content
        FROM messages
        WHERE session_id = ?
        ORDER BY id ASC
    """, (session_id,))

    messages = cur.fetchall()
    steps = []

    for msg_id, role, content, tool_call_id, tool_calls_json, tool_name, timestamp, reasoning, reasoning_content in messages:
        if role == "user":
            if content and not content.startswith("You are a session observer"):
                steps.append({
                    "type": "user_request",
                    "content": content[:5000],
                    "timestamp": timestamp
                })
        elif role == "assistant":
            if content:
                steps.append({
                    "type": "assistant_reasoning",
                    "content": content[:5000],
                    "timestamp": timestamp
                })
            if tool_calls_json:
                try:
                    tc_list = json.loads(tool_calls_json)
                    if isinstance(tc_list, dict):
                        tc_list = [tc_list]
                    for tc in tc_list:
                        if isinstance(tc, dict) and "function" in tc:
                            fn = tc["function"]
                            try:
                                args = json.loads(fn.get("arguments", "{}"))
                            except:
                                args = {}
                            step = {
                                "type": "tool_call",
                                "tool": fn["name"],
                                "args": _clean_args(fn["name"], args),
                                "timestamp": timestamp
                            }
                            if reasoning_content:
                                step["reasoning"] = reasoning_content[:2000]
                            steps.append(step)
                except json.JSONDecodeError:
                    pass
        elif role == "tool":
            result_content = content[:3000] if content else ""
            success = _determine_success(tool_name, result_content)
            steps.append({
                "type": "tool_result",
                "tool": tool_name,
                "result": result_content,
                "success": success,
                "timestamp": timestamp
            })

    trajectory_type = _classify_trajectory(steps)
    code_changes = _extract_code_changes(steps)

    final_result = None
    for step in reversed(steps):
        if step["type"] == "assistant_reasoning" and len(step["content"]) > 50:
            final_result = step["content"][:1000]
            break

    return {
        "session_id": session_id,
        "title": title,
        "source": source,
        "model": model,
        "cwd": cwd,
        "started_at": datetime.fromtimestamp(started).isoformat() if started else None,
        "ended_at": datetime.fromtimestamp(ended).isoformat() if ended else None,
        "tool_call_count": tc_count,
        "message_count": mc_count,
        "trajectory_type": trajectory_type,
        "n_steps": len(steps),
        "n_code_changes": len(code_changes),
        "code_changes": code_changes,
        "steps": steps,
        "final_result": final_result
    }


def _clean_args(tool_name, args):
    cleaned = {}
    for key, val in args.items():
        if isinstance(val, str) and len(val) > 2000:
            cleaned[key] = val[:2000] + "...[truncated]"
        else:
            cleaned[key] = val
    return cleaned


def _determine_success(tool_name, result_content):
    if not result_content:
        return None
    lower = result_content.lower()
    if tool_name == "patch":
        return "error" not in lower and "fail" not in lower
    elif tool_name == "terminal":
        try:
            data = json.loads(result_content)
            return data.get("exit_code", 1) == 0
        except:
            return None
    elif tool_name == "write_file":
        return "error" not in lower
    return None


def _classify_trajectory(steps):
    tools_used = set()
    has_patches = False
    has_terminal = False
    has_errors = False

    for step in steps:
        if step["type"] == "tool_call":
            tools_used.add(step["tool"])
            if step["tool"] in ("patch", "write_file"):
                has_patches = True
            if step["tool"] == "terminal":
                has_terminal = True
        elif step["type"] == "tool_result":
            if step.get("success") is False:
                has_errors = True

    if has_patches and has_terminal and has_errors:
        return "bug_fix_with_debugging"
    elif has_patches and has_terminal:
        return "feature_implementation"
    elif has_patches:
        return "code_edit"
    elif has_terminal:
        return "system_administration"
    else:
        return "other"


def _extract_code_changes(steps):
    changes = []
    for i, step in enumerate(steps):
        if step["type"] != "tool_call":
            continue
        if step["tool"] == "patch":
            args = step.get("args", {})
            changes.append({
                "tool": "patch",
                "path": args.get("path", ""),
                "action": args.get("action", "replace"),
                "old_string": args.get("old_string", "")[:500],
                "new_string": args.get("new_string", "")[:500],
                "step_index": i
            })
        elif step["tool"] == "write_file":
            args = step.get("args", {})
            changes.append({
                "tool": "write_file",
                "path": args.get("path", ""),
                "content_length": len(args.get("content", "")),
                "step_index": i
            })
    return changes


def extract_all_trajectories(min_tools=MIN_TOOL_CALLS, output_dir=DEFAULT_OUTPUT):
    os.makedirs(output_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, tool_call_count,
               datetime(started_at, 'unixepoch', 'localtime') as when_dt
        FROM sessions
        WHERE tool_call_count >= ?
          AND source IN ('tui', 'gateway')
        ORDER BY started_at DESC
    """, (min_tools,))

    sessions = cur.fetchall()
    print(f"Found {len(sessions)} sessions with >={min_tools} tool calls")

    summaries = []
    stats = {
        "total_sessions": len(sessions),
        "by_type": {},
        "total_code_changes": 0,
        "total_steps": 0,
        "successful_trajectories": 0,
        "extracted_at": datetime.now().isoformat()
    }

    for sid, title, tc_count, when_dt in sessions:
        trajectory = extract_session_trajectory(conn, sid)
        if not trajectory:
            continue
        if trajectory.get("source") == "observer":
            continue

        filepath = os.path.join(output_dir, f"{sid}.json")
        with open(filepath, "w") as f:
            json.dump(trajectory, f, indent=2, ensure_ascii=False, default=str)

        summary = {
            "session_id": sid,
            "title": title,
            "when": when_dt,
            "type": trajectory["trajectory_type"],
            "n_steps": trajectory["n_steps"],
            "n_code_changes": trajectory["n_code_changes"],
            "filepath": filepath
        }
        summaries.append(summary)

        ttype = trajectory["trajectory_type"]
        stats["by_type"][ttype] = stats["by_type"].get(ttype, 0) + 1
        stats["total_code_changes"] += trajectory["n_code_changes"]
        stats["total_steps"] += trajectory["n_steps"]
        if trajectory["n_code_changes"] > 0:
            stats["successful_trajectories"] += 1

        print(f"  [{ttype:30s}] {when_dt} | changes={trajectory['n_code_changes']:3d} | {title[:50] if title else '?'}")

    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)

    with open(os.path.join(output_dir, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    conn.close()

    print(f"\n=== Extraction complete ===")
    print(f"Trajectories extracted: {len(summaries)}")
    print(f"Total code changes: {stats['total_code_changes']}")
    print(f"Total steps: {stats['total_steps']}")
    print(f"Trajectories with code changes: {stats['successful_trajectories']}")
    print(f"By type: {json.dumps(stats['by_type'], indent=2)}")
    print(f"Output: {output_dir}/")


if __name__ == "__main__":
    parser = ArgumentParser(description="Extract code-editing trajectories from Hermes state.db")
    parser.add_argument("--min-tools", type=int, default=MIN_TOOL_CALLS, help=f"Minimum tool calls (default: {MIN_TOOL_CALLS})")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help=f"Output directory (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()
    extract_all_trajectories(min_tools=args.min_tools, output_dir=args.output)
