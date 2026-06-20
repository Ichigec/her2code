# Knowledge Curator — LLM Ingest Pipeline

The primary automated ingestion pipeline for the education knowledge graph — runs as a cron job or manually.

## Script

```
~/.hermes/scripts/knowledge-curator-ingest-llm.py
```

**Purpose:** Scans markdown research artifacts, extracts typed knowledge entities via local LLM (Qwen 3.6 35B, llama.cpp :8092), and MERGEs them into Neo4j as `KnowledgeEntity` nodes.

**Scan roots:**
- `~/dev/codemes/` (~530+ `.md` files)
- `~/docs/research/` (~5 `.md` files)

**Entity types extracted:** Paper, Pattern, Gap, Trend, BestPractice, Concept

## How It Works

1. `find_artifacts()` — recursively globs `*.md` files in scan roots (excludes `.git/`, `node_modules/`)
2. `state_hash(path)` — computes `sha256(path:st_mtime:st_size)[:16]` to detect changes
3. Loads previous state from `~/.hermes/skills/.curator_state` (JSON: `{path: hash}`)
4. Skips unchanged files; for new/changed files:
   - Reads content, sends first 3500 chars to LLM with extraction prompt
   - LLM returns JSON array of `{n: name, t: type, d: description}`
   - `MERGE`s each entity into Neo4j as `KnowledgeEntity` node
5. Saves updated state

**LLM prompt:** Extracts up to 8 entities per file. Temperature 0.1, max_tokens 600.

## Pitfalls

### State saved even when LLM fails → need --force

**Observed 2026-06-19:** When llama-server is down (port 8092 connection refused), the curator still saves `state[pstr] = h` after each file — marking it as "processed" even though zero entities were ingested. The output shows `none` for each file, but the state hash is checkpointed.

On the next run, all those files are skipped because their hashes match. The curator reports `0 files processed, 0 entities ingested` — silently losing the opportunity to re-process.

**Fix:** After fixing the LLM server, re-run with `--force`:
```bash
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py --force
```

This ignores the saved state and re-processes every file.

### LLM server down: restart llama-server on :8092

The curator depends on a local llama.cpp server at `http://127.0.0.1:8092/v1` (env: `LLAMA_URL`). When it's down, every file fails with `Connection refused`.

**Quick restart (Jetson):**
```bash
# Kill any stale processes on the port
fuser -k 8092/tcp 2>/dev/null; sleep 2

# Start with the Qwen 3.6 35B profile (BF16, MTP, 8092)
nohup /home/user/dev/llama.cpp/build/bin/llama-server \
  --model <MODEL_PATH> \
  --mmproj <MODEL_PATH> \
  --host 127.0.0.1 --port 8092 \
  --ctx-size 32768 --n-gpu-layers 41 --threads 20 \
  --batch-size 512 --ubatch-size 512 --parallel 2 \
  --cont-batching --alias qwen3.6-35b-heretic \
  --flash-attn on --no-mmap --direct-io \
  --kv-unified --jinja --reasoning off \
  >> /home/user/cursor/opencode+/.run/llama-8092.log 2>&1 &

# Wait for ready (model loads in ~15-30 seconds)
for i in $(seq 1 30); do
  if curl -fsS -m 3 http://127.0.0.1:8092/v1/models >/dev/null 2>&1; then
    echo "llama-server ready"; break
  fi; sleep 2
done
```

**Pitfall — Dify/port conflict:** Dify occupies port 8090 by default. The curator uses 8092 (set by the `llama-qwen-heretic` profile). Do NOT use port 8090 for llama-server — it will conflict with Dify's Next.js app.

**Alternative:** Use the managed start script with the qwen-heretic profile:
```bash
OPENCODE_PLUS_LLAMA_PROFILE=llama-qwen-heretic \
  bash /home/user/cursor/opencode+/start-llama-qwen.sh --daemon
```

### State file not saved incrementally (FIXED)

**Original behavior:** `save_state()` called only once after the entire loop completes. If the script times out or is killed mid-run, all progress is lost and the next run starts from scratch.

**Fix applied (2026-06-17):** Checkpoint state every 10 files:
```python
if not dry_run and processed % 10 == 0:
    save_state(state)
```

### Runtime: ~15-30 minutes for full scan (546 files)

With 546 markdown files, ~8-16 seconds per file (LLM call + Neo4j ingest), a full force-scan completes in approximately 15-30 minutes on the Jetson GB10. The script checkpoints state every 10 files, so timeouts or interruptions resume cleanly without re-processing. Observed: 2026-06-19 — full scan of 546 files completed across two runs (first was interrupted by 600s timeout; second picked up remaining and found 0 left).

### Background process stdout invisible

When running in background mode, Python's `print()` output is not captured by the process monitor — even with `flush=True` and `PYTHONUNBUFFERED=1`. 

**Workaround:** Verify progress via Neo4j queries:
```bash
curl -s -u neo4j:changeme -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN count(ke) as c"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```

Check the state file directly to see how many files have been processed:
```bash
python3 -c "import json; s=json.loads(open('$HOME/.hermes/skills/.curator_state').read()); print(len(s))"
```

## Manual Run

```bash
# Normal run (processes new/changed files only)
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py

# Dry run (no LLM/Neo4j calls, just prints what would be processed)
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py --dry-run

# Force re-process all files (ignores state hash — use after LLM server outage)
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py --force
```

## Verification

After a run, verify entities were ingested:
```bash
# Total KnowledgeEntity count
curl -s -u neo4j:changeme -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN count(ke) as c"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# Recent entities (by type)
curl -s -u neo4j:changeme -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN ke.type, count(ke) as cnt ORDER BY cnt DESC"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```
