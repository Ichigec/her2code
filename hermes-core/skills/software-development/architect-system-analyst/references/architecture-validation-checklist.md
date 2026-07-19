# Architecture Validation Checklist

Complete checklist for validating architecture documentation against reality.
Use after generating any architecture knowledge graph or C4 model.

## Phase 1: File Existence & Size Verification

For every entity in the architecture description:

```bash
# Verify file exists
test -f <path> && echo "✓" || echo "✗ MISSING"

# Verify line count matches claim
wc -l <path>

# Verify class/function exists at claimed line
sed -n '<line>p' <path>
```

## Phase 2: Dependency Verification

For every "imports X" claim:

```bash
# Top-level imports (fast but incomplete)
grep -n '^from\|^import' <path> | grep <claimed_import>

# Lazy imports (CRITICAL — often missed)
grep -n 'import ' <path> | grep -v '^.*:#' | grep <claimed_import>

# Reverse: who imports this module?
grep -rn 'from <module>\|import <module>' --include='*.py' .
```

**Rule:** If grep returns 0 results for both top-level and lazy, the dependency claim is WRONG.

## Phase 3: Signature Verification

For every API/extension point documented:

```bash
# Get actual function signature
grep -A10 'def <function_name>' <path>

# Compare parameter order and names
# Document: register(name, schema, handler, toolset)
# Actual:   register(self, name, toolset, schema, handler, ...)
#                     ^^^^^^^^^^^ SWAPPED!
```

## Phase 4: Missing Entity Detection

Search for large/important files NOT in the knowledge graph:

```bash
# Top 20 largest Python files (likely architecturally significant)
find . -name '*.py' -exec wc -l {} + | sort -rn | head -20

# Files with high fan-in (imported by many)
grep -rn '^from\|^import' --include='*.py' . | awk -F: '{print $3}' | sort | uniq -c | sort -rn | head -20
```

## Phase 5: Cross-Report Consistency

When multiple reports exist (audit, critic, knowledge graph):

| Check | How |
|-------|-----|
| Line counts agree? | Compare all reports for same file |
| Dependency claims agree? | Cross-reference import lists |
| Component lists agree? | Are the same entities documented? |
| Severity ratings consistent? | Does audit say "critical" while KG says "minor"? |

## Common Verification Failures (from real Hermes audit)

| Failure | Cause | Prevention |
|---------|-------|------------|
| Wrong import claims | LLM hallucinated dependencies | Always grep-verify |
| Wrong function signature | LLM guessed parameter order | Always `grep -A10 'def '` |
| Missing lazy imports | Top-level grep misses `_ra()` pattern | Grep ALL import statements |
| Missing entities | LLM didn't explore deeply enough | Always run `find + wc -l` for top-20 files |
| Misleading transport layer | KG points to wrapper, not implementation | Check file SIZES — bigger = more logic |
| Docker volumes missed | Deployment map only covers filesystem | Always `docker volume ls` |

## Verification Score Card

| Metric | Target | Acceptable |
|--------|--------|------------|
| File paths correct | 100% | 95% |
| Line counts correct | 100% | 90% |
| Dependency claims correct | 90% | 70% |
| Function signatures correct | 100% | 80% |
| Missing entities | 0 | <5 |
| Extension points verified | 100% | 90% |

If dependency claims accuracy < 70%, the knowledge graph needs a full re-verification pass.
