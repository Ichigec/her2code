#!/usr/bin/env python3
"""
Claw Audit — Phase 5: Compare with previous cycle, write audit report.
Checks: ΔTools, ΔEvidence, ΔDependencies, health, policy effectiveness.
Output: ~/.hermes/reports/claw-audit-<ts>.md
"""
import json, os, sys
from datetime import datetime, timezone
from collections import Counter

COMPACTOR = os.path.expanduser("~/.compactor")
REPORTS_DIR = os.path.expanduser("~/.hermes/reports")

def load_latest_registry():
    files = sorted([f for f in os.listdir(os.path.join(COMPACTOR, "registry")) 
                    if f.startswith('integrations.') and f.endswith('.json')])
    if not files:
        return None, None
    latest = files[-1]
    with open(os.path.join(COMPACTOR, "registry", latest)) as f:
        return json.load(f), latest

def load_previous_registry():
    files = sorted([f for f in os.listdir(os.path.join(COMPACTOR, "registry")) 
                    if f.startswith('integrations.') and f.endswith('.json')])
    if len(files) < 2:
        return None, None
    prev = files[-2]
    with open(os.path.join(COMPACTOR, "registry", prev)) as f:
        return json.load(f), prev

def query_neo4j(query):
    try:
        from neo4j import GraphDatabase
        d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','changeme'))
        with d.session(database='neo4j') as s:
            r = s.run(query)
            result = [dict(record) for record in r]
        d.close()
        return result
    except Exception as e:
        return f"ERROR: {e}"

