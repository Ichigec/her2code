#!/usr/bin/env python3
"""
validate-plan3-models.py — Validate plan3 model routing consistency.

Checks ALL 5 sources of truth:
  1. Sub-agent frontmatter (~/.hermes/agents/plan3/*.md)
  2. registry.json (~/.hermes/agents/registry.json)
  3. Physical llama-server health (ports :8101, :8102, :8103)
  4. LiteLLM :4000 model connectivity
  5. start-llama.sh operational health (PID files + process count)

Exit code 0 = all local + all servers up. Non-zero = problems found.

Usage:
    python3 scripts/validate-plan3-models.py [--fix] [--json]

    --fix   Auto-fix frontmatter/registry drift (reasoning->agents-a1, coding->nex, sim->agentworld)
    --json  Output results as JSON instead of table
"""

import os, sys, re, json, urllib.request, time, argparse, subprocess
from pathlib import Path

HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
AGENTS_DIR = os.path.join(HERMES_HOME, "agents")
PLAN3_DIR = os.path.join(AGENTS_DIR, "plan3")
REGISTRY_PATH = os.path.join(AGENTS_DIR, "registry.json")

# Resolve REAL home (Hermes sets $HOME=/home/user/.hermes/home, but model
# files and PID dirs live under the real user home /home/user)
try:
    REAL_HOME = subprocess.check_output(
        ["getent", "passwd", os.environ.get("USER", "pavel")], text=True
    ).strip().split(":")[5]
except Exception:
    REAL_HOME = "/home/user"

# Design intent -- plan3 "Fully Local" model routing
ROUTING = {
    "reasoning": ("agents-a1-abliterated", "custom:local"),
    "coding": ("nex-n2-mini", "custom:local"),
    "simulation": ("agentworld", "custom:local"),
}

# Role classification for each sub-agent
ROLE_MAP = {
    # Reasoning
    "aflow-orchestrator": "reasoning",
    "architect-agent": "reasoning",
    "auditor": "reasoning",
    "critic": "reasoning",
    "enterprise-architect": "reasoning",
    "idea-generator": "reasoning",
    "knowledge-curator": "reasoning",
    "requirements-agent": "reasoning",
    "researcher": "reasoning",
    "system-analyst": "reasoning",
    # Coding
    "developer-agent": "coding",
    "deployment-agent": "coding",
    "devops-engineer": "coding",
    "jidoka-evaluator": "coding",
    "security-agent": "coding",
    "techlead-agent": "coding",
    "tester-agent": "coding",
    # Simulation
    "sim-rl-agent": "simulation",
}

CLOUD_INDICATORS = ["deepseek", "kimi", "openai", "zai"]


def is_cloud_provider(provider: str) -> bool:
    return any(c in provider.lower() for c in CLOUD_INDICATORS)


def check_frontmatter():
    """Check all plan3/*.md frontmatter model/provider."""
    issues = []
    results = []

    if not os.path.isdir(PLAN3_DIR):
        return results, [{"file": PLAN3_DIR, "error": "plan3 directory not found"}]

    for fn in sorted(os.listdir(PLAN3_DIR)):
        if not fn.endswith(".md"):
            continue
        name = fn.replace(".md", "")
        path = os.path.join(PLAN3_DIR, fn)

        model = provider = ""
        with open(path) as f:
            for line in f:
                if line.startswith("model:"):
                    model = line.split(":", 1)[1].strip()
                if line.startswith("provider:"):
                    provider = line.split(":", 1)[1].strip()

        role = ROLE_MAP.get(name, "reasoning")
        expected_model, expected_provider = ROUTING[role]

        entry = {
            "name": name,
            "model": model,
            "provider": provider,
            "expected_model": expected_model,
            "expected_provider": expected_provider,
            "is_cloud": is_cloud_provider(provider),
            "mismatch": model != expected_model or provider != expected_provider,
            "path": path,
        }
        results.append(entry)

        if entry["is_cloud"]:
            issues.append({"file": name, "error": f"CLOUD provider: {model}/{provider}"})
        if entry["mismatch"] and not entry["is_cloud"]:
            issues.append({"file": name, "error": f"Expected {expected_model}/{expected_provider}, got {model}/{provider}"})

    return results, issues


