"""
Observer Hook — fires on every agent lifecycle event.
Writes structured observations to Neo4j (AuditFinding, Idea, CriticFinding, Mutation).

Events handled:
  - agent:start  — session bootstrap, ensure Session node
  - agent:end    — turn completed, record observation
  - session:end  — finalize session stats
"""

import json
import subprocess
import os
from datetime import datetime, timezone

NEO4J_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"
NEO4J_AUTH = os.environ.get("NEO4J_AUTH", "neo4j:<YOUR_NEO4J_PASSWORD>")


def _neo4j(statement: str, params: dict = None) -> dict:
    """Execute a Cypher statement via curl. Non-blocking, errors swallowed."""
    payload = json.dumps({
        "statements": [{"statement": statement, "parameters": params or {}}]
    })
    try:
        r = subprocess.run(
            ["curl", "-s", "-u", NEO4J_AUTH,
             "-H", "Content-Type: application/json",
             "-d", payload, NEO4J_URL],
            capture_output=True, text=True, timeout=10
        )
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def handle(event_type: str, context: dict) -> None:
    """
    Main hook handler. Called by Hermes hook system on every registered event.

    SDB contract:
      PROPOSER: context contains agent output
      VERIFIER: we validate fields are present
      COMMIT:   write to Neo4j
      REJECT:   silent — hook errors never block the pipeline
    """

    session_id = context.get("session_id", "unknown")
    agent_preset = context.get("agent_prompt_label", context.get("agent", "unknown"))
    platform = context.get("platform", "tui")

    if event_type == "agent:start":
        # Bootstrap: ensure Session node exists
        _neo4j(
            "MERGE (s:Session {session_id: $sid}) "
            "SET s.started_at = coalesce(s.started_at, $ts), "
            "    s.agent_preset = $preset, "
            "    s.platform = $plat, "
            "    s.last_active = $ts",
            {"sid": session_id, "ts": _ts(), "preset": agent_preset, "plat": platform}
        )

    elif event_type == "agent:end":
        # Record turn completion
        user_message = context.get("user_message", "")[:200]
        response_preview = context.get("agent_response", "")[:200]
        turn_count = context.get("turn_count", 0)

        finding_text = (
            f"Agent turn {turn_count}: {user_message[:80]}... → "
            f"{response_preview[:80]}..."
        ) if user_message else f"Agent turn {turn_count} completed"

        _neo4j(
            "CREATE (f:AuditFinding {"
            "  session_id: $sid, phase: 'agent_turn', severity: 'INFO',"
            "  finding: $finding, agent_preset: $preset, platform: $plat,"
            "  turn: $turn, timestamp: $ts"
            "})",
            {
                "sid": session_id, "finding": finding_text,
                "preset": agent_preset, "plat": platform,
                "turn": turn_count, "ts": _ts()
            }
        )

        # Every 5th turn: also write an Idea for pipeline improvement
        if turn_count and turn_count % 5 == 0:
            _neo4j(
                "CREATE (i:Idea {"
                "  session_id: $sid, phase: 'continuous', category: 'optimization',"
                "  idea: $idea, potential_value: 5, timestamp: $ts"
                "})",
                {
                    "sid": session_id,
                    "idea": f"Observer hook active for {turn_count} turns — "
                            f"consider deeper session analysis via LLM",
                    "ts": _ts()
                }
            )

    elif event_type == "session:end":
        # Finalize: update session node with end stats
        _neo4j(
            "MATCH (s:Session {session_id: $sid}) "
            "SET s.ended_at = $ts, s.status = 'completed'",
            {"sid": session_id, "ts": _ts()}
        )
