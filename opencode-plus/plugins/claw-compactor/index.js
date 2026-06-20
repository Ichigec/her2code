/**
 * OpenCode plugin: claw-compactor
 *
 * Catches the `experimental.session.compacting` hook (fires when opencode
 * is about to compact a session that crossed `reserved`-tokens-from-context-end).
 * For sessions running the `claw` or `composter` agent, the plugin:
 *
 *   1. Aggregates `tool.execute.after` traces from this session leg.
 *   2. Issues a second LLM call to extract a structured payload (tools,
 *      prospects, a2a/acp endpoints, plan) per checkpoint.schema.json.
 *   3. Writes the payload to
 *      opencode+/opencode_claw/.compactor/sessions/<sid>/checkpoint.<n>.json
 *      + plan.json.
 *   4. Merges tools/prospects/a2a_acp append-only into knowledge/*.json.
 *   5. Replaces the default compaction prompt with one that tells claw/
 *      composter exactly where the checkpoint and knowledge live.
 *
 * On any error in the extraction LLM call we still write a *partial*
 * checkpoint containing the raw tool trace + a minimal summary — SOFT
 * invariant #6 from the plan. The hook never throws upward; failing to
 * checkpoint must not block opencode's own compaction.
 */

import { promises as fs } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

// Project root resolved from the plugin's own file location — does NOT
// depend on opencode passing a sensible `directory` (it doesn't: when
// opencode-web is launched from a launcher with cwd="/", the plugin
// context's `directory` is "/", not the workspace).
// Plugin lives at <projectRoot>/opencode+/plugins/claw-compactor/index.js,
// so going 3 levels up yields the project root.
const __PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..")

const DEFAULTS = {
  tokenThreshold: 100000,
  agents: ["composter"],
  dir: "opencode+/opencode_claw/.compactor",
  model: "qwen3.6-35b-heretic",
  baseURL: process.env.OPENAI_BASE_URL || "http://127.0.0.1:4000/v1",
  apiKey:
    process.env.OPENAI_API_KEY ||
    process.env.LITELLM_API_KEY ||
    process.env.OPENCODE_LLM_API_KEY ||
    "sk-local",
  maxOutputTokens: 2048,
  extractTimeoutMs: 30000,
  maxToolsInPrompt: 80,
}

function mergeConfig(opts = {}) {
  return { ...DEFAULTS, ...opts }
}

function parseModel(spec) {
  const s = String(spec || DEFAULTS.model)
  const slash = s.indexOf("/")
  return slash >= 0 ? s.slice(slash + 1) : s
}

function truncate(value, max = 400) {
  const s = value == null ? "" : String(value)
  return s.length <= max ? s : `${s.slice(0, max)}…`
}

function summarizeArgs(args) {
  if (args == null) return ""
  if (typeof args === "string") return truncate(args, 200)
  try {
    return truncate(JSON.stringify(args), 200)
  } catch {
    return truncate(String(args), 200)
  }
}

function getSession(sessions, sessionID) {
  if (!sessions.has(sessionID)) {
    sessions.set(sessionID, {
      toolsObserved: [],
      agentName: null,
    })
  }
  return sessions.get(sessionID)
}

/**
 * Resolve an absolute path under the plugin's storage directory.
 *
 * Resolution order for the base when `cfg.dir` is relative:
 *   1. Absolute `cfg.dir`              — use as-is.
 *   2. `directory` arg if non-root     — opencode's project directory when set.
 *   3. `__PROJECT_ROOT`                — derived from this file's location.
 *
 * The `directory === "/"` case is the one observed in opencode-web when
 * launched from a wrapper that inherits cwd=`/`. Falling back to
 * `__PROJECT_ROOT` avoids attempts to mkdir under POSIX root.
 */
function storagePath(directory, cfg, ...parts) {
  if (path.isAbsolute(cfg.dir)) {
    return path.join(cfg.dir, ...parts)
  }
  const base = directory && directory !== "/" && directory.length > 1 ? directory : __PROJECT_ROOT
  return path.join(base, cfg.dir, ...parts)
}

