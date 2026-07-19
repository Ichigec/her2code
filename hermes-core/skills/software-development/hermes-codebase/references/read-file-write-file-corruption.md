# read_file + write_file = CORRUPTION

**CRITICAL — discovered 2026-07-01.**

## The bug

`read_file()` through `execute_code` returns content WITH line number prefixes:
```
1|import { useStore } from '@nanostores/react'
2|import { useQueryClient } from '@tanstack/react-query'
```

When you pass this content to `write_file()`, the `"1|"` prefixes become part of the file:
```
1|import { useStore } from '@nanostores/react'   ← literal "1|" in file!
2|import { useQueryClient } from '@tanstack/react-query'
```

The file is now CORRUPTED — Python/TypeScript cannot parse it.

## Real impact

`desktop-controller.tsx` was truncated from 1189 to 500 lines. All imports were lost. The file had to be restored with `git checkout`, which caused further data loss (observerItem, plan2/plan3 subagents — not yet committed).

`observer.py` was similarly corrupted — 356 lines with `1|`, `2|` prefixes. Had to be recovered with `sed 's/^[0-9]*|//'`.

## Fix: use these tools instead

```python
# ✅ SAFE — patch operates on real disk file
patch(path, old_string, new_string)

# ✅ SAFE — write_file with constructed content (not from read_file)
write_file(path, completely_new_content)

# ✅ SAFE — terminal + heredoc
terminal("cat > file.tsx << 'EOF'\n...content...\nEOF")

# ❌ CORRUPTS — read_file content → write_file
content = read_file(path).get("content","")  # has line numbers
write_file(path, modified_content)            # writes line numbers!
```

## Rule

**NEVER pass `read_file` output to `write_file`.** For modifications, use `patch`. For full rewrites, construct content from scratch.
