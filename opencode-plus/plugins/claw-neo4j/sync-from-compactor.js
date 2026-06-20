#!/usr/bin/env node
/**
 * Sync .compactor/ JSON artifacts into Neo4j.
 *
 * Usage:
 *   node sync-from-compactor.js --init-only
 *   node sync-from-compactor.js --all
 *   node sync-from-compactor.js --session <sid> --registry <path>
 */
import { promises as fs } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { createNeo4jSync } from "./index.js"

const __DIR = path.dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = path.resolve(__DIR, "..", "..", "..")
const DEFAULT_COMPACTOR = path.join(PROJECT_ROOT, "opencode+/opencode_claw/.compactor")

function parseArgs(argv) {
  const out = { initOnly: false, all: false, session: null, registry: null }
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i]
    if (a === "--init-only") out.initOnly = true
    else if (a === "--all") out.all = true
    else if (a === "--session") out.session = argv[++i]
    else if (a === "--registry") out.registry = argv[++i]
    else if (a === "--compactor") out.compactor = argv[++i]
  }
  return out
}

async function readJSON(filePath, fallback) {
  try {
    const raw = await fs.readFile(filePath, "utf8")
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

async function syncSessionDir(sync, compactorDir, sessionID) {
  const sessionDir = path.join(compactorDir, "sessions", sessionID)
  let entries
  try {
    entries = await fs.readdir(sessionDir)
  } catch {
    return
  }
  const checkpoints = entries.filter((f) => /^checkpoint\.\d+\.json$/.test(f)).sort()
  for (const file of checkpoints) {
    const checkpoint = await readJSON(path.join(sessionDir, file), null)
    if (checkpoint) {
      await sync.syncCheckpoint({ sessionID, checkpoint })
    }
  }
}

async function syncRegistryFiles(sync, compactorDir, sessionID) {
  const regDir = path.join(compactorDir, "registry")
  let files
  try {
    files = (await fs.readdir(regDir)).filter((f) => f.startsWith("integrations.")).sort()
  } catch {
    return
  }
  for (const file of files) {
    const registryPath = path.join(regDir, file)
    const registry = await readJSON(registryPath, { records: [] })
    await sync.syncDiscover({ sessionID, registryPath, registry, actions: [] })
  }
}

async function syncLog(sync, compactorDir, sessionID) {
  const logPath = path.join(compactorDir, "log.jsonl")
  let raw
  try {
    raw = await fs.readFile(logPath, "utf8")
  } catch {
    return
  }
  const actions = raw
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line)
      } catch {
        return null
      }
    })
    .filter((a) => a && (!sessionID || a.session_id === sessionID))
  if (actions.length > 0) {
    const { syncCompactionActions } = await import("./graph/upsert.js")
    const { loadConfig } = await import("./graph/config.js")
    await syncCompactionActions(loadConfig(), { sessionID: sessionID || "replay", actions })
  }
}

async function main() {
  const args = parseArgs(process.argv)
  const compactorDir = path.resolve(args.compactor || DEFAULT_COMPACTOR)
  const sync = createNeo4jSync()

  if (args.initOnly) {
    const ok = await sync.init()
    await sync.close()
    process.exit(ok ? 0 : 1)
  }

  await sync.init()

  if (args.all) {
    const sessionsDir = path.join(compactorDir, "sessions")
    let sessions = []
    try {
      sessions = await fs.readdir(sessionsDir)
    } catch {
      /* empty */
    }
    for (const sid of sessions) {
      await syncSessionDir(sync, compactorDir, sid)
    }
    await syncRegistryFiles(sync, compactorDir, "replay-all")
    await syncLog(sync, compactorDir, null)
  } else if (args.session) {
    await syncSessionDir(sync, compactorDir, args.session)
    if (args.registry) {
      const registry = await readJSON(path.resolve(args.registry), { records: [] })
      await sync.syncDiscover({
        sessionID: args.session,
        registryPath: path.resolve(args.registry),
        registry,
        actions: [],
      })
    }
    await syncLog(sync, compactorDir, args.session)
  } else {
    console.error("Usage: --init-only | --all | --session <sid> [--registry <path>]")
    process.exit(1)
  }

  await sync.close()
  console.log("[claw-neo4j] sync complete")
}

main().catch((err) => {
  console.error("[claw-neo4j] fatal:", err)
  process.exit(1)
})
