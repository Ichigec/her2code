# Knowledge Curator — LLM Ingest Pipeline (v2)

The primary automated ingestion pipeline for the education knowledge graph — runs as a cron job or manually. v2 adds: paper discovery + deep-read, 14+ entity types, relation extraction, confidence scoring, CodeExample nodes, and health monitoring.

## Architecture (v2)

```
Daily cron (2:00) → curator-daily.sh
  ├── Phase A: paper-collector.py     arXiv → Semantic Scholar → Score → Top-K queue
  ├── Phase B: paper-deep-read.py     PDF→text→Qwen 35B→entities+relations+code→Neo4j
  └── Phase C: knowledge-curator-ingest-llm.py   .md files→Qwen→entities+relations→Neo4j
```

Key improvement: the pipeline now discovers *new* scientific papers daily (arXiv), scores them by composite quality (citations × venue × h-index × recency × relevance), deep-reads top papers, and ingests structured knowledge into Neo4j with full relationship graphs. Static markdown files still processed as before.

## Scripts (v2)

| Script | Purpose | New in v2? |
|--------|---------|:---:|
| `~/.hermes/scripts/curator-daily.sh` | Daily orchestrator: Phase A→B→C + health check | ✅ |
| `~/.hermes/scripts/paper-collector.py` | arXiv + Semantic Scholar → composite scoring → top-K | ✅ |
| `~/.hermes/scripts/paper-deep-read.py` | PDF→text→Qwen 35B extraction→Neo4j (14 types + relations + code) | ✅ |
| `~/.hermes/scripts/knowledge-curator-ingest-llm.py` | .md artifact scanner (updated to 14+ types + relations) | 🔄 |

## How It Works (v2 — Multi-Pass Extraction)

1. **Phase A (paper-collector.py):**
   - Fetches new papers from arXiv API (categories: cs.AI, cs.CL, cs.LG, cs.MA)
   - Enriches with Semantic Scholar (citation count, author h-index, venue)
   - Computes composite quality score: `0.25·log(cit) + 0.20·venue_tier + 0.15·h_index + 0.25·recency + 0.15·LLM_relevance`
   - Ranks and saves top-K to `~/.hermes/paper_queue/YYYY-MM-DD/papers.json`

2. **Phase B (paper-deep-read.py):**
   - Downloads PDF from arXiv → `pdftotext` → first 8000 chars of text
   - Qwen 3.6 35B (llama.cpp :8092) extracts structured knowledge:
     - `paper_meta`: title, year, venue, arxiv_id
     - `entities` (14+ types, 8-15 per paper): Algorithm, Framework, Model, Pattern, Concept, CodeExample, Dataset, Metric, Tool, Organization, Author, ProgrammingLanguage, Benchmark, Gap, BestPractice
     - `relationships` (with predicates): IMPLEMENTS, IMPROVES_ON, USES, DESCRIBES, DERIVED_FROM, EVALUATED_ON, OUTPERFORMS, EXTENDS, COMPARES_TO, TRAINED_ON, BUILT_WITH
     - `code_examples`: language, code, what it demonstrates
     - `citations`: arxiv IDs of cited papers
   - Ingests to Neo4j: Paper nodes, KnowledgeEntity nodes (MERGE by name), RELATES_TO edges, CodeExample nodes → IMPLEMENTS edges, Paper → CITES → Paper edges

3. **Phase C (knowledge-curator-ingest-llm.py):**
   - Scans `~/dev/codemes/` and `~/docs/research/` for `.md` files
   - Skips unchanged files (state hash: `sha256(path:mtime:size)[:16]`)
   - Qwen 3.6 35B extracts: entities (14+ types) + relations (with predicates)
   - MERGEs entities + relations into Neo4j
   - State checkpointed every 10 files

**LLM prompt (v2):** 14+ entity types, 6 predicate types, confidence scores, max 12 entities + 6 relations per file. See script source for the exact prompt template.

