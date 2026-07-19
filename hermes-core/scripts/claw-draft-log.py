#!/usr/bin/env python3
"""
Claw Draft+Log — Phase 3: Write proposals for merge/collapse/rebudget; log rationale for prune/mcp-dedupe.
Reads checkpoint.2.json → writes drafts + log.jsonl + summary.
"""
import json, os, sys
from datetime import datetime, timezone, date

COMPACTOR = os.path.expanduser("~/.compactor")
DRAFTS_DIR = os.path.join(COMPACTOR, "drafts")
SUMMARIES_DIR = os.path.join(COMPACTOR, "summaries")

def load_checkpoint():
    """Load the latest Phase 2 checkpoint."""
    # Read .last_session
    last_session_file = os.path.join(COMPACTOR, ".last_session")
    if not os.path.exists(last_session_file):
        print("No .last_session found", file=sys.stderr)
        sys.exit(1)
    
    with open(last_session_file) as f:
        session_id = f.read().strip()
    
    checkpoint_path = os.path.join(COMPACTOR, "sessions", session_id, "checkpoint.2.json")
    if not os.path.exists(checkpoint_path):
        print(f"Checkpoint not found: {checkpoint_path}", file=sys.stderr)
        sys.exit(1)
    
    with open(checkpoint_path) as f:
        return json.load(f), session_id

def write_draft_proposal(axis, candidate, session_id):
    """Write a draft proposal for merge/collapse/rebudget."""
    op_id = f"{axis}-{candidate.get('tool_name', 'unknown').replace(':', '-').replace('/', '-')[:40]}"
    draft_dir = os.path.join(DRAFTS_DIR, op_id)
    os.makedirs(draft_dir, exist_ok=True)
    
    draft = {
        "op_id": op_id,
        "axis": axis,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "proposed",
        "candidate": candidate,
        "rationale": "",
        "proposed_action": "",
        "estimated_impact": "",
    }
    
    if axis == "rebudget":
        size_kb = candidate.get('size_kb', 0)
        lines = candidate.get('line_count', 0)
        draft["rationale"] = f"Skill '{candidate['tool_name']}' is {size_kb:.1f} KB ({lines} lines), exceeding the 8 KB rebudget threshold. At routing time, only the frontmatter is needed; the full body is only required when the skill is activated."
        draft["proposed_action"] = f"Add separate_load: true to frontmatter to load only frontmatter at routing time. Move body to lazy-load."
        draft["estimated_impact"] = f"Reduces system-prompt token usage by approximately {int(size_kb * 0.7)} tokens."
    
    elif axis == "collapse":
        draft["rationale"] = f"Layer '{candidate['layer']}' has only one inhabitant ({candidate['tool_name']}) with {candidate['line_count']} lines. The layer is structural noise."
        draft["proposed_action"] = f"Move '{candidate['tool_name']}' up one layer and collapse '{candidate['layer']}'."
    
    draft_path = os.path.join(draft_dir, "proposal.json")
    with open(draft_path, 'w') as f:
        json.dump(draft, f, indent=2, default=str)
    
    return op_id, draft_path

def write_log_entry(axis, candidate, session_id, proposal_ref=None):
    """Create a log.jsonl entry."""
    return {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "axis": axis,
        "tool_id": candidate.get('tool_id', ''),
        "tool_name": candidate.get('tool_name', ''),
        "reason": candidate.get('reason', ''),
        "proposal_ref": proposal_ref,
        "jaccard": candidate.get('jaccard'),
        "size_kb": candidate.get('size_kb'),
        "line_count": candidate.get('line_count'),
        "evidence": [
            f"source_path:{candidate.get('source_path', 'unknown')}"
        ],
    }

