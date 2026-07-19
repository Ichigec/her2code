# OpenCode+ Claw Compactor & Neo4j Graph

The `opencode+` ecosystem at `/home/user/cursor/first/opencode+` wraps the
upstream opencode CLI with a **claw compactor** for skill/MCP lifecycle
and a **Neo4j graph projection** for system introspection.

## Architecture

```
openCode+/
├── opencode_claw/        ← AGENTS.md runbook, schemas, .compactor/ audit trail
├── plugins/
│   ├── claw-compactor/   ← hooks opencode compaction → checkpoint + Neo4j sync
│   ├── claw-neo4j/       ← Neo4j driver, graph schema, MCP server, search CLI
│   └── step-reviewer/    ← LLM step oversight
├── configs/
│   └── opencode.litellm-dual.json  ← main config: agents, plugins, MCP, Neo4j block
└── compose.neo4j.yml     ← Neo4j 5 Community Docker
```

## Neo4j HTTP querying (when cypher-shell is absent)

```
curl -s -u neo4j:PASSWORD \
  -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (t:Tool)-[:DEPENDS_ON]->(d:Tool) RETURN t.id, d.id"}]}' \
  http://127.0.0.1:7474/db/neo4j/tx/commit
```

## Sync commands

```bash
# Init constraints + indexes
node opencode+/plugins/claw-neo4j/sync-from-compactor.js --init-only

# Full replay of all sessions + registry + log
node opencode+/plugins/claw-neo4j/sync-from-compactor.js --all

# Single discovery sync (what claw runs after writing registry)
node opencode+/plugins/claw-neo4j/sync-from-compactor.js \
  --session <sid> \
  --registry opencode+/opencode_claw/.compactor/registry/integrations.<ts>.json
```

## Search & traversal

```bash
# Fulltext search
node opencode+/plugins/claw-neo4j/search.mjs tools -q searchbox

# System tree traversals
node opencode+/plugins/claw-neo4j/search.mjs graph -s <id> --pattern system_deps -d 3
node opencode+/plugins/claw-neo4j/search.mjs graph -s x --pattern layered_view
node opencode+/plugins/claw-neo4j/search.mjs graph -s <id> --pattern tool_chains -d 2
node opencode+/plugins/claw-neo4j/search.mjs graph -s x --pattern system_roots

# Tool detail
node opencode+/plugins/claw-neo4j/search.mjs detail -i mcp.searchbox
```

## Pitfalls

### Neo4j driver: no parameterised variable-length patterns
`MATCH (t)-[:DEPENDS_ON*1..$depth]->(d)` is SYNTAX ERROR in neo4j-driver 5.x.
Use `MATCH (t)-[:DEPENDS_ON*1..5]->(d) WHERE length(path) <= $depth` instead.

### Plugin agents list controls Neo4j sync
The `claw-compactor` plugin only syncs to Neo4j for agents listed in its `agents`
config array. If claw isn't listed, its sessions won't get checkpoint→Neo4j sync.
Config: `plugin.claw-compactor.agents: ["claw", "composter"]`.

### Registry sync > checkpoint sync for relationships
Checkpoint sync (from plugin at ~100k tokens) only syncs `tools_found[]` — basic
tool nodes without `depends_on` edges. The full registry sync (`sync-from-compactor.js
--registry ...`) is the authoritative source of relationships, layers, and endpoints.
Always run a registry sync after a claw discovery cycle.

### depends_on coverage
A healthy system should have ≥80% of registry records with `depends_on`.
Check with:
```bash
python3 -c "
import json
with open('opencode+/opencode_claw/.compactor/registry/<latest>.json') as f:
    r = json.load(f)
with_deps = sum(1 for x in r['records'] if x.get('depends_on'))
print(f'{with_deps}/{len(r[\"records\"])} records have depends_on')
"
```
