# Deep Research Validation — Ground-Truth Checklist

**Purpose:** Before committing to a deep research phase (Phase 3, 600+ lines, 6 RQs, multi-iteration), verify the research is actually needed vs a quick A/B test.

**Context:** The codemes_neo4j_repo-graph cycle (2026-06-17) spent 631 lines of research
benchmarking tree-sitter parsers, embedding throughput, and tool comparisons on Jetson
ARM64. Post-deploy analysis revealed:
- Codebase is 12.7× larger than the census found (1,429 files vs 113 predicted)
- Embedding throughput is 5.8× faster than benchmarks predicted (595 vs 102.8 emb/s)
- Tree-sitter was never actually integrated (regex was used instead)
- The bottleneck was integration, not tool selection

**Lesson:** A 5-minute A/B test of regex vs tree-sitter on one file would have been more
valuable than the 631-line literature review.

## Validation Gates

Before spawning Phase 3 (Researcher), run these checks:

### 1. Package/Environment Freshness

```bash
# Check if key packages are up-to-date
~/.hermes/hermes-agent/venv/bin/pip list --format=json | python3 -c "
import json, sys
pkgs = json.load(sys.stdin)
for p in pkgs:
    if p['name'] in ['neo4j','tree-sitter','sentence-transformers',
                       'watchdog','ctranslate2','openai','httpx']:
        print(f'{p[\"name\"]}=={p[\"version\"]}')
"
```

**Red flag:** Packages >6 months old → research needs update. All packages current → skip
benchmark re-validation, reference existing benchmarks.

### 2. Git Activity Check

```bash
# How active is the target codebase?
find /path/to/codebase -name ".git" -maxdepth 3 -type d | while read d; do
    repo=$(dirname "$d")
    echo "--- $repo ---"
    git -C "$repo" log --oneline --since="7 days ago" --all | head -5
done
```

**Red flag:** Active development (>10 commits/week) → deep research on tooling may be
stale by the time implementation starts. Prefer quick A/B tests.
**Green flag:** Static codebase (<5 commits/week) → deep research has longer shelf life.

### 3. Codebase Size Verification

```bash
# Don't trust census estimates. Measure directly.
find /path/to/codebase -name "*.py" | wc -l
find /path/to/codebase -name "*.js" -o -name "*.ts" | wc -l
```

**Red flag:** Census off by >3× from ground truth → re-scope all performance estimates.

## Decision Matrix

| Signal | Action |
|--------|--------|
| Packages current + static codebase + census accurate | **Light research** (skip Phase 3, do 15-min A/B test) |
| Packages current + active codebase | **Targeted research** (2 RQs max, focus on integration) |
| Packages stale (>6mo) + static codebase | **Full research** (Phase 3, benchmark everything) |
| Packages stale + active codebase | **Full research** + **note shelf life** (results valid ~2 weeks) |

## Integration Test > Literature Review

When the core question is "tree-sitter vs regex for Python parsing", a 5-minute A/B test
on the ACTUAL codebase beats any literature review:

```bash
# A/B test: regex parser vs tree-sitter on one representative file
time python3 -c "
from codebase_scanner import TreeSitterParser
p = TreeSitterParser()
result = p.parse('auth.py')
print(f'Functions: {len(result.functions)}, Classes: {len(result.classes)}, Calls: {len(result.calls)}')
"
```

This pattern generalizes: **one measurement on real data > ten papers about the tool.**
