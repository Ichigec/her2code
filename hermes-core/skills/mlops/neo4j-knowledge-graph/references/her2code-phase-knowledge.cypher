// Knowledge extraction ingestion script for PID <SESSION_ID>
// Source artifacts: docs/requirements, docs/system-analysis, docs/research,
// docs/architecture, her2code/SANITIZATION_LOG.md, her2code/DOCKER.md,
// her2code/README.md, her2code/BUILD.md, her2code/sanitize.py,
// her2code/sanitize-config.yaml, her2code/docker-compose.yml,
// her2code/docker-entrypoint.sh, her2code/status-proxy.py
//
// Run against Neo4j Community Edition via cypher-shell or HTTP API:
//   cypher-shell -u neo4j -p changeme -f her2code-phase-knowledge.cypher

// --- LearningSource nodes ---
MERGE (ls_req:LearningSource {id: "LS-HER2CODE-REQ", type: "PhaseArtifact", title: "Requirements: Hermes sanitization and GitHub publication", url: "file:///home/user/dev/codemes/<SESSION_ID>/docs/requirements/hermes-sanitization.md"})
MERGE (ls_sys:LearningSource {id: "LS-HER2CODE-SYS", type: "PhaseArtifact", title: "System Analysis: Hermes sanitization approach", url: "file:///home/user/dev/codemes/<SESSION_ID>/docs/system-analysis/hermes-sanitization.md"})
MERGE (ls_res:LearningSource {id: "LS-HER2CODE-RES", type: "PhaseArtifact", title: "Research: Deep analysis of Hermes infrastructure for sanitization", url: "file:///home/user/dev/codemes/<SESSION_ID>/docs/research/hermes-sanitization.md"})
MERGE (ls_arch:LearningSource {id: "LS-HER2CODE-ARCH", type: "PhaseArtifact", title: "Architecture: COMPONENTS.md inventory", url: "file:///home/user/dev/codemes/<SESSION_ID>/docs/architecture/COMPONENTS.md"})
MERGE (ls_orch:LearningSource {id: "LS-HER2CODE-ORCH-REQ", type: "PhaseArtifact", title: "Requirements: Orchestrator methodology improvement", url: "file:///home/user/dev/codemes/<SESSION_ID>/docs/requirements/orchestrator-improvement.md"})
MERGE (ls_log:LearningSource {id: "LS-HER2CODE-SANLOG", type: "Artifact", title: "Sanitization Log", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/SANITIZATION_LOG.md"})
MERGE (ls_docker:LearningSource {id: "LS-HER2CODE-DOCKER", type: "Artifact", title: "Docker Deployment Guide", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/DOCKER.md"})
MERGE (ls_readme:LearningSource {id: "LS-HER2CODE-README", type: "Artifact", title: "README.md", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/README.md"})
MERGE (ls_build:LearningSource {id: "LS-HER2CODE-BUILD", type: "Artifact", title: "BUILD.md", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/BUILD.md"})
MERGE (ls_sanpy:LearningSource {id: "LS-HER2CODE-SANPY", type: "Artifact", title: "sanitize.py", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/sanitize.py"})
MERGE (ls_sancfg:LearningSource {id: "LS-HER2CODE-SANCFG", type: "Artifact", title: "sanitize-config.yaml", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/sanitize-config.yaml"})
MERGE (ls_dc:LearningSource {id: "LS-HER2CODE-DC", type: "Artifact", title: "docker-compose.yml", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/docker-compose.yml"})
MERGE (ls_entry:LearningSource {id: "LS-HER2CODE-ENTRY", type: "Artifact", title: "docker-entrypoint.sh", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/docker-entrypoint.sh"})
MERGE (ls_proxy:LearningSource {id: "LS-HER2CODE-PROXY", type: "Artifact", title: "status-proxy.py", url: "file:///home/user/dev/codemes/<SESSION_ID>/her2code/status-proxy.py"})

// --- Technologies / Components ---
MERGE (e_hermes:KnowledgeEntity {name: "Hermes Agent"})
  SET e_hermes.type = "Technology", e_hermes.description = "AI agent framework by Nous Research: CLI, tools, gateway, plugins, skills, providers."
MERGE (e_core:KnowledgeEntity {name: "Hermes Agent Core"})
  SET e_core.type = "Subsystem", e_core.description = "Core subsystem: AIAgent engine, tool orchestrator, CLI/TUI, session DB, gateway, plugins, skills, provider adapters."
MERGE (e_android:KnowledgeEntity {name: "Android Client"})
  SET e_android.type = "Component", e_android.description = "Native Android chat app (Kotlin + Jetpack Compose) with voice and SSE streaming."
MERGE (e_opencode:KnowledgeEntity {name: "OpenCode+"})
  SET e_opencode.type = "Component", e_opencode.description = "Local LLM infrastructure: LiteLLM proxy, llama.cpp server, OpenCode web UI configs, systemd."
MERGE (e_neo4j:KnowledgeEntity {name: "Neo4j"})
  SET e_neo4j.type = "Technology", e_neo4j.description = "Graph database backbone for Claw, education, and codebase knowledge graphs."
MERGE (e_docker:KnowledgeEntity {name: "Docker Compose"})
  SET e_docker.type = "Technology", e_docker.description = "Container orchestration for Hermes stack and peripheral services."
MERGE (e_sqlite:KnowledgeEntity {name: "SQLite"})
  SET e_sqlite.type = "Technology", e_sqlite.description = "File-based database for sessions, audit, kanban, metrics; uses WAL and FTS5."
MERGE (e_gateway:KnowledgeEntity {name: "Hermes Gateway"})
  SET e_gateway.type = "Component", e_gateway.description = "Multi-platform messaging gateway and API/SSE server for Hermes Agent."
MERGE (e_api:KnowledgeEntity {name: "Hermes API Server"})
  SET e_api.type = "Component", e_api.description = "HTTP API server exposed by Hermes Gateway on port 8648."
MERGE (e_tools:KnowledgeEntity {name: "Tool Orchestrator"})
  SET e_tools.type = "Component", e_tools.description = "Registry and dispatch system for Hermes tools and MCP servers."
MERGE (e_session:KnowledgeEntity {name: "Session DB"})
  SET e_session.type = "Component", e_session.description = "SQLite FTS5 session/message store; 535 MB production data cleared to schema-only."
MERGE (e_litellm:KnowledgeEntity {name: "LiteLLM Proxy"})
  SET e_litellm.type = "Component", e_litellm.description = "Multi-provider LLM proxy on port 4000 with failover and cost tracking."
MERGE (e_llama:KnowledgeEntity {name: "Llama.cpp Server"})
  SET e_llama.type = "Component", e_llama.description = "Local GGUF inference server on port 8092 (CPU-only on Jetson ARM64)."
MERGE (e_voice:KnowledgeEntity {name: "Voice Proxy"})
  SET e_voice.type = "Component", e_voice.description = "HTTP proxy for STT (Faster-Whisper) and TTS (Piper) on port 8647."
MERGE (e_mcp:KnowledgeEntity {name: "MCP"})
  SET e_mcp.type = "Protocol", e_mcp.description = "Model Context Protocol connecting Hermes to external tool servers."
MERGE (e_claw:KnowledgeEntity {name: "Claw-Graph MCP"})
  SET e_claw.type = "Component", e_claw.description = "Neo4j MCP server for tool catalog and knowledge graph traversal."
MERGE (e_edu:KnowledgeEntity {name: "Education-Graph MCP"})
  SET e_edu.type = "Component", e_edu.description = "Neo4j MCP server for education/knowledge graph queries."
MERGE (e_code:KnowledgeEntity {name: "Codebase-Graph MCP"})
  SET e_code.type = "Component", e_code.description = "Neo4j MCP server for codebase indexing and semantic search."
MERGE (e_search:KnowledgeEntity {name: "Searchbox MCP"})
  SET e_search.type = "Component", e_search.description = "Web search MCP over 15 engines via Docker on port 8024."
MERGE (e_fastapi:KnowledgeEntity {name: "FastAPI"})
  SET e_fastapi.type = "Technology", e_fastapi.description = "Python web framework used for Hermes API layer."
MERGE (e_starlette:KnowledgeEntity {name: "Starlette"})
  SET e_starlette.type = "Technology", e_starlette.description = "ASGI toolkit used for SSE streaming in Hermes Gateway."
MERGE (e_kotlin:KnowledgeEntity {name: "Kotlin"})
  SET e_kotlin.type = "Technology", e_kotlin.description = "Language for Android Hermes client."
MERGE (e_compose:KnowledgeEntity {name: "Jetpack Compose"})
  SET e_compose.type = "Technology", e_compose.description = "UI toolkit for Android Hermes client."
MERGE (e_s6:KnowledgeEntity {name: "s6-overlay"})
  SET e_s6.type = "Technology", e_s6.description = "Process supervisor used in Hermes Agent Docker image."

// --- Sanitization Approaches ---
MERGE (e_scripted:KnowledgeEntity {name: "Scripted Sanitization"})
  SET e_scripted.type = "Pattern", e_scripted.description = "Deterministic Python/Bash-driven copy + regex replacement + verification; chosen as optimal via WSM/AHP."
MERGE (e_container:KnowledgeEntity {name: "Containerized Sanitization"})
  SET e_container.type = "Pattern", e_container.description = "Docker-based read-only mount pipeline; highest security but slower; kept as Plan B."
MERGE (e_manual:KnowledgeEntity {name: "Manual Sanitization"})
  SET e_manual.type = "Pattern", e_manual.description = "Human-driven file-by-file cleanup; rejected due to high risk of missed secrets."
MERGE (e_hybridgit:KnowledgeEntity {name: "Hybrid Git Sanitization"})
  SET e_hybridgit.type = "Pattern", e_hybridgit.description = "Scripted cleanup plus git filter-repo history rewrite; rejected as overkill."

// --- Concrete Artifacts ---
MERGE (e_sanpy:KnowledgeEntity {name: "sanitize.py"})
  SET e_sanpy.type = "Artifact", e_sanpy.description = "Python sanitizer implementing regex replacements, DB schema-only cleanup, and template memory files."
MERGE (e_sancfg:KnowledgeEntity {name: "sanitize-config.yaml"})
  SET e_sancfg.type = "Artifact", e_sancfg.description = "Declarative config for copy sources, replacement patterns, DB handling, and verification."
MERGE (e_dc:KnowledgeEntity {name: "her2code/docker-compose.yml"})
  SET e_dc.type = "Artifact", e_dc.description = "Final Docker Compose using network_mode: host and API_SERVER_PORT=18648."
MERGE (e_entry:KnowledgeEntity {name: "docker-entrypoint.sh"})
  SET e_entry.type = "Artifact", e_entry.description = "Entrypoint that strips Telegram from config.yaml in-place; fragile and symptom-fixing."
MERGE (e_proxy:KnowledgeEntity {name: "status-proxy.py"})
  SET e_proxy.type = "Artifact", e_proxy.description = "HTTP proxy adding /api/status because Desktop GUI contract was not researched; dead code."

// --- Orchestrator Errors ---
MERGE (e_err1:KnowledgeEntity {name: "Implement Before Research"})
  SET e_err1.type = "Error", e_err1.description = "Building Docker before reading Desktop AGENTS.md and verifying Gateway /health endpoint."
MERGE (e_err2:KnowledgeEntity {name: "Symptom Treatment"})
  SET e_err2.type = "Error", e_err2.description = "Writing status-proxy.py instead of fixing the real API contract mismatch."
MERGE (e_err3:KnowledgeEntity {name: "Repeated Entrypoint Failures"})
  SET e_err3.type = "Error", e_err3.description = "docker-entrypoint.sh broke config.yaml three times due to untested YAML mutation."
MERGE (e_err4:KnowledgeEntity {name: "No Contracts Before Integration"})
  SET e_err4.type = "Error", e_err4.description = "Integrating Hermes Agent, Desktop GUI, and docker-compose without verified endpoint/port contracts."
MERGE (e_err5:KnowledgeEntity {name: "Skipping Observers on Timeout"})
  SET e_err5.type = "Error", e_err5.description = "Health checks configured but results ignored; failures silently allowed to proceed."
MERGE (e_err6:KnowledgeEntity {name: "Clock-Based Timing"})
  SET e_err6.type = "Error", e_err6.description = "Using fixed sleeps and start_period instead of reactive readiness/health checks."
MERGE (e_err7:KnowledgeEntity {name: "Over-Engineering"})
  SET e_err7.type = "Error", e_err7.description = "Added bridge network + proxy + entrypoint wrapper instead of using network_mode: host."

// --- Methodology Gates / Solutions ---
MERGE (e_req1:KnowledgeEntity {name: "Research-Before-Implement Gate"})
  SET e_req1.type = "Pattern", e_req1.description = "Mandatory read of AGENTS.md/SKILL.md and curl-verified contracts before any write_file."
MERGE (e_req2:KnowledgeEntity {name: "Check-Contracts Gate"})
  SET e_req2.type = "Pattern", e_req2.description = "Create docs/research/contracts-<component>.md with verified endpoints before integration."
MERGE (e_req3:KnowledgeEntity {name: "Fail-Fast Gate"})
  SET e_req3.type = "Pattern", e_req3.description = "All wait loops have timeouts; entrypoints use set -euo pipefail; errors abort."
MERGE (e_req4:KnowledgeEntity {name: "Never-Skip-Observers Gate"})
  SET e_req4.type = "Pattern", e_req4.description = "Block until HEALTHCHECK=healthy or abort with logs after 120s."
MERGE (e_req5:KnowledgeEntity {name: "KISS/YAGNI Gate"})
  SET e_req5.type = "Pattern", e_req5.description = "Justify every new layer; prefer removing a layer over adding one; document deviations."
MERGE (e_nmhost:KnowledgeEntity {name: "network_mode: host"})
  SET e_nmhost.type = "Solution", e_nmhost.description = "Simple Docker network mode that eliminated need for bridge network and status proxy."
MERGE (e_timeout:KnowledgeEntity {name: "Timeout Loops"})
  SET e_timeout.type = "Solution", e_timeout.description = "Replace infinite while-sleep with timeout-bounded polling and explicit failure."
MERGE (e_pipefail:KnowledgeEntity {name: "set -euo pipefail"})
  SET e_pipefail.type = "Solution", e_pipefail.description = "Shell strict mode for immediate failure on errors and undefined variables."
MERGE (e_hcwait:KnowledgeEntity {name: "HEALTHCHECK-based Waiting"})
  SET e_hcwait.type = "Solution", e_hcwait.description = "Wait for Docker container Health.Status==healthy instead of blind sleeps."
MERGE (e_contractfiles:KnowledgeEntity {name: "Contract Files"})
  SET e_contractfiles.type = "Solution", e_contractfiles.description = "Markdown contracts with real curl request/response evidence per component pair."

// --- Process Patterns ---
MERGE (e_agentsmd:KnowledgeEntity {name: "AGENTS.md Single Source of Truth"})
  SET e_agentsmd.type = "Pattern", e_agentsmd.description = "One project file for conventions, build commands, pitfalls, lifecycle; loaded by orchestrator at Phase 0."
MERGE (e_devlog:KnowledgeEntity {name: "Deviation Log"})
  SET e_devlog.type = "Pattern", e_devlog.description = "docs/deviation-log.md records every rule violation with time/file/restriction/reason/risk."
MERGE (e_plugin:KnowledgeEntity {name: "Plugin Architecture"})
  SET e_plugin.type = "Pattern", e_plugin.description = "Fail-open plugin system that does not crash the agent when a plugin fails."
MERGE (e_failopen:KnowledgeEntity {name: "Fail-Open Design"})
  SET e_failopen.type = "Pattern", e_failopen.description = "Design where component failures degrade gracefully rather than block."
MERGE (e_wal:KnowledgeEntity {name: "SQLite WAL Mode"})
  SET e_wal.type = "Pattern", e_wal.description = "Write-ahead logging for SQLite with foreign keys and 0600 permissions."
MERGE (e_hmac:KnowledgeEntity {name: "HMAC-SHA256"})
  SET e_hmac.type = "Pattern", e_hmac.description = "Tamper-evidence mechanism for audit trail integrity."
MERGE (e_tdd:KnowledgeEntity {name: "TDD"})
  SET e_tdd.type = "Pattern", e_tdd.description = "RED-GREEN-REFACTOR cycle enforced for all code changes."
MERGE (e_skillrouter:KnowledgeEntity {name: "Skill Router"})
  SET e_skillrouter.type = "Pattern", e_skillrouter.description = "Runtime loading of Markdown skills into system prompt based on context triggers."
MERGE (e_worktree:KnowledgeEntity {name: "Worktree Isolation"})
  SET e_worktree.type = "Pattern", e_worktree.description = "Developers work in isolated git worktrees; Tech Lead merges."
MERGE (e_whitelist:KnowledgeEntity {name: "White-List Copy"})
  SET e_whitelist.type = "Pattern", e_whitelist.description = "Copy only explicitly listed sources with excludes for secrets and build artifacts."
MERGE (e_schemaonly:KnowledgeEntity {name: "Schema-Only DB Cleaning"})
  SET e_schemaonly.type = "Pattern", e_schemaonly.description = "Dump CREATE statements only, recreate empty DBs to preserve schema without user data."
MERGE (e_placeholder:KnowledgeEntity {name: "Placeholder Replacement"})
  SET e_placeholder.type = "Pattern", e_placeholder.description = "Replace real keys/IPs/IDs with <YOUR_*> placeholders for open-source publication."

// --- Security Tools ---
MERGE (e_gitleaks:KnowledgeEntity {name: "gitleaks"})
  SET e_gitleaks.type = "Tool", e_gitleaks.description = "Secret scanner used to verify 0 findings in sanitized her2code."
MERGE (e_semgrep:KnowledgeEntity {name: "semgrep"})
  SET e_semgrep.type = "Tool", e_semgrep.description = "SAST scanner for critical/high findings."
MERGE (e_bandit:KnowledgeEntity {name: "bandit"})
  SET e_bandit.type = "Tool", e_bandit.description = "Python security linter."
MERGE (e_pipaudit:KnowledgeEntity {name: "pip-audit"})
  SET e_pipaudit.type = "Tool", e_pipaudit.description = "Dependency vulnerability scanner."
MERGE (e_sastgate:KnowledgeEntity {name: "SAST Gate"})
  SET e_sastgate.type = "Process", e_sastgate.description = "Security gate: bandit, pip-audit, gitleaks, semgrep, npm audit before deploy."

// --- Relationships ---
MERGE (e_hermes)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_core)
MERGE (e_core)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_gateway)
MERGE (e_core)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_tools)
MERGE (e_core)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_session)
MERGE (e_core)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_api)
MERGE (e_gateway)-[:RELATES_TO {predicate: "PROVIDES", source: "LS-HER2CODE-ARCH"}]->(e_api)
MERGE (e_api)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_fastapi)
MERGE (e_api)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_starlette)
MERGE (e_session)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-RES"}]->(e_sqlite)
MERGE (e_android)-[:RELATES_TO {predicate: "DEPENDS_ON", source: "LS-HER2CODE-ARCH"}]->(e_api)
MERGE (e_android)-[:RELATES_TO {predicate: "DEPENDS_ON", source: "LS-HER2CODE-ARCH"}]->(e_gateway)
MERGE (e_android)-[:RELATES_TO {predicate: "DEPENDS_ON", source: "LS-HER2CODE-ARCH"}]->(e_voice)
MERGE (e_android)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_kotlin)
MERGE (e_android)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_compose)
MERGE (e_opencode)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_litellm)
MERGE (e_opencode)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_llama)
MERGE (e_litellm)-[:RELATES_TO {predicate: "ROUTES_TO", source: "LS-HER2CODE-ARCH"}]->(e_llama)
MERGE (e_mcp)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_claw)
MERGE (e_mcp)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_edu)
MERGE (e_mcp)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_code)
MERGE (e_mcp)-[:RELATES_TO {predicate: "INCLUDES", source: "LS-HER2CODE-ARCH"}]->(e_search)
MERGE (e_claw)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_neo4j)
MERGE (e_edu)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_neo4j)
MERGE (e_code)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_neo4j)
MERGE (e_hermes)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_docker)
MERGE (e_hermes)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_s6)
MERGE (e_hermes)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_neo4j)

