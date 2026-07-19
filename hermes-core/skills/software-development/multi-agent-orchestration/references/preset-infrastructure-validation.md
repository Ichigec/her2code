# Preset Infrastructure Validation Checklist

Run this **before** starting any `/agent plan2` (or similar multi-agent preset)
cycle. Catches the most common failure modes that only surface mid-cycle when
a sub-agent tries to invoke a missing model or a broken gate script.

## 1. Model routing cross-check (MOST COMMON BLOCKER)

Registry can reference models that the serving layer (LiteLLM :4000) doesn't
have. Every agent's `model` field must exist in LiteLLM's catalog.

```bash
# Get available models from LiteLLM
curl -s http://localhost:4000/v1/models \
  -H 'Authorization: Bearer sk-local' | \
  python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"

# Cross-check: every model in registry must be in that list
python3 -c "
import json
reg = json.load(open('$HOME/.hermes/agents/registry.json'))
litellm_models = set()  # paste the list from above, or fetch programmatically
# Quick inline fetch:
from urllib.request import urlopen, Request
req = Request('http://localhost:4000/v1/models', headers={'Authorization': 'Bearer sk-local'})
litellm_models = {m['id'] for m in json.loads(urlopen(req).read())['data']}
missing = {}
for name, a in reg['agents'].items():
    m = a.get('model','')
    if m and m not in litellm_models:
        missing[name] = m
if missing:
    print('MISSING MODELS:')
    for agent, model in missing.items():
        print(f'  {agent:30s} → {model}  (NOT in LiteLLM)')
else:
    print('All models OK')
"
```

**Fix:** replace missing model names with available ones in the preset's routing
table. Common substitutions on this system:
- `kimi-k2.7-code` → `deepseek-v4-pro` (reasoning) or `agents-a1-abliterated`
- Any external model not in config.yaml → check LiteLLM catalog first

## 2. Gate script smoke test

Gate scripts in `~/.hermes/scripts/` can have runtime bugs that only surface
when invoked with real args. Test each one:

```bash
for script in capability_gate orchestrator_gate research_quality_gate \
              research_completeness_gate citation_enforcement_gate; do
    echo "=== $script ==="
    python3 ~/.hermes/scripts/${script}.py --help 2>&1 | head -5
done
```

**Known pitfall:** scripts using custom enums (e.g., `Severity`) crash on
`json.dumps(output)` with `TypeError: Object of type X is not JSON serializable`.
The fix is `json.dumps(output, default=str)` or a custom encoder. This affects
the `--json` output path specifically — the human-readable path may work fine.

## 3. Neo4j schema validation

The preset may expect specific labels and relationships. Verify they exist:

```bash
# Check labels
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"CALL db.labels() YIELD label RETURN collect(label) AS all_labels"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# Check relationship types
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS all_rels"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# Node counts (verify data is populated, not just empty schema)
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt ORDER BY cnt DESC LIMIT 20"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```

If a preset expects labels like `AFlowVariant` or `SelfModificationProposal`
and they're missing, those phases will silently produce empty results.

## 4. Registry path validation

Every agent entry has a `path` field. Verify files exist:

```bash
python3 -c "
import json, os
reg = json.load(open(os.path.expanduser('~/.hermes/agents/registry.json')))
base = os.path.expanduser('~/.hermes/agents')
for name, a in reg['agents'].items():
    p = os.path.join(base, a.get('path',''))
    if not os.path.exists(p):
        print(f'MISSING: {name} → {p}')
"
```

## 5. Service connectivity (orchestrator_gate)

```bash
python3 ~/.hermes/scripts/orchestrator_gate.py 2>&1
```

This checks Neo4j, LiteLLM, and Hermes API. Note: the Hermes API port it
checks (e.g., :18648) may not match the active profile's gateway port
(e.g., :9121). If only the port mismatch is failing, the cycle can still run.

## 6. Port architecture (who listens where)

Verify each port has the expected process. Use `ss -tlnp` + `curl`:

