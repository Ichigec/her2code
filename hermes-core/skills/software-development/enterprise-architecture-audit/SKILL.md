---
name: enterprise-architecture-audit
description: "Audit cross-project conflicts across the local AI stack (Hermes, OpenCode+, graph MCP servers, Android client). Verify landscape-wide standards: embedding dimensions, single Neo4j DB, plugin architecture, ports, models, credentials."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [architecture, audit, cross-project, hermes, opencode, neo4j, android, enterprise-architect]
    related_skills: [architecture-design, build-engineering-standards, hermes-codebase, neo4j-knowledge-graph, android-hermes-gui, opencode, claw-maintenance-cycle]
---

# Enterprise Architecture Audit

Cross-project conflict detection for the integrated local AI stack. The user may phrase this as:

- "You are Enterprise Architect #N. Check cross-project conflicts..."
- "Audit the landscape: Hermes, OpenCode+, Education Graph, Claw Graph, Android app..."
- "Verify standards: 384-dim embeddings, Neo4j CE single DB, plugin architecture..."

This skill treats the whole stack as one system of systems and produces a conflict report, not a redesign.

## When to Use

- The user assigns an Enterprise Architect persona and asks for a landscape-wide check.
- Multiple subsystems (Hermes API, OpenCode+, graph MCP servers, Android client) are suspected of drifting apart.
- A new standard (embedding dim, DB topology, port, plugin contract) was declared and needs enforcement across repos.

## Landscape Map (canonical components)

Know these moving parts before searching:

| Component | Source of truth | What to read |
|-----------|-----------------|--------------|
| Hermes core config | `~/.hermes/config.yaml` | `api_server`, `mcp_servers`, `model`, `providers`, `platforms` |
| Hermes scripts | `~/.hermes/scripts/` | embedding generators, discovery, compaction helpers |
| Hermes plugins | `~/.hermes/plugins/` | MCP-style plugins (claw-neo4j, hermes-opencode, ...) |
| Hermes skills | `~/.hermes/skills/` | Markdown skills with frontmatter; may reference graph standards |
| OpenCode+ | `~/cursor/opencode+/` | `architecture.md`, `start-*.sh`, `configs/opencode.litellm-dual.json`, `plugins/` |
| Graph tooling | `~/cursor/first/graph_tool/` | `python/graph/*.cypher`, `python/education/education_agent.py`, `mcp/*-server.mjs` |
| Codebase graph | `~/dev/codemes/codemes_neo4j_repo-graph_*/` | `codebase_schema.cypher` |
| Android client | `~/dev/Opencode/` | `Constants.kt`, `SettingsDataStore.kt`, `AuthInterceptor.kt`, `HermesApi.kt` |
| Packaged dist | `~/dev/codemes/codemes_1/dist/` | Stale copies of Hermes scripts/plugins can override active files |
| Compactor | `~/.compactor/` and per-project `.compactor/` | Registry snapshots, log, sessions |
| LiteLLM | `~/cursor/first/docker/litellm/config.yaml` | Model aliases, embedding model passthrough |

## Mandatory Standards Checklist

Always verify these against the live files. If the user names different standards, replace this list and state the delta.

1. **Embedding dimension**: `384` across all vector indexes and embedding generators (`all-MiniLM-L6-v2` is the local default).
2. **Neo4j topology**: Community Edition = single `neo4j` database. Namespace separation by node labels, not `CREATE DATABASE`.
3. **Plugin architecture**: one canonical home per plugin; no duplicate copies in Hermes + OpenCode+ trees.
4. **Ports and URLs**: Android client, tunnel docs, and Hermes API server must agree on the same endpoint.
5. **Models/aliases**: default model in Android must exist in the backend it targets (Hermes catalog or LiteLLM aliases).
6. **Secrets**: no hardcoded API keys, passwords, or tokens in source.
7. **Env overrides**: environment variables in `mcp_servers` config should not mask wrong hardcoded defaults in code.

