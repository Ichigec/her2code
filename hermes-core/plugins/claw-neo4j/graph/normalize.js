import path from "node:path"

const TARGET_BY_TYPE = {
  mcp: "agents",
  lsp: "filesystem",
  script: "host",
  "compose-service": "host",
  skill: "agents",
  agent: "agents",
  adapter: "agents",
  "llm-model": "llm",
  env: "host",
  doc: "filesystem",
}

const EMPTY_RESERVED = {
  version: null,
  owner: null,
  tags: [],
  cost_tier: null,
  health_status: null,
  last_probe_at: null,
}

/**
 * @param {string} source
 */
function toolDirFromSource(source) {
  if (!source || typeof source !== "string") return ""
  const noLine = source.split(":")[0]
  if (noLine.includes("/")) return path.dirname(noLine)
  return noLine
}

/**
 * @param {Record<string, unknown>} record integration-record or catalog row
 * @returns {Record<string, unknown>}
 */
export function integrationToToolNode(record) {
  const id = String(record.id || "")
  const type = String(record.type || record.kind || "mcp")
  const source = String(record.source || (Array.isArray(record.evidence) ? record.evidence[0] : "") || "")
  const tools = Array.isArray(record.tools) ? record.tools : []
  const mcpUsage = JSON.stringify(
    tools.length > 0
      ? { tools }
      : { note: "No MCP tools/list captured at discovery time" },
    null,
    0,
  )
  const name =
    tools.length > 0 && tools[0]?.name
      ? String(tools[0].name)
      : id.split(".").slice(-1).join(".") || id

  return {
    id,
    tool_dir: toolDirFromSource(source),
    name,
    description: String(record.description || record.skill_id || `${type} integration ${id}`),
    type,
    target: String(record.target || TARGET_BY_TYPE[type] || "host"),
    mcp_usage: typeof record.mcp_usage === "string" ? record.mcp_usage : mcpUsage,
    endpoint: record.endpoint ? String(record.endpoint) : null,
    c_layer: record.c_layer ? String(record.c_layer) : null,
    linux_layer: record.linux_layer ? String(record.linux_layer) : null,
    confirmations: Number(record.confirmations) || 1,
    status: record.status === "pruned" ? "pruned" : "active",
    evidence: Array.isArray(record.evidence) ? record.evidence : source ? [source] : [],
    _reserved: record._reserved && typeof record._reserved === "object" ? record._reserved : { ...EMPTY_RESERVED },
  }
}

/**
 * @param {Record<string, unknown>} t tools_found[] item
 * @param {string} sessionID
 */
export function checkpointToolToNode(t, sessionID) {
  const source = String(t.source || (Array.isArray(t.evidence) ? t.evidence[0] : ""))
  const kind = String(t.kind || "mcp")
  return integrationToToolNode({
    id: t.id,
    type: kind,
    source,
    evidence: t.evidence,
    confirmations: 1,
    description: `Confirmed in session ${sessionID}`,
  })
}