def check_registry():
    """Check registry.json for cloud providers."""
    issues = []

    if not os.path.exists(REGISTRY_PATH):
        return [], [{"file": "registry.json", "error": "not found"}]

    with open(REGISTRY_PATH) as f:
        reg = json.load(f)

    cloud_agents = []
    for name, info in reg.get("agents", {}).items():
        provider = info.get("provider", "")
        if is_cloud_provider(provider):
            cloud_agents.append({"name": name, "model": info.get("model", "?"), "provider": provider})

    if cloud_agents:
        issues = [{"file": f"registry.json:{a['name']}", "error": f"CLOUD: {a['model']}/{a['provider']}"} for a in cloud_agents]

    return cloud_agents, issues


def check_servers():
    """Check llama-server health on ports 8101, 8102, 8103."""
    servers = {
        8101: ("nex-n2-mini", "Coding"),
        8102: ("agents-a1", "Reasoning"),
        8103: ("agentworld", "Simulation"),
    }
    results = {}
    issues = []

    for port, (name, role) in servers.items():
        try:
            req = urllib.request.Request(f"http://localhost:{port}/health")
            with urllib.request.urlopen(req, timeout=5) as r:
                ok = r.status == 200
        except Exception:
            ok = False

        results[port] = {"name": name, "role": role, "up": ok}
        if not ok:
            issues.append({"server": f":{port}", "error": f"DOWN ({name})"})

    return results, issues


def check_start_llama():
    """Check start-llama.sh operational health: PID files + process count.

    Under Hermes terminal, $HOME=/home/user/.hermes/home (session isolation),
    but start-llama.sh writes PID files to ${HOME}/dev/llama/pids/. If models
    were started from a real shell (HOME=/home/user) but status is checked
    from Hermes, PID files appear missing. This check uses REAL_HOME.
    """
    issues = []
    results = {"pid_files_ok": True, "procs_ok": True, "proc_count": 0}

    pid_dir = os.path.join(REAL_HOME, "dev", "llama", "pids")
    expected_pids = ["nex.pid", "agents.pid", "world.pid"]

    for pidfile in expected_pids:
        path = os.path.join(pid_dir, pidfile)
        if not os.path.exists(path):
            results["pid_files_ok"] = False
            issues.append({"start_llama": pidfile, "error": f"PID file missing: {path}"})

    # Check process count regardless of PID files
    try:
        ps = subprocess.check_output("pgrep -c -f llama-server", shell=True, text=True).strip()
        count = int(ps)
        results["proc_count"] = count
        if count < 3:
            results["procs_ok"] = False
            issues.append({"start_llama": "procs", "error": f"Only {count} llama-server processes (need 3)"})
    except subprocess.CalledProcessError:
        results["procs_ok"] = False
        issues.append({"start_llama": "procs", "error": "No llama-server processes running"})

    # Check for $HOME bug in start-llama.sh itself
    script_path = os.path.join(REAL_HOME, "dev", "llama", "start-llama.sh")
    if os.path.exists(script_path):
        with open(script_path) as f:
            content = f.read()
        if "${HOME}" in content and "REAL_HOME" not in content:
            results["home_bug"] = True
            issues.append({
                "start_llama": "$HOME",
                "error": "start-llama.sh uses ${HOME} without REAL_HOME fix -- status will fail under Hermes terminal"
            })
        else:
            results["home_bug"] = False
    else:
        results["home_bug"] = None

    return results, issues


