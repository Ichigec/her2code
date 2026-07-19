#!/usr/bin/env python3
"""
Observer Daemon v1 — always-on system observer. Runs via cron.
Independent of agent preset. Writes structured findings to Neo4j.
"""

import json, subprocess, sqlite3, os
from datetime import datetime, timezone

NEO4J_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"
NEO4J_AUTH = "neo4j:<YOUR_NEO4J_PASSWORD>"
OBSERVER_DB = os.path.expanduser("~/.hermes/observer_state.db")
STATE_DB = os.path.expanduser("~/.hermes/state.db")

def neo4j_write(statement, params=None):
    """Execute Cypher write via curl."""
    payload = json.dumps({"statements": [{"statement": statement, "parameters": params or {}}]})
    cmd = [
        "curl", "-s", "-u", NEO4J_AUTH,
        "-H", "Content-Type: application/json",
        "-d", payload, NEO4J_URL
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout) if r.stdout.strip() else {"results": [{"data": []}]}
    except Exception as e:
        return {"error": str(e)}

def init_db():
    conn = sqlite3.connect(OBSERVER_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS cycles (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, audit_findings INTEGER, critic_findings INTEGER, ideas INTEGER, mutations INTEGER, aflow_variants INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, msg TEXT)")
    conn.commit()
    return conn

def count_label(label):
    """Count nodes with given label."""
    r = neo4j_write(f"MATCH (n:{label}) RETURN count(n) AS cnt")
    try:
        return r["results"][0]["data"][0]["row"][0]
    except:
        return -1

def ensure_session_node(session_id, conn):
    """Ensure a Session node exists for this conversation."""
    ts = datetime.now(timezone.utc).isoformat()
    neo4j_write(
        "MERGE (s:Session {session_id: $sid}) SET s.observer_active = true, s.last_checkin = $ts, s.agent_preset = $preset",
        {"sid": session_id, "ts": ts, "preset": "plan2"}
    )

def record_audit_finding(session_id, phase, severity, finding, evidence=""):
    """Write an AuditFinding to Neo4j."""
    ts = datetime.now(timezone.utc).isoformat()
    return neo4j_write(
        "CREATE (f:AuditFinding {session_id: $sid, phase: $phase, severity: $sev, finding: $finding, evidence: $ev, timestamp: $ts})",
        {"sid": session_id, "phase": phase, "sev": severity, "finding": finding, "ev": evidence, "ts": ts}
    )

def record_idea(session_id, phase, category, idea, value):
    """Write an Idea to Neo4j."""
    ts = datetime.now(timezone.utc).isoformat()
    return neo4j_write(
        "CREATE (i:Idea {session_id: $sid, phase: $phase, category: $cat, idea: $idea, potential_value: $val, timestamp: $ts})",
        {"sid": session_id, "phase": phase, "cat": category, "idea": idea, "val": value, "ts": ts}
    )

def record_mutation(session_id, target, change, rationale, confidence):
    """Write a Mutation (ADAS) to Neo4j."""
    ts = datetime.now(timezone.utc).isoformat()
    return neo4j_write(
        "CREATE (m:Mutation {session_id: $sid, target: $tgt, change: $chg, rationale: $rat, confidence: $conf, status: 'proposed', timestamp: $ts})",
        {"sid": session_id, "tgt": target, "chg": change, "rat": rationale, "conf": confidence, "ts": ts}
    )

def main():
    conn = init_db()
    ts = datetime.now(timezone.utc).isoformat()
    session_id = f"daemon_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 1. Ensure Session node
    ensure_session_node(session_id, conn)
    
    # 2. Write observer check-in finding
    record_audit_finding(
        session_id, "daemon_checkin", "INFO",
        f"Observer daemon check-in at {ts}. System observer active — monitoring all agent presets.",
        "observer_daemon.py cron job"
    )
    
    # 3. Write idea about ADAS/AFlow integration
    record_idea(
        session_id, "continuous", "optimization",
        "Observers now run as daemon — independent of agent preset. Next: LLM-based session analysis.",
        8
    )
    
    # 4. Write ADAS mutation about observer independence
    record_mutation(
        session_id,
        "hermes_architecture",
        "observers as system daemon instead of agent-bound subagents",
        "Observer data should persist regardless of which agent preset is active. Daemon approach decouples observation from conversation lifecycle.",
        0.9
    )
    
    # 5. Stats
    stats = {}
    for label in ["AuditFinding", "CriticFinding", "Idea", "Mutation", "AFlowVariant", "Session", "KnowledgeEntity"]:
        stats[label] = count_label(label)
    
    conn.execute(
        "INSERT INTO cycles (ts, audit_findings, ideas, mutations) VALUES (?, ?, ?, ?)",
        (ts, stats["AuditFinding"], stats["Idea"], stats["Mutation"])
    )
    conn.commit()
    
    print(f"[{ts}] Observer daemon check-in complete.")
    print(f"  Neo4j: AuditFinding={stats['AuditFinding']}, Idea={stats['Idea']}, Mutation={stats['Mutation']}, Session={stats['Session']}, KnowledgeEntity={stats['KnowledgeEntity']}")
    conn.close()

if __name__ == "__main__":
    main()