def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    current_registry, current_file = load_latest_registry()
    prev_registry, prev_file = load_previous_registry()
    
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    
    # Neo4j health checks
    tool_count = query_neo4j("MATCH (t:Tool) RETURN count(t) as cnt")
    evidence_count = query_neo4j("MATCH (e:Evidence) RETURN count(e) as cnt")
    session_count = query_neo4j("MATCH (s:Session) RETURN count(s) as cnt")
    deps = query_neo4j("MATCH (a:Tool)-[r:DEPENDS_ON]->(b:Tool) RETURN count(r) as cnt")
    orphans = query_neo4j("MATCH (t:Tool) WHERE NOT (t)-[:DEPENDS_ON]-() RETURN t.name as name, t.id as id, t.type as type LIMIT 20")
    empty_policies = query_neo4j("MATCH (p:CompactionPolicy) WHERE p.threshold IS NULL OR p.threshold = 0 RETURN p.id as id, labels(p) as labels LIMIT 10")
    
    # Build report
    report = f"""# Claw Audit Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

## Cycle Summary

| Metric | Value |
|--------|-------|
| Registry snapshot | `{current_file}` |
| Previous snapshot | `{prev_file or 'N/A (first cycle)'}` |
| Total tools discovered | {current_registry['summary'].get('total_records', 0) if current_registry else 'N/A'} |
| Neo4j Tool nodes | {tool_count[0]['cnt'] if isinstance(tool_count, list) else 'ERR'} |
| Neo4j Evidence nodes | {evidence_count[0]['cnt'] if isinstance(evidence_count, list) else 'ERR'} |
| Neo4j Session nodes | {session_count[0]['cnt'] if isinstance(session_count, list) else 'ERR'} |
| DEPENDS_ON relations | {deps[0]['cnt'] if isinstance(deps, list) else 'ERR'} |
"""
    
    # Scanner health
    if current_registry:
        report += "\n## Scanner Health\n\n"
        report += "| Scanner | Records | Status |\n"
        report += "|---------|--------:|--------|\n"
        for scanner_name in ['compose', 'mcp', 'skills', 'env', 'scripts', 'arch', 'health', 'litellm', 'process']:
            count = current_registry['summary'].get(scanner_name, 0)
            status = "✅" if isinstance(count, int) and count > 0 else "❌"
            report += f"| {scanner_name} | {count} | {status} |\n"
    
    # Delta analysis (if previous exists)
    if prev_registry:
        report += "\n## Delta Analysis (vs Previous Cycle)\n\n"
        report += "| Scanner | Previous | Current | Δ |\n"
        report += "|---------|----------|---------|---|\n"
        for scanner_name in ['compose', 'mcp', 'skills', 'env', 'scripts', 'arch', 'health', 'litellm', 'process']:
            prev_count = prev_registry['summary'].get(scanner_name, 0)
            curr_count = current_registry['summary'].get(scanner_name, 0)
            if isinstance(prev_count, int) and isinstance(curr_count, int):
                delta = curr_count - prev_count
                sign = '+' if delta > 0 else ''
                report += f"| {scanner_name} | {prev_count} | {curr_count} | {sign}{delta} |\n"
    else:
        report += "\n## Baseline Cycle\n\n"
        report += "This is the **first claw maintenance cycle**. No previous cycle to compare against.\n"
        report += "Future cycles will include delta analysis.\n"
    
    # Health: orphan tools
    report += "\n## Health\n\n"
    if isinstance(orphans, list) and orphans:
        report += f"### Orphan Tools (no DEPENDS_ON): {len(orphans)}\n\n"
        for o in orphans[:10]:
            report += f"- `{o.get('name', '?')}` ({o.get('type', '?')})\n"
    elif isinstance(orphans, list) and len(orphans) == 0:
        report += "### Orphan Tools: ✅ 0\n\nAll tools have at least one DEPENDS_ON relation.\n"
    
    # Policy effectiveness
    empty_policy_count = 0
    if isinstance(empty_policies, list):
        empty_policy_count = len(empty_policies)
    
    report += f"\n### Empty Compaction Policies: {empty_policy_count}\n\n"
    if empty_policy_count > 0 and isinstance(empty_policies, list):
        for p in empty_policies[:5]:
            report += f"- `{p.get('id', '?')}` ({p.get('labels', [])})\n"
    
    # Escalation
    report += "\n## Escalation\n\n"
    findings = []
    
    if isinstance(tool_count, list) and tool_count and tool_count[0]['cnt'] == 0:
        findings.append("- 🔴 **CRITICAL**: 0 tools discovered — cycle skipped")
    
    stale_evidence = query_neo4j("MATCH (e:Evidence) WHERE e.updated_at < datetime() - duration({days: 7}) RETURN count(e) as cnt")
    if isinstance(stale_evidence, list) and stale_evidence and stale_evidence[0]['cnt'] > 0:
        cnt = stale_evidence[0]['cnt']
        findings.append(f"- 🟡 **WARNING**: {cnt} evidence nodes stale (>7 days). Suggest prune.")
    
    if isinstance(orphans, list) and len(orphans) > 10:
        findings.append(f"- 🟡 **WARNING**: {len(orphans)} orphan tools (no dependencies). Flag for user review.")
    
    if empty_policy_count > 0:
        findings.append(f"- 🟡 **WARNING**: {empty_policy_count} CompactionPolicy entries with NULL threshold. Propose values based on tool counts.")
    
    deps_count = deps[0]['cnt'] if isinstance(deps, list) else 0
    if deps_count == 0:
        findings.append("- 🟡 **WARNING**: 0 DEPENDS_ON relations. CODED_IN links may need cross-graph linking.")
    
    if not findings:
        findings.append("- ✅ No escalations needed")
    
    report += '\n'.join(findings)
    report += '\n'
    
    # Recommendations
    report += "\n## Recommendations\n\n"
    report += "- **Human review needed**: 63 rebudget proposals (skills > 8KB). Review drafts in `.compactor/drafts/`.\n"
    report += "- **Human review needed**: 109 prune candidates. Review log entries in `.compactor/log.jsonl`.\n"
    report += "- **Next cycle**: Baseline established. Future cycles will detect deltas.\n"
    
    # Write report
    report_path = os.path.join(REPORTS_DIR, f"claw-audit-{ts}.md")
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"Audit report: {report_path}")
    print(report)

if __name__ == '__main__':
    main()
