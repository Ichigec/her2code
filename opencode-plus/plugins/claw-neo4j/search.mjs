#!/usr/bin/env node
import { searchTools, traverseGraph, getToolDetail } from "./search.js"

function parseFlags(argv) {
  const flags = {}
  const positional = []
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith("-")) {
      const key = a.replace(/^-+/, "")
      const next = argv[i + 1]
      if (next && !next.startsWith("-")) {
        flags[key] = next
        i++
      } else {
        flags[key] = true
      }
    } else {
      positional.push(a)
    }
  }
  return { flags, cmd: positional[0] || "tools" }
}

async function main() {
  const { flags, cmd } = parseFlags(process.argv)

  if (flags.smoke) {
    await searchTools({}, { query: "mcp", limit: 3 })
    console.log("smoke ok")
    return
  }

  if (cmd === "tools") {
    const rows = await searchTools(
      {},
      {
        query: flags.q || flags.query || "",
        type: flags.type,
        target: flags.target,
        limit: Number(flags.limit) || 20,
        include_pruned: flags["include-pruned"] === "true",
      },
    )
    console.log(JSON.stringify(rows, null, 2))
    return
  }

  if (cmd === "graph") {
    const rows = await traverseGraph(
      {},
      {
        pattern: flags.pattern || "session_tools",
        start_id: flags.s || flags.session,
        depth: Number(flags.d || flags.depth) || 2,
        since_days: Number(flags.since) || 7,
      },
    )
    console.log(JSON.stringify(rows, null, 2))
    return
  }

  if (cmd === "detail") {
    const id = flags.i || flags.id
    if (!id) {
      console.error("detail requires -i <tool_id>")
      process.exit(1)
    }
    const row = await getToolDetail({}, id)
    console.log(JSON.stringify(row, null, 2))
    return
  }

  console.error(`Usage:
  search.mjs tools -q <query> [--type mcp] [--limit 20]
  search.mjs graph -s <session_or_tool_id> [--pattern session_tools] [-d 2]
  search.mjs detail -i <tool_id>
  search.mjs --smoke`)
  process.exit(1)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
