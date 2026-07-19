import { withSession } from "./client.js"
import { checkpointToolToNode, integrationToToolNode } from "./normalize.js"

/**
 * @param {import('neo4j-driver').Session} session
 * @param {Record<string, unknown>} tool
 * @param {{ mergeOnlyEmpty?: boolean }} [opts]
 */
async function mergeTool(session, tool, opts = {}) {
  const t = integrationToToolNode(tool)
  const evidence = Array.isArray(t.evidence) ? t.evidence.filter(Boolean) : []

  await session.run(
    `MERGE (tool:Tool {id: $id})
     ON CREATE SET
       tool.tool_dir = $tool_dir,
       tool.name = $name,
       tool.description = $description,
       tool.type = $type,
       tool.target = $target,
       tool.mcp_usage = $mcp_usage,
       tool.endpoint = $endpoint,
       tool.c_layer = $c_layer,
       tool.linux_layer = $linux_layer,
       tool.confirmations = $confirmations,
       tool.status = $status,
       tool._reserved_json = $_reserved_json,
       tool.updated_at = datetime()
     ON MATCH SET
       tool.last_seen_session = coalesce($last_seen_session, tool.last_seen_session),
       tool.confirmations = coalesce(tool.confirmations, 1) + coalesce($confirmations_delta, 0),
       tool.updated_at = datetime(),
       tool.tool_dir = CASE WHEN $mergeOnlyEmpty AND tool.tool_dir <> '' THEN tool.tool_dir ELSE coalesce($tool_dir, tool.tool_dir) END,
       tool.name = CASE WHEN $mergeOnlyEmpty AND tool.name <> '' THEN tool.name ELSE coalesce($name, tool.name) END,
       tool.description = CASE WHEN $mergeOnlyEmpty AND tool.description <> '' THEN tool.description ELSE coalesce($description, tool.description) END,
       tool.target = CASE WHEN $mergeOnlyEmpty AND tool.target <> '' THEN tool.target ELSE coalesce($target, tool.target) END,
       tool.mcp_usage = CASE WHEN $mergeOnlyEmpty AND tool.mcp_usage <> '{}' THEN tool.mcp_usage ELSE coalesce($mcp_usage, tool.mcp_usage) END
     RETURN tool`,
    {
      id: t.id,
      tool_dir: t.tool_dir || "",
      name: t.name || t.id,
      description: t.description || "",
      type: t.type,
      target: t.target || "host",
      mcp_usage: t.mcp_usage || "{}",
      endpoint: t.endpoint,
      c_layer: t.c_layer,
      linux_layer: t.linux_layer,
      confirmations: t.confirmations || 1,
      confirmations_delta: opts.mergeOnlyEmpty ? 1 : 0,
      status: t.status || "active",
      _reserved_json: JSON.stringify(t._reserved || {}),
      last_seen_session: tool.last_seen_session || null,
      mergeOnlyEmpty: Boolean(opts.mergeOnlyEmpty),
    },
  )

  for (const anchor of evidence) {
    await session.run(
      `MERGE (e:Evidence {anchor: $anchor})
       WITH e
       MATCH (tool:Tool {id: $id})
       MERGE (tool)-[:EVIDENCED_BY]->(e)`,
      { anchor: String(anchor), id: t.id },
    )
  }
}

/**
 * @param {import('./config.js').Neo4jConfig} cfg
 * @param {{ sessionID: string, agent?: string, pwd_scope?: string }} session
 */
export async function upsertSession(cfg, session) {
  await withSession(cfg, async (s) => {
    await s.run(
      `MERGE (sess:Session {id: $id})
       ON CREATE SET sess.agent = $agent, sess.started_at = datetime(), sess.pwd_scope = $pwd_scope
       ON MATCH SET sess.agent = coalesce($agent, sess.agent), sess.updated_at = datetime()`,
      {
        id: session.sessionID,
        agent: session.agent || "claw",
        pwd_scope: session.pwd_scope || "",
      },
    )
  })
}

/**
 * @param {import('./config.js').Neo4jConfig} cfg
 * @param {{ sessionID: string, checkpoint: Record<string, unknown>, plan?: Record<string, unknown> }} input
 */
export async function syncCheckpoint(cfg, input) {
  const { sessionID, checkpoint } = input
  const agent = String(checkpoint.agent || "claw")

  await upsertSession(cfg, { sessionID, agent })

  await withSession(cfg, async (session) => {
    const seq = Number(checkpoint.seq) || 1
    await session.run(
      `MATCH (sess:Session {id: $sessionID})
       MERGE (cp:Checkpoint {session_id: $sessionID, seq: $seq})
       ON CREATE SET cp.ts = $ts, cp.tokens_before = $tokens_before, cp.summary = $summary, cp.agent = $agent
       ON MATCH SET cp.ts = $ts, cp.summary = $summary
       MERGE (sess)-[:HAS_CHECKPOINT]->(cp)`,
      {
        sessionID,
        seq,
        ts: checkpoint.ts || new Date().toISOString(),
        tokens_before: Number(checkpoint.tokens_before) || 0,
        summary: String(checkpoint.summary || "").slice(0, 500),
        agent,
      },
    )

    const tools = Array.isArray(checkpoint.tools_found) ? checkpoint.tools_found : []
    for (const raw of tools) {
      const node = checkpointToolToNode(raw, sessionID)
      await mergeTool(session, { ...node, last_seen_session: sessionID }, { mergeOnlyEmpty: true })
      await session.run(
        `MATCH (sess:Session {id: $sessionID}), (cp:Checkpoint {session_id: $sessionID, seq: $seq}), (tool:Tool {id: $toolId})
         MERGE (cp)-[:FOUND]->(tool)
         MERGE (sess)-[:OBSERVED]->(tool)`,
        { sessionID, seq, toolId: node.id },
      )
      await session.run(
        `MATCH (p:CompactionPolicy {axis: 'knowledge_merge'})
         MATCH (tool:Tool {id: $toolId})
         CREATE (d:DedupeEvent {kind: 'knowledge_merge', ts: datetime()})
         MERGE (d)-[:CONFIRMED]->(tool)
         MERGE (d)-[:APPLIES_AXIS]->(p)`,
        { toolId: node.id },
      )
    }

    const prospects = Array.isArray(checkpoint.prospects) ? checkpoint.prospects : []
    for (const p of prospects) {
      if (!p?.id) continue
      await session.run(
        `MERGE (pr:Prospect {id: $id})
         ON CREATE SET pr.candidate_path = $candidate_path, pr.why = $why, pr.score = $score
         ON MATCH SET pr.score = CASE WHEN $score > pr.score THEN $score ELSE pr.score END
         WITH pr
         MATCH (cp:Checkpoint {session_id: $sessionID, seq: $seq})
         MERGE (cp)-[:SUGGESTS]->(pr)`,
        {
          id: p.id,
          candidate_path: p.candidate_path || "",
          why: p.why_could_be_tool || "",
          score: Number(p.score) || 0,
          sessionID,
          seq,
        },
      )
    }
  })
}

