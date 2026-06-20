/**
 * Hybrid search: BM25 (fulltext) + Cosine (vector) via Reciprocal Rank Fusion.
 * After ranking, enriches results with graph context (neighbors, dependencies).
 */
import { withSession } from "./neo4j_client.js";
import { reciprocalRankFusion } from "./rrf.js";
import neo4j from "neo4j-driver";

/**
 * BM25 search via Neo4j fulltext index.
 * @param {import('neo4j-driver').Session} session
 * @param {string} query
 * @param {number} k
 */
async function bm25Search(session, query, k = 50) {
  const q = query.includes(" ") ? query : `${query}*`;
  const result = await session.run(
    `CALL db.index.fulltext.queryNodes('toolSearch', $q)
     YIELD node, score
     WHERE coalesce(node.status, 'active') <> 'pruned'
     RETURN node.id AS id, node.name AS name, node.type AS type,
            node.description AS description, score
     ORDER BY score DESC
     LIMIT $k`,
    { q, k: neo4j.int(k) },
  );
  return result.records.map((r) => ({
    id: r.get("id"),
    name: r.get("name"),
    type: r.get("type"),
    description: r.get("description"),
    bm25_score: r.get("score"),
  }));
}

/**
 * Cosine similarity search via Neo4j vector index.
 * Falls back gracefully if vector index doesn't exist.
 * @param {import('neo4j-driver').Session} session
 * @param {number[]} embedding
 * @param {number} k
 */
async function cosineSearch(session, embedding, k = 50) {
  try {
    const result = await session.run(
      `CALL db.index.vector.queryNodes('toolEmbeddings', $k, $embedding)
       YIELD node, score
       WHERE coalesce(node.status, 'active') <> 'pruned'
       RETURN node.id AS id, node.name AS name, node.type AS type,
              node.description AS description, score
       ORDER BY score DESC
       LIMIT $k`,
      { k: neo4j.int(k), embedding },
    );
    return result.records.map((r) => ({
      id: r.get("id"),
      name: r.get("name"),
      type: r.get("type"),
      description: r.get("description"),
      cosine_score: r.get("score"),
    }));
  } catch {
    return [];
  }
}

/**
 * Enrich ranked IDs with graph context: neighbors, dependencies, co-occurrences.
 * @param {import('neo4j-driver').Session} session
 * @param {string[]} toolIds - ranked tool IDs
 * @param {number} depth
 */
async function enrichWithGraphContext(session, toolIds, depth = 2) {
  if (toolIds.length === 0) return [];

  const result = await session.run(
    `UNWIND $ids AS tid
     MATCH (t:Tool {id: tid})
     OPTIONAL MATCH (t)-[:DEPENDS_ON]->(dep:Tool)
     OPTIONAL MATCH (t)-[:CO_OCCURS_WITH]-(co:Tool)
     OPTIONAL MATCH (t)-[:DUPLICATE_OF]->(dup:Tool)
     OPTIONAL MATCH (t)<-[:DUPLICATE_OF]-(dupOf:Tool)
     OPTIONAL MATCH (t)-[:MERGED_INTO]->(merged:Tool)
     OPTIONAL MATCH (t)<-[:EVIDENCED_BY]-(ev:Evidence)
     RETURN t.id AS id,
            t.name AS name,
            t.type AS type,
            t.description AS description,
            t.target AS target,
            t.mcp_usage AS mcp_usage,
            t.confirmations AS confirmations,
            t.status AS status,
            collect(DISTINCT dep.id) AS depends_on,
            collect(DISTINCT co.id) AS co_occurs_with,
            collect(DISTINCT dup.id) AS duplicate_of,
            collect(DISTINCT dupOf.id) AS duplicated_by,
            collect(DISTINCT merged.id) AS merged_into,
            collect(DISTINCT ev.anchor) AS evidence`,
    { ids: toolIds, depth: neo4j.int(depth) },
  );

  const toolMap = new Map();
  for (const r of result.records) {
    toolMap.set(r.get("id"), {
      id: r.get("id"),
      name: r.get("name"),
      type: r.get("type"),
      description: r.get("description"),
      target: r.get("target"),
      mcp_usage: r.get("mcp_usage"),
      confirmations: neo4jIntegerToNumber(r.get("confirmations")),
      status: r.get("status"),
      depends_on: r.get("depends_on").filter(Boolean),
      co_occurs_with: r.get("co_occurs_with").filter(Boolean),
      duplicate_of: r.get("duplicate_of").filter(Boolean),
      duplicated_by: r.get("duplicated_by").filter(Boolean),
      merged_into: r.get("merged_into").filter(Boolean),
      evidence: r.get("evidence").filter(Boolean),
    });
  }
  return toolMap;
}

