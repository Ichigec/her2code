#!/usr/bin/env python3
"""
Claw Process — Phase 2: Classify tools and detect compaction candidates.
Reads registry snapshot → classifies → detects along 5 axes.
Output: .compactor/sessions/<ts>/checkpoint.2.json
"""
import json, os, sys, re
from datetime import datetime, timezone
from collections import defaultdict

COMPACTOR = os.path.expanduser("~/.compactor")
REGISTRY_DIR = os.path.join(COMPACTOR, "registry")

def load_latest_registry():
    """Find the most recent registry snapshot."""
    files = sorted([f for f in os.listdir(REGISTRY_DIR) if f.startswith('integrations.') and f.endswith('.json')])
    if not files:
        print("No registry snapshot found", file=sys.stderr)
        sys.exit(1)
    latest = files[-1]
    with open(os.path.join(REGISTRY_DIR, latest)) as f:
        return json.load(f), latest

def get_skill_map(registry):
    """Build map of skill name → skill data."""
    skill_map = {}
    for s in registry['scanners'].get('skills', []):
        name = s.get('tool_name', '')
        skill_map[name] = s
    return skill_map

def classify_linux_layer(tool):
    """Classify tool into linux_layer hierarchy based on type and name."""
    ttype = tool.get('tool_type', '') or ''
    tname = (tool.get('tool_name') or '').lower()
    
    layer_map = {
        'compose_service': 'L4_services',
        'mcp_server': 'L3_middleware',
        'skill': 'L5_skills',
        'env_file': 'L1_config',
        'script': 'L2_scripts',
        'service_port': 'L4_services',
        'systemd_service': 'L0_system',
        'health_check': 'L4_services',
        'litellm_model': 'L3_middleware',
        'litellm_config': 'L1_config',
        'process': 'L0_system',
        'unknown': 'L5_skills',
    }
    
    return layer_map.get(ttype, 'L5_skills')

def classify_c_layer(tool):
    """Classify tool into c_layer (capability domain)."""
    ttype = tool.get('tool_type', '') or ''
    tname = (tool.get('tool_name') or '').lower()
    
    if ttype == 'skill':
        # Classify skills based on category/name
        if any(k in tname for k in ['android', 'kotlin', 'gradle']):
            return 'mobile'
        if any(k in tname for k in ['neo4j', 'graph', 'database']):
            return 'data'
        if any(k in tname for k in ['deploy', 'ci', 'docker', 'server']):
            return 'infra'
        if any(k in tname for k in ['test', 'audit', 'security', 'sast']):
            return 'quality'
        if any(k in tname for k in ['code', 'dev', 'implementation', 'developer']):
            return 'development'
        if any(k in tname for k in ['research', 'arxiv', 'paper']):
            return 'research'
        if any(k in tname for k in ['voice', 'audio', 'stt', 'tts']):
            return 'voice'
        if any(k in tname for k in ['design', 'ui', 'frontend', 'ui-ux']):
            return 'design'
        return 'general'
    
    if ttype == 'mcp_server':
        return 'middleware'
    if ttype == 'compose_service':
        return 'infra'
    if ttype == 'script':
        return 'automation'
    if ttype == 'env_file':
        return 'config'
    if ttype in ('service_port', 'health_check', 'systemd_service', 'process'):
        return 'infra'
    if ttype == 'litellm_model':
        return 'ai'
    
    return 'general'

def detect_merges(skill_map):
    """Detect skills with overlapping triggers (Jaccard ≥ 50%)."""
    candidates = []
    skills = list(skill_map.values())
    for i in range(len(skills)):
        for j in range(i+1, len(skills)):
            s1, s2 = skills[i], skills[j]
            t1 = set(s1.get('triggers', []))
            t2 = set(s2.get('triggers', []))
            if not t1 or not t2:
                continue
            intersection = t1 & t2
            union = t1 | t2
            if not union:
                continue
            jaccard = len(intersection) / len(union)
            if jaccard >= 0.3:  # Lower threshold for discovery
                candidates.append({
                    "axis": "merge",
                    "tool_a": s1.get('tool_id'),
                    "tool_b": s2.get('tool_id'),
                    "name_a": s1.get('tool_name'),
                    "name_b": s2.get('tool_name'),
                    "jaccard": round(jaccard, 3),
                    "shared_triggers": sorted(intersection),
                })
    return candidates

def detect_prunes(registry):
    """Detect potentially stale tools."""
    candidates = []
    # Skills with no triggers
    for s in registry['scanners'].get('skills', []):
        if not s.get('triggers'):
            candidates.append({
                "axis": "prune",
                "tool_id": s.get('tool_id'),
                "tool_name": s.get('tool_name'),
                "reason": "no_triggers",
                "source_path": s.get('source_path', ''),
            })
    
    # Small, empty-looking skills
    for s in registry['scanners'].get('skills', []):
        if s.get('line_count', 999) < 20 and s.get('size_kb', 999) < 2:
            candidates.append({
                "axis": "prune",
                "tool_id": s.get('tool_id'),
                "tool_name": s.get('tool_name'),
                "reason": "tiny_skill",
                "line_count": s.get('line_count'),
                "size_kb": s.get('size_kb'),
            })
    
    return candidates

