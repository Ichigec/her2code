# Hermes Multi-Repo Layout

Pavel's Hermes installation spans several git repos. When saving a version or
making changes, know which one you're working with.

## Repos

| Repo | Path | Branch | Remote | Purpose |
|------|------|--------|--------|---------|
| **hermes-agent (installed)** | `~/.hermes/hermes-agent/` | `dev` | `github.com/NousResearch/hermes-agent` | Main Hermes Agent source — this is the installed/running version. Python + TS + desktop GUI. On `dev` branch with experimental features. |
| **hermes-agent (docker fork)** | `~/.hermes-docker/hermes-agent/` | `main` | `github.com/NousResearch/hermes-agent` | Docker-compatible fork with 2 local commits ahead of upstream. Differs from installed version (different branch). |
| **her2code (distribution)** | `~/dev/codemes/<SESSION_ID>/her2code/` | `master` | (GitHub) | **Sanitized distribution** — the one you ship. Contains `hermes-agent` as a **git submodule**. This is the canonical exportable version. |
| **dev/hermes** | `~/dev/hermes/` | `master` | `gitea/master` | Older/legacy dev copy. Usually clean. |

## Submodule chain

```
her2code/                      ← parent (distribution)
  ├── hermes-agent/            ← submodule (pinned commit from upstream)
  └── README.md, ...
```

When committing to her2code:
1. Commit inside `her2code/hermes-agent/` first (the submodule)
2. Then `git add hermes-agent` + commit in `her2code/` (the parent)

## Which repo is "the one we're working on"?

**The running/working version is ALWAYS `~/.hermes/hermes-agent/` (dev branch).**
This is the installed Hermes. All other repos are derivatives.

`her2code` is a **sanitized distribution snapshot** — its submodule may be stale
(an old sanitized commit). When the user says "сохрани текущую версию", do NOT
assume her2code reflects the running state. Instead:

1. **First**, verify `~/.hermes/hermes-agent/` is clean (`git status`). This IS
   the working version — if it has uncommitted changes, commit there.
2. **Then**, sync her2code's submodule FROM the running version:
   ```bash
   rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
     --exclude='venv' --exclude='.venv' --exclude='node_modules' \
     --exclude='dist' --exclude='release' \
     ~/.hermes/hermes-agent/ ~/dev/codemes/<SESSION_ID>/her2code/hermes-agent/
   ```
3. Commit inside submodule first, then update parent pointer.

```bash
# Quick scan for active changes:
for repo in ~/.hermes/hermes-agent ~/.hermes-docker/hermes-agent ~/dev/codemes/<SESSION_ID>/her2code ~/dev/hermes; do
  echo "=== $repo ==="
  git -C "$repo" status --short
done
```
