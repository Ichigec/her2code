---
name: architecture-as-code-discovery
description: "Architecture-as-code discovery when data is insufficient: incremental recovery from source, drift detection, C4/Structurizr, LLM-assisted archaeology — output docs/architecture/<slug>-discovery.md."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [architecture, discovery, archaeology, c4, structurizr, drift, recovery, legacy]
    related_skills: [architecture-design, codebase-inspection, systematic-debugging, requirements-analysis]
---

# Architecture-as-Code Discovery (Insufficient Data)

When there is **no architecture documentation**, **outdated diagrams**, or
**incomplete knowledge** of a codebase — this skill provides a systematic,
incremental methodology to build "architecture as code" from scratch.

**Core principle:** Architecture is not discovered in one pass. It is
**reconstructed incrementally** through a pipeline of static analysis,
runtime observation, LLM-assisted inference, and human validation. Each
phase produces a verifiable artifact that feeds the next.

## When to Use

- Legacy codebase with no/missing/outdated architecture docs
- New team inheriting an undocumented system
- Pre-refactor architecture assessment
- After a major incident reveals hidden coupling
- When asked "how does this system actually work?"
- **NOT** for greenfield design — use `architecture-design` instead

## The 5-Phase Discovery Pipeline

```
Phase 1: Surface Scan     →  what files/modules exist?
Phase 2: Static Analysis  →  what calls what?
Phase 3: Runtime Trace    →  what actually runs?
Phase 4: LLM Inference    →  what does it mean?
Phase 5: Architecture-Code →  Structurizr DSL + C4 + ADRs
```

Each phase has **explicit data collection commands** and **output artifacts**.
Do not skip phases — each builds on the previous one's evidence.

### Phase 1: Surface Scan (5-10 min)

**Goal:** Map the file/module landscape without reading logic.

```bash
# Language distribution
find . -name '*.py' -o -name '*.ts' -o -name '*.go' | sed 's/.*\.//' | sort | uniq -c | sort -rn

# Directory tree (depth 3, no node_modules/.git)
find . -maxdepth 3 -type d ! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/venv/*' | sort

# Entry points (main files, __main__, main(), app.py, index.ts)
grep -rl 'if __name__.*__main__\|def main(\|app = ' . --include='*.py' --include='*.ts' --include='*.go' | head -20

# Config files (reveal infrastructure)
find . -maxdepth 2 -name 'docker-compose*' -o -name 'Dockerfile*' -o -name '*.yaml' -o -name '*.yml' -o -name '.env*' | head -20

# Dependency manifests
find . -maxdepth 2 -name 'requirements*.txt' -o -name 'package.json' -o -name 'go.mod' -o -name 'Cargo.toml' | head -10
```

**Output:** `docs/architecture/<slug>-01-surface.md`

```markdown
# Surface Scan: [project]

## Languages
| Language | Files | % |
|----------|-------|---|
| Python   | 847   | 72% |
| TypeScript | 213 | 18% |

## Entry Points
- `run_agent.py` — main agent loop
- `cli.py` — CLI entry
- `gateway/run.py` — gateway server

## Infrastructure (from config files)
- Docker Compose: Neo4j, LiteLLM
- No Kubernetes manifests
- `.env`: 15 API keys (7 providers)

## Module Groups (top-level dirs)
| Dir | Purpose (guess) | Confidence |
|-----|-----------------|------------|
| agent/ | Agent internals | HIGH (has __init__.py, imported by run_agent) |
| tools/ | Tool implementations | HIGH |
| gateway/ | Messaging gateway | MEDIUM |
```

### Phase 2: Static Analysis (15-30 min)

**Goal:** Extract call graphs, import dependencies, and coupling metrics
**without running anything**.

