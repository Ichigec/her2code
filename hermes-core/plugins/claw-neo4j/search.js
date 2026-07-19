import { promises as fs } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import neo4j from "neo4j-driver"
import { loadConfig } from "./graph/config.js"
import { withSession } from "./graph/client.js"

const __DIR = path.dirname(fileURLToPath(import.meta.url))

/**
 * @param {string} name
 */
async function loadQuery(name) {
  const file = path.join(__DIR, "queries", `${name}.cypher`)
  return fs.readFile(file, "utf8")
}

/**
 * @param {Record<string, unknown>} [opts]
 * @param {{ query: string, type?: string, target?: string, min_confirmations?: number, include_pruned?: boolean, limit?: number }} params
 */
export async function searchTools(opts, params) {
  const cfg = loadConfig(opts)
  const limit = neo4j.int(Math.min(Number(params.limit) || 20, 100))
  const minConfirmations = neo4j.int(Number(params.min_confirmations) || 1)
  const q = String(params.query || "").trim()
  if (!q) return []

  return withSession(cfg, async (session) => {
    const result = await session.run(
      `CALL db.index.fulltext.queryNodes('toolSearch', $q) YIELD node, score
       WHERE ($type IS NULL OR node.type = $type)
         AND ($target IS NULL OR node.target = $target)
         AND ($include_pruned OR coalesce(node.status, 'active') <> 'pruned')
         AND coalesce(node.confirmations, 1) >= $min_confirmations
       RETURN node, score
       ORDER BY score DESC
       LIMIT $limit`,
      {
        q: q.includes(" ") ? q : `${q}*`,
        type: params.type || null,
        target: params.target || null,
        include_pruned: Boolean(params.include_pruned),
        min_confirmations: minConfirmations,
        limit,
      },
    )
    return result.records.map((r) => ({
      ...(r.get("node")?.properties || {}),
      score: r.get("score"),
    }))
  })
}

/**
 * @param {Record<string, unknown>} [opts]
 * @param {{ pattern: string, start_id: string, depth?: number, since_days?: number }} params
 */
export async function traverseGraph(opts, params) {
  const cfg = loadConfig(opts)
  const pattern = String(params.pattern || "session_tools")
  const cypher = await loadQuery(pattern)
  const depth = neo4j.int(Math.min(Number(params.depth) || 2, 5))

  return withSession(cfg, async (session) => {
    const result = await session.run(cypher, {
      start_id: params.start_id,
      depth,
      since_days: neo4j.int(Number(params.since_days) || 7),
    })
    return result.records.map((r) => r.toObject())
  })
}

/**
 * @param {Record<string, unknown>} [opts]
 * @param {string} toolId
 */
export async function getToolDetail(opts, toolId) {
  const cfg = loadConfig(opts)
  return withSession(cfg, async (session) => {
    const result = await session.run(
      `MATCH (t:Tool {id: $id})
       OPTIONAL MATCH (t)-[:EVIDENCED_BY]->(e:Evidence)
       OPTIONAL MATCH (t)-[:DUPLICATE_OF]->(dup:Tool)
       OPTIONAL MATCH (a:CompactionAction)-[:TARGETS]->(t)
       RETURN t,
         collect(DISTINCT e.anchor) AS evidence,
         collect(DISTINCT dup.id) AS duplicates,
         collect(DISTINCT {id: a.id, op: a.op, ts: a.ts, human_gate: a.human_gate}) AS actions`,
      { id: toolId },
    )
    const row = result.records[0]
    if (!row) return null
    return {
      ...(row.get("t")?.properties || {}),
      evidence: row.get("evidence"),
      duplicates: row.get("duplicates"),
      actions: row.get("actions"),
    }
  })
}