def check_litellm():
    """Quick connectivity test for the 3 models via LiteLLM :4000."""
    models = ["agents-a1-abliterated", "nex-n2-mini", "agentworld"]
    results = {}
    issues = []

    for model in models:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "Say OK"}],
            "max_tokens": 5,
        }).encode()
        req = urllib.request.Request(
            "http://localhost:4000/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": "Bearer sk-local",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                results[model] = {"ok": True, "response": content[:50]}
        except Exception as e:
            results[model] = {"ok": False, "error": str(e)[:100]}
            issues.append({"model": model, "error": str(e)[:100]})

    return results, issues


def fix_frontmatter():
    """Auto-fix frontmatter drift."""
    fixed = 0
    for fn in sorted(os.listdir(PLAN3_DIR)):
        if not fn.endswith(".md"):
            continue
        name = fn.replace(".md", "")
        path = os.path.join(PLAN3_DIR, fn)

        role = ROLE_MAP.get(name, "reasoning")
        expected_model, expected_provider = ROUTING[role]

        with open(path) as f:
            content = f.read()

        original = content
        content = re.sub(r"^model:.*$", f"model: {expected_model}", content, count=1, flags=re.MULTILINE)
        content = re.sub(r"^provider:.*$", f"provider: {expected_provider}", content, count=1, flags=re.MULTILINE)

        if content != original:
            with open(path, "w") as f:
                f.write(content)
            fixed += 1

    return fixed


def main():
    parser = argparse.ArgumentParser(description="Validate plan3 model routing")
    parser.add_argument("--fix", action="store_true", help="Auto-fix frontmatter drift")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.fix:
        n = fix_frontmatter()
        print(f"Fixed {n} frontmatter files", file=sys.stderr)

    fm_results, fm_issues = check_frontmatter()
    reg_cloud, reg_issues = check_registry()
    srv_results, srv_issues = check_servers()
    sll_results, sll_issues = check_start_llama()
    llm_results, llm_issues = check_litellm()

    all_issues = fm_issues + reg_issues + srv_issues + sll_issues + llm_issues

    if args.json:
        print(json.dumps({
            "frontmatter": fm_results,
            "registry_cloud_count": len(reg_cloud),
            "servers": srv_results,
            "start_llama": sll_results,
            "litellm": llm_results,
            "issues": all_issues,
            "passed": len(all_issues) == 0,
        }, indent=2))
    else:
        # Table output
        print("=" * 70)
        print("PLAN3 MODEL ROUTING VALIDATION")
        print("=" * 70)

        print("\n1. Sub-agent frontmatter:")
        cloud_count = sum(1 for r in fm_results if r["is_cloud"])
        mismatch_count = sum(1 for r in fm_results if r["mismatch"] and not r["is_cloud"])
        print(f"   Total: {len(fm_results)} | Cloud: {cloud_count} | Mismatch: {mismatch_count}")

        print("\n2. Registry cloud agents:", len(reg_cloud))

        print("\n3. Physical servers:")
        for port, info in sorted(srv_results.items()):
            status = "[OK]" if info["up"] else "[DOWN]"
            print(f"   :{port} ({info['name']:<15}) {status} [{info['role']}]")

        print("\n4. start-llama.sh health:")
        print(f"   PID files: {'OK' if sll_results['pid_files_ok'] else 'MISSING'}")
        print(f"   Processes: {sll_results['proc_count']}/3 {'OK' if sll_results['procs_ok'] else 'INSUFFICIENT'}")
        if sll_results.get("home_bug") is True:
            print(f"   $HOME bug: DETECTED (start-llama.sh lacks REAL_HOME fix)")
        elif sll_results.get("home_bug") is False:
            print(f"   $HOME fix: APPLIED (REAL_HOME)")

        print("\n5. LiteLLM connectivity:")
        for model, info in sorted(llm_results.items()):
            status = f"[OK] {info.get('response', '')}" if info["ok"] else f"[FAIL] {info.get('error', '')}"
            print(f"   {model:<30} {status}")

        total_issues = len(all_issues)
        print(f"\n{'='*70}")
        if total_issues == 0:
            print("ALL CHECKS PASSED -- Fully Local confirmed")
        else:
            print(f"{total_issues} ISSUES FOUND:")
            for iss in all_issues:
                print(f"  - {iss}")
        print(f"{'='*70}")

    sys.exit(0 if len(all_issues) == 0 else 1)


if __name__ == "__main__":
    main()
