import { loadConfig } from "./graph/config.js"
import { verifyConnectivity, closeDriver } from "./graph/client.js"
import { initGraph } from "./graph/init.js"
import { syncCheckpoint, syncRegistry, syncCompactionActions, upsertSession } from "./graph/upsert.js"

/**
 * @param {Record<string, unknown>} [opts]
 */
export function createNeo4jSync(opts = {}) {
  const cfg = loadConfig(opts.neo4j && typeof opts.neo4j === "object" ? opts.neo4j : opts)

  async function ensureReady() {
    if (!cfg.enabled) {
      console.log("[claw-neo4j] skip: NEO4J_ENABLED=0")
      return false
    }
    try {
      await verifyConnectivity(cfg)
      return true
    } catch (err) {
      console.log(`[claw-neo4j] skip: unreachable (${err?.message || err})`)
      return false
    }
  }

  return {
    cfg,
    async init() {
      if (!(await ensureReady())) return false
      await initGraph(cfg)
      console.log("[claw-neo4j] graph initialized (constraints + indexes)")
      return true
    },
    async syncCheckpoint(input) {
      if (!(await ensureReady())) return false
      await syncCheckpoint(cfg, input)
      console.log(
        `[claw-neo4j] checkpoint synced session=${input.sessionID} seq=${input.checkpoint?.seq}`,
      )
      return true
    },
    async syncDiscover(input) {
      if (!(await ensureReady())) return false
      if (input.registry && input.registryPath) {
        await syncRegistry(cfg, {
          sessionID: input.sessionID,
          registryPath: input.registryPath,
          registry: input.registry,
        })
      }
      if (Array.isArray(input.actions) && input.actions.length > 0) {
        await syncCompactionActions(cfg, {
          sessionID: input.sessionID,
          actions: input.actions,
        })
      }
      console.log(`[claw-neo4j] discover synced session=${input.sessionID}`)
      return true
    },
    async close() {
      await closeDriver()
    },
  }
}

export { loadConfig, initGraph, syncCheckpoint, syncRegistry, syncCompactionActions, upsertSession }
