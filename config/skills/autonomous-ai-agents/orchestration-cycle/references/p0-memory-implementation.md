# P0 Memory Scaffolding — Implementation Results

> Cycle: `hermes-p0-memory_20260615_232649` (2026-06-16)
> Full report: `/home/user/dev/codemes/hermes-p0-memory_20260615_232649/`
> Code: `~/.hermes/hermes-agent/`

## Files Modified/Created (7 files, ~1900 LOC)

| File | What |
|------|------|
| `agent/memory_provider.py` | +`prefetch_temporal()`, +`consolidate()`, +`is_system_provider` |
| `plugins/memory/segtree/__init__.py` | SegTreeMem — system provider, 252ms temporal queries |
| `plugins/memory/segtree/segment_tree.py` | Binary segment tree, O(log n) range queries |
| `plugins/memory/segtree/temporal_scorer.py` | TF-IDF × exponential time decay (half-life 7d) |
| `agent/consolidation_manager.py` | TiMem 4-tier, HMAC, atomic SQLite, LLM prompt builder |
| `agent/memory_manager.py` | +`add_system_provider()`, +`prefetch_temporal_all()`, +`_call_consolidation_llm()` |
| `hermes_state.py` | +`memory_consolidations` table, +`after_ts`/`before_ts` in `search_messages()` |

## Key Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|:------:|
| Temporal query | 252ms | <500ms | ✅ |
| Tests | 323/323 | 0 failures | ✅ |
| AC coverage | 6/6 | all | ✅ |
| LLM consolidation | 9.4s | via DeepSeek | ✅ |
| Warmup | 1531ms | <200ms | ⚠️ deferred |

## Architecture Decisions

- **D1:** SegTreeMem = system provider. Bypasses 1-external-provider limit.
- **D2:** Exponential time decay, half-life 7 days
- **D3:** Consolidation trigger: on_session_end + cron daily
- **D4:** Structured bullet prompts
- **D5:** In-memory Python segment tree
- **D6:** HMAC-SHA256 tamper-evidence
- **D8:** Configurable tier boundaries (24h/7d/30d)

## What Still Needs Wiring

1. `agent_init.py` does NOT call add_system_provider(SegTreeMem()).
2. on_session_end trigger exists but 0 consolidation runs since deploy.
3. Cron consolidate_daily() not registered.

## Next Candidates (from research sessions)

| # | What | Effort | Why |
|---|------|:------:|-----|
| 1 | **Reranker** — LLM scores BM25 candidates | ~100 LOC | Better than vector search |
| 2 | **Provenance Grounding** — memory_trace(fact) tool | ~80 LOC | source_message_ids already in schema |
| 3 | **Silence Gate** — relevance threshold | ~150 LOC | Saves tokens |
| 4 | **Repo-map via tree-sitter** | ~200 LOC | Structural context in system prompt |
| 5 | **KG integration** — code entities to Neo4j | ~150 LOC | Link code to research papers |

## Note on External Memory Providers

User decided: **FTS5 + SegTreeMem is sufficient**. External plugins (Mem0, Honcho, Holographic — 500K LOC total) add complexity without clear benefit. config: `memory.provider: ''` — none active. Reranker preferred over external semantic backend.

## User's Preferences

- **Simplicity:** don't add external services when built-in works.
- **Fast action:** 5 steps into 1 command. Act, don't deliberate.
- **Autonomous testing:** test yourself, don't ask user to verify.
- **Reranker + Provenance:** next most-wanted features after P0.
- **Russian speaker.** Tech lead, deep architectural questions.