```bash
# Python import graph (who imports whom)
python3 -c "
import ast, os, json
from collections import defaultdict

graph = defaultdict(set)
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '__pycache__', 'node_modules')]
    for f in files:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        module = path.replace('./', '').replace('/', '.').replace('.py', '')
        try:
            tree = ast.parse(open(path).read(), path)
        except: continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    graph[module].add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    graph[module].add(node.module.split('.')[0])
# Print top 30 most-connected modules
ranked = sorted(graph.items(), key=lambda x: len(x[1]), reverse=True)[:30]
for mod, deps in ranked:
    print(f'{mod}: {len(deps)} imports')
"

# Cross-directory coupling (which dirs import from which)
python3 -c "
import ast, os, re
from collections import defaultdict
cross = defaultdict(int)
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '__pycache__')]
    for f in files:
        if not f.endswith('.py'): continue
        src_dir = root.split('/')[1] if '/' in root else '.'
        try:
            tree = ast.parse(open(os.path.join(root, f)).read())
        except: continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for part in node.module.split('.'):
                    if part in ('tools','agent','gateway','cli','hermes_cli','plugins'):
                        cross[src_dir][part] += 1
for src in sorted(cross):
    for dst, cnt in sorted(cross[src].items(), key=lambda x: -x[1]):
        print(f'{src} -> {dst}: {cnt}')
"
```

**Tools (if available):**
- `pygount` — LOC, language ratios (see `codebase-inspection` skill)
- `pyreverse` — UML class diagrams from Python code
- `madge` — circular dependency detection for JS/TS
- `depcheck` — unused dependencies

**Output:** `docs/architecture/<slug>-02-static.md`

Include: import graph (top N hubs), cross-directory coupling matrix, circular
dependencies, fan-in/fan-out outliers.

### Phase 3: Runtime Trace (10-20 min)

**Goal:** Observe what **actually executes** — static analysis misses
reflection, dynamic imports, plugin loading, and runtime composition.

```bash
# Python: strace what files are opened during startup
strace -f -e trace=openat python3 -c "import main_module" 2>&1 | grep -v ENOENT | awk -F'"' '{print $2}' | sort -u | head -50

# Log-based trace: what modules log during a typical request
grep -E "INFO|DEBUG" ~/.hermes/logs/agent.log | grep -oP '\[([\w.]+)\]' | sort | uniq -c | sort -rn | head -30

# Network trace: what endpoints are called
tcpdump -i lo -w /tmp/arch-trace.pcap port 7474 or port 4000 or port 8643 &
# ... run a typical operation ...
kill %1
tcpdump -r /tmp/arch-trace.pcap -n | awk '{print $3, $5}' | sort -u

# Process tree: what spawns what
pstree -p $(pgrep -f hermes) | head -30
```

**Output:** `docs/architecture/<slug>-03-runtime.md`

Include: actual module load order, runtime dependencies (DB, cache, external
APIs), process tree, network endpoints hit.

### Phase 4: LLM-Assisted Inference (20-40 min)

**Goal:** Use LLM to bridge the gap between raw code facts and architectural
meaning. This is where the arXiv 2511.05165 methodology applies: extract
→ filter → infer → validate.

**The hybrid pipeline (from research):**

```
Source Code
    ↓  [RE: reverse engineering extraction]
Class/Module Diagram (comprehensive, noisy)
    ↓  [LLM: filter architecturally significant elements]
Core Components (filtered, ~10-20 key modules)
    ↓  [LLM: infer behavior + state machines]
Behavioral View (what each component does)
    ↓  [LLM: generate architecture description]
Architecture-as-Code (Structurizr DSL)
```

**Step 1: Extract** — Use Phase 2 output (import graph) as the raw material.

**Step 2: Filter** — Prompt the LLM to identify the ~10-20 "architecturally
significant" components from the full list:

```
Given these N modules with their import counts and cross-references:
[list from Phase 2]

Identify the 10-20 "architecturally significant" components. A component is
architecturally significant if:
- It is imported by 5+ other modules (high fan-in)
- It imports from 3+ different directories (high coupling)
- It appears in runtime traces (Phase 3)
- It has a public API/interface (__init__.py exports, class definitions)

Output: JSON array of {name, role, confidence, evidence}
```

**Step 3: Infer** — For each significant component, prompt:

