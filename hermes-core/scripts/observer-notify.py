#!/usr/bin/env python3
"""Observer Notify — polls Neo4j for new observer findings and reports them.

Run as a cron job in no_agent mode.  When findings exist it prints them
(and cron delivers the output to the user).  When there are no new findings
it prints nothing (silent — cron skips delivery on empty stdout).

State is tracked via ~/.hermes/.observer_last_check — an ISO-8601 timestamp.
"""

import json
import time
import base64
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

HERMES_HOME = Path.home() / ".hermes"
STATE_FILE = HERMES_HOME / ".observer_last_check"
NEO4J_URL = "http://127.0.0.1:7474/db/neo4j/tx/commit"
NEO4J_AUTH = "neo4j:<YOUR_NEO4J_PASSWORD>"
LOOKBACK_MINUTES = 15  # on first run (no state file), look back this far


def _query(statement: str, params: dict = None) -> list:
    """Execute a Neo4j Cypher query, return list of rows."""
    auth = base64.b64encode(NEO4J_AUTH.encode()).decode()
    payload = json.dumps({"statements": [{"statement": statement,
                                           "parameters": params or {}}]})
    req = urllib.request.Request(
        NEO4J_URL, data=payload.encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["results"][0]["data"]


def main():
    # Determine the lookback window
    now_ts = time.time()
    if STATE_FILE.exists():
        try:
            last_check = float(STATE_FILE.read_text().strip())
        except (ValueError, OSError):
            last_check = now_ts - LOOKBACK_MINUTES * 60
    else:
        last_check = now_ts - LOOKBACK_MINUTES * 60

    since_iso = datetime.fromtimestamp(last_check, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S")

    all_findings = []

    for label, tag in [("AuditFinding", "📋"), ("CriticFinding", "🔍")]:
        try:
            rows = _query(
                f"MATCH (f:{label}) WHERE f.timestamp > $since "
                "RETURN f.finding AS finding, f.severity AS severity, "
                "f.session_id AS sid, f.timestamp AS ts "
                "ORDER BY f.timestamp DESC LIMIT 5",
                {"since": since_iso})
            for row in rows:
                finding, sev, sid, ts = row["row"]
                all_findings.append({
                    "tag": tag,
                    "label": label,
                    "finding": finding,
                    "severity": sev or "INFO",
                    "session_id": sid or "?",
                    "timestamp": ts or "",
                    "type": "audit" if label == "AuditFinding" else "critic",
                })
        except Exception:
            pass  # Neo4j unavailable — silent

    # Update state *before* printing so a crash mid-output doesn't replay
    STATE_FILE.write_text(str(now_ts))

    if not all_findings:
        return  # silent — nothing to report

    all_findings.sort(key=lambda f: f.get("timestamp", ""), reverse=True)

    since_str = datetime.fromtimestamp(last_check, tz=timezone.utc).strftime(
        "%H:%M UTC")
    print(f"👁 Observer activity since {since_str}:\n")
    for f in all_findings[:8]:
        sev_str = f" [{f['severity']}]" if f["severity"] != "INFO" else ""
        short_sid = f["session_id"][-12:] if len(f["session_id"]) > 12 else f["session_id"]
        print(f"  {f['tag']}{sev_str} {f['finding'][:200]}")
    if len(all_findings) > 8:
        print(f"  ... and {len(all_findings) - 8} more")


if __name__ == "__main__":
    main()