MERGE (e_scripted)-[:RELATES_TO {predicate: "IMPROVES_ON", source: "LS-HER2CODE-SYS"}]->(e_manual)
MERGE (e_scripted)-[:RELATES_TO {predicate: "IMPROVES_ON", source: "LS-HER2CODE-SYS"}]->(e_hybridgit)
MERGE (e_container)-[:RELATES_TO {predicate: "IMPROVES_ON", source: "LS-HER2CODE-SYS"}]->(e_scripted)
MERGE (e_sanpy)-[:RELATES_TO {predicate: "IMPLEMENTS", source: "LS-HER2CODE-SANPY"}]->(e_scripted)
MERGE (e_sancfg)-[:RELATES_TO {predicate: "CONFIGURES", source: "LS-HER2CODE-SANCFG"}]->(e_sanpy)
MERGE (e_sanpy)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-SANPY"}]->(e_whitelist)
MERGE (e_sanpy)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-SANPY"}]->(e_schemaonly)
MERGE (e_sanpy)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-SANPY"}]->(e_placeholder)
MERGE (e_sastgate)-[:RELATES_TO {predicate: "VERIFIES", source: "LS-HER2CODE-REQ"}]->(e_scripted)
MERGE (e_gitleaks)-[:RELATES_TO {predicate: "PART_OF", source: "LS-HER2CODE-REQ"}]->(e_sastgate)
MERGE (e_semgrep)-[:RELATES_TO {predicate: "PART_OF", source: "LS-HER2CODE-REQ"}]->(e_sastgate)
MERGE (e_bandit)-[:RELATES_TO {predicate: "PART_OF", source: "LS-HER2CODE-REQ"}]->(e_sastgate)
MERGE (e_pipaudit)-[:RELATES_TO {predicate: "PART_OF", source: "LS-HER2CODE-REQ"}]->(e_sastgate)

