# SegTree & Consolidation Code Review Findings

Audit date: 2026-07-03. Modules: `plugins/memory/segtree/`, `agent/consolidation_manager.py`.

## Performance bugs

### `_get_session` — O(n) per message (HIGH)

**File:** `plugins/memory/segtree/segment_tree.py:132-135`

```python
def _get_session(self, msg_id: int) -> str:
    idx = self._leaf_msg_ids.index(msg_id)  # ← O(n) scan
    return self._leaves[idx][1]
```

Every session-filtered query result iterates through all result msg_ids, each calling `.index()` — O(k·n). For 100K messages and a 1000-result full-range query with session filter, that's 100M operations (~23s).

**Fix:** Build a dict `{msg_id: (session_id, timestamp)}` during `build()`, use `self._lookup[msg_id][0]` for O(1).

### `_query_tree` sorted merge — O(m log m) per node (MEDIUM)

**File:** `plugins/memory/segtree/segment_tree.py:130`

```python
return sorted(left + right)
```

Called at every recursive merge during both `build` and `query_range`. At the root node for a full-range query, this is O(n log n). For 100K messages, the root-level query does a 100K-element sort — expensive on every call.

**Fix:** Store pre-sorted arrays (`left_ids + right_ids` are already sorted because leaves are sorted; merge with `heapq.merge` or two-pointer).

### `_compute_tfidf` — O(n) per query term (LOW)

**File:** `plugins/memory/segtree/temporal_scorer.py:150`

```python
tf = content_terms.count(term) / content_len  # ← O(n)
```

For 500-word content × 5 query terms = 2500 operations/call. Acceptable for current scale, but should use `collections.Counter`.

## Dead / redundant code

### `SegTreeMem.consolidate()` — never called by ConsolidationManager

**File:** `plugins/memory/segtree/__init__.py:242-306`

ConsolidationManager writes directly to `memory_consolidations` via `_write_consolidation()`. SegTreeMem's `consolidate()` method:
- Has no caller in the codebase
- Writes to the same table with a different connection (non-atomic, no transaction)
- Missing `token_count`, `model_used`, `hmac` fields
- Missing `UPDATE messages SET active=0`

**Action:** Either wire it into ConsolidationManager as a post-write callback, or remove it. In its current state it's dead code that could cause data inconsistency if accidentally invoked.

### `_mark_messages_rewound()` — standalone dead code (LOW)

**File:** `agent/consolidation_manager.py:439-454`

Duplicates the UPDATE logic already in `_write_consolidation()` but without a transaction. No caller in the codebase. Safe to remove.

### Two consolidation write paths diverge

| Path | Location | What |
|---|---|---|
| `_write_consolidation()` | `consolidation_manager.py:378` | INSERT + UPDATE in `BEGIN IMMEDIATE`/`COMMIT` |
| `SegTreeMem.consolidate()` | `segtree/__init__.py:242` | INSERT only, separate connection, no transaction |

If both were active, they'd race on `memory_consolidations` and the messages table.

## Missing test coverage

| Module | Tests | Risk |
|---|---|---|
| `segment_tree.py` | 0 | No unit tests for build, query_range, query_k_nearest, edge cases (duplicate timestamps, empty trees, session filtering) |
| `temporal_scorer.py` | 0 | No tests for TF-IDF computation, time decay, zero-match, empty inputs |
| `SegTreeMem.__init__.py` | 0 | No integration tests for warmup, prefetch_temporal, consolidate |
| `observer-hook/__init__.py` | 0 | No tests for activity gate, worker spawn, Neo4j write, observer session detection |

## ConsolidationManager observations

### `_build_placeholder_summary` — graceful but never reached in practice

**File:** `agent/consolidation_manager.py:350-374`

Only called when `_mm` lacks `_call_consolidation_llm`. In production MemoryManager always has this method. Falls back to extracting message snippets from the prompt — useful as a safety net but untested.

### Token estimation is rough

**File:** `agent/consolidation_manager.py:531-535`

`len(text) // 4` is English-biased. `len(text)` in Python 3 returns Unicode character count (not bytes), so Russian text has the same `len()` as English of the same visual length. The real issue is BPE tokenization: Russian text produces more tokens per character because Cyrillic subword units are less common in training data. Effective ratio is ~2-3 chars/token for Russian vs ~4 chars/token for English. The budget will be ~1.5-2x oversized for Russian text — not a correctness bug, but reduces effective consolidation depth.

### Placeholder session_id in prompt

**File:** `agent/consolidation_manager.py:317`

`PROMPT_TEMPLATE.format(session_id="(session)", ...)` — the placeholder `(session)` is passed to the LLM instead of the real session ID. Low impact (LLM doesn't need the real ID for summarization), but confusing in prompt traces.
