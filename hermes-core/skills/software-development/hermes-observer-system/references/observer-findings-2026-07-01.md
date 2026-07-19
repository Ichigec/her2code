# Observer Findings — 2026-07-01

## Cascade Architecture

```
claw-daily cron (02:08) ──→ claw-orchestrator session ──→ 4 observers (auditor, critic, IG, KC)
                                                                        │
                          ┌─────────────────────────────────────────────┘
                          ▼
knowledge-curator cron (04:07) ──→ observer ──→ observer-of-observer (depth=2)
                                                                        │
                          ┌─────────────────────────────────────────────┘
                          ▼
Session observers (20:14-20:19) ──→ 5 observers spawned for 3 user sessions
                                     ALL UNANSWERED — 1 message each, no assistant reply
```

## Key Findings

### 1. Knowledge-curator pipeline silently broken → PARTIALLY RESOLVED (2026-07-01)
- ~~Script returns `exit 0`, finds 0 files~~ → **FIXED**: `_resolve_real_home()` with 4-tier fallback + `dev/codemes` sanity check
- Root cause was TWO bugs: (a) empty `HERMES_HOME=""` → `Path("")` = `.`, (b) `Path.home()` returns session-isolated `~/.hermes/home/` under Hermes Agent
- 1789 `.md` files now found correctly in dry-run
- Remaining: no relationships, no embeddings, no source tracking — planned as 5-pass pipeline v2 (see `neo4j-knowledge-graph` → references/knowledge-curator-cron.md §Planned improvements)

### 2. Observer-of-observer is waste
- 3-level chain: `cron → observer → observer-of-observer`
- Observer-of-observer restates same 4 findings word-for-word
- No incremental insight, just token burn

### 3. AGENTS.md pollution
- 12KB of project conventions injected into every observer/cron `terminal()` call
- At 4 observer sessions per cycle: ~48K tokens wasted on irrelevant context

### 4. claw-daily: 37K tokens for 5 deterministic scripts
- LLM agent runs `claw-discovery.py → claw-process.py → ...` sequentially
- Zero LLM reasoning needed — all 5 phases are fixed scripts
- Recommendation: `no_agent=true` wrapper script saves ~1.1M tokens/month

### 5. Neo4j schema drift in claw scripts
- `claw-discovery.py` queries `tool_id`, `tool_name`, `tool_type` — properties don't exist
- Actual: `id`, `name`, `type`
- DBMS warnings every cycle, never fixed

### 6. Phase 5 audit → Neo4j gap
- Audit markdown produced with 20+ orphan tools, 63 rebudget, 109 prune
- Zero AuditFinding nodes written to Neo4j
- Cross-cycle trend analysis impossible

## Session Observer Failures

5 observer sessions created at 20:14-20:19 for 3 user sessions:
- `20260701_195104_b7f068` (Prevent agent preset auto-off) — auditor, critic, IG, KC
- `20260701_195949_3d5f7a` — auditor, critic, KC, IG
- `20260701_195714_424c97` (Comparing Three AI Models) — IG only

All 5 have exactly 1 message (task dispatch), zero assistant replies. Findings NOT written to Neo4j.
Root cause unknown — possibly observer dispatch mechanism broken, or model/proxy unavailable at the time.