/**
 * Calculate graph connectivity score for re-ranking.
 * Higher score = more connected = more likely relevant hub.
 */
function graphConnectivityScore(tool) {
  let score = 0;
  score += Math.min(tool.depends_on.length, 10) * 1.0;
  score += Math.min(tool.co_occurs_with.length, 10) * 0.5;
  score += (tool.confirmations || 0) * 0.3;
  score += (tool.evidence?.length || 0) * 0.2;
  return score;
}

function neo4jIntegerToNumber(val) {
  if (val === null || val === undefined) return 0;
  if (typeof val === "number") return val;
  if (typeof val.toNumber === "function") return val.toNumber();
  return Number(val);
}

/**
 * Main hybrid search entry point.
 * @param {{ query: string, embedding?: number[], limit?: number,
 *           bm25_weight?: number, use_graph_enrichment?: boolean,
 *           database?: string }} params
 */
export async function hybridSearch(params) {
  const {
    query,
    embedding = null,
    limit = 20,
    bm25_weight = 0.3,
    use_graph_enrichment = true,
  } = params;

  return withSession(params, async (session) => {
    // Stage 1: BM25 + Cosine
    const [bm25Results, cosineResults] = await Promise.all([
      bm25Search(session, query, 50),
      embedding ? cosineSearch(session, embedding, 50) : Promise.resolve([]),
    ]);

    // Stage 2: RRF fusion
    const fused = reciprocalRankFusion(bm25Results, cosineResults, limit, bm25_weight);

    if (!use_graph_enrichment || fused.length === 0) {
      const bm25Map = new Map(bm25Results.map((r) => [r.id, r]));
      const cosineMap = new Map(cosineResults.map((r) => [r.id, r]));
      return fused.map(([id, rrfScore]) => ({
        id,
        bm25_score: bm25Map.get(id)?.bm25_score ?? 0,
        cosine_score: cosineMap.get(id)?.cosine_score ?? 0,
        rrf_score: rrfScore,
        name: bm25Map.get(id)?.name ?? id,
        type: bm25Map.get(id)?.type ?? "",
        description: bm25Map.get(id)?.description ?? "",
      }));
    }

    // Stage 3: Graph enrichment
    const toolMap = await enrichWithGraphContext(
      session,
      fused.map(([id]) => id),
      1,
    );

    // Stage 4: Re-rank with connectivity
    const enriched = fused.map(([id, rrfScore]) => {
      const tool = toolMap.get(id);
      const graphScore = tool ? graphConnectivityScore(tool) : 0;
      return {
        ...(tool || { id }),
        rrf_score: rrfScore,
        graph_score: graphScore,
        combined_score: rrfScore * 0.7 + normalizeScore(graphScore, 10) * 0.3,
      };
    });

    return enriched.sort((a, b) => b.combined_score - a.combined_score);
  });
}

function normalizeScore(val, max) {
  return Math.min(val / max, 1.0);
}

