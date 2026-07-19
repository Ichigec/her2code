#!/usr/bin/env python3
"""
Claw Discovery — Phase 1: Run 9 scanners, produce registry snapshot.
Scanners: compose, mcp, skills, env, scripts, arch, health, litellm, process
Output: .compactor/registry/integrations.<ts>.json
"""
import json, os, sys, subprocess, time, fnmatch, re
from datetime import datetime, timezone

COMPACTOR = os.path.expanduser("~/.compactor")
REGISTRY_DIR = os.path.join(COMPACTOR, "registry")
os.makedirs(REGISTRY_DIR, exist_ok=True)

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), -1

def scanner_compose():
    """Scan for docker-compose files and extract services."""
    records = []
    for root, dirs, files in os.walk(os.path.expanduser("~")):
        dirs[:] = [d for d in dirs if not d.startswith('.') or d in ('.hermes',)]
        for f in files:
            if f in ('docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml'):
                fp = os.path.join(root, f)
                try:
                    with open(fp) as fh:
                        import yaml
                        data = yaml.safe_load(fh)
                    services = data.get('services', {}) if isinstance(data, dict) else {}
                    for svc_name, svc in services.items():
                        records.append({
                            "tool_id": f"compose:{os.path.relpath(fp, os.path.expanduser('~'))}:{svc_name}",
                            "tool_type": "compose_service",
                            "tool_name": svc_name,
                            "source_path": fp,
                            "image": svc.get('image', ''),
                            "ports": svc.get('ports', []),
                            "networks": list(svc.get('networks', {}).keys()) if isinstance(svc.get('networks'), dict) else [],
                        })
                except Exception:
                    pass
    return records

def scanner_mcp():
    """Scan MCP server configs."""
    records = []
    # Check Hermes MCP config
    hermes_config = os.path.expanduser("~/.hermes/config.yaml")
    if os.path.exists(hermes_config):
        try:
            import yaml
            with open(hermes_config) as f:
                cfg = yaml.safe_load(f)
            mcp_servers = cfg.get('mcp', {}).get('servers', {})
            for name, srv in mcp_servers.items():
                records.append({
                    "tool_id": f"mcp:{name}",
                    "tool_type": "mcp_server",
                    "tool_name": name,
                    "command": srv.get('command', ''),
                    "args": srv.get('args', []),
                    "enabled": srv.get('enabled', True),
                })
        except Exception:
            pass
    
    # Check OpenCode MCP configs
    opencode_config = os.path.expanduser("~/.config/opencode/opencode.json")
    if os.path.exists(opencode_config):
        try:
            with open(opencode_config) as f:
                cfg = json.load(f)
            mcp_servers = cfg.get('mcpServers', {})
            for name, srv in mcp_servers.items():
                records.append({
                    "tool_id": f"mcp:{name}",
                    "tool_type": "mcp_server",
                    "tool_name": name,
                    "command": srv.get('command', ''),
                    "args": srv.get('args', []),
                    "source": "opencode",
                })
        except Exception:
            pass
    
    # Query Neo4j for existing Tool nodes (claw graph)
    try:
        from neo4j import GraphDatabase
        d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','changeme'))
        with d.session(database='neo4j') as s:
            res = s.run("MATCH (t:Tool) RETURN t.tool_id as tid, t.tool_name as name, t.tool_type as type, labels(t) as labels LIMIT 200")
            for r in res:
                records.append({
                    "tool_id": r['tid'],
                    "tool_type": r['type'] or 'unknown',
                    "tool_name": r['name'],
                    "labels": r['labels'],
                    "source": "neo4j_claw_graph",
                })
        d.close()
    except Exception:
        pass
    
    return records

