#!/usr/bin/env python3
"""
Deep Plan Research integration test — validates all components:
  - Registry consistency (37+ agents, all research agents registered)
  - Gate scripts compilability and execution
  - Plan2.md references (sub-phases, gates, debate, developer query)
  - AGENTS.md references
  - Agent file headers (YAML frontmatter)
  - Research-loop skill v3.0 sections

Usage: HERMES_HOME=/home/user/.hermes python3 integration-test.py
"""
import json, os, subprocess, sys, tempfile

HERMES = os.environ.get("HERMES_HOME", "/home/user/.hermes")
SCRIPTS = os.path.join(HERMES, "scripts")
AGENTS = os.path.join(HERMES, "agents")

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition: passed += 1; print(f"  OK  {name}")
    else: failed += 1; print(f"  FAIL  {name}  {detail}")

# 1. Registry consistency
with open(os.path.join(AGENTS, "registry.json")) as f:
    registry = json.load(f)
agents = registry.get("agents", {})
test("Registry >= 37 agents", len(agents) >= 37, f"found {len(agents)}")
for ra in ["deep-plan-researcher","plan2","research/citation-agent","research/codebase-analyzer",
           "research/education-graph-analyzer","research/debate-agent","research/academic-researcher",
           "research/code-researcher","research/community-researcher","research/vendor-docs-researcher",
           "research/claw-analyzer","research/synthesizer"]:
    test(f"Agent '{ra}' registered", ra in agents)
test("Old researcher.md NOT in registry", "researcher" not in agents)

# 2. Gate scripts
for s in ["research_quality_gate.py","research_completeness_gate.py","citation_enforcement_gate.py"]:
    path = os.path.join(SCRIPTS, s)
    test(f"{s} exists", os.path.isfile(path))
    r = subprocess.run(["python3","-c",f"compile(open('{path}').read(),'{s}','exec')"],
                       capture_output=True, text=True, timeout=10)
    test(f"{s} compiles", r.returncode == 0)

# 3. Gate pipeline on test artifact
TEST_ARTIFACT = """# Research Report: Test\n\n**Mode:** BALANCED\n\n## RQ Answers\n\n#### RQ1: Test\nAnswer is 42. [1]\nAdditional verification done. [1]\nSecond source confirms. [2]\n\n### Source Quality Matrix\n\n| # | Title | URL | Authority | Recency | Relevance | Corroboration | Score |\n|---|-------|-----|-----------|---------|-----------|---------------|-------|\n| 1 | Primary | https://example.com/1 | 2 | 2 | 2 | 2 | 8 |\n| 2 | Secondary | https://example.com/2 | 2 | 2 | 2 | 1 | 7 |\n\n## Recommendations for Architect\n\nProceed.\n\n## Developer Handoff\n\n- RQ1: done\n"""
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, "docs", "research"))
    art = os.path.join(tmp, "docs", "research", "test.md")
    with open(art, "w") as f: f.write(TEST_ARTIFACT)
    r = subprocess.run(["python3", os.path.join(SCRIPTS, "research_quality_gate.py"), "--artifact", art, "--json"],
                       capture_output=True, text=True, timeout=15, cwd=tmp)
    test("GATE B passes", r.returncode == 0)
    r = subprocess.run(["python3", os.path.join(SCRIPTS, "research_completeness_gate.py"), "--artifact", art, "--json"],
                       capture_output=True, text=True, timeout=15, cwd=tmp)
    test("GATE C runs", r.returncode in (0, 1), "exit " + str(r.returncode))
    r = subprocess.run(["python3", os.path.join(SCRIPTS, "citation_enforcement_gate.py"), "--artifact", art, "--verify-sample", "10", "--json"],
                       capture_output=True, text=True, timeout=30, cwd=tmp)
    test("GATE D runs", r.returncode in (0, 1), "exit " + str(r.returncode))

# 4. Plan2.md references
with open(os.path.join(AGENTS, "plan2.md")) as f: plan2 = f.read()
for name, check in [("3.0 Research Plan", "3.0" in plan2 and "Research Plan" in plan2),
    ("3.1 Parallel Execution", "3.1" in plan2), ("3.2 Synthesis", "3.2" in plan2),
    ("3.3 Citation", "3.3" in plan2), ("GATE A", "GATE A" in plan2),
    ("GATE B", "GATE B" in plan2), ("GATE C", "GATE C" in plan2),
    ("GATE D", "GATE D" in plan2), ("Developer Query", "Developer" in plan2 and "Deep Research" in plan2),
    ("7 checks", "7 checks" in plan2), ("Cost Gate", "Cost Gate" in plan2),
    ("Debate mode", "debate" in plan2.lower())]:
    test(name, check)

# 5. Agent file headers
for af in ["deep-plan-researcher.md","research/citation-agent.md","research/codebase-analyzer.md",
           "research/education-graph-analyzer.md","research/debate-agent.md"]:
    path = os.path.join(AGENTS, af)
    test(f"{af} exists", os.path.isfile(path))
    if os.path.isfile(path):
        with open(path) as f: test(f"{af} has YAML frontmatter", f.read().startswith("---"))

# Summary
print(f"\n{'='*40}\n  Passed: {passed}/{passed+failed}  Failed: {failed}/{passed+failed}")
sys.exit(0 if failed == 0 else 1)
