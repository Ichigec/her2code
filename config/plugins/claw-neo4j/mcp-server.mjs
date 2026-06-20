#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js"
import { searchTools, traverseGraph, getToolDetail } from "./search.js"

const server = new Server(
  { name: "claw-graph", version: "1.0.0" },
  { capabilities: { tools: {} } },
)

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "search_tools",
      description: "Fulltext search over confirmed tools in the claw Neo4j graph.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string" },
          type: { type: "string" },
          target: { type: "string" },
          min_confirmations: { type: "integer", default: 1 },
          include_pruned: { type: "boolean", default: false },
          limit: { type: "integer", default: 20 },
        },
        required: ["query"],
      },
    },
    {
      name: "graph_traverse",
      description: "Named graph traversal (session_tools, tool_dependencies, duplicates, …).",
      inputSchema: {
        type: "object",
        properties: {
          pattern: {
            type: "string",
            enum: [
              "session_tools",
              "tool_dependencies",
              "duplicates",
              "discover_to_prune",
              "prospects_to_confirmed",
              "compaction_history",
            ],
          },
          start_id: { type: "string" },
          depth: { type: "integer", default: 2 },
          since_days: { type: "integer" },
        },
        required: ["pattern", "start_id"],
      },
    },
    {
      name: "tool_detail",
      description: "Full tool card including mcp_usage, evidence, compaction actions.",
      inputSchema: {
        type: "object",
        properties: { tool_id: { type: "string" } },
        required: ["tool_id"],
      },
    },
  ],
}))

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params
  let result
  if (name === "search_tools") {
    result = await searchTools({}, args || {})
  } else if (name === "graph_traverse") {
    result = await traverseGraph({}, args || {})
  } else if (name === "tool_detail") {
    result = await getToolDetail({}, args?.tool_id || "")
  } else {
    throw new Error(`Unknown tool: ${name}`)
  }
  return {
    content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
  }
})

const transport = new StdioServerTransport()
await server.connect(transport)