def scanner_skills():
    """Scan Hermes skills for triggers, dependencies, etc."""
    records = []
    skills_dir = os.path.expanduser("~/.hermes/skills")
    if not os.path.isdir(skills_dir):
        return records
    
    for root, dirs, files in os.walk(skills_dir):
        for f in files:
            if f == 'SKILL.md':
                fp = os.path.join(root, f)
                try:
                    with open(fp) as fh:
                        content = fh.read()
                    
                    # Extract frontmatter if YAML
                    name = os.path.relpath(root, skills_dir).replace('/', ':')
                    triggers = []
                    desc = ""
                    
                    if content.startswith('---'):
                        parts = content.split('---', 2)
                        if len(parts) >= 3:
                            import yaml
                            try:
                                fm = yaml.safe_load(parts[1])
                                name = fm.get('name', name)
                                desc = fm.get('description', '')
                                triggers = fm.get('triggers', [])
                            except Exception:
                                pass
                    
                    # Count lines and size
                    size_kb = len(content.encode('utf-8')) / 1024
                    line_count = content.count('\n')
                    
                    records.append({
                        "tool_id": f"skill:{name}",
                        "tool_type": "skill",
                        "tool_name": name,
                        "source_path": fp,
                        "triggers": triggers if isinstance(triggers, list) else [],
                        "description": desc,
                        "size_kb": round(size_kb, 1),
                        "line_count": line_count,
                    })
                except Exception:
                    pass
    
    return records

def scanner_env():
    """Scan for environment files and variables."""
    records = []
    env_patterns = ['.env', '.env.local', '.env.production', '.env.development']
    for root, dirs, files in os.walk(os.path.expanduser("~")):
        dirs[:] = [d for d in dirs if not d.startswith('.') or d == '.hermes']
        for f in files:
            if f in env_patterns:
                fp = os.path.join(root, f)
                try:
                    with open(fp) as fh:
                        lines = fh.readlines()
                    vars_found = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key = line.split('=', 1)[0].strip()
                            vars_found.append(key)
                    records.append({
                        "tool_id": f"env:{os.path.relpath(fp, os.path.expanduser('~'))}",
                        "tool_type": "env_file",
                        "tool_name": os.path.basename(fp),
                        "source_path": fp,
                        "variable_count": len(vars_found),
                        "variables": vars_found[:20],  # cap at 20
                    })
                except Exception:
                    pass
    return records

def scanner_scripts():
    """Scan for scripts and executables."""
    records = []
    script_dirs = [
        os.path.expanduser("~/.hermes/scripts/"),
        os.path.expanduser("~/.hermes/hooks/"),
    ]
    for sdir in script_dirs:
        if not os.path.isdir(sdir):
            continue
        for f in os.listdir(sdir):
            fp = os.path.join(sdir, f)
            if os.path.isfile(fp) and os.access(fp, os.X_OK):
                try:
                    size = os.path.getsize(fp)
                    records.append({
                        "tool_id": f"script:{f}",
                        "tool_type": "script",
                        "tool_name": f,
                        "source_path": fp,
                        "size_bytes": size,
                    })
                except Exception:
                    pass
    return records

def scanner_arch():
    """Discover system architecture: running services, ports, topology."""
    records = []
    
    # Check known ports
    port_checks = [
        ("neo4j_http", 7474),
        ("neo4j_bolt", 7687),
        ("litellm", 4000),
        ("hermes_gateway", 8643),
        ("voice_proxy", 8647),
        ("hermes_tui", 8648),
    ]
    import socket
    for name, port in port_checks:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            records.append({
                "tool_id": f"port:{port}",
                "tool_type": "service_port",
                "tool_name": name,
                "port": port,
                "accessible": result == 0,
            })
        except Exception:
            records.append({
                "tool_id": f"port:{port}",
                "tool_type": "service_port",
                "tool_name": name,
                "port": port,
                "accessible": False,
            })
    
    # Check systemd services
    out, rc = run(["systemctl", "list-units", "--type=service", "--state=running", "--no-legend"], timeout=5)
    if rc == 0:
        for line in out.split('\n'):
            parts = line.split()
            if parts:
                svc_name = parts[0]
                if any(k in svc_name for k in ['neo4j', 'hermes', 'litellm', 'docker', 'ssh']):
                    records.append({
                        "tool_id": f"systemd:{svc_name}",
                        "tool_type": "systemd_service",
                        "tool_name": svc_name,
                        "state": "running",
                    })
    
    return records

