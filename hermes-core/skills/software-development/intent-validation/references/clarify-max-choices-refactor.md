# Clarify MAX_CHOICES Refactoring Checklist

When changing `MAX_CHOICES` in `tools/clarify_tool.py`, update ALL of these locations.
Missing any spot causes test failures + schema lies to the LLM.

## Files to update

### 1. `tools/clarify_tool.py` — 3 inline spots

| Line | What | Example (4→8) |
|------|------|---------------|
| ~33 | Docstring: `Up to N predefined answer choices` | `4` → `8` |
| ~93 | Schema description (multiple choice mode): `up to N choices` | `4` → `8` |
| ~117 | Schema description (choices property): `Up to N answer choices` | `4` → `8` |

### 2. `tests/tools/test_clarify_tool.py` — 2 tests

| Lines | Test | What |
|-------|------|------|
| ~67-78 | `test_choices_trimmed_to_max` | Ensure `many_choices` list has MORE elements than new MAX_CHOICES (e.g., 10 when MAX_CHOICES=8) |
| ~192-194 | `test_max_choices_is_N` | Rename test (`_is_four` → `_is_eight`), update docstring, update assertion `== N` |

### 3. Other files (search, don't assume)

```bash
grep -rn "up to [0-9].*choice\|MAX_CHOICES\|max_choices\|maxChoices" ~/.hermes/ --include="*.py" --include="*.ts" --include="*.tsx" --include="*.md"
```

This catches stale references in gateway adapters (Telegram/Discord button builders), desktop GUI hints, and documentation.

## Session that triggered this checklist

2026-07-01: MAX_CHOICES was changed 4→8 but only the constant and `maxItems` in schema were updated. Result: 2 failing tests + schema description told LLM "up to 4" while actual limit was 8 — LLM self-limited unnecessarily.
