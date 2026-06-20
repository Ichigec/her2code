import neo4j from "neo4j-driver"
import { loadConfig } from "./config.js"

/** @type {import('neo4j-driver').Driver | null} */
let driver = null

/**
 * @param {import('./config.js').Neo4jConfig} cfg
 */
export function getDriver(cfg) {
  if (!driver) {
    driver = neo4j.driver(cfg.uri, neo4j.auth.basic(cfg.user, cfg.password))
  }
  return driver
}

export async function closeDriver() {
  if (driver) {
    await driver.close()
    driver = null
  }
}

/**
 * @param {import('./config.js').Neo4jConfig} cfg
 * @param {(session: import('neo4j-driver').Session) => Promise<T>} fn
 * @template T
 */
export async function withSession(cfg, fn) {
  const d = getDriver(cfg)
  const session = d.session({ database: cfg.database })
  try {
    return await fn(session)
  } finally {
    await session.close()
  }
}

/**
 * @param {import('./config.js').Neo4jConfig} cfg
 */
export async function verifyConnectivity(cfg) {
  const d = getDriver(cfg)
  await d.verifyConnectivity()
}
