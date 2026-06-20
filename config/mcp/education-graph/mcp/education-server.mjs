#!/usr/bin/env node
/**
 * education-graph MCP server — dedicated to the `education` Neo4j database.
 * 
 * Tools:
 *   - education_search: BM25 + Cosine + RRF search over KnowledgeEntity nodes
 *   - education_ingest: Full pipeline — security validation → triple extraction → merge
 *
 * Register in Hermes config.yaml:
 *   mcp_servers:
 *     education-graph:
 *       command: node
 *       args: [/path/to/graph_tool/mcp/education-server.mjs]
 *       enabled: true
 *       env:
 *         NEO4J_URI: bolt://127.0.0.1:7687
 *         NEO4J_USER: neo4j
 *         NEO4J_PASSWORD: ${NEO4J_PASSWORD}
 *         NEO4J_DATABASE: education
 *         PYTHON_BIN: /home/user/jupyterlab/.venv/bin/python
 *         GRAPH_TOOL_DIR: /home/user/projects/graph_tool/python
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { getDriver, closeDriver } from "./neo4j_client.js";
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const server = new Server(
  { name: "education-graph", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "education_search",
      description:
        "Search the education knowledge graph (BM25 fulltext + cosine vector fused via RRF). " +
        "Use when: finding learned knowledge, concepts, tool relationships, previously ingested facts.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search query (natural language or keywords)" },
          limit: { type: "integer", default: 10, description: "Max results" },
          bm25_weight: {
            type: "number",
            default: 0.3,
            description: "BM25 weight in RRF fusion (0.0 = pure cosine, 1.0 = pure BM25)",
          },
        },
        required: ["query"],
      },
    },
    {
      name: "education_ingest",
      description:
        "Ingest text into the education knowledge graph. Runs full pipeline: " +
        "security validation → triple extraction → entity resolution → merge. " +
        "Use when: learning from a document, conversation, web page, or tool output.",
      inputSchema: {
        type: "object",
        properties: {
          text: {
            type: "string",
            description: "Text to ingest (document content, conversation, web page, etc.)",
          },
          source_id: {
            type: "string",
            description: "Unique source identifier (session_id, URL, file path)",
          },
          source_type: {
            type: "string",
            enum: ["session", "document", "url", "tool_output"],
            default: "document",
            description: "Type of source",
          },
        },
        required: ["text"],
      },
    },
  ],
}));

// === education_search: BM25 + Cosine + RRF ===

async function bm25SearchEntities(session, query, k = 20) {
  const q = query.includes(" ") ? query : `${query}*`;
  try {
    const result = await session.run(
      `CALL db.index.fulltext.queryNodes('entitySearch', $q)
       YIELD node, score
       RETURN node.name AS name, node.type AS type,
              node.description AS description,
              node.confidence AS confidence, score
       ORDER BY score DESC
       LIMIT $k`,
      { q, k: neo4jInt(k) },
    );
    return result.records.map((r) => ({
      name: r.get("name"),
      type: r.get("type"),
      description: r.get("description"),
      confidence: r.get("confidence"),
      bm25_score: r.get("score"),
    }));
  } catch (e) {
    return [];
  }
}

async function cosineSearchEntities(session, embedding, k = 20) {
  try {
    const result = await session.run(
      `CALL db.index.vector.queryNodes('entityEmbeddings', $k, $embedding)
       YIELD node, score
       RETURN node.name AS name, node.type AS type,
              node.description AS description,
              node.confidence AS confidence, score
       ORDER BY score DESC
       LIMIT $k`,
      { k: neo4jInt(k), embedding },
    );
    return result.records.map((r) => ({
      name: r.get("name"),
      type: r.get("type"),
      description: r.get("description"),
      confidence: r.get("confidence"),
      cosine_score: r.get("score"),
    }));
  } catch (e) {
    return [];
  }
}

function rrfFuse(bm25, cosine, topK = 10, bm25Weight = 0.3) {
  const K = 60;
  const cosineWeight = 1 - bm25Weight;
  const scores = new Map();

  for (let rank = 0; rank < bm25.length; rank++) {
    const name = bm25[rank].name;
    scores.set(name, (scores.get(name) || 0) + bm25Weight / (K + rank));
  }
  for (let rank = 0; rank < cosine.length; rank++) {
    const name = cosine[rank].name;
    scores.set(name, (scores.get(name) || 0) + cosineWeight / (K + rank));
  }

  return Array.from(scores.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, topK);
}

function neo4jInt(n) {
  return n;  // Community driver handles small integers natively
}

async function educationSearch(params) {
  const { query, limit = 10, bm25_weight = 0.3 } = params;
  const driver = getDriver();
  const database = process.env.NEO4J_DATABASE || "education";
  const session = driver.session({ database });

  try {
    const [bm25, cosine] = await Promise.all([
      bm25SearchEntities(session, query, 20),
      cosineSearchEntities(session, null, 20), // embedding not available in Node; BM25-only fallback
    ]);

    // If vector index doesn't exist, cosine will be empty → pure BM25
    const fused = rrfFuse(bm25, cosine, limit, bm25_weight);

    const bm25Map = new Map(bm25.map((r) => [r.name, r]));
    const cosineMap = new Map(cosine.map((r) => [r.name, r]));

    return fused.map(([name, rrfScore]) => ({
      name,
      type: bm25Map.get(name)?.type || cosineMap.get(name)?.type || "",
      description: bm25Map.get(name)?.description || cosineMap.get(name)?.description || "",
      confidence: bm25Map.get(name)?.confidence || cosineMap.get(name)?.confidence || 0,
      bm25_score: round(bm25Map.get(name)?.bm25_score || 0, 4),
      cosine_score: round(cosineMap.get(name)?.cosine_score || 0, 4),
      rrf_score: round(rrfScore, 4),
    }));
  } finally {
    await session.close();
  }
}

// === education_ingest: spawn Python pipeline ===

async function educationIngest(params) {
  const { text, source_id = "", source_type = "document" } = params;
  const pythonBin = process.env.PYTHON_BIN || "python3";
  const graphToolDir = process.env.GRAPH_TOOL_DIR || path.join(__dirname, "..", "python");

  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin, [
      "-c", `
import sys, json, asyncio
sys.path.insert(0, '${graphToolDir}')
import os
os.environ['NEO4J_PASSWORD'] = '${process.env.NEO4J_PASSWORD || "changeme"}'
os.environ['NEO4J_DATABASE'] = '${process.env.NEO4J_DATABASE || "education"}'
os.environ['EDUCATION_DATABASE'] = '${process.env.NEO4J_DATABASE || "education"}'

from education.education_agent import EducationAgent

async def main():
    agent = EducationAgent()
    try:
        result = await agent.ingest(
            content=sys.stdin.read(),
            source_id='${source_id.replace(/'/g, "\\'")}',
            source_type='${source_type}',
        )
        print(json.dumps(result, ensure_ascii=False))
    finally:
        agent.close()

asyncio.run(main())
      `.trim(),
    ], {
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (d) => { stdout += d.toString(); });
    child.stderr.on("data", (d) => { stderr += d.toString(); });

    child.on("close", (code) => {
      if (code === 0) {
        try {
          resolve(JSON.parse(stdout.trim()));
        } catch {
          resolve({ status: "error", stdout, stderr });
        }
      } else {
        resolve({ status: "error", exit_code: code, stderr });
      }
    });

    child.on("error", (err) => {
      reject(err);
    });

    child.stdin.write(text);
    child.stdin.end();
  });
}

// === Request handler ===

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  let result;
  try {
    if (name === "education_search") {
      result = await educationSearch(args || {});
    } else if (name === "education_ingest") {
      result = await educationIngest(args || {});
    } else {
      throw new Error(`Unknown tool: ${name}`);
    }
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    return {
      content: [{ type: "text", text: JSON.stringify({ error: err.message }, null, 2) }],
      isError: true,
    };
  }
});

// === Shutdown ===

process.on("SIGINT", async () => {
  await closeDriver();
  process.exit(0);
});
process.on("SIGTERM", async () => {
  await closeDriver();
  process.exit(0);
});

const transport = new StdioServerTransport();
await server.connect(transport);