**Entity types (v2 — 14+):** Paper, Algorithm, Framework, Model, Pattern, Concept, CodeExample, Dataset, Metric, Tool, Organization, Author, ProgrammingLanguage, Benchmark, Gap, BestPractice

**Relation predicates:** IMPLEMENTS, IMPROVES_ON, USES, DESCRIBES, DERIVED_FROM, EVALUATED_ON, OUTPERFORMS, EXTENDS, COMPARES_TO, TRAINED_ON, BUILT_WITH

**New Neo4j node types (v2):** Paper (arxiv_id UNIQUE, title, year, venue), CodeExample (name UNIQUE, language, code, loc), Community (name UNIQUE — for GraphRAG clustering), CuratorRun (timestamp, status, papers_processed, entities_ingested, relationships_created)

**New Neo4j relationships (v2):** Paper→CITES→Paper, KnowledgeEntity→EXTRACTED_FROM→Paper, CodeExample→IMPLEMENTS→KnowledgeEntity, KnowledgeEntity→BELONGS_TO→Community

## Pitfalls

### Path resolution broken: 0 files found with 3633 on disk (FIXED 2026-07-01)

**Two root causes:**

1. **Empty `HERMES_HOME=""`** — when the env var is set but empty, `os.environ.get("HERMES_HOME", default)` returns `""` (NOT the default). `Path("")` resolves to `.` (cwd), so `_REAL_HOME` becomes `.` and scan roots `dev/codemes` and `docs/research` don't exist.

2. **Redirected `HOME` under Hermes Agent** — when `HERMES_HOME` is NOT set, `Path.home()` returns the session-isolated directory (`~/.hermes/home/`), NOT the real home (`/home/user`). So scan roots resolve to `~/.hermes/home/dev/codemes/` — which doesn't exist.

**Reproduction (before fix):**
```bash
# Scenario A: HERMES_HOME= (empty string)
HERMES_HOME= python3 knowledge-curator-ingest-llm.py --dry-run
# → Done: 0 files processed

# Scenario B: HERMES_HOME not set (cron)
env -u HERMES_HOME python3 knowledge-curator-ingest-llm.py --dry-run
# → Done: 0 files processed
```

**Fix:** `_resolve_real_home()` with 4-tier fallback + validation:
```python
def _resolve_real_home() -> Path:
    # 1. HERMES_HOME (non-empty guard via .strip())
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        p = Path(hermes_home)
        return p.parent if p.name == ".hermes" else p
    # 2. expanduser("~") with dev/codemes sanity check
    expanded = Path(os.path.expanduser("~"))
    if (expanded / "dev" / "codemes").exists():
        return expanded
    # 3. /home/$USER
    # 4. /home/user
```

**Verification after fix:**
```bash
HERMES_HOME= python3 knowledge-curator-ingest-llm.py --dry-run --force | tail -1
# → Done: 1789 files processed, 0 entities ingested.  ✅
```

### Planned improvements: 5-pass pipeline (2026-07-01)

The current script is a **single-pass flat extractor**: entities are MERGEd as standalone nodes with no relationships, no embeddings, no source tracking. The planned v2 pipeline adds 4 more passes:

| Pass | What | Output |
|------|------|--------|
| 1. Extract | 14+ entity types (Paper, Algorithm, Framework, CodeExample, ...) | KnowledgeEntity + LearningSource + Fact |
| 2. Resolve | Deduplication via name + embedding cosine | EQUIVALENT_TO, SUPERSEDES |
| 3. Relate | Intra-file + cross-file + cross-domain links | RELATES_TO, HAS_SOURCE, MENTIONS_TOOL |
| 4. Embed | 384-dim vectors (all-MiniLM-L6-v2) | embedding[] + vector index |
| 5. Verify | Health status, stats, error tracking | CuratorRun nodes |

Full plan: see main conversation 2026-07-01 «План улучшения Knowledge Curator».