async function ensureDir(p) {
  await fs.mkdir(p, { recursive: true })
}

async function readJSON(filePath, fallback) {
  try {
    const raw = await fs.readFile(filePath, "utf8")
    return JSON.parse(raw)
  } catch (err) {
    if (err && err.code === "ENOENT") return fallback
    throw err
  }
}

async function writeJSON(filePath, data) {
  await ensureDir(path.dirname(filePath))
  await fs.writeFile(filePath, `${JSON.stringify(data, null, 2)}\n`, "utf8")
}

async function nextSeq(sessionDir) {
  try {
    const files = await fs.readdir(sessionDir)
    let max = 0
    for (const f of files) {
      const m = f.match(/^checkpoint\.(\d+)\.json$/)
      if (m) {
        const n = Number(m[1])
        if (Number.isFinite(n) && n > max) max = n
      }
    }
    return max + 1
  } catch (err) {
    if (err && err.code === "ENOENT") return 1
    throw err
  }
}

/**
 * Detect which agent a session is running by reading the latest user
 * message (`UserMessage.agent` is a string per @opencode-ai/sdk types).
 * Returns "claw", "composter", "other", or null on failure.
 */
async function detectAgent(client, sessionID) {
  try {
    const res = await client.session.messages({ path: { id: sessionID } })
    const messages = Array.isArray(res?.data) ? res.data : Array.isArray(res) ? res : []
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i]?.info
      if (m && m.role === "user" && typeof m.agent === "string" && m.agent) {
        return m.agent
      }
    }
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i]?.info
      if (m && m.role === "assistant" && typeof m.mode === "string" && m.mode) {
        return m.mode
      }
    }
    return null
  } catch (err) {
    console.error(`[claw-compactor] detectAgent failed: ${err?.message || err}`)
    return null
  }
}

function formatToolTrace(traces, limit) {
  const sliced = traces.slice(-limit)
  return sliced
    .map((t, i) => {
      const args = summarizeArgs(t.args)
      const out = truncate(t.output, 240)
      return `${i + 1}. ${t.tool}(${args}) => ${out}`
    })
    .join("\n")
}

function buildExtractionPrompt(agent, sessionID, traces, cfg) {
  return [
    "You are an extractor. Given a trace of tool calls from one opencode agent session,",
    "produce a STRICT JSON object describing what was discovered. No prose, no markdown,",
    "no code fences — only a single JSON object.",
    "",
    `Agent: ${agent}`,
    `Session: ${sessionID}`,
    "",
    "Categorise findings into:",
    "  - tools_found[]    confirmed tools (mcp/lsp/script/compose-service/skill/agent/adapter/llm-model)",
    "  - prospects[]      could-be-tools with score in [0,1]",
    "  - a2a_acp[]        A2A / ACP / MCP endpoints",
    "",
    "HARD rules:",
    "  - Every tools_found[] entry MUST have evidence:[ 'path:line', ... ] (≥1 anchor).",
    "  - Every prospects[] entry MUST have candidate_path:'path:line' and score in [0,1].",
    "  - Use only what is supported by the trace below — do NOT invent files.",
    "  - Tool id pattern: ^[a-z][a-z0-9._-]+$ (e.g. mcp.searchbox).",
    "  - Prospect id pattern: ^candidate\\.[a-z0-9_.-]+$",
    "",
    "Return EXACTLY this shape (omit empty arrays as []):",
    "{",
    '  "tools_found": [{"id":"...","kind":"mcp|lsp|script|compose-service|skill|agent|adapter|llm-model","source":"path:line","evidence":["path:line"]}],',
    '  "prospects":   [{"id":"candidate....","candidate_path":"path:line","why_could_be_tool":"...","score":0.6}],',
    '  "a2a_acp":     [{"id":"a2a.foo|acp.bar|mcp.baz","transport":"a2a|acp|mcp","endpoint":"...","capabilities":["..."]}],',
    '  "summary":     "≤500 chars human one-liner",',
    '  "plan":        {"current_step":1..6,"next_actions":["..."],"blockers":["..."],"assumptions":["..."]}',
    "}",
    "",
    "Tool trace (most recent last):",
    formatToolTrace(traces, cfg.maxToolsInPrompt),
  ].join("\n")
}