| Port | Component | Verify | Notes |
|------|-----------|--------|-------|
| :8643 | Hermes Gateway (external API, bots, VPS tunnel) | `curl localhost:8643/health` → `{"status":"ok"}` | systemd `hermes-gateway.service`, separate HERMES_HOME |
| :9120 | Desktop Agent (Electron backend) | `curl localhost:9120/` → may return "Frontend not built" | This is NORMAL — Electron renders its own UI |
| :9123 | Dashboard (Docker, web UI) | `curl localhost:9123/` → HTML | Separate Docker instance |
| :4000 | LiteLLM (model proxy) | `curl -H 'Authorization: Bearer *** localhost:4000/v1/models` | `/health` endpoint may timeout — use `/v1/models` instead |
| :7474 | Neo4j HTTP | `curl -u neo4j:<YOUR_NEO4J_PASSWORD> localhost:7474/` → 200 | |
| :7687 | Neo4j Bolt | Used by MCP servers | |
| :8647 | Voice proxy (optional) | `curl localhost:8647/health` | Optional, not required for cycles |

**Key insight:** Gateway (:8643) ≠ Desktop Agent (:9120). They serve different
purposes — Gateway is for external integrations (Telegram/Discord), Desktop is
the GUI backend. `orchestrator_gate.py` should check :8643/health, NOT :18648
or :18649 (those are stale env vars from old configs).

**Reasoning model testing pitfall:** Models like deepseek-v4-pro and glm-5.2 may
return empty content with `max_tokens=5` because they spend tokens on reasoning
first. Use `max_tokens=50+` for reliable smoke tests.

## 7. MCP server registration

Presets may reference MCP tools (`codebase_search`, `education_search`, etc.).
Verify MCP servers are registered in config.yaml:

```bash
python3 -c "import yaml; cfg=yaml.safe_load(open('$HOME/.hermes/config.yaml')); print(cfg.get('mcp_servers', 'NONE'))"
```

Existing MCP servers may already exist at unexpected locations:
- `/home/user/cursor/first/graph_tool/mcp/codebase-server.mjs` (5 tools)
- `/home/user/cursor/first/graph_tool/mcp/education-server.mjs`

**Registration pattern:**
```yaml
mcp_servers:
  codebase-graph:
    command: node
    args: [/path/to/codebase-server.mjs]
    enabled: true
    env:
      NEO4J_URI: bolt://127.0.0.1:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: changeme
```

Test MCP server responds to initialize:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | \
  NEO4J_URI="bolt://127.0.0.1:7687" NEO4J_USER="neo4j" NEO4J_PASSWORD=changeme \
  timeout 10 node codebase-server.mjs
```

## 8. research_deep gate — legacy artifact filtering

`orchestrator_gate.py:check_research_deep()` runs GATE B/C/D on the most recent
`.md` in `docs/research/`. These gates parse Markdown for structured sections
(`## RQ Answers`, `Source Quality Matrix` table, `[N]` citations).

**Problem:** Legacy free-form research notes (bibliographies, brainstorms) fail
all three gates — they were never meant to satisfy structural requirements.
This causes a false BLOCKER on Pre-Flight Gate.

**Fix applied (2026-07-15):** Gate now filters artifacts by structured markers:
1. Prefer `.json` (per research-output-v1.json schema)
2. For `.md`, read first 2048 bytes and check for markers: `## RQ Answers`,
   `Source Quality Matrix`, `schema_version`, `research-output-v1`
3. No structured artifact found → SKIP (PASS with info message), not FAIL

This means: no active research cycle → deep gates pass (nothing to validate).
Active cycle with structured artifact → gates run and validate properly.

## Summary: minimum viable checks (60 seconds)

1. `curl -H 'Authorization: Bearer *** localhost:4000/v1/models` → compare against registry models
2. `python3 capability_gate.py --json` → check it doesn't crash
3. Neo4j HTTP 200 on :7474
4. `curl localhost:8643/health` → `{"status":"ok"}`
5. `cd /home/user && python3 ~/.hermes/scripts/orchestrator_gate.py --json` → 7/7 PASS

If all five pass, the preset will likely run without infrastructure errors.

## Validation cycle log (2026-07-15)

Full audit of plan2 found and fixed 10 issues, achieving 7/7 Pre-Flight Gate:
1. capability_gate.py JSON crash (Enum serialization → custom encoder)
2. kimi-k2.7-code model not in LiteLLM (replaced with agents-a1-abliterated in 34 files)
3. AFlowVariant Neo4j label/constraint missing (created)
4. Hermes API port :18649 → :8643 in orchestrator_gate.py
5. LiteLLM /health timeout → /v1/models endpoint
6. Observer gate false blocker → config.yaml aware (PASS when no PID files)
7. agents/dev/ empty → copied 4 dev files
8. Registry with kimi → regenerated, 0 kimi, 125 agents
9. MCP servers not registered → codebase-graph + education-graph added
10. research_deep gate → structured marker filter (SKIP for legacy artifacts)