### State saved even when LLM fails → need --force (FIXED in code)

**Status:** This issue has been **fixed** in the current code. When `call_llm()` returns `None` (LLM error/connection refused), the script now does `continue` — state is NOT saved for failed files, so they will be retried on the next run.

**Historical context (pre-fix, 2026-06-19):** The old code saved `state[pstr] = h` after every file regardless of LLM success, marking failed files as "processed." On the next run, those files were skipped because hashes matched, silently losing the opportunity to re-process.

**Current behavior:** LLM failures are transient — the script prints `"{file}: LLM extraction failed, will retry"` and moves to the next file without saving state. The file will be reprocessed on the next run.

**When to still use `--force`:** If the LLM was up but producing garbage (e.g., reasoning-only empty content, wrong model loaded), the script may have saved state for files that got bad extractions. In that case:

```bash
python3 -c "
import json
state_path = '$HOME/.hermes/skills/.curator_state'
with open(state_path) as f:
    state = json.load(f)
# Remove specific failed entries — copy paths from the failure output
failed = [
    '/home/user/dev/codemes/path/to/failed-file.md',
    '/home/user/dev/codemes/path/to/other-failed-file.md',
]
for path in failed:
    if path in state: del state[path]
with open(state_path, 'w') as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
print(f'Cleaned {len([p for p in failed if p not in state])} entries')
"
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py
```

**Fix B — brute force (small catalog or full rebuild):** Re-process everything:
```bash
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py --force
```

This ignores the saved state and re-processes every file. With 5000+ files at ~8-16s each, expect **12-24 hours** (use background mode + `notify_on_complete`).

## LLM Server: Multi-Port Fallback (8092 → 8102 → 8103 → 8101)

### The problem: silent 6-day outage

The daily cron (`curator-daily.sh`) originally hardcoded a single port 8092 check. When port 8092 was down (Qwen3.6-35B BF16 not started), the script logged "⚠ Qwen NOT running" and skipped ALL three pipeline phases — paper collection, deep-read, and markdown ingestion. This caused a **6-day silent outage** (June 29 – July 5, 2026) where the graph stagnated at 15,184 entities while ~3 new/changed files went unprocessed.

Meanwhile, three other llama-server instances were running on ports 8101 (nex-n2-mini), 8102 (Qwen3.6-35B APEX), and 8103 (SuperQwen-AgentWorld) — any of which could have served the extraction requests.

### The fix: multi-port fallback with content-generation health check

Both `curator-daily.sh` and `knowledge-curator-ingest-llm.py` now support LLM server auto-detection:

1. **`curator-daily.sh`** probes ports in order (8092 → 8102 → 8103 → 8101)
2. For each responding port, it sends a **test chat completion** (`"Say OK"`, `max_tokens=50`) — not just `/v1/models`
3. If the response `content` is non-empty, the server is accepted; `LLAMA_URL` and `LLAMA_MAX_TOKENS` (set to 4000) are exported
4. If `content` is empty (reasoning-only models with low `max_tokens`), the port is skipped with a warning
5. If no usable server is found, all phases are skipped (same as before, but now with a clear message)

**Critical insight:** A `/v1/models` health check is NOT sufficient. Port 8102 (Qwen3.6-35B APEX) responds to `/v1/models` but generates **empty `content`** when `max_tokens` is low (1200) — reasoning tokens consume the entire budget, returning `finish_reason: "length"` with empty `content`. The content-generation health check catches this.

### Env var support in knowledge-curator-ingest-llm.py

The ingest script now respects two env vars (set automatically by `curator-daily.sh`):

| Env var | Default | Purpose |
|---------|---------|---------|
| `LLAMA_URL` | `http://127.0.0.1:8092/v1` | LLM endpoint (OpenAI-compatible) |
| `LLAMA_MAX_TOKENS` | `1200` | Max tokens for extraction (use 4000+ for reasoning models) |

