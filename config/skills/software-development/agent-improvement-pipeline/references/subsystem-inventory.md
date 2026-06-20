# Agent Improvement Pipeline — Subsystem Inventory

Built 2026-06-13 across 9 orchestration phases. All code under `${HOME}/plugins/` (deployed as `${HOME}/dev/codemes_apk/plugins/` in distribution).

## S1: Audit & Observability
- **Plugin:** `plugins/audit/`
- **DB:** `~/.hermes/audit.db` (SQLite, 10 tables, retention 5 days)
- **Components:** AuditDB, SessionRecorder, ClaimEngine (5 verifiers), HallucinationDetector (6 types), EscalationManager (6 levels)
- **Slash:** `/audit`, `/retro`
- **Tests:** 434 (in `plugins/audit/tests/`)
- **Architecture:** `docs/architecture/agent-improvement-pipeline.md`
- **Plan:** `.hermes/plans/2026-06-13_001000-agent-improvement-pipeline.md`

## S2: Mutual Audit
- **Plugin:** `plugins/mutual_audit/`
- **DB:** Extends audit.db (migration v2, 5 new tables)
- **Components:** MutualAuditDB, PostSessionAnalyzer, WasteDetector, CrossAgentReviewer (Constitutional AI rubric), ImprovementEngine, CritiqueHandler
- **Slash:** `/critique`
- **Tests:** 283 (in `plugins/mutual_audit/tests/`)
- **Architecture:** `docs/architecture/agent-improvement-pipeline-s2-mutual-audit.md`
- **Plan:** `.hermes/plans/2026-06-13-mutual-audit.md`

## S3: Quality Metrics
- **Plugin:** `plugins/metrics/`
- **DB:** `~/.hermes/metrics.db` (SQLite, 4 tables)
- **Components:** MetricsDB, MetricsCollector, TrendEngine (linear regression), RetroGenerator, ReportGenerator
- **Slash:** `/metrics`
- **Tests:** 121 (in `plugins/metrics/tests/`)
- **Architecture:** `docs/architecture/agent-improvement-pipeline-s3-metrics.md`
- **Plan:** `.hermes/plans/2026-06-13-metrics.md`

## S4: Knowledge Graph
- **Plugin:** `plugins/knowledge_graph/`
- **DB:** Neo4j (localhost:7474), new labels: `:Practice`, `:PracticeApplication`, `:PracticeOutcome`
- **Components:** PracticeGraph (Python API), 30 integration tests
- **Bridge:** `USES_CONCEPT` edges → education graph (68 KnowledgeEntity)
- **Field:** `usage_experience` already exists on all KnowledgeEntity (empty string) — populated with structured JSON
- **Tests:** 30 (in `plugins/knowledge_graph/tests/`)
- **Architecture:** `docs/architecture/agent-improvement-pipeline-s4-knowledge-graph.md`

## Total: 868 tests, 47.75s full suite

## Key files for future sessions
- Full test run: `python3 -m pytest plugins/audit/tests/ plugins/mutual_audit/tests/ plugins/metrics/tests/ plugins/knowledge_graph/tests/ -v`
- Security findings: `${HOME}/vulnerabilities.md` (10 findings, all fixed)
- Neo4j driver: `pip install neo4j --break-system-packages` (PEP 668)