function parseJSONPayload(text) {
  if (!text) return null
  const trimmed = String(text).trim()
  const first = trimmed.indexOf("{")
  const last = trimmed.lastIndexOf("}")
  if (first < 0 || last <= first) return null
  const candidate = trimmed.slice(first, last + 1)
  try {
    return JSON.parse(candidate)
  } catch {
    return null
  }
}

async function extractStructured(cfg, agent, sessionID, state) {
  const prompt = buildExtractionPrompt(agent, sessionID, state.toolsObserved, cfg)
  const url = `${String(cfg.baseURL).replace(/\/$/, "")}/chat/completions`

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), cfg.extractTimeoutMs)

  try {
    const res = await fetch(url, {
      method: "POST",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${cfg.apiKey}`,
      },
      body: JSON.stringify({
        model: parseModel(cfg.model),
        max_tokens: cfg.maxOutputTokens,
        temperature: 0.1,
        response_format: { type: "json_object" },
        messages: [
          {
            role: "system",
            content:
              "You extract structured facts from agent tool traces. Output exactly one JSON object. Never invent paths.",
          },
          { role: "user", content: prompt },
        ],
      }),
    })

    if (!res.ok) {
      const err = await res.text()
      console.error(
        `[claw-compactor] extractor LLM failed (${res.status}): ${truncate(err, 300)}`,
      )
      return null
    }

    const data = await res.json()
    const text = data?.choices?.[0]?.message?.content
    return parseJSONPayload(text)
  } catch (err) {
    console.error(
      `[claw-compactor] extractor LLM error: ${err?.message || err}`,
    )
    return null
  } finally {
    clearTimeout(timer)
  }
}

function dedupeStrings(arr) {
  return Array.from(new Set((arr || []).filter((x) => typeof x === "string" && x.length > 0)))
}

function normalizeTool(t) {
  if (!t || typeof t !== "object") return null
  if (typeof t.id !== "string" || !/^[a-z][a-z0-9._-]+$/.test(t.id)) return null
  if (typeof t.source !== "string") return null
  const evidence = dedupeStrings(t.evidence)
  if (evidence.length === 0) return null
  return {
    id: t.id,
    kind: typeof t.kind === "string" ? t.kind : "mcp",
    source: t.source,
    evidence,
  }
}

function normalizeProspect(p) {
  if (!p || typeof p !== "object") return null
  if (typeof p.id !== "string" || !/^candidate\.[a-z0-9_.-]+$/.test(p.id)) return null
  if (typeof p.candidate_path !== "string") return null
  const score = Math.max(0, Math.min(1, Number(p.score)))
  if (!Number.isFinite(score)) return null
  return {
    id: p.id,
    candidate_path: p.candidate_path,
    why_could_be_tool: String(p.why_could_be_tool || "").slice(0, 500) || "unspecified",
    score,
  }
}

function normalizeA2A(a) {
  if (!a || typeof a !== "object") return null
  if (typeof a.id !== "string" || !/^(a2a|acp|mcp)\.[a-z0-9_.-]+$/.test(a.id)) return null
  if (typeof a.endpoint !== "string") return null
  const transport = typeof a.transport === "string" && /^(a2a|acp|mcp)$/.test(a.transport)
    ? a.transport
    : a.id.split(".")[0]
  return {
    id: a.id,
    transport,
    endpoint: a.endpoint,
    capabilities: Array.isArray(a.capabilities) ? dedupeStrings(a.capabilities) : [],
    ...(typeof a.agent_card_url === "string" ? { agent_card_url: a.agent_card_url } : {}),
  }
}

function normalizePayload(raw) {
  const payload = raw && typeof raw === "object" ? raw : {}
  return {
    tools_found: Array.isArray(payload.tools_found)
      ? payload.tools_found.map(normalizeTool).filter(Boolean)
      : [],
    prospects: Array.isArray(payload.prospects)
      ? payload.prospects.map(normalizeProspect).filter(Boolean)
      : [],
    a2a_acp: Array.isArray(payload.a2a_acp)
      ? payload.a2a_acp.map(normalizeA2A).filter(Boolean)
      : [],
    summary:
      typeof payload.summary === "string"
        ? payload.summary.slice(0, 500)
        : "partial checkpoint (extractor unavailable)",
    plan: payload.plan && typeof payload.plan === "object" ? payload.plan : {},
  }
}

function buildPartialPayload(traces) {
  const tools = []
  const seen = new Set()
  for (const t of traces.slice(-DEFAULTS.maxToolsInPrompt)) {
    if (!t || typeof t.tool !== "string") continue
    const id = `tool.${t.tool.replace(/[^a-z0-9._-]/gi, "_").toLowerCase()}`
    if (seen.has(id)) continue
    seen.add(id)
    tools.push({
      id,
      kind: "mcp",
      source: `runtime:0`,
      evidence: [`runtime:0`],
    })
  }
  return {
    tools_found: [],
    prospects: [],
    a2a_acp: [],
    summary: `Partial checkpoint: ${traces.length} tool calls observed; extractor LLM unavailable.`,
    plan: {
      current_step: 1,
      next_actions: ["Re-run discovery on resume (extractor was unavailable)."],
      blockers: ["Structured extraction failed during compaction."],
      assumptions: [],
    },
  }
}

async function writeCheckpoint(filePath, body) {
  await writeJSON(filePath, body)
}

async function writePlan(filePath, body) {
  await writeJSON(filePath, body)
}

/**
 * Append-only merge of new records into a knowledge file. Files have
 * shape { records: [...] }. Dedup by `id`:
 *   - new id  → push record (set first_seen_session, last_seen_session, confirmations=1).
 *   - existing → update last_seen_session, ++confirmations, union evidence/capabilities/sessions_observed.
 * Returns the new record count.
 */
async function mergeAppend(filePath, kind, incoming, sessionID) {
  if (!Array.isArray(incoming) || incoming.length === 0) return 0
  const current = await readJSON(filePath, { records: [] })
  if (!current.records || !Array.isArray(current.records)) current.records = []
  const byId = new Map(current.records.map((r) => [r.id, r]))
  for (const item of incoming) {
    if (!item || typeof item.id !== "string") continue
    const existing = byId.get(item.id)
    if (existing) {
      existing.last_seen_session = sessionID
      existing.confirmations = (existing.confirmations || 1) + 1
      if (kind === "tool-catalog") {
        existing.evidence = dedupeStrings([...(existing.evidence || []), ...(item.evidence || [])])
        for (const field of [
          "tool_dir",
          "name",
          "description",
          "target",
          "mcp_usage",
          "endpoint",
          "c_layer",
          "linux_layer",
        ]) {
          if (item[field] && (!existing[field] || existing[field] === "")) {
            existing[field] = item[field]
          }
        }
      } else if (kind === "prospect-index") {
        existing.sessions_observed = dedupeStrings([
          ...(existing.sessions_observed || []),
          sessionID,
        ])
        existing.score = Math.max(Number(existing.score) || 0, Number(item.score) || 0)
      } else if (kind === "a2a-acp-index") {
        existing.capabilities = dedupeStrings([
          ...(existing.capabilities || []),
          ...(item.capabilities || []),
        ])
      }
    } else {
      let record
      if (kind === "tool-catalog") {
        record = {
          id: item.id,
          kind: item.kind,
          first_seen_session: sessionID,
          last_seen_session: sessionID,
          evidence: dedupeStrings(item.evidence),
          confirmations: 1,
          ...(item.tool_dir ? { tool_dir: item.tool_dir } : {}),
          ...(item.name ? { name: item.name } : {}),
          ...(item.description ? { description: item.description } : {}),
          ...(item.target ? { target: item.target } : {}),
          ...(item.mcp_usage ? { mcp_usage: item.mcp_usage } : {}),
          ...(item.endpoint ? { endpoint: item.endpoint } : {}),
          ...(item.c_layer ? { c_layer: item.c_layer } : {}),
          ...(item.linux_layer ? { linux_layer: item.linux_layer } : {}),
        }
      } else if (kind === "prospect-index") {
        record = {
          id: item.id,
          candidate_path: item.candidate_path,
          why_could_be_tool: item.why_could_be_tool,
          score: Number(item.score) || 0,
          sessions_observed: [sessionID],
        }
      } else if (kind === "a2a-acp-index") {
        record = {
          id: item.id,
          transport: item.transport,
          endpoint: item.endpoint,
          ...(item.agent_card_url ? { agent_card_url: item.agent_card_url } : {}),
          capabilities: Array.isArray(item.capabilities) ? dedupeStrings(item.capabilities) : [],
          first_seen_session: sessionID,
          last_seen_session: sessionID,
        }
      } else {
        continue
      }
      current.records.push(record)
      byId.set(record.id, record)
    }
  }
  await writeJSON(filePath, current)
  return current.records.length
}

/**
 * Build the absolute pointer lines that the plugin appends to opencode's
 * default compaction prompt via `output.context`. They MUST be absolute
 * paths — the agent's cwd may be "/" when scanning the whole host (the
 * "global" project in opencode), not the project root.
 */
function buildContextPointers(checkpointPath, planPath, knowledgeDir, payload) {
  const lines = [
    `Checkpoint just saved by claw-compactor plugin: ${checkpointPath}`,
    `Continuation plan: ${planPath}`,
    `Cross-session knowledge base (append-only, plugin-owned): ${knowledgeDir}/{tool-catalog,prospect-index,a2a-acp-index}.json`,
  ]
  if (payload && typeof payload.summary === "string" && payload.summary.length > 0) {
    lines.push(`Checkpoint summary: ${payload.summary}`)
  }
  return lines
}

export default {
  id: "claw-compactor",
  server: async (ctx, opts) => {
    const { directory, client } = ctx
    const cfg = mergeConfig(opts)
    /** @type {Map<string, ReturnType<typeof getSession>>} */
    const sessions = new Map()

    console.log(
      `[claw-compactor] loaded threshold=${cfg.tokenThreshold} agents=${cfg.agents.join(",")} dir=${cfg.dir} model=${parseModel(cfg.model)} projectRoot=${__PROJECT_ROOT}`,
    )

    return {
      "tool.execute.after": async (input, output) => {
        const st = getSession(sessions, input.sessionID)
        st.toolsObserved.push({
          tool: input.tool,
          args: input.args,
          output: output.output,
        })
      },

      "experimental.session.compacting": async (input, output) => {
        const sessionID = input.sessionID
        const agent = await detectAgent(client, sessionID)
        if (!agent || !cfg.agents.includes(agent)) {
          console.log(
            `[claw-compactor] skipping session=${sessionID} agent=${agent ?? "unknown"} (not in ${cfg.agents.join(",")})`,
          )
          return
        }

        const state = getSession(sessions, sessionID)
        state.agentName = agent

        let raw = null
        if (state.toolsObserved.length > 0) {
          raw = await extractStructured(cfg, agent, sessionID, state)
        }
        const payload = raw
          ? normalizePayload(raw)
          : buildPartialPayload(state.toolsObserved)

        const sessionDir = storagePath(directory, cfg, "sessions", sessionID)
        const knowledgeDir = storagePath(directory, cfg, "knowledge")
        let seq
        let ts
        try {
          await ensureDir(sessionDir)
          await ensureDir(knowledgeDir)
          seq = await nextSeq(sessionDir)
          ts = new Date().toISOString()
        } catch (err) {
          console.error(
            `[claw-compactor] dirs failed for ${sessionID}: ${err?.message || err}`,
          )
          // Do not throw — opencode's compaction must still complete with
          // its default summary. Plugin is a best-effort enrichment.
          state.toolsObserved = []
          return
        }

        const checkpoint = {
          session_id: sessionID,
          seq,
          ts,
          tokens_before: cfg.tokenThreshold,
          agent,
          tools_found: payload.tools_found,
          prospects: payload.prospects,
          a2a_acp: payload.a2a_acp,
          plan_ref: `sessions/${sessionID}/plan.json`,
          summary: payload.summary,
        }
        await writeCheckpoint(path.join(sessionDir, `checkpoint.${seq}.json`), checkpoint)

        const plan = {
          session_id: sessionID,
          current_step:
            Number.isInteger(payload.plan?.current_step) &&
            payload.plan.current_step >= 1 &&
            payload.plan.current_step <= 6
              ? payload.plan.current_step
              : 1,
          next_actions:
            Array.isArray(payload.plan?.next_actions) && payload.plan.next_actions.length > 0
              ? payload.plan.next_actions.map(String).filter((s) => s.length > 0)
              : ["Re-read AGENTS.md and decide the next action."],
          blockers: Array.isArray(payload.plan?.blockers)
            ? payload.plan.blockers.map(String).filter((s) => s.length > 0)
            : [],
          assumptions: Array.isArray(payload.plan?.assumptions)
            ? payload.plan.assumptions.map(String).filter((s) => s.length > 0)
            : [],
          checkpoint_ref: `sessions/${sessionID}/checkpoint.${seq}.json`,
        }
        await writePlan(path.join(sessionDir, "plan.json"), plan)

        try {
          await mergeAppend(
            path.join(knowledgeDir, "tool-catalog.json"),
            "tool-catalog",
            payload.tools_found,
            sessionID,
          )
          await mergeAppend(
            path.join(knowledgeDir, "prospect-index.json"),
            "prospect-index",
            payload.prospects,
            sessionID,
          )
          await mergeAppend(
            path.join(knowledgeDir, "a2a-acp-index.json"),
            "a2a-acp-index",
            payload.a2a_acp,
            sessionID,
          )
        } catch (err) {
          console.error(
            `[claw-compactor] knowledge merge failed: ${err?.message || err}`,
          )
        }

        try {
          const neo4jOpts = cfg.neo4j && typeof cfg.neo4j === "object" ? cfg.neo4j : {}
          const { createNeo4jSync } = await import("../claw-neo4j/index.js")
          const neo4j = createNeo4jSync(neo4jOpts)
          await neo4j.init()
          await neo4j.syncCheckpoint({ sessionID, checkpoint })
          await neo4j.close()
        } catch (err) {
          console.log(`[claw-neo4j] checkpoint sync skipped: ${err?.message || err}`)
        }

        // Append absolute pointers to opencode's default compaction prompt
        // via `output.context`. Do NOT set `output.prompt` — overriding the
        // summarisation prompt with an impersonation ("You are resuming the
        // claw agent…") caused the summariser to emit agent-like text
        // instead of a true session summary, leaving the UI empty after
        // compaction.
        const checkpointPath = path.join(sessionDir, `checkpoint.${seq}.json`)
        const planPath = path.join(sessionDir, "plan.json")
        for (const line of buildContextPointers(checkpointPath, planPath, knowledgeDir, payload)) {
          output.context.push(line)
        }

        state.toolsObserved = []

        console.log(
          `[claw-compactor] checkpoint seq=${seq} session=${sessionID} agent=${agent} tools=${checkpoint.tools_found.length} prospects=${checkpoint.prospects.length} a2a=${checkpoint.a2a_acp.length}`,
        )
      },

      event: async ({ event }) => {
        if (!event || event.type !== "session.compacted") return
        const sessionID = event.properties?.sessionID || event.properties?.info?.id
        const state = sessionID ? sessions.get(sessionID) : null
        const agent = state?.agentName
        if (!agent) return
        console.log(
          `[claw-compactor] session.compacted session=${sessionID} agent=${agent}`,
        )
      },
    }
  },
}
