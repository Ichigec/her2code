/**
 * Shared Neo4j client for graph-tool MCP server.
 * Reuses the same connection pool as claw-neo4j.
 */
import neo4j from "neo4j-driver";

/** @type {import('neo4j-driver').Driver | null} */
let driver = null;

/**
 * @param {{ uri?: string, user?: string, password?: string, database?: string }} [opts]
 * @returns {import('neo4j-driver').Driver}
 */
export function getDriver(opts = {}) {
  if (!driver) {
    const uri = opts.uri || process.env.NEO4J_URI || "bolt://127.0.0.1:7687";
    const user = opts.user || process.env.NEO4J_USER || "neo4j";
    const password = opts.password || process.env.NEO4J_PASSWORD || "changeme";
    driver = neo4j.driver(uri, neo4j.auth.basic(user, password), {
      maxConnectionPoolSize: 20,
      connectionAcquisitionTimeout: 5000,
    });
  }
  return driver;
}

/**
 * @param {{ database?: string }} [opts]
 * @param {(session: import('neo4j-driver').Session) => Promise<T>} fn
 * @template T
 */
export async function withSession(opts, fn) {
  const d = getDriver(opts);
  const database = opts?.database || process.env.NEO4J_DATABASE || "neo4j";
  const session = d.session({ database });
  try {
    return await fn(session);
  } finally {
    await session.close();
  }
}

export async function closeDriver() {
  if (driver) {
    await driver.close();
    driver = null;
  }
}
