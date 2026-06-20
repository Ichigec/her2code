/** @typedef {{ enabled: boolean, uri: string, user: string, password: string, database: string }} Neo4jConfig */

/**
 * @param {Record<string, unknown>} [opts]
 * @returns {Neo4jConfig}
 */
export function loadConfig(opts = {}) {
  const enabled =
    opts.enabled !== undefined
      ? Boolean(opts.enabled)
      : process.env.NEO4J_ENABLED !== "0" && process.env.NEO4J_ENABLED !== "false"
  return {
    enabled,
    uri: String(opts.uri || process.env.NEO4J_URI || "bolt://127.0.0.1:7687"),
    user: String(opts.user || process.env.NEO4J_USER || "neo4j"),
    password: String(opts.password || process.env.NEO4J_PASSWORD || "changeme"),
    database: String(opts.database || process.env.NEO4J_DATABASE || "neo4j"),
  }
}