def scanner_health():
    """Health checks on known endpoints."""
    records = []
    health_checks = [
        ("neo4j_http", "http://localhost:7474"),
        ("litellm_health", "http://localhost:4000/health"),
        ("litellm_models", "http://localhost:4000/v1/models"),
        ("hermes_gateway_health", "http://localhost:8643/health"),
    ]
    for name, url in health_checks:
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={'User-Agent': 'claw-discovery/1.0'})
            resp = urllib.request.urlopen(req, timeout=3)
            body = resp.read().decode('utf-8', errors='replace')[:500]
            records.append({
                "tool_id": f"health:{name}",
                "tool_type": "health_check",
                "tool_name": name,
                "url": url,
                "status_code": resp.getcode(),
                "body_preview": body,
                "healthy": resp.getcode() < 400,
            })
        except Exception as e:
            records.append({
                "tool_id": f"health:{name}",
                "tool_type": "health_check",
                "tool_name": name,
                "url": url,
                "error": str(e)[:200],
                "healthy": False,
            })
    
    return records

def scanner_litellm():
    """Scan LiteLLM for available models, providers, configs."""
    records = []
    try:
        import urllib.request, json
        req = urllib.request.Request(
            "http://localhost:4000/v1/models",
            headers={'User-Agent': 'claw-discovery/1.0', 'Authorization': 'Bearer sk-litellm'}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        for model in data.get('data', []):
            records.append({
                "tool_id": f"litellm_model:{model.get('id', 'unknown')}",
                "tool_type": "litellm_model",
                "tool_name": model.get('id', 'unknown'),
                "owned_by": model.get('owned_by', 'unknown'),
                "object": model.get('object', ''),
            })
    except Exception:
        pass
    
    # Also check litellm config files
    config_paths = [
        os.path.expanduser("~/.hermes/litellm_config.yaml"),
        os.path.expanduser("~/cursor/opencode+/configs/opencode.litellm-dual.json"),
    ]
    for fp in config_paths:
        if os.path.exists(fp):
            try:
                size = os.path.getsize(fp)
                records.append({
                    "tool_id": f"litellm_config:{os.path.basename(fp)}",
                    "tool_type": "litellm_config",
                    "tool_name": os.path.basename(fp),
                    "source_path": fp,
                    "size_bytes": size,
                })
            except Exception:
                pass
    
    return records

def scanner_process():
    """Scan running processes for key daemons."""
    records = []
    key_procs = ['neo4j', 'hermes', 'litellm', 'node', 'docker', 'python3']
    out, rc = run(["ps", "aux", "--no-headers"], timeout=5)
    if rc != 0:
        return records
    
    for line in out.split('\n'):
        parts = line.split()
        if len(parts) < 11:
            continue
        cmd = ' '.join(parts[10:])
        for key in key_procs:
            if key in cmd and not 'grep' in cmd:
                records.append({
                    "tool_id": f"process:{parts[1]}_{key}",
                    "tool_type": "process",
                    "tool_name": key,
                    "pid": parts[1],
                    "cmd": cmd[:200],
                    "cpu": parts[2],
                    "mem": parts[3],
                })
                break
    
    return records

def main():
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    registry = {
        "timestamp": ts,
        "scanners": {},
        "summary": {},
    }
    
    scanners = {
        "compose": scanner_compose,
        "mcp": scanner_mcp,
        "skills": scanner_skills,
        "env": scanner_env,
        "scripts": scanner_scripts,
        "arch": scanner_arch,
        "health": scanner_health,
        "litellm": scanner_litellm,
        "process": scanner_process,
    }
    
    total = 0
    for name, fn in scanners.items():
        try:
            records = fn()
            registry["scanners"][name] = records
            registry["summary"][name] = len(records)
            total += len(records)
        except Exception as e:
            registry["scanners"][name] = []
            registry["summary"][name] = f"ERROR: {e}"
    
    registry["summary"]["total_records"] = total
    
    # Write registry snapshot
    snapshot_path = os.path.join(REGISTRY_DIR, f"integrations.{ts}.json")
    with open(snapshot_path, 'w') as f:
        json.dump(registry, f, indent=2, default=str)
    
    print(f"Written: {snapshot_path}")
    print(f"Total records: {total}")
    for name, count in registry["summary"].items():
        if name != "total_records":
            print(f"  {name}: {count}")
    
    return snapshot_path

if __name__ == '__main__':
    main()