def detect_collapses(skill_map):
    """Detect thin layers with single inhabitant."""
    candidates = []
    layer_inhabitants = defaultdict(list)
    for name, s in skill_map.items():
        layer = classify_linux_layer(s)
        layer_inhabitants[layer].append(s)
    
    for layer, inhabitants in layer_inhabitants.items():
        if len(inhabitants) == 1:
            s = inhabitants[0]
            if s.get('line_count', 999) < 30:
                candidates.append({
                    "axis": "collapse",
                    "layer": layer,
                    "tool_id": s.get('tool_id'),
                    "tool_name": s.get('tool_name'),
                    "line_count": s.get('line_count'),
                })
    
    return candidates

def detect_rebudgets(skill_map):
    """Detect skills > 8KB that load unconditionally."""
    candidates = []
    for name, s in skill_map.items():
        if s.get('size_kb', 0) > 8:
            candidates.append({
                "axis": "rebudget",
                "tool_id": s.get('tool_id'),
                "tool_name": s.get('tool_name'),
                "size_kb": s.get('size_kb'),
                "line_count": s.get('line_count'),
            })
    return candidates

def detect_mcp_dedupes(registry):
    """Detect MCP servers with overlapping functionality."""
    candidates = []
    mcp_servers = registry['scanners'].get('mcp', [])
    
    # Group by similar names
    name_groups = defaultdict(list)
    for m in mcp_servers:
        name = (m.get('tool_name') or '').lower()
        # Normalize: remove numbers and common suffixes
        base = re.sub(r'[\d_-]+', '', name)
        name_groups[base].append(m)
    
    for base, group in name_groups.items():
        if len(group) > 1 and len(base) > 2:  # meaningful base name
            candidates.append({
                "axis": "mcp-dedupe",
                "base_name": base,
                "count": len(group),
                "tools": [m.get('tool_id') for m in group],
            })
    
    return candidates

def main():
    registry, snapshot_file = load_latest_registry()
    skill_map = get_skill_map(registry)
    
    # Classify all tools
    all_tools = []
    for scanner_name, records in registry['scanners'].items():
        for r in records:
            r['linux_layer'] = classify_linux_layer(r)
            r['c_layer'] = classify_c_layer(r)
            all_tools.append(r)
    
    # Detect candidates
    merge_candidates = detect_merges(skill_map)
    prune_candidates = detect_prunes(registry)
    collapse_candidates = detect_collapses(skill_map)
    rebudget_candidates = detect_rebudgets(skill_map)
    mcp_dedupe_candidates = detect_mcp_dedupes(registry)
    
    all_candidates = (
        merge_candidates + 
        prune_candidates + 
        collapse_candidates + 
        rebudget_candidates + 
        mcp_dedupe_candidates
    )
    
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    session_id = ts
    
    checkpoint = {
        "session_id": session_id,
        "phase": 2,
        "timestamp": ts,
        "snapshot_file": snapshot_file,
        "classification_summary": {
            "total_tools": len(all_tools),
            "layers": {},
        },
        "candidates": {
            "merge": len(merge_candidates),
            "prune": len(prune_candidates),
            "collapse": len(collapse_candidates),
            "rebudget": len(rebudget_candidates),
            "mcp_dedupe": len(mcp_dedupe_candidates),
            "total": len(all_candidates),
            "items": all_candidates,
        },
    }
    
    # Layer distribution
    layer_counts = defaultdict(int)
    for t in all_tools:
        layer_counts[t.get('linux_layer', 'unknown')] += 1
    checkpoint['classification_summary']['layers'] = dict(layer_counts)
    
    # Write checkpoint
    session_dir = os.path.join(COMPACTOR, "sessions", session_id)
    os.makedirs(session_dir, exist_ok=True)
    checkpoint_path = os.path.join(session_dir, "checkpoint.2.json")
    with open(checkpoint_path, 'w') as f:
        json.dump(checkpoint, f, indent=2, default=str)
    
    print(f"Session: {session_id}")
    print(f"Registry: {snapshot_file}")
    print(f"Total tools classified: {len(all_tools)}")
    print(f"Layer distribution: {json.dumps(layer_counts, indent=2)}")
    print(f"Candidates detected: {len(all_candidates)}")
    print(f"  merge: {len(merge_candidates)}")
    print(f"  prune: {len(prune_candidates)}")
    print(f"  collapse: {len(collapse_candidates)}")
    print(f"  rebudget: {len(rebudget_candidates)}")
    print(f"  mcp_dedupe: {len(mcp_dedupe_candidates)}")
    print(f"Checkpoint: {checkpoint_path}")
    
    # Store session_id for next phases
    with open(os.path.join(COMPACTOR, ".last_session"), 'w') as f:
        f.write(session_id)
    
    return session_id

if __name__ == '__main__':
    main()
