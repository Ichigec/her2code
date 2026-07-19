# claw-neo4j

Neo4j projection for the `claw` compactor. JSON under `opencode+/opencode_claw/.compactor/` remains the audit trail; Neo4j enables graph search and tool catalog queries.

## Setup

```bash
# From repo root
docker compose --env-file .env -f compose.neo4j.yml up -d
cd opencode+/plugins/claw-neo4j && npm install
node sync-from-compactor.js --init-only
```

Set `NEO4J_PASSWORD` in `.env` to match `compose.neo4j.yml`.

## Sync

| Trigger | Command |
|---------|---------|
| End of discover cycle | `node sync-from-compactor.js --session <sid> --registry <path>` |
| Checkpoint (~100k tokens) | automatic via `claw-compactor` plugin |
| Full replay | `node sync-from-compactor.js --all` |

## Search

```bash
node search.mjs tools -q searchbox
node search.mjs graph -s <session_id> --pattern session_tools
node search.mjs detail -i mcp.searchbox
```

## MCP

```json
"claw-graph": {
  "command": "node",
  "args": ["/path/to/opencode+/plugins/claw-neo4j/mcp-server.mjs"]
}
```

Tools: `search_tools`, `graph_traverse`, `tool_detail`.
