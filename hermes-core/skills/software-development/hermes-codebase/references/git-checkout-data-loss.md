# Git Checkout Data Loss

**CRITICAL — discovered 2026-07-01.**

## The incident

`git checkout desktop-controller.tsx` was used to recover from a corrupted file (read_file→write_file bug). This silently destroyed 14+ uncommitted changes:
- `observerItem` (50 lines)
- `observerConfig`, `$observerSessions`, `OBSERVER_SECTION_LIMIT`, `setObserverSessions` imports
- `excludeSources: ['cron', 'observer']` (was `['cron']`)
- `Eye`, `EyeOff`, `ObserverPanel` imports
- `plan2SubagentsItem`, `plan3SubagentsItem`, `clawOrchestratorItem` (new StatusbarItems)
- `SubagentDropdown` import

These changes existed only in the working tree (not committed).

## Pre-checkout hook

A hook is installed at `.git/hooks/pre-checkout` that blocks checkout when uncommitted changes exist:

```bash
#!/bin/bash
if [ "$CHECKOUT_TYPE" != "1" ]; then exit 0; fi
if ! git diff --quiet 2>/dev/null; then
    echo "⚠️ UNCOMMITTED CHANGES DETECTED"
    git diff --name-only
    echo "Save: git stash | Force: git checkout -f"
    exit 1
fi
```

## Rule

**Before `git checkout <file>`:**
1. `git diff --name-only` — check what will be lost
2. `git stash` — save changes
3. `git checkout <file>` — restore original
4. `git stash pop` — reapply changes
5. **If hook blocks you: `git stash` first, then retry**

**Before ANY destructive operation** (git checkout, git reset, rm): if `git diff --name-only` is not empty, ask the user whether to commit first.