MERGE (e_err1)-[:RELATES_TO {predicate: "CAUSES", source: "LS-HER2CODE-ORCH-REQ"}]->(e_proxy)
MERGE (e_err2)-[:RELATES_TO {predicate: "MANIFESTS_AS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_proxy)
MERGE (e_err3)-[:RELATES_TO {predicate: "MANIFESTS_AS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_entry)
MERGE (e_err4)-[:RELATES_TO {predicate: "CAUSES", source: "LS-HER2CODE-ORCH-REQ"}]->(e_dc)
MERGE (e_err7)-[:RELATES_TO {predicate: "MANIFESTS_AS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_proxy)
MERGE (e_err7)-[:RELATES_TO {predicate: "MANIFESTS_AS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_entry)
MERGE (e_nmhost)-[:RELATES_TO {predicate: "REPLACES", source: "LS-HER2CODE-ORCH-REQ"}]->(e_proxy)
MERGE (e_nmhost)-[:RELATES_TO {predicate: "REPLACES", source: "LS-HER2CODE-ORCH-REQ"}]->(e_err7)
MERGE (e_req1)-[:RELATES_TO {predicate: "PREVENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_err1)
MERGE (e_req2)-[:RELATES_TO {predicate: "PREVENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_err2)
MERGE (e_req2)-[:RELATES_TO {predicate: "PREVENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_err4)
MERGE (e_req3)-[:RELATES_TO {predicate: "PREVENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_err3)
MERGE (e_req3)-[:RELATES_TO {predicate: "PREVENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_err6)
MERGE (e_req4)-[:RELATES_TO {predicate: "PREVENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_err5)
MERGE (e_req5)-[:RELATES_TO {predicate: "PREVENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_err7)
MERGE (e_timeout)-[:RELATES_TO {predicate: "IMPLEMENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_req3)
MERGE (e_pipefail)-[:RELATES_TO {predicate: "IMPLEMENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_req3)
MERGE (e_hcwait)-[:RELATES_TO {predicate: "IMPLEMENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_req4)
MERGE (e_contractfiles)-[:RELATES_TO {predicate: "IMPLEMENTS", source: "LS-HER2CODE-ORCH-REQ"}]->(e_req2)

MERGE (e_agentsmd)-[:RELATES_TO {predicate: "SUPPORTS", source: "LS-HER2CODE-REQ"}]->(e_req1)
MERGE (e_devlog)-[:RELATES_TO {predicate: "SUPPORTS", source: "LS-HER2CODE-REQ"}]->(e_req5)
MERGE (e_plugin)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_failopen)
MERGE (e_hermes)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_plugin)
MERGE (e_hermes)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_skillrouter)
MERGE (e_session)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-ARCH"}]->(e_wal)
MERGE (e_hermes)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-REQ"}]->(e_hmac)
MERGE (e_hermes)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-REQ"}]->(e_tdd)
MERGE (e_hermes)-[:RELATES_TO {predicate: "USES", source: "LS-HER2CODE-REQ"}]->(e_worktree)

// --- HAS_SOURCE links ---
WITH *
MATCH (ls:LearningSource)
WHERE ls.id STARTS WITH "LS-HER2CODE"
MATCH (ke:KnowledgeEntity)
WHERE ke.name IN [
  "Hermes Agent","Hermes Agent Core","Android Client","OpenCode+","Neo4j","Docker Compose","SQLite",
  "Hermes Gateway","Hermes API Server","Tool Orchestrator","Session DB","LiteLLM Proxy","Llama.cpp Server",
  "Voice Proxy","MCP","Claw-Graph MCP","Education-Graph MCP","Codebase-Graph MCP","Searchbox MCP",
  "FastAPI","Starlette","Kotlin","Jetpack Compose","s6-overlay",
  "Scripted Sanitization","Containerized Sanitization","Manual Sanitization","Hybrid Git Sanitization",
  "sanitize.py","sanitize-config.yaml","her2code/docker-compose.yml","docker-entrypoint.sh","status-proxy.py",
  "Implement Before Research","Symptom Treatment","Repeated Entrypoint Failures","No Contracts Before Integration",
  "Skipping Observers on Timeout","Clock-Based Timing","Over-Engineering",
  "Research-Before-Implement Gate","Check-Contracts Gate","Fail-Fast Gate","Never-Skip-Observers Gate","KISS/YAGNI Gate",
  "network_mode: host","Timeout Loops","set -euo pipefail","HEALTHCHECK-based Waiting","Contract Files",
  "AGENTS.md Single Source of Truth","Deviation Log","Plugin Architecture","Fail-Open Design","SQLite WAL Mode",
  "HMAC-SHA256","TDD","Skill Router","Worktree Isolation","White-List Copy","Schema-Only DB Cleaning","Placeholder Replacement",
  "gitleaks","semgrep","bandit","pip-audit","SAST Gate"
]
MERGE (ke)-[:HAS_SOURCE]->(ls)

// --- Fact nodes (key triples) ---
MERGE (f1:Fact {id: "F-HER2CODE-001"})
  SET f1.subject = "Hermes Agent Core", f1.predicate = "contains", f1.object = "37+ components"
MERGE (f1)-[:ABOUT]->(e_core)
MERGE (f1)-[:HAS_SOURCE]->(ls_arch)

MERGE (f2:Fact {id: "F-HER2CODE-002"})
  SET f2.subject = "Scripted Sanitization", f2.predicate = "scored", f2.object = "462 WSM points vs 436 containerized"
MERGE (f2)-[:ABOUT]->(e_scripted)
MERGE (f2)-[:HAS_SOURCE]->(ls_sys)

MERGE (f3:Fact {id: "F-HER2CODE-003"})
  SET f3.subject = "state.db", f3.predicate = "cleared", f3.object = "498 sessions / 25,052 messages / 535 MB"
MERGE (f3)-[:ABOUT]->(e_session)
MERGE (f3)-[:HAS_SOURCE]->(ls_res)

MERGE (f4:Fact {id: "F-HER2CODE-004"})
  SET f4.subject = "status-proxy.py", f4.predicate = "exists because", f4.object = "Desktop GUI /api/status expectation not verified"
MERGE (f4)-[:ABOUT]->(e_proxy)
MERGE (f4)-[:HAS_SOURCE]->(ls_orch)

MERGE (f5:Fact {id: "F-HER2CODE-005"})
  SET f5.subject = "docker-entrypoint.sh", f5.predicate = "mutates", f5.object = "config.yaml in-place without backup"
MERGE (f5)-[:ABOUT]->(e_entry)
MERGE (f5)-[:HAS_SOURCE]->(ls_orch)

MERGE (f6:Fact {id: "F-HER2CODE-006"})
  SET f6.subject = "docker-entrypoint.sh", f6.predicate = "uses", f6.object = "infinite while-sleep loop without timeout"
MERGE (f6)-[:ABOUT]->(e_entry)
MERGE (f6)-[:HAS_SOURCE]->(ls_orch)

MERGE (f7:Fact {id: "F-HER2CODE-007"})
  SET f7.subject = "docker-compose.yml", f7.predicate = "uses", f7.object = "network_mode: host and API_SERVER_PORT=18648"
MERGE (f7)-[:ABOUT]->(e_dc)
MERGE (f7)-[:HAS_SOURCE]->(ls_dc)

MERGE (f8:Fact {id: "F-HER2CODE-008"})
  SET f8.subject = "Orchestrator", f8.predicate = "methodological errors count", f8.object = "7 errors mapped to 5 gates"
MERGE (f8)-[:ABOUT]->(e_req1)
MERGE (f8)-[:HAS_SOURCE]->(ls_orch)

MERGE (f9:Fact {id: "F-HER2CODE-009"})
  SET f9.subject = "Sanitization", f9.predicate = "verified by", f9.object = "0 gitleaks findings, 0 /home/user occurrences"
MERGE (f9)-[:ABOUT]->(e_scripted)
MERGE (f9)-[:HAS_SOURCE]->(ls_log)

MERGE (f10:Fact {id: "F-HER2CODE-010"})
  SET f10.subject = "BUILD.md", f10.predicate = "documents", f10.object = "Dockerfile SHA update for uv base image"
MERGE (f10)-[:ABOUT]->(e_docker)
MERGE (f10)-[:HAS_SOURCE]->(ls_build)
