# Large Model Download Workflow (`hf download`)

Resilient workflow for downloading multi-gigabyte safetensors models from HuggingFace
using `hf download --local-dir`. Covers auto-resume, stale process cleanup, cache
reclamation, and final verification.

## Quick Start

```bash
export PATH="$HOME/.hermes/home/.local/bin:$PATH"
hf download <REPO_ID> --local-dir /home/user/<dest-dir>
```

**Always use absolute paths.** `~/...` inside Hermes `terminal()` resolves to the
session-isolated `$HOME` (`/home/user/.hermes/home/`), not the real home.

## Auto-Resume Behavior

`hf download` writes partial downloads as `.incomplete` files in
`.cache/huggingface/download/`. Re-running the SAME command automatically resumes —
it detects existing `.incomplete` files and picks up where it left off. No extra
flags needed.

**This means:** if a background process dies (SIGTERM, OOM, timeout), just re-run the
identical command. It skips already-complete shards and resumes partial ones.

## Process Management for Background Downloads

### Check for existing/stale processes

```bash
ps aux | grep "hf download" | grep -v grep
```

Stale processes from old sessions accumulate. Look for:
- PIDs from hours/days ago (check START time)
- Multiple `hf download` processes targeting the same repo

### Kill stale duplicates before restarting

```bash
kill <old_pid> <old_child_pid>
```

The `hf download` wrapper (bash) + the actual Python process (`/usr/bin/python3 hf download ...`)
are separate PIDs. Kill both.

**Hermes `process(action="list")` only shows processes from the CURRENT session** —
it won't find processes from past sessions. Use `ps aux | grep` instead.

## Monitoring Progress

```bash
# Total downloaded
du -sh /home/user/<dest-dir>/

# Count incomplete files
find /home/user/<dest-dir>/.cache -name "*.incomplete" | wc -l

# Count completed safetensors
ls /home/user/<dest-dir>/model-*.safetensors | wc -l

# Download speed (run twice ~15s apart)
sz1=$(du -sb /home/user/<dest-dir>/.cache/ | cut -f1)
sleep 15
sz2=$(du -sb /home/user/<dest-dir>/.cache/ | cut -f1)
rate=$(( (sz2 - sz1) / 15 / 1048576 ))
echo "Speed: ${rate} MB/s"
```

### Speed expectations

- Good connection: 10-100 MB/s (DGX Spark over Ethernet)
- Model size × shard count varies by repo. ~5 GB per safetensors shard is typical.
- ETA = remaining_GB × 1024 / rate_MBps / 60 (minutes)

## Cache Cleanup After Completion

After all safetensors are finalized, stale `.incomplete` files from old/failed
processes linger in `.cache/huggingface/download/`. They waste significant space
(10-25 GB is common).

```bash
# After download finishes, remove entire cache
rm -rf /home/user/<dest-dir>/.cache/
```

The cache is ONLY needed during active downloads. Completed safetensors are written
to the destination directory — deleting `.cache/` is safe.

## Final Verification

### All shards present?

```bash
ls /home/user/<dest-dir>/model-*.safetensors | wc -l
```

Compare against the expected count (from `model.safetensors.index.json` or the HF repo).

### Sizes look right?

```bash
ls -lhS /home/user/<dest-dir>/model-*.safetensors
```

All shards should be ~same size (~5 GB each). The LAST shard (`model-XXXXX-of-YYYYY`)
is typically smaller (hundreds of MB). If any shard is orders of magnitude smaller
than its peers, it may be truncated — delete and re-download.

### Config files present?

```bash
ls -lh /home/user/<dest-dir>/{config.json,tokenizer.json,tokenizer_config.json,model.safetensors.index.json}
```

At minimum: `config.json`, `tokenizer.json`, `model.safetensors.index.json` are
required for GGUF conversion.

## Full Example: Agents-A1 35B (66 GB, 14 shards)

```bash
# Start background download
terminal(background=true, notify_on_complete=true):
  export PATH="/home/user/.hermes/home/.local/bin:$PATH"
  hf download huihui-ai/Huihui-Agents-A1-abliterated \
    --local-dir /home/user/dev/a1-agents

# Monitor (run periodically)
du -sh /home/user/dev/a1-agents/
find /home/user/dev/a1-agents/.cache -name "*.incomplete" | wc -l
ls /home/user/dev/a1-agents/model-*.safetensors | wc -l

# After completion — cleanup + verify
rm -rf /home/user/dev/a1-agents/.cache/
ls -lhS /home/user/dev/a1-agents/model-*.safetensors
# Expected: 14 files, 13 × 5.1 GB + 1 × ~400 MB
```

## Pitfalls

- **`process(action="list")` is session-scoped** — won't find bg processes from
  other sessions. Use `ps aux | grep` instead.
- **Stale `.incomplete` files accumulate** across failed attempts. Always
  `rm -rf .cache/` after completion to reclaim space.
- **Multiple `hf download` processes for the same repo** can collide on
  `.incomplete` files. Kill the old one before restarting.
- **`--local-dir` with `~` resolves to session HOME** — use absolute paths.
- **`notify_on_complete=true` is critical** for background downloads longer
  than a few minutes. Without it, you won't know when it finishes.
