# Debugging Transcript: knowledge-curator-ingest-llm.py Silent Failure

Date: 2026-06-23

## Symptoms
- Cron job ran: `python3 /home/user/.hermes/scripts/knowledge-curator-ingest-llm.py`
- Output: `Done: 0 files processed, 0 entities ingested.`
- Expected: 1,778 markdown files to process
- Dependencies (llama.cpp, Neo4j) both healthy

## Debugging Steps

### Step 1 — Verify scan roots exist
```
$ ls -d /home/user/dev/codemes /home/user/docs/research
/home/user/dev/codemes
/home/user/docs/research

$ find /home/user/dev/codemes -name "*.md" | wc -l
1773
```
Roots exist, files present. Problem is in the script's path resolution.

### Step 2 — Check `Path.home()` in the Hermes environment
```
$ echo "HOME=$HOME"
HOME=/home/user/.hermes/home

$ python3 -c "from pathlib import Path; print(Path.home())"
/home/user/.hermes/home
```
**Root cause found.** Hermes redirects `HOME` for session isolation. `Path.home()` returns the isolated home, not `/home/user`. The script's scan roots resolve to non-existent paths:
- `/home/user/.hermes/home/dev/codemes` (doesn't exist)
- `/home/user/.hermes/home/docs/research` (doesn't exist)

### Step 3 — Find the correct env var
```
$ echo "HERMES_HOME=$HERMES_HOME"
HERMES_HOME=/home/user/.hermes

$ python3 -c "import os; print(os.path.expanduser('~pavel'))"
/home/user
```
`HERMES_HOME` always points to the real `~/.hermes`. Deriving real home as `Path(HERMES_HOME).parent` gives `/home/user`.

### Step 4 — Apply fix and verify
Patched `CURATOR_STATE` and `SCAN_ROOTS` to use `HERMES_HOME`-derived paths. Dry run:
```
[dry-run] AGENTS.md (1669 chars)
[dry-run] README.md (1924 chars)
...
Done: 1778 files processed, 0 entities ingested.
```
Now finding all 1,778 files.

### Step 5 — Output buffering issue
Background process produced no visible output despite script running. Root cause: `print(f"{path.name} ... ", end="", flush=True)` emits no newline; the pipe-based log capture reads line-by-line, so partial lines are buffered until a newline arrives. Fix: emit only complete lines with newlines, and add `sys.stdout.reconfigure(line_buffering=True)`.

## Key Pattern

```python
import os
from pathlib import Path

# Robust real-home derivation for Hermes Agent
_REAL_HERMES = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
_REAL_HOME = _REAL_HERMES.parent if _REAL_HERMES.name == ".hermes" else _REAL_HERMES
```

This works both under Hermes (where `HERMES_HOME` is set) and during manual testing (fallback to `Path.home() / ".hermes"`).