Manual override:
```bash
# Use port 8103 (AgentWorld) with higher token budget for reasoning models
export LLAMA_URL=http://127.0.0.1:8103/v1
# Reasoning models need ~4k tokens (default 1200 produces empty content)
# Set LLAMA_MAX_TOKENS to 4000 or higher before running the script
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py
```

### ⚠ CRITICAL: Bare-script invocation bypasses ALL fallback (observed 2026-07-08)

The multi-port fallback (8092 → 8102 → 8103 → 8101) lives **only in `curator-daily.sh`**. The ingest script `knowledge-curator-ingest-llm.py` by itself has **no fallback** — it reads `LLAMA_URL` from the environment (default `http://127.0.0.1:8092/v1`) and uses that single endpoint. If a cron job or manual invocation calls the bare script without setting `LLAMA_URL`, and port 8092 is down, **every file fails with `Connection refused` and the run ingests 0 entities**.

This is a silent failure: exit code 0, no crash, just `Done: 0 files processed, 0 entities, 0 relations ingested`. Because failed files don't save state (see "State saved even when LLM fails" above), they retry on the next run — but the next run hits the same dead port.

**Signature of this failure:**
```
LLM error: HTTPConnectionPool(host='127.0.0.1', port=8092): Max retries exceeded ...
AGENTS.md: LLM extraction failed, will retry
README.md: LLM extraction failed, will retry
...
Done: 0 files processed, 0 entities, 0 relations ingested.
```

**Recovery procedure — diagnose → verify → re-run:**

1. **Find a working LLM server** (check which ports are listening):
```bash
ss -tlnp | grep -E ':809[0-9]|:810[0-9]'
# or look at running llama-server processes:
pgrep -af 'llama-server' | grep -oP 'port \K[0-9]+'
```

2. **Verify Neo4j is up and auth works:**
```bash
curl -s -m 10 -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:7474/db/neo4j/tx/commit \
  -d '{"statements":[{"statement":"MATCH (n:KnowledgeEntity) RETURN count(n) AS c"}]}'
```

3. **Test a single extraction** against the available server (catches reasoning-only models, wrong-model issues BEFORE launching a multi-hour run):
```bash
curl -s http://127.0.0.1:<PORT>/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Return JSON: {\"test\":true}"}],"max_tokens":50}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); c=d['choices'][0]['message']; print('OK' if c.get('content','').strip() else 'EMPTY CONTENT — reasoning model, need --reasoning off or LLAMA_MAX_TOKENS=4000+')"
```