def main():
    checkpoint, session_id = load_checkpoint()
    candidates = checkpoint['candidates']['items']
    
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    os.makedirs(SUMMARIES_DIR, exist_ok=True)
    
    # Log entries
    log_entries = []
    proposals_written = 0
    rationale_logged = 0
    
    for c in candidates:
        axis = c.get('axis', '')
        
        if axis in ('merge', 'collapse', 'rebudget'):
            # Write draft proposal
            op_id, draft_path = write_draft_proposal(axis, c, session_id)
            entry = write_log_entry(axis, c, session_id, proposal_ref=op_id)
            log_entries.append(entry)
            proposals_written += 1
            
        elif axis in ('prune', 'mcp-dedupe'):
            # Log rationale only
            entry = write_log_entry(axis, c, session_id)
            log_entries.append(entry)
            rationale_logged += 1
    
    # Write log.jsonl (append)
    log_path = os.path.join(COMPACTOR, "log.jsonl")
    with open(log_path, 'a') as f:
        for entry in log_entries:
            f.write(json.dumps(entry, default=str) + '\n')
    
    # Write summary
    today = date.today().isoformat()
    summary_path = os.path.join(SUMMARIES_DIR, f"{today}.md")
    
    axis_counts = {}
    for c in candidates:
        axis = c.get('axis', '')
        axis_counts[axis] = axis_counts.get(axis, 0) + 1
    
    summary = f"""# Claw Compaction Summary — {today}

**Session:** `{session_id}`
**Registry:** `{checkpoint.get('snapshot_file', 'unknown')}`
**Total tools:** {checkpoint.get('classification_summary', {}).get('total_tools', 0)}
**Candidates detected:** {len(candidates)}

## Detection Results

| Axis | Count | Action |
|------|------:|--------|
"""
    for axis in ['merge', 'prune', 'collapse', 'rebudget', 'mcp-dedupe']:
        count = axis_counts.get(axis, 0)
        action = "Draft proposal" if axis in ('merge', 'collapse', 'rebudget') else "Log rationale"
        summary += f"| {axis} | {count} | {action} |\n"
    
    summary += f"""
## Candidates

### Rebudget (skills > 8KB) — {axis_counts.get('rebudget', 0)} candidates
"""
    
    for c in candidates:
        if c.get('axis') == 'rebudget':
            summary += f"- **{c.get('tool_name', 'unknown')}**: {c.get('size_kb', 0):.1f} KB, {c.get('line_count', 0)} lines\n"
    
    summary += f"\n### Prune — {axis_counts.get('prune', 0)} candidates\n"
    
    prune_reasons = {}
    for c in candidates:
        if c.get('axis') == 'prune':
            reason = c.get('reason', 'unknown')
            prune_reasons[reason] = prune_reasons.get(reason, 0) + 1
    
    for reason, count in prune_reasons.items():
        summary += f"- **{reason}**: {count} tools\n"
    
    summary += f"""
## Log
- Proposals written: {proposals_written}
- Rationale logged: {rationale_logged}
- Log entries appended: {len(log_entries)}
- Log file: `.compactor/log.jsonl`
"""
    
    with open(summary_path, 'w') as f:
        f.write(summary)
    
    # Write checkpoint.3.json
    session_dir = os.path.join(COMPACTOR, "sessions", session_id)
    checkpoint3 = {
        "session_id": session_id,
        "phase": 3,
        "timestamp": datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        "proposals_written": proposals_written,
        "rationale_logged": rationale_logged,
        "log_entries": len(log_entries),
        "summary_path": summary_path,
        "drafts_dir": DRAFTS_DIR,
        "axis_counts": axis_counts,
    }
    
    checkpoint3_path = os.path.join(session_dir, "checkpoint.3.json")
    with open(checkpoint3_path, 'w') as f:
        json.dump(checkpoint3, f, indent=2, default=str)
    
    print(f"Session: {session_id}")
    print(f"Proposals written: {proposals_written}")
    print(f"Rationale logged: {rationale_logged}")
    print(f"Log entries: {len(log_entries)}")
    print(f"Summary: {summary_path}")
    print(f"Checkpoint: {checkpoint3_path}")

if __name__ == '__main__':
    main()