```
Read this module's source code and answer:
1. What is its single responsibility? (one sentence)
2. What are its inputs? (API calls, events, function params)
3. What are its outputs? (return values, side effects, events emitted)
4. What state does it manage?
5. What components depend on it? (from Phase 2 graph)
6. What components does it depend on?

Be conservative — mark anything uncertain as [INFERRED] vs [VERIFIED].
```

**Step 4: Validate** — Cross-check LLM inferences against:
- Phase 1 (does the file exist?)
- Phase 2 (does the import graph confirm the dependency?)
- Phase 3 (does runtime trace show the interaction?)

Discard any inference that contradicts evidence from Phases 1-3.

**Output:** `docs/architecture/<slug>-04-inference.md`

```markdown
# Architectural Inference: [project]

## Core Components (LLM-filtered, evidence-validated)

| Component | Responsibility | Fan-in | Fan-out | Confidence |
|-----------|---------------|--------|---------|------------|
| run_agent.py | Core conversation loop | 12 | 8 | VERIFIED |
| delegate_tool.py | Subagent spawning | 5 | 6 | VERIFIED |
| agent_runtime_helpers.py | Runtime state management | 8 | 4 | VERIFIED |

## Disputed / Low-Confidence
| Component | LLM says | Evidence says | Resolution |
|-----------|----------|---------------|------------|
| observer.py | "Inline heuristics" | Also spawns subagents via hook | AMBIGUOUS |
```

### Phase 5: Architecture-as-Code (30-60 min)

**For D2-based diagrams** (`.d2` files as an alternative or complement to
Structurizr), see `references/d2-diagram-rendering.md` for installation, syntax
migration from old `<style>{…}` blocks to modern D2 v0.7.x, and rendering to
SVG/PNG/PDF for documentation or DrawIO import.

**Goal:** Produce executable architecture definition in Structurizr DSL +
ADR records. This is the **living** artifact — it can be validated,
diffed, and kept in sync with code.

**Step 1: C4 Model in Structurizr DSL**

```
workspace {
    model {
        # System Context (Level 1)
        person user "Pavel" "Developer using Hermes"
        system hermes "Hermes Agent" "AI agent framework"

        # Container (Level 2)
        container cli "CLI/TUI" "Python, Ink" "Interactive command interface"
        container gateway "Gateway" "Python" "Messaging gateway (Telegram, Discord, ...)"
        container agent "Agent Core" "Python, run_agent.py" "LLM conversation loop"
        container db "State DB" "SQLite" "Session storage + FTS5 search"
        container neo4j "Neo4j" "Docker" "Knowledge graph"

        # Component (Level 3 — only for agent core)
        component conv_loop "Conversation Loop" "agent/conversation_loop.py"
        component tool_exec "Tool Executor" "agent/tool_executor.py"
        component delegate "Delegation" "tools/delegate_tool.py"
        component cred_pool "Credential Pool" "agent/credential_pool.py"

        # Relationships (from Phase 2+3 evidence)
        user -> cli "uses"
        cli -> agent "spawns"
        gateway -> agent "routes messages"
        agent -> db "reads/writes sessions"
        agent -> neo4j "knowledge queries"
        conv_loop -> tool_exec "executes tools"
        tool_exec -> delegate "delegates tasks"
        delegate -> cred_pool "rotates credentials"
    }
    views {
        systemContext hermes "Context" {
            include *
        }
        container hermes "Containers" {
            include *
        }
        component agent "Components" {
            include *
        }
        theme default
    }
}
```

**Step 2: Architecture Decision Records (ADRs)**

For each significant decision discovered (not designed — discovered):

```markdown
# ADR-001: Credential Pool per Provider

**Date:** 2026-07-06 (discovered)
**Status:** Active

## Context
The system uses multiple LLM providers (zai, deepseek, openrouter). Each
provider has its own API key, rate limits, and billing. Credential rotation
is needed for resilience.

## Decision
A `CredentialPool` abstraction per provider, with lease/rotate/refresh
semantics.

## Consequences
- ✅ Isolates provider credentials
- ✅ Enables rotation on 429/402
- ⚠️ Pool must be updated on provider switch (bug found: stale pool
  caused HTTP 400 when parent switched deepseek→zai but pool stayed deepseek)

## Drift Risk
`switch_model()` must update `_credential_pool` — this is the coupling
point. Any new provider switch path must handle pool rotation.
```

