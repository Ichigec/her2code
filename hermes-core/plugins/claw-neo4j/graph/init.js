import { promises as fs } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { withSession } from "./client.js"
import { COMPACTION_POLICIES } from "./policies.js"

const __DIR = path.dirname(fileURLToPath(import.meta.url))

async function loadSchemaStatements() {
  const raw = await fs.readFile(path.join(__DIR, "constraints.cypher"), "utf8")
  return raw
    .split(";")
    .map((s) => s.replace(/^\s*--.*$/gm, "").trim())
    .filter((s) => s.length > 0)
}

/**
 * @param {import('./config.js').Neo4jConfig} cfg
 */
export async function initGraph(cfg) {
  const statements = await loadSchemaStatements()
  await withSession(cfg, async (session) => {
    for (const cypher of statements) {
      try {
        await session.run(cypher)
      } catch (err) {
        const msg = String(err?.message || err)
        if (!msg.includes("equivalent") && !msg.includes("already exists")) throw err
      }
    }
    for (const pol of COMPACTION_POLICIES) {
      await session.run(
        `MERGE (p:CompactionPolicy {axis: $axis})
         ON CREATE SET p.description = $description
         ON MATCH SET p.description = $description`,
        pol,
      )
    }
  })
}
