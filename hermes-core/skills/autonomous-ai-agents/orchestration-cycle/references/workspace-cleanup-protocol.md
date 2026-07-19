# Workspace Cleanup Protocol

Produced 2026-06-20 by Critic (#11) during orchestrator transformation cycle.

## When to run

After every 2-3 orchestration cycles, or when the Critic reports
duplication/bloat. Run the checklist below.

## Checklist

### 1. Duplicate project directories

```bash
# Find projects that contain ONLY AGENTS.md + structure.md
for d in /home/user/dev/codemes/*/; do
  file_count=$(find "$d" -type f -not -name 'AGENTS.md' -not -name 'structure.md' 2>/dev/null | wc -l)
  if [ "$file_count" -eq 0 ]; then
    echo "EMPTY: $d"
  fi
done
```

Remove with `rm -rf` after confirming.

### 2. Old config backups

```bash
ls -t /home/user/.hermes/config.yaml.bak* 2>/dev/null
# Keep 2 most recent, delete rest
ls -t /home/user/.hermes/config.yaml.bak* 2>/dev/null | tail -n +3 | xargs rm -v
```

Also check: `.env.bak*`, `config.yaml.corrupt.*.bak` — remove all corrupt variants.

### 3. AGENTS.md proliferation

```bash
find /home/user/dev/codemes -name 'AGENTS.md' -not -path '*/node_modules/*' | wc -l
```

Expect: 1 copy per active project. If >10, many are orphaned.
Do NOT bulk-delete — each project needs its AGENTS.md. Only remove
from empty directories (see step 1).

### 4. Duplicate project copies

```bash
ls -d /home/user/dev/codemes/*_202[0-9]*/ /home/user/dev/codemes/*_pre_restore*/ 2>/dev/null
```

These are copies of active projects with timestamps. Remove if original
exists and copy is >7 days old.

### 5. state.db vacuum

```bash
ls -lh /home/user/.hermes/state.db
sqlite3 /home/user/.hermes/state.db "VACUUM;"
```

VACUUM is safe on active database. Expect modest savings (1-5%) —
the DB is mostly live data, not fragmentation.

## What NOT to remove

- `~/.hermes/config.yaml` (active config)
- `~/.hermes/config.yaml.bak-<latest>` (2 most recent backups)
- `~/.hermes/AGENTS.md` (canonical source)
- Any project with actual code files (check: `find dir -name '*.py' -o -name '*.kt' -o -name '*.ts' | head -1`)

## Observed results (2026-06-20)

Removed: 3 multi-agent-runtime copies, 6 config/.env backups, 3 empty projects.
Saved: ~300KB disk. state.db VACUUM: 563M→562M (negligible — data is live).
