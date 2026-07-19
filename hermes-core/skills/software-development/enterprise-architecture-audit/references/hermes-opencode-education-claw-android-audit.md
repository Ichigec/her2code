# Example: Enterprise Architecture Audit — Hermes / OpenCode+ / Graphs / Android

> Session reference: audit performed under Enterprise Architect #11 persona.
> Standards enforced: 384-dim embeddings, Neo4j CE single DB, plugin architecture.

## Landscape snapshot (at audit time)

- **Hermes API server**: `0.0.0.0:8648` (`~/.hermes/config.yaml:63-65`, `:546-548`)
- **OpenCode+**: LiteLLM `:4000` → LM Studio `:1234` + llama.cpp `:8092`; web UI `:3400`
- **Neo4j**: `bolt://127.0.0.1:7687`
- **MCP servers in Hermes**: `claw-graph`, `education-graph`, `graph-tool`, `codebase-graph`, `searchbox`
- **Android source**: `/home/user/dev/Opencode` (`com.hermes.gui`)

## Conflicts found

| # | Conflict | File(s):line(s) | Impact | Recommendation |
|---|---|---|---|---|
| 1 | Android default URL port `8643` ≠ Hermes API `8648` | `dev/Opencode/app/.../Constants.kt:4`; `SettingsDataStore.kt:31` | App and tunnel docs (`codemes_apk`, `android-hermes/AGENTS.md`, `cellular-tunnel`) point at wrong port. | Unify on one port; update Android constants + docs or revert Hermes to `8643`. |
| 2 | Android default model is OpenCode+ alias, not Hermes model | `SettingsDataStore.kt:19` (`qwen3.6-35b-heretic`); `Constants.kt:5` (`hermes-agent`) | Default model not in Hermes catalog/Constants list. | Align `selectedModel` with `Constants.kt` or register alias in Hermes. |
| 3 | Education Graph uses separate DB `education` | `graph_tool/python/graph/init_education.py:40,50,54`; `education_agent.py:39`; `graph_enricher.py:24`; `mcp/education-server.mjs:169,212-213` | Violates Neo4j CE single-DB standard; `CREATE DATABASE` fails on CE. | Remove `CREATE DATABASE`, default `EDUCATION_DATABASE`/`NEO4J_DATABASE` to `neo4j`, rely on label separation (`KnowledgeEntity`, `LearningSource`, ...). |
| 4 | `embed_skills.py` uses 768-dim nomic embeddings | `~/.hermes/scripts/embed_skills.py:8,31`; `codemes_1/dist/hermes-core/scripts/embed_skills.py:8,31` | Conflicts with 384-dim standard used by education/codebase/tool graphs. | Switch to `all-MiniLM-L6-v2` + 384-dim index; remove nomic alias from LiteLLM graph use. |
| 5 | Duplicate `claw-neo4j` plugin | `~/.hermes/plugins/claw-neo4j` and `cursor/opencode+/plugins/claw-neo4j` | Two copies; README in Hermes version still references OpenCode+ path. | Keep one canonical copy under `~/.hermes/plugins`; delete/symlink OpenCode+ copy; update README. |
| 6 | `sync-from-compactor.js` default compactor path is wrong | `~/.hermes/plugins/claw-neo4j/sync-from-compactor.js:17` | Resolves to non-existent `/home/user/opencode+/...`; real data is in `~/.compactor` and `cursor/opencode+/opencode_claw/.compactor`. | Point default to `~/.compactor` and accept `--compactor` override. |
| 7 | `hermes-opencode` plugin imports missing modules | `~/.hermes/plugins/hermes-opencode/__init__.py:33` | `tools.glob_tool`, `list_tool`, `lsp_tool` not present in active Hermes. | Implement modules or remove plugin claims. |
| 8 | Hardcoded secrets / default passwords | `SettingsDataStore.kt:32`; `claw-discovery.py:93`; `embed_skills.py:16,22`; `education-server.mjs:211` | Credentials committed/used in source. | Move secrets to env/BuildConfig; scripts should default to env vars only. |

## Standards compliance summary

- **384-dim embeddings**: ✅ education, codebase, tool embeddings, GNN; ❌ `embed_skills.py` (768).
- **Single Neo4j DB**: ✅ claw, codebase, graph-tool, practice; ❌ education (separate `education` DB).
- **Plugin architecture**: ✅ MCP integration is consistent; ❌ duplicate `claw-neo4j` + dead `hermes-opencode` imports.

## Key pitfall observed

Environment overrides in `~/.hermes/config.yaml` (e.g. `education-graph.env.NEO4J_DATABASE=neo4j`) can make the system *look* compliant while the underlying code still defaults to the wrong database. Always inspect code defaults, not only config overrides.
