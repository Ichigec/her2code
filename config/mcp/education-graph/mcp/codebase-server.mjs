#!/usr/bin/env node
/**
 * codebase-server.mjs — MCP server for codebase graph search and analysis.
 *
 * Tools:
 *   - codebase_search          : Hybrid search (BM25 + Cosine + RRF) over code entities
 *   - codebase_traverse        : Multi-hop traversal of code graph
 *   - codebase_impact_analysis : Reverse traversal: who depends on this entity?
 *   - codebase_entry_points    : List all entry points (__main__, shebang, CLI)
 *   - codebase_stats           : Aggregate graph statistics
 *
 * Neo4j labels: CodeFile, CodeFunction, CodeClass, CodeImport, CodeEntryPoint,
 *               CodePackage, CodeModule, CodeTypeAnnotation, CodeDataFlow
 * Relations:    CONTAINS, IMPORTS, CALLS, INHERITS, PART_OF, HAS_TYPE, FLOWS_TO, CODED_IN
 *
 * Register in Hermes config.yaml:
 *   mcp_servers:
 *     codebase-graph:
 *       command: node
 *       args: [/path/to/graph_tool/mcp/codebase-server.mjs]
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
import { getDriver, closeDriver } from "./neo4j_client.js";
import { rrfFuse, reciprocalRankFusion } from "./rrf.js";

// ============================================================================
// Neo4j helpers
// ============================================================================

/**
 * Get a session for the given database.
 */
function getSession(opts = {}) {
  const driver = getDriver(opts);
  const database = opts.database || process.env.NEO4J_DATABASE || "neo4j";
  return driver.session({ database });
}

/**
 * Safely convert Neo4j integer types to JS numbers.
 */
function neo4jToNumber(val) {
  if (val === null || val === undefined) return 0;
  if (typeof val === "number") return val;
  if (typeof val.toNumber === "function") return val.toNumber();
  return Number(val);
}

// ============================================================================
// MCP Server
// ============================================================================