**Step 3: Drift Detection Setup**

Architecture-as-code is only valuable if it stays in sync with reality.
Set up automated drift detection:

```bash
# Simple: compare import graph hash
python3 -c "
import ast, os, hashlib
from collections import defaultdict
graph = defaultdict(set)
for root, dirs, files in os.walk('src'):
    for f in files:
        if not f.endswith('.py'): continue
        # ... build graph ...
h = hashlib.sha256(str(sorted(graph.items())).encode()).hexdigest()
print(f'import_graph_hash: {h}')
" > docs/architecture/.drift-baseline

# CI check: compare current hash vs baseline
# If different → architecture may have drifted → review needed
```

**Output:**
- `docs/architecture/<slug>-05-architecture.dsl` — Structurizr DSL
- `docs/architecture/adr/` — ADR directory
- `docs/architecture/.drift-baseline` — drift detection baseline

## The "Insufficient Data" Escalation Ladder

When a phase produces insufficient data, **escalate** rather than guess:

```
Phase 1 yields nothing?     → Code is not where you think. Find it first.
                              Check: git log, deployment configs, package manifests.
Phase 2 import graph sparse? → Dynamic imports, plugins, reflection.
                              Escalate to Phase 3 (runtime trace).
Phase 3 runtime trace empty? → System not running, or tracing wrong layer.
                              Check: is the process alive? strace the PID.
Phase 4 LLM inference uncertain? → More context needed.
                              Feed the LLM larger code chunks (full files, not snippets).
                              Cross-reference with git blame for history.
Phase 5 DSL doesn't compile? → Model is wrong, not the tool.
                              Go back to Phase 2, recheck dependencies.
```

**NEVER fabricate architecture.** Every component, relationship, and
responsibility in the final artifact MUST trace back to evidence from
Phase 1, 2, or 3. If you can't cite the evidence, mark it `[UNVERIFIED]`.

## Key Research References

| Source | Key Insight |
|--------|-------------|
| arXiv 2511.05165 (Nov 2025) | Hybrid RE+LLM pipeline: extract class diagram → LLM filters core components → generates behavioral view |
| Structurizr (Simon Brown) | C4 model as code: DSL → multiple diagram views from single model |
| Architecture Drift Detection (Archyl, Erode) | Drift score = distance between documented and actual architecture; CI-integrated |
| Software Archaeology (Wikipedia) | Systematic recovery from undocumented legacy: reverse engineer modules, apply patterns |
| Living C4 (lmishra.substack) | Architecture-as-code → validate like code → block PRs on drift |
| Event Storming (DDD) | Big-picture event storming for bounded context discovery when domain knowledge is sparse |

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| **LLM hallucinates components** | Every component MUST have file-path evidence from Phase 1 |
| **Import graph is too noisy** | Filter to top N by fan-in; LLM filter in Phase 4 |
| **Plugin systems invisible to static analysis** | Runtime trace (Phase 3) is mandatory for plugin architectures |
| **Circular dependencies missed** | Use `madge` (JS) or custom DFS cycle detection (Python) |
| **ADR becomes stale** | Link ADRs to code via `@adr` annotations; CI checks references |
| **Structurizr DSL diverges from code** | Drift detection baseline + CI gate on hash change |
| **Architecture is "done" after one pass** | Architecture-as-code is LIVING — schedule re-discovery on major changes |

## Verification Checklist

- [ ] Phase 1 surface scan complete (file inventory, entry points, infra)
- [ ] Phase 2 static analysis complete (import graph, coupling matrix)
- [ ] Phase 3 runtime trace complete (module load order, network, process tree)
- [ ] Phase 4 LLM inference cross-validated against Phases 1-3
- [ ] Phase 5 Structurizr DSL compiles and renders
- [ ] Every component in DSL has evidence citation (Phase 1/2/3)
- [ ] ADRs written for discovered decisions (not just designed ones)
- [ ] Drift baseline committed
- [ ] `[UNVERIFIED]` items listed in Open Items section