/**
 * @param {import('./config.js').Neo4jConfig} cfg
 * @param {{ sessionID: string, registryPath: string, registry: { records?: unknown[], discovered_at?: string } }} input
 */
export async function syncRegistry(cfg, input) {
  const { sessionID, registryPath, registry } = input
  const records = Array.isArray(registry.records) ? registry.records : []

  await upsertSession(cfg, { sessionID, agent: "claw" })

  await withSession(cfg, async (session) => {
    await session.run(
      `MATCH (sess:Session {id: $sessionID})
       MERGE (rs:RegistrySnapshot {path: $path})
       ON CREATE SET rs.discovered_at = $discovered_at, rs.record_count = $record_count
       ON MATCH SET rs.discovered_at = $discovered_at, rs.record_count = $record_count
       MERGE (sess)-[:PRODUCED]->(rs)`,
      {
        sessionID,
        path: registryPath,
        discovered_at: registry.discovered_at || new Date().toISOString(),
        record_count: records.length,
      },
    )

    for (const rec of records) {
      if (!rec || typeof rec !== "object") continue
      const node = integrationToToolNode(rec)
      await mergeTool(session, node)
      await session.run(
        `MATCH (rs:RegistrySnapshot {path: $path}), (tool:Tool {id: $id})
         MERGE (rs)-[:RECORDS]->(tool)
         WITH tool
         MATCH (sess:Session {id: $sessionID})
         MERGE (sess)-[:OBSERVED]->(tool)`,
        { path: registryPath, id: node.id, sessionID },
      )

      const deps = Array.isArray(rec.depends_on) ? rec.depends_on : []
      for (const depId of deps) {
        if (typeof depId !== "string") continue
        await session.run(
          `MATCH (t:Tool {id: $id}), (dep:Tool {id: $depId})
           MERGE (t)-[:DEPENDS_ON]->(dep)`,
          { id: node.id, depId },
        )
      }
    }
  })
}

/**
 * @param {import('./config.js').Neo4jConfig} cfg
 * @param {{ sessionID: string, actions: Record<string, unknown>[] }} input
 */
export async function syncCompactionActions(cfg, input) {
  await withSession(cfg, async (session) => {
    for (const act of input.actions) {
      if (!act?.id) continue
      const op = String(act.op || "")
      await session.run(
        `MERGE (a:CompactionAction {id: $id})
         ON CREATE SET a.op = $op, a.ts = $ts, a.session_id = $session_id,
           a.human_gate = $human_gate, a.rationale = $rationale
         ON MATCH SET a.human_gate = $human_gate
         WITH a
         MATCH (p:CompactionPolicy {axis: $axis})
         MERGE (a)-[:APPLIES_AXIS]->(p)`,
        {
          id: act.id,
          op,
          ts: act.ts || new Date().toISOString(),
          session_id: act.session_id || input.sessionID,
          human_gate: act.human_gate || "pending",
          rationale: String(act.rationale || "").slice(0, 2000),
          axis: op === "rollback" ? "merge" : op,
        },
      )

      const targets = Array.isArray(act.targets) ? act.targets : []
      for (const target of targets) {
        if (typeof target !== "string") continue
        if (target.startsWith("act_")) continue
        await session.run(
          `MATCH (a:CompactionAction {id: $actionId})
           MERGE (t:Tool {id: $toolId})
           ON CREATE SET t.name = $toolId, t.type = 'unknown', t.target = 'host',
             t.tool_dir = '', t.description = '', t.mcp_usage = '{}'
           MERGE (a)-[:TARGETS]->(t)`,
          { actionId: act.id, toolId: target },
        )
        if (op === "merge" && targets.length >= 2) {
          await session.run(
            `MATCH (t1:Tool {id: $id1}), (t2:Tool {id: $id2})
             MERGE (t1)-[:MERGED_INTO]->(t2)`,
            { id1: String(targets[0]), id2: String(targets[1]) },
          )
        }
        if (op === "mcp-dedupe" && targets.length >= 2) {
          await session.run(
            `MATCH (t1:Tool {id: $id1}), (t2:Tool {id: $id2})
             MERGE (t1)-[:DUPLICATE_OF]->(t2)`,
            { id1: String(targets[0]), id2: String(targets[1]) },
          )
        }
        if (op === "prune") {
          await session.run(`MATCH (t:Tool) WHERE t.id CONTAINS $frag SET t.status = 'pruned'`, {
            frag: target.split("/").pop() || target,
          })
        }
      }
    }
  })
}