const server = new Server(
  { name: "codebase-graph", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

// ============================================================================
// Tool: codebase_search (BM25 + Cosine + RRF hybrid search)
// ============================================================================

/**
 * BM25 fulltext search over CodeFile, CodeFunction, CodeClass.
 */
async function bm25CodeSearch(session, query, k = 50) {
  try {
    const q = query.includes(" ") ? query : `${query}*`;
    const result = await session.run(
      `CALL db.index.fulltext.queryNodes('codeSearch', $q)
       YIELD node, score
       WHERE coalesce(node.status, 'active') <> 'deleted'
       RETURN node.name AS name,
              coalesce(node.signature, node.path, '') AS signature,
              labels(node) AS labels,
              node.path AS path,
              node.start_line AS start_line,
              node.end_line AS end_line,
              score
       ORDER BY score DESC
       LIMIT $k`,
      { q, k: k },
    );
    return result.records.map((r) => ({
      id: r.get("name") + (r.get("signature") ? "|" + r.get("signature") : ""),
      name: r.get("name"),
      signature: r.get("signature"),
      type: (r.get("labels") || [])[0] || "Unknown",
      path: r.get("path") || "",
      start_line: neo4jToNumber(r.get("start_line")),
      end_line: neo4jToNumber(r.get("end_line")),
      bm25_score: r.get("score"),
    }));
  } catch {
    return [];
  }
}

/**
 * Cosine similarity search via vector index (codeEmbeddings).
 */
async function cosineCodeSearch(session, embedding, k = 50) {
  try {
    const result = await session.run(
      `CALL db.index.vector.queryNodes('codeEmbeddings', $k, $embedding)
       YIELD node, score
       WHERE coalesce(node.status, 'active') <> 'deleted'
       RETURN node.name AS name,
              coalesce(node.signature, node.path, '') AS signature,
              labels(node) AS labels,
              node.path AS path,
              node.start_line AS start_line,
              node.end_line AS end_line,
              score
       ORDER BY score DESC
       LIMIT $k`,
      { k: k, embedding },
    );
    return result.records.map((r) => ({
      id: r.get("name") + (r.get("signature") ? "|" + r.get("signature") : ""),
      name: r.get("name"),
      signature: r.get("signature"),
      type: (r.get("labels") || [])[0] || "Unknown",
      path: r.get("path") || "",
      start_line: neo4jToNumber(r.get("start_line")),
      end_line: neo4jToNumber(r.get("end_line")),
      cosine_score: r.get("score"),
    }));
  } catch {
    return [];
  }
}

async function codebaseSearch(params) {
  const {
    query,
    embedding = null,
    limit = 20,
    bm25_weight = 0.3,
    mode = "hybrid",
  } = params;

  if (!query) {
    return { error: "query is required", results: [] };
  }

  const session = getSession(params);

  try {
    // Stage 1: BM25 + Cosine (in parallel)
    const [bm25Results, cosineResults] = await Promise.all([
      bm25CodeSearch(session, query, 50),
      embedding && mode !== "keyword"
        ? cosineCodeSearch(session, embedding, 50)
        : Promise.resolve([]),
    ]);

    // Stage 2: RRF fusion
    let fused;
    if (mode === "keyword" || cosineResults.length === 0) {
      // Pure BM25 (no cosine results)
      fused = bm25Results.slice(0, limit).map((r, rank) => [r.id, 1.0 / (60 + rank)]);
    } else if (mode === "semantic") {
      // Pure cosine
      fused = cosineResults.slice(0, limit).map((r, rank) => [r.id, 1.0 / (60 + rank)]);
    } else {
      // Hybrid: RRF fusion
      fused = reciprocalRankFusion(bm25Results, cosineResults, limit, bm25_weight);
    }

    const bm25Map = new Map(bm25Results.map((r) => [r.id, r]));
    const cosineMap = new Map(cosineResults.map((r) => [r.id, r]));

    const results = fused.map(([id, rrfScore]) => {
      const bm25 = bm25Map.get(id);
      const cosine = cosineMap.get(id);
      return {
        id,
        name: bm25?.name || cosine?.name || id,
        type: bm25?.type || cosine?.type || "",
        path: bm25?.path || cosine?.path || "",
        start_line: bm25?.start_line || cosine?.start_line || 0,
        end_line: bm25?.end_line || cosine?.end_line || 0,
        signature: bm25?.signature || cosine?.signature || "",
        bm25_score: bm25?.bm25_score || 0,
        cosine_score: cosine?.cosine_score || 0,
        rrf_score: rrfScore,
      };
    });

    return { results, total: results.length, mode };
  } catch (err) {
    return { error: err.message, results: [] };
  } finally {
    await session.close();
  }
}

// ============================================================================
// Tool: codebase_traverse (multi-hop graph traversal)
// ============================================================================

async function codebaseTraverse(params) {
  const {
    path: filePath,
    depth = 2,
    direction = "both",
    max_level = 3,
  } = params;

  if (!filePath) {
    return { error: "path is required", nodes: [], edges: [] };
  }

  const d = Math.min(Math.max(1, depth), 5);
  const session = getSession(params);

  try {
    const dirArrow =
      direction === "downstream" ? "->" :
      direction === "upstream" ? "<-" : "-";

    const cypher = `
      MATCH (f:CodeFile {path: $path})
      OPTIONAL MATCH (f)-[:CONTAINS]->(child)
      WHERE coalesce(child.level, 1) <= $max_level
      OPTIONAL MATCH path_traverse = (f)${dirArrow}[:IMPORTS|CALLS|CONTAINS|INHERITS*1..${d}]-(related)
      WHERE coalesce(related.level, 1) <= $max_level
      RETURN f AS root,
             collect(DISTINCT child) AS children,
             collect(DISTINCT related) AS related_nodes,
             collect(DISTINCT {from: startNode(last(relationships(path_traverse))).path,
                               to: endNode(last(relationships(path_traverse))).path,
                               type: type(last(relationships(path_traverse)))}) AS edges
    `;

    const result = await session.run(cypher, {
      path: filePath,
      max_level: max_level,
    });

    if (result.records.length === 0) {
      return { root: null, nodes: [], edges: [], message: "File not found" };
    }

    const record = result.records[0];
    const rootNode = record.get("root");
    const children = record.get("children") || [];
    const relatedNodes = record.get("related_nodes") || [];
    const edges = record.get("edges") || [];

    const allNodes = new Map();

    // Add root
    if (rootNode) {
      allNodes.set(rootNode.properties.path, {
        ...rootNode.properties,
        labels: rootNode.labels,
      });
    }

    // Add children and related
    for (const node of [...children, ...relatedNodes]) {
      if (node && node.properties) {
        allNodes.set(node.properties.path || node.properties.signature || node.properties.name, {
          ...node.properties,
          labels: node.labels,
        });
      }
    }

    return {
      root: rootNode?.properties || null,
      nodes: Array.from(allNodes.values()),
      edges: edges.filter((e) => e && e.from && e.to),
      total_nodes: allNodes.size,
      depth: d,
      direction,
    };
  } catch (err) {
    return { error: err.message, nodes: [], edges: [] };
  } finally {
    await session.close();
  }
}

// ============================================================================
// Tool: codebase_impact_analysis (reverse traversal)
// ============================================================================

async function codebaseImpactAnalysis(params) {
  const { entity, depth = 3 } = params;

  if (!entity) {
    return { error: "entity is required", impacted: [] };
  }

  const d = Math.min(Math.max(1, depth), 5);
  const session = getSession(params);

  try {
    // Find the entity first, then traverse reverse edges to find what depends on it
    const cypher = `
      MATCH (target)
      WHERE (target:CodeFunction OR target:CodeClass OR target:CodeFile)
        AND (target.signature = $entity OR target.name = $entity OR target.path = $entity)
      WITH target
      LIMIT 1
      OPTIONAL MATCH (caller)-[:CALLS*1..${d}]->(target)
      WHERE caller:CodeFunction
      OPTIONAL MATCH (importer)-[:IMPORTS*1..${d}]->(target)
      WHERE importer:CodeFile
      OPTIONAL MATCH (inheritor)-[:INHERITS*1..${d}]->(target)
      WHERE inheritor:CodeClass
      OPTIONAL MATCH (parent)-[:CONTAINS]->(target)
      RETURN target,
             collect(DISTINCT caller) AS callers,
             collect(DISTINCT importer) AS importers,
             collect(DISTINCT inheritor) AS inheritors,
             collect(DISTINCT parent) AS parents
    `;

    const result = await session.run(cypher, { entity });

    if (result.records.length === 0) {
      return {
        entity,
        found: false,
        message: "Entity not found in codebase graph",
        impacted: [],
      };
    }

    const record = result.records[0];
    const targetNode = record.get("target");
    const callers = (record.get("callers") || []).filter(Boolean);
    const importers = (record.get("importers") || []).filter(Boolean);
    const inheritors = (record.get("inheritors") || []).filter(Boolean);
    const parents = (record.get("parents") || []).filter(Boolean);

    const toImpact = (node, relation) => ({
      name: node.properties.name,
      signature: node.properties.signature || "",
      path: node.properties.path || "",
      type: (node.labels || [])[0] || "Unknown",
      relation,
    });

    const impacted = [
      ...callers.map((n) => toImpact(n, "CALLS")),
      ...importers.map((n) => toImpact(n, "IMPORTS")),
      ...inheritors.map((n) => toImpact(n, "INHERITS")),
    ];

    return {
      entity: {
        name: targetNode?.properties.name || entity,
        signature: targetNode?.properties.signature || "",
        path: targetNode?.properties.path || "",
        type: (targetNode?.labels || [])[0] || "Unknown",
      },
      found: true,
      impacted,
      parents: parents.map((n) => toImpact(n, "CONTAINS")),
      total_impacted: impacted.length,
      depth: d,
    };
  } catch (err) {
    return { error: err.message, impacted: [] };
  } finally {
    await session.close();
  }
}

// ============================================================================
// Tool: codebase_entry_points
// ============================================================================

async function codebaseEntryPoints(_params) {
  const session = getSession(_params);

  try {
    // Match CodeEntryPoint nodes OR CodeFunction/CodeFile with is_entry_point
    const cypher = `
      MATCH (ep:CodeEntryPoint)
      OPTIONAL MATCH (f:CodeFile)-[:HAS_ENTRY_POINT]->(ep)
      RETURN ep.entry_type AS entry_type,
             ep.command AS command,
             f.path AS file_path,
             f.name AS file_name
      UNION
      MATCH (f:CodeFunction {is_entry_point: true})
      OPTIONAL MATCH (file:CodeFile)-[:CONTAINS]->(f)
      RETURN 'function' AS entry_type,
             f.signature AS command,
             file.path AS file_path,
             file.name AS file_name
    `;

    const result = await session.run(cypher);

    const entries = result.records.map((r) => ({
      entry_type: r.get("entry_type") || "unknown",
      command: r.get("command") || "",
      file_path: r.get("file_path") || "",
      file_name: r.get("file_name") || "",
    }));

    return {
      entry_points: entries,
      total: entries.length,
    };
  } catch (err) {
    return { error: err.message, entry_points: [] };
  } finally {
    await session.close();
  }
}

// ============================================================================
// Tool: codebase_stats
// ============================================================================

async function codebaseStats(_params) {
  const session = getSession(_params);

  try {
    const cypher = `
      MATCH (f:CodeFile)
      OPTIONAL MATCH (func:CodeFunction)
      OPTIONAL MATCH (cls:CodeClass)
      OPTIONAL MATCH (imp:CodeImport)
      OPTIONAL MATCH (ep:CodeEntryPoint)
      OPTIONAL MATCH (pkg:CodePackage)
      OPTIONAL MATCH (mod:CodeModule)
      OPTIONAL MATCH (ta:CodeTypeAnnotation)
      OPTIONAL MATCH (df:CodeDataFlow)
      RETURN count(DISTINCT f) AS total_files,
             count(DISTINCT func) AS total_functions,
             count(DISTINCT cls) AS total_classes,
             count(DISTINCT imp) AS total_imports,
             count(DISTINCT ep) AS total_entry_points,
             count(DISTINCT pkg) AS total_packages,
             count(DISTINCT mod) AS total_modules,
             count(DISTINCT ta) AS total_type_annotations,
             count(DISTINCT df) AS total_data_flows
    `;

    const result = await session.run(cypher);

    if (result.records.length === 0) {
      return { error: "No data found", total_files: 0 };
    }

    const record = result.records[0];

    // Also count CALLS edges
    const edgeResult = await session.run(`
      MATCH ()-[r:CALLS]->()
      RETURN count(r) AS total_calls
    `);
    const totalCalls = edgeResult.records[0]?.get("total_calls") || 0;

    return {
      total_files: neo4jToNumber(record.get("total_files")),
      total_functions: neo4jToNumber(record.get("total_functions")),
      total_classes: neo4jToNumber(record.get("total_classes")),
      total_imports: neo4jToNumber(record.get("total_imports")),
      total_entry_points: neo4jToNumber(record.get("total_entry_points")),
      total_packages: neo4jToNumber(record.get("total_packages")),
      total_modules: neo4jToNumber(record.get("total_modules")),
      total_type_annotations: neo4jToNumber(record.get("total_type_annotations")),
      total_data_flows: neo4jToNumber(record.get("total_data_flows")),
      total_calls: neo4jToNumber(totalCalls),
    };
  } catch (err) {
    return { error: err.message, total_files: 0 };
  } finally {
    await session.close();
  }
}

// ============================================================================
// MCP Request Handlers
// ============================================================================

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "codebase_search",
      description:
        "Hybrid search over the codebase graph: BM25 fulltext + cosine vector similarity " +
        "fused via Reciprocal Rank Fusion (RRF). Searches CodeFile, CodeFunction, and CodeClass nodes. " +
        "Use when: finding functions, classes, or files by name, signature, or semantic meaning.",
      inputSchema: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description: "Search query (function name, class name, file path, or natural language)",
          },
          embedding: {
            type: "array",
            items: { type: "number" },
            description: "384-dim query embedding for cosine similarity (optional)",
          },
          limit: {
            type: "integer",
            default: 20,
            description: "Maximum number of results",
          },
          bm25_weight: {
            type: "number",
            default: 0.3,
            description: "BM25 weight in RRF fusion (0.0-1.0, cosine = 1-bm25_weight)",
          },
          mode: {
            type: "string",
            enum: ["hybrid", "keyword", "semantic"],
            default: "hybrid",
            description: "Search mode: hybrid (BM25+cosine), keyword (BM25 only), semantic (cosine only)",
          },
        },
        required: ["query"],
      },
    },
    {
      name: "codebase_traverse",
      description:
        "Multi-hop graph traversal from a code file: follow IMPORTS, CALLS, CONTAINS, INHERITS edges. " +
        "Returns root node, children, related nodes, and edges. " +
        "Use when: exploring code dependencies, understanding file structure.",
      inputSchema: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "File path to start traversal from (e.g., 'src/main.py')",
          },
          depth: {
            type: "integer",
            default: 2,
            minimum: 1,
            maximum: 5,
            description: "Hop depth for traversal",
          },
          direction: {
            type: "string",
            enum: ["downstream", "upstream", "both"],
            default: "both",
            description: "Traversal direction: downstream (outgoing), upstream (incoming), both",
          },
          max_level: {
            type: "integer",
            default: 3,
            minimum: 1,
            maximum: 3,
            description: "Maximum AST level to include (1=functions/classes, 2=packages/modules, 3=types/dataflow)",
          },
        },
        required: ["path"],
      },
    },
    {
      name: "codebase_impact_analysis",
      description:
        "Reverse impact analysis: find all entities that depend on a given function, class, or file. " +
        "Traverses CALLS, IMPORTS, and INHERITS edges in reverse. " +
        "Use when: assessing impact of changes, refactoring risk analysis.",
      inputSchema: {
        type: "object",
        properties: {
          entity: {
            type: "string",
            description: "Entity identifier: function signature, class name, or file path",
          },
          depth: {
            type: "integer",
            default: 3,
            minimum: 1,
            maximum: 5,
            description: "Hop depth for reverse traversal",
          },
        },
        required: ["entity"],
      },
    },
    {
      name: "codebase_entry_points",
      description:
        "List all entry points in the codebase: __main__ guards, shebang scripts, CLI entry points. " +
        "Use when: discovering how to run or invoke the codebase.",
      inputSchema: {
        type: "object",
        properties: {},
      },
    },
    {
      name: "codebase_stats",
      description:
        "Aggregate statistics about the codebase graph: total files, functions, classes, imports, " +
        "entry points, packages, modules, type annotations, data flows, and call edges. " +
        "Use when: getting an overview of the indexed codebase.",
      inputSchema: {
        type: "object",
        properties: {},
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  let result;
  try {
    switch (name) {
      case "codebase_search":
        result = await codebaseSearch(args || {});
        break;
      case "codebase_traverse":
        result = await codebaseTraverse(args || {});
        break;
      case "codebase_impact_analysis":
        result = await codebaseImpactAnalysis(args || {});
        break;
      case "codebase_entry_points":
        result = await codebaseEntryPoints(args || {});
        break;
      case "codebase_stats":
        result = await codebaseStats(args || {});
        break;
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    return {
      content: [
        { type: "text", text: JSON.stringify({ error: err.message }, null, 2) },
      ],
      isError: true,
    };
  }
});

// ============================================================================
// Lifecycle
// ============================================================================

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