## Audit Steps

1. **Load relevant skills**.
   - Likely: `hermes-codebase`, `opencode`, `claw-maintenance-cycle`, `android-hermes-gui`, `neo4j-knowledge-graph`.
   - Read them; they contain canonical paths and known pitfalls.

2. **Build the runtime map**.
   - Read `~/.hermes/config.yaml` for `api_server.port`, `mcp_servers`, `model.default`, `providers`.
   - Read OpenCode+ `architecture.md` and `configs/opencode.litellm-dual.json` for LLM proxy topology.
   - Read LiteLLM config for model/embedding aliases.

3. **Inspect graph schemas**.
   - Search all `*.cypher` for `vector.dimensions` and collect dimensions.
   - Search Python/JS graph code for `CREATE DATABASE`, `session(database=...)` defaults, `NEO4J_DATABASE` defaults.
   - Compare with the user's single-DB standard.

4. **Inspect embedding generators**.
   - Search for `EMBED_MODEL`, `SentenceTransformer(`, `text-embedding-` aliases, `vector.dimensions`.
   - Flag any generator/index using a dimension or model different from the standard.

5. **Inspect plugin duplications and dead plugins**.
   - List `~/.hermes/plugins/` and OpenCode+ `plugins/`.
   - Compare names/sizes; flag duplicates.
   - Check plugin README/setup instructions for stale paths.

6. **Inspect Android client**.
   - Read `Constants.kt` and `SettingsDataStore.kt` for default URL, model, API key.
   - Read `AuthInterceptor.kt` to see whether `backendMode`/URL switching is actually implemented.
   - Cross-check default model against Hermes model catalog and LiteLLM aliases.

7. **Inspect packaged dist for drift**.
   - `~/dev/codemes/codemes_1/dist/hermes-core/scripts/` and `dist/plugins/` often mirror active files.
   - If the active file is clean but the dist copy still carries the conflict, both need fixing.

8. **Synthesize findings**.
   - Use the output format below.
   - Cite exact files and line numbers.
   - Prioritize: standards violations > security issues > stale docs/duplicates.

## Conflict Categories to Probe

| Category | Search patterns | Typical violators |
|----------|-----------------|-------------------|
| Wrong embedding dim | `vector.dimensions`, `EMBED_MODEL`, `SentenceTransformer(`, `text-embedding-nomic` | `embed_skills.py`, LiteLLM alias list |
| Multi-DB on CE | `CREATE DATABASE`, `database:`, `EDUCATION_DATABASE`, `NEO4J_DATABASE` default | `init_education.py`, `education_agent.py`, `education-server.mjs` |
| Port/URL drift | `DEFAULT_API_URL`, `api_server.port`, `8643`, `8648` | Android constants, tunnel docs, Hermes config |
| Model mismatch | `selectedModel`, `DEFAULT_MODEL`, `model_list` | Android default pointing at OpenCode+ alias instead of Hermes catalog |
| Plugin duplication | identical plugin names under `~/.hermes/plugins/` and `opencode+/plugins/` | `claw-neo4j` |
| Stale paths | `DEFAULT_COMPACTOR`, hardcoded relative paths in plugin README/sync scripts | `sync-from-compactor.js`, `claw-neo4j/README.md` |
| Missing tool modules | plugin imports non-existent modules | `hermes-opencode/__init__.py` |
| Hardcoded secrets | `DEFAULT_API_KEY`, `changeme` defaults in scripts | Android settings, discovery scripts |

## Output Format

Return a concise report with this structure:

```markdown
## Landscape snapshot
- Hermes API: host:port
- OpenCode+ proxy: host:port → backends
- Neo4j: uri
- MCP servers: list
- Android default URL/model

## Conflicts found
| # | Conflict | File(s):line(s) | Impact | Recommendation |
|---|---|---|---|---|
| 1 | ... | ... | ... | ... |

## Standards compliance
- 384-dim: ✅/❌ with exceptions
- Single Neo4j DB: ✅/❌ with exceptions
- Plugin architecture: ✅/❌ with exceptions

## Files not modified
```