4. **Re-run with `LLAMA_URL` override** (do NOT change the script's default — `:8092` is canonical; the override is for recovery only):
```bash
export LLAMA_URL=http://127.0.0.1:<PORT>/v1
# Reasoning models (APEX quant): set higher token budget
export LLAMA_MAX_TOKENS=4000
python3 -u ~/.hermes/scripts/knowledge-curator-ingest-llm.py 2>&1 | tee ~/.hermes/logs/curator-ingest-$(date +%Y%m%d-%H%M%S).log
```

5. **Verify live progress** (stdout may be buffered — check state + Neo4j counts instead):
```bash
# Checkpointed files in state:
python3 -c "import json; d=json.load(open('$HOME/.hermes/skills/.curator_state')); print(len([k for k in d if k.startswith('/')]),'files checkpointed')"
# Live Neo4j counts:
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN count(ke) AS c"}]}' \
  http://127.0.0.1:7474/db/neo4j/tx/commit
```

**Prevention:** Cron jobs should invoke `curator-daily.sh` (which does multi-port fallback), NOT the bare ingest script. If a cron must call the bare script, it should set `LLAMA_URL` explicitly or add its own port-probe logic.

### Port reference (Jetson GB10, July 2026)

| Port | Model | Quant | Curator-compatible? | Notes |
|------|-------|-------|:---:|-------|
| 8092 | Qwen3.6-35B Heretic (BF16) | BF16 | ✅ | Preferred, but frequently down |
| 8101 | Nex-N2-mini abliterated | APEX-Quality | ✅ | Smaller model, works for extraction |
| 8102 | Qwen3.6-35B APEX I-Quality | APEX | ⚠️ | Empty content with `max_tokens<4000` (reasoning tokens) |
| 8103 | SuperQwen-AgentWorld-35B | APEX I-Quality v3 | ✅ | Reliable for JSON extraction, preferred fallback |

### KeyError bug fix (e["name"] vs e["n"])

The LLM returns entities with short keys: `{"n":"name","t":"type","d":"desc","c":0.9}`. The display code on line 355 accessed `e["name"]` (the normalized key, only set AFTER `ingest_entities()`) on the raw entities list. This caused a `KeyError: 'name'` crash when extraction succeeded. Fixed to use `e.get("n", e.get("name", "?"))`.

### Quick start (Jetson) — port 8092 (preferred)

```bash
# Kill any stale processes on the port
fuser -k 8092/tcp 2>/dev/null; sleep 2

# Start with the llmfan46 Native MTP model (BF16, MTP, port 8092)
nohup /home/user/dev/llama.cpp/build/bin/llama-server \
  --model /home/user/.lmstudio/models/llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-GGUF/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-BF16.gguf \
  --mmproj /home/user/.lmstudio/models/llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-GGUF/Qwen3.6-35B-A3B-mmproj-BF16.gguf \
  --host 0.0.0.0 --port 8092 \
  --ctx-size 262144 --n-gpu-layers 41 --threads 20 \
  --batch-size 512 --ubatch-size 512 --parallel 4 \
  --cont-batching --alias qwen3.6-35b-heretic \
  --flash-attn on --no-mmap --direct-io \
  --kv-unified --jinja --reasoning off \
  >> $HOME/cursor/first/opencode+/.run/llama.log 2>&1 &

# Wait for ready (model loads in ~15-30 seconds)
for i in $(seq 1 30); do
  if curl -fsS -m 3 http://127.0.0.1:8092/v1/models >/dev/null 2>&1; then
    echo "llama-server ready"; break
  fi; sleep 2
done
```

**Note for Hermes Agent contexts:** The managed script (`start-llama-qwen.sh`) may fail under Hermes because `EFFECTIVE_HOME` resolves to the session-isolated HOME directory. Use the explicit command above instead.

### Alternative: managed start script

Only reliable when HOME is not redirected (direct terminal, not under Hermes Agent):

```bash
OPENCODE_PLUS_LLAMA_PROFILE=llama-qwen-heretic \
  bash /home/user/cursor/first/opencode+/start-llama-qwen.sh --daemon
```

### Port conflict

Dify occupies port 8090 by default. The curator uses 8092 (set by the `llama-qwen-heretic` profile). Do NOT use port 8090 for llama-server — it will conflict with Dify's Next.js app.

### State file not saved incrementally (FIXED)

**Original behavior:** `save_state()` called only once after the entire loop completes. If the script times out or is killed mid-run, all progress is lost and the next run starts from scratch.

**Fix applied (2026-06-17):** Checkpoint state every 10 files:
```python
if not dry_run and processed % 10 == 0:
    save_state(state)
```

### Runtime: ~4-8 hours for full scan (~1780 files → now 5000+)

The catalog has grown from ~1780 markdown files (July 2026) to **5000+ files** (observed 2026-07-08: 5083 in `~/dev/codemes/` + 5 in `~/docs/research/`). At ~8-16 seconds per file (LLM call + Neo4j ingest), a full force-scan now takes **~12-24 hours** on the Jetson GB10. Normal (non-force) runs process only new/changed files and complete much faster. State is checkpointed every 10 files so progress survives interruptions — the next cron run continues where the previous one stopped.

### Qwen 3.6 outputs to reasoning_content — MUST use `--reasoning off`

**Observed 2026-06-24:** When llama-server starts without `--reasoning off`, Qwen 3.6 35B routes its output to `reasoning_content` instead of `content`. The curator script reads only `message["content"]` — so it gets an empty string (`0 chars, no ']' in response`). Entity extraction fails for every file.

The `/v1/models` health check succeeds (server is up), but every chat completion returns `content: ""` with the actual answer in `reasoning_content`. This is invisible unless you inspect the raw API response.

**Fix:** Always start llama-server with `--reasoning off` for the curator. If the curator outputs `No ']' in response (0 chars)` for every file despite the server being up, this is the cause.

**Verification — check if reasoning is interfering:**
```bash
curl -s http://127.0.0.1:8092/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hi"}],"max_tokens":10}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); c=d['choices'][0]['message']; print(f'content: [{c.get(\"content\",\"\")}] reasoning: [{c.get(\"reasoning_content\",\"\")}]')"
```
Expected: `content: [Hi! ...] reasoning: []`. If content is empty and reasoning has text → server needs `--reasoning off`.

### Background process stdout invisible

When running in background mode, Python's `print()` output is not captured by the process monitor — even with `flush=True` and `PYTHONUNBUFFERED=1`. 

**Workaround:** Verify progress via Neo4j queries:
```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN count(ke) as c"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```

Check the state file directly to see how many files have been processed:
```bash
python3 -c "import json; s=json.loads(open('$HOME/.hermes/skills/.curator_state').read()); print(len(s))"
```

### Agent-as-Extractor Fallback (all LLM servers down)

When running as a cron job (no user present), all LLM servers may be down simultaneously — port 8092 connection refused, no fallback ports listening, and even the MCP `education_ingest` tool fails (broken Python env). In this situation the agent itself can substitute as the entity extractor.

**When to use:** Only in cron/autonomous context where ALL of these are true:
1. Bare script run found pending files (state hash mismatch)
2. No LLM server responds on any port (8092/8101/8102/8103)
3. MCP `education_ingest` tool is also broken
4. Pending file count is small (≤10) — the agent reads and extracts each manually

**Procedure:**

1. **Read the script** to understand the MERGE pattern (entity: `KnowledgeEntity`, relation: `RELATES_TO {predicate}`)
2. **Check pending files** by comparing state hashes:
```python
import hashlib, json
from pathlib import Path
REAL_HOME = Path("/home/user")
CURATOR_STATE = REAL_HOME / ".hermes" / "skills" / ".curator_state"
SCAN_ROOTS = [REAL_HOME / "dev" / "codemes", REAL_HOME / "docs" / "research"]
def state_hash(path):
    stat = path.stat()
    return hashlib.sha256(f"{path}:{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()[:16]
state = json.loads(CURATOR_STATE.read_text())
artifacts = []
for root in SCAN_ROOTS:
    if not root.exists(): continue
    for md in root.rglob("*.md"):
        s = str(md)
        if "/.git/" in s or "/node_modules/" in s: continue
        artifacts.append(md)
pending = [p for p in artifacts if state.get(str(p)) != state_hash(p)]
print(f"Pending: {len(pending)}")
for p in pending: print(f"  {p}")
```

3. **Read each pending file**, extract entities manually (act as the LLM would):
   - Choose best-fit types from the 14+ entity types (Paper, Algorithm, Framework, Model, Pattern, Concept, etc.)
   - Extract ≤12 entities, ≤6 relations per file
   - Confidence: 0.85-0.95 for explicit mentions, 0.7-0.85 for implied

4. **MERGE into Neo4j via REST API** using `execute_code` (avoids shell auth tuple corruption):
```python
import requests
NEO4J_URL = "http://127.0.0.1:7474"
# Use HTTPBasicAuth to avoid *** tuple corruption
from requests.auth import HTTPBasicAuth
auth = HTTPBasicAuth("neo4j", "changeme")

# Entity MERGE
statements = [{"statement": (
    "MERGE (ke:KnowledgeEntity {name: $name}) "
    "ON CREATE SET ke.created_at = timestamp() "
    "SET ke.type = $type, ke.description = $desc, "
    "ke.confidence = $conf, ke.source = $source, ke.updated_at = timestamp()"
), "parameters": {"name": ent["name"], "type": ent["type"],
    "desc": ent["description"], "conf": ent["confidence"], "source": str(path)}} for ent in entities]
requests.post(f"{NEO4J_URL}/db/neo4j/tx/commit", json={"statements": statements}, auth=auth).raise_for_status()

# Relation MERGE
for rel in relations:
    requests.post(f"{NEO4J_URL}/db/neo4j/tx/commit", json={"statements": [{
        "statement": ("MATCH (a:KnowledgeEntity {name: $s}) MATCH (b:KnowledgeEntity {name: $o}) "
                      "MERGE (a)-[r:RELATES_TO {predicate: $p}]->(b) SET r.source = $source"),
        "parameters": {"s": rel["s"], "o": rel["o"], "p": rel["p"], "source": str(path)}
    }]}, auth=auth).raise_for_status()
```

5. **Update curator state** so the script doesn't retry these files:
```python
state[str(path)] = state_hash(path)
CURATOR_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
```

6. **Verify** — confirm 0 pending remain.

**Limitation:** This is a manual fallback for small pending sets. For large backlogs (50+ files), start an LLM server instead — the agent cannot efficiently extract entities from hundreds of files in one turn.

## Manual Run

```bash
# Normal run (processes new/changed files only)
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py

# Dry run (no LLM/Neo4j calls, just prints what would be processed)
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py --dry-run

# Force re-process all files (ignores state hash — use after LLM server outage)
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py --force
```

## Verification (v2)

After a run, check the pipeline health:

```bash
# Total KnowledgeEntity count
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN count(ke) as c"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# Paper count (new in v2)
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (p:Paper) RETURN count(p) as c"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# Entities by type (v2 — 14+ types)
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ke:KnowledgeEntity) RETURN ke.type, count(ke) as cnt ORDER BY cnt DESC"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# Relationship predicates
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH ()-[r:RELATES_TO]->() RETURN r.predicate, count(r) as cnt ORDER BY cnt DESC"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# Code examples ingested
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (ce:CodeExample) RETURN count(ce) as c"}]}' \
  http://localhost:7474/db/neo4j/tx/commit

# CuratorRun history (health monitoring)
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (cr:CuratorRun) RETURN cr.timestamp, cr.status, cr.papers_processed, cr.entities_ingested ORDER BY cr.timestamp DESC LIMIT 5"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```

**Health status codes:**
- `healthy_active` — new content found and ingested
- `healthy_idle` — nothing new to process (all files unchanged)
- `degraded` — some phases succeeded, some failed
- `failed` — all phases failed (LLM down, Neo4j unreachable, etc.)

## Manual Run (v2)

```bash
# Full daily pipeline (dry-run: no LLM/Neo4j writes)
bash ~/.hermes/scripts/curator-daily.sh --dry-run

# Full daily pipeline (real run)
bash ~/.hermes/scripts/curator-daily.sh

# Phase A only: collect papers without deep-reading
python3 ~/.hermes/scripts/paper-collector.py --days=1 --top=10

# Phase B only: deep-read queued papers
python3 ~/.hermes/scripts/paper-deep-read.py --top=5

# Phase B: deep-read specific paper by arxiv ID
python3 ~/.hermes/scripts/paper-deep-read.py --arxiv-id=2502.06472

# Phase C only: scan markdown files (unchanged from v1 interface)
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py --force   # re-process all
python3 ~/.hermes/scripts/knowledge-curator-ingest-llm.py --dry-run # no LLM/Neo4j
```
