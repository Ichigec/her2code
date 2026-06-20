#!/usr/bin/env node
/**
 * graph-tool MCP server — extends claw-graph with:
 *   - hybrid_search: BM25 + Cosine + RRF + graph enrichment
 *   - graph_traverse: multi-hop dependency/co-occurrence traversal
 *   - embed_tool: generate embedding for a tool (calls SentenceTransformer)
 *
 * Register in Hermes config.yaml:
 *   mcp_servers:
 *     graph-tool:
 *       command: node
 *       args: [/path/to/graph_tool/mcp/mcp-server.mjs]
 *       enabled: true
 *       env:
 *         NEO4J_URI: bolt://127.0.0.1:7687
 *         NEO4J_USER: neo4j
 *         NEO4J_PASSWORD: ${NEO4J_PASSWORD}
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { hybridSearch, graphTraverse } from "./search.js";
import { closeDriver } from "./neo4j_client.js";

const server = new Server(
  { name: "graph-tool", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "hybrid_search",
      description:
        "Hybrid search over Neo4j tool catalog: BM25 fulltext + cosine similarity (vector) " +
        "fused via Reciprocal Rank Fusion, enriched with graph context (dependencies, co-occurrences). " +
        "Use when: finding relevant tools for a task, discovering tool capabilities.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Natural language query" },
          embedding: {
            type: "array",
            items: { type: "number" },
            description: "384-dim query embedding (optional, enables cosine search)",
          },
          limit: { type: "integer", default: 20, description: "Max results" },
          bm25_weight: {
            type: "number",
            default: 0.3,
            description: "BM25 weight in RRF (0.0-1.0, cosine = 1-bm25_weight)",
          },
          use_graph_enrichment: {
            type: "boolean",
            default: true,
            description: "Enrich results with graph neighbors",
          },
        },
        required: ["query"],
      },
    },
    {
      name: "graph_traverse",
      description:
        "Multi-hop graph traversal from a tool or code entity: follow DEPENDS_ON, CO_OCCURS_WITH, DUPLICATE_OF edges " +
        "(claw graph), or IMPORTS, CALLS, CONTAINS, INHERITS (codebase graph). " +
        "Pattern 'related' now also includes CODED_IN (Tool → CodeFile cross-graph). " +
        "Use when: understanding tool ecosystem, finding alternatives, debugging tool chains, exploring code dependencies.",
      inputSchema: {
        type: "object",
        properties: {
          start_id: {
            type: "string",
            description: "Tool ID to start traversal from",
          },
          pattern: {
            type: "string",
            enum: ["related", "dependencies", "co_occurring", "code_imports", "code_calls", "code_all"],
            default: "related",
            description: "Traversal pattern: all relations, only dependencies, or only co-occurrences",
          },
          depth: {
            type: "integer",
            default: 2,
            minimum: 1,
            maximum: 5,
            description: "Hop depth",
          },
        },
        required: ["start_id"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  let result;
  try {
    if (name === "hybrid_search") {
      result = await hybridSearch(args || {});
    } else if (name === "graph_traverse") {
      result = await graphTraverse(args || {});
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