/**
 * Graph traversal: find related tools/code entities from a starting point.
 *
 * Patterns:
 *   - "dependencies"    : DEPENDS_ON (Tool → Tool)
 *   - "co_occurring"    : CO_OCCURS_WITH (Tool — Tool)
 *   - "related"         : all claw edges + CODED_IN (Tool → CodeFile cross-graph)
 *   - "code_imports"    : IMPORTS (CodeFile → CodeImport → CodeFile)
 *   - "code_calls"      : CALLS (CodeFunction → CodeFunction)
 *   - "code_all"        : all code edges: IMPORTS, CALLS, CONTAINS, INHERITS
 */
export async function graphTraverse(params) {
  const { start_id, pattern = "related", depth = 2 } = params;
  return withSession(params, async (session) => {
    const d = Math.min(depth, 5);
    let cypher;
    let paramsObj = { start_id };

    if (pattern === "dependencies") {
      cypher = `MATCH (t:Tool {id: $start_id})-[:DEPENDS_ON*1..${d}]->(dep:Tool)
                RETURN DISTINCT dep`;
    } else if (pattern === "co_occurring") {
      cypher = `MATCH (t:Tool {id: $start_id})-[:CO_OCCURS_WITH*1..${d}]-(co:Tool)
                RETURN DISTINCT co`;
    } else if (pattern === "code_imports") {
      // Traverse IMPORTS edges from any Code* entity
      cypher = `MATCH (start)
                WHERE (start:CodeFile OR start:CodeFunction OR start:CodeClass)
                  AND (start.path = $start_id OR start.signature = $start_id OR start.name = $start_id)
                MATCH (start)-[:IMPORTS*1..${d}]-(related)
                WHERE related:CodeFile OR related:CodeImport
                RETURN DISTINCT related, labels(related) AS labels`;
    } else if (pattern === "code_calls") {
      // Traverse CALLS edges from any CodeFunction
      cypher = `MATCH (start:CodeFunction)
                WHERE start.signature = $start_id OR start.name = $start_id
                MATCH (start)-[:CALLS*1..${d}]-(related:CodeFunction)
                RETURN DISTINCT related`;
    } else if (pattern === "code_all") {
      // Traverse all code edges: IMPORTS, CALLS, CONTAINS, INHERITS
      cypher = `MATCH (start)
                WHERE (start:CodeFile OR start:CodeFunction OR start:CodeClass)
                  AND (start.path = $start_id OR start.signature = $start_id OR start.name = $start_id)
                MATCH (start)-[:IMPORTS|CALLS|CONTAINS|INHERITS*1..${d}]-(related)
                RETURN DISTINCT related, labels(related) AS labels`;
    } else {
      // Default "related": all claw edges + CODED_IN cross-graph
      cypher = `MATCH (t:Tool {id: $start_id})
                OPTIONAL MATCH (t)-[r:DEPENDS_ON|CO_OCCURS_WITH|DUPLICATE_OF|MERGED_INTO*1..${d}]-(related:Tool)
                OPTIONAL MATCH (t)-[:CODED_IN]->(code:CodeFile)
                RETURN related, CASE WHEN r IS NOT NULL THEN type(last(r)) ELSE null END AS rel_type, code`;
    }

    const result = await session.run(cypher, paramsObj);

    return result.records.map((r) => {
      const relatedNode =
        r.get("related") || r.get("dep") || r.get("co") || null;
      const codeNode = r.get("code") || null;
      const entry = {
        ...(relatedNode?.properties || {}),
        rel_type: r.get("rel_type") || null,
      };

      // Include CODED_IN file if present
      if (codeNode && codeNode.properties) {
        entry.coded_in = {
          path: codeNode.properties.path,
          name: codeNode.properties.name,
          ext: codeNode.properties.ext,
        };
      }

      // Clean up: remove null rel_type if not present
      if (entry.rel_type === null) delete entry.rel_type;

      return entry;
    }).filter((e) => Object.keys(e).length > 1 || e.rel_type || e.coded_in);
  });
}