Keep the report readable: bullets and tables, not prose.

## Pitfalls

- **Env override can hide bad defaults.** Hermes `mcp_servers.education-graph.env.NEO4J_DATABASE=neo4j` may look compliant, but if the underlying `education-server.mjs` defaults to `education`, standalone runs break. Always check code defaults, not just config.
- **Dist copies drift.** A fix in `~/.hermes/scripts/` but not in `~/dev/codemes/codemes_1/dist/` will regress on the next install/packaging run.
- **Docs lie.** Tunnel/ADB docs (`codemes_apk`, `android-hermes/AGENTS.md`, `cellular-tunnel`) often hardcode ports that no longer match the live server.
- **Android `backendMode` may be dead code.** Verify in `AuthInterceptor.kt`/`ChatRepository.kt` that the mode actually changes URL/model before assuming a dual-backend design exists.
- **Skills can be stale.** The skill docs for `neo4j-knowledge-graph` may already declare the correct standard while implementation files violate it. Trust file contents over skill text.
- **Gate scripts check wrong ports (FIXED 2026-07-15).** `orchestrator_gate.py` was checking Hermes API at `:18649/health` (not listening) and LiteLLM at `/health` (hangs). Fix applied: Hermes API → `:8643/health` (Native Gateway, systemd service), LiteLLM → `/v1/models` (responds instantly). Also fixed: `capability_gate.py --json` crashed on `Severity` enum serialization — added `_CapabilityEncoder` with `Enum.value` + `default=str`. Both gates now produce valid JSON output. Pre-Flight Gate: was 3/7, now 6/7 PASS.
- **Plan preset model drift (FIXED 2026-07-15).** Forked presets (plan2→plan3→plan4) referenced `kimi-k2.7-code` / `custom:kimi` which does NOT exist in LiteLLM. Replaced across all 34 agent `.md` files + registry.json (125 agents, 0 kimi). Replacement model: `agents-a1-abliterated` via `custom:local` (0.2s latency, no reasoning overhead). Always verify with: `curl -s http://localhost:4000/v1/models -H 'Authorization: Bearer *** | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"`.
- **Agent file path drift (FIXED 2026-07-15).** Presets reference `agents/dev/dev-skeptic.md` but the `agents/dev/` subdirectory was empty. Files now copied to `agents/dev/` (dev-skeptic.md, dev-pragmatic.md, dev-creative.md, dev-maverick.md). Note: `agent_registry.py` reads model from frontmatter — if frontmatter says `kimi-k2.7-code`, the registry will carry the stale model even after editing `plan2.md`. Bulk-fix with: `find agents/ -name '*.md' ! -name '*.bak*' -exec sed -i 's/kimi-k2\.7-code/agents-a1-abliterated/g; s/custom:kimi/custom:local/g' {} +` then regenerate registry.
- **MCP servers not registered (FIXED 2026-07-15).** `codebase-graph` and `education-graph` MCP servers exist at `~/cursor/first/graph_tool/mcp/` but were never added to `config.yaml → mcp_servers`. Registration: add `command: node, args: [path], env: {NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD}`. Test with stdio handshake before registering. See `hermes-codebase` skill → references/port-architecture.md for the full MCP server map.
- **Observer gate false-fails (FIXED 2026-07-15).** `orchestrator_gate.py:check_observers()` searched for daemon PID files and returned BLOCKER when none found. But plan2 spawns observers in-process via `delegate_task`. Gate now reads `config.yaml → observer.enabled` and treats missing PID files as WARNING, not BLOCKER.

## References

- See `references/hermes-opencode-education-claw-android-audit.md` for a worked example from a real session.
