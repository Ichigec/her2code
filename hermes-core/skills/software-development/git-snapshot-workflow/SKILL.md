---
name: git-snapshot-workflow
description: "Save a known-good working state of a multi-component system using git tags, dev branches, and config backups before making experimental changes. Use when user asks to 'save current version', 'preserve working state', or 'test improvements separately'."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [git, version-control, snapshot, dev-branch, backup, safe-iteration]
    related_skills: [github-repo-management, build-engineering-standards, graph-of-thoughts]
---

# Git Snapshot Workflow

Save a recoverable checkpoint of a multi-component system before making
experimental changes. Creates git tags on the stable branch, dev branches for
future work, and separate backups for config files containing secrets.

## Trigger

- "Save current version" / "сохранить текущий вариант"
- "Before changes, save working state"
- "Test improvements separately" / "тестировать доработки"
- Any request to preserve a known-good state before experimentation

## Workflow

### Step 1: Clarify scope

Use `clarify()` to determine which components to snapshot. A "save everything"
request may span:

- Backend repos (e.g. Hermes Agent — Python + CLI + desktop GUI in one repo)
- Mobile apps (e.g. Android — separate repo)
- Desktop GUI (may be inside backend repo or separate)
- Config files with secrets (config.yaml, .env — NEVER in git)
- Docker copies / external service configs

### Step 2: Verify each component's state

For each component, check BEFORE acting:

```bash
# Is it a git repo?
git -C <path> rev-parse --show-toplevel

# Current branch + uncommitted file count
git -C <path> branch --show-current
git -C <path> status --short | wc -l

# Existing tags
git -C <path> tag --list

# CRITICAL: Is .gitignore present?
ls <path>/.gitignore

# CRITICAL: Are build artifacts tracked in git?
git -C <path> ls-files | grep -E "^(build/|\.gradle/|app/build/|dist/|node_modules/)" | wc -l
```

Record findings per-component. This determines whether Step 3 (cleaning) is needed.

### Step 3: Clean repos (if build artifacts are tracked)

If a repo was committed without `.gitignore`, build artifacts (.class, .bin,
generated sources, .gradle cache) are tracked in git. Must remove them BEFORE
the snapshot commit — otherwise the tag includes garbage.

1. **Create `.gitignore`** for the project type. See `references/gitignore-templates.md`
   for ready-to-use templates (Android/Gradle, Node, Python).

2. **Remove build artifacts from git index** (keeps files on disk):
   ```bash
   git -C <path> rm -r --cached --quiet <build-dir>/
   ```
   Only remove paths that actually exist as tracked files. If a path doesn't
   exist, git returns an error — skip it and continue.

3. **Verify removal**:
   ```bash
   git -C <path> ls-files | grep -E "^<build-dir>/" | wc -l  # should be 0
   ```

4. **Stage everything** (`.gitignore` prevents re-adding artifacts):
   ```bash
   git -C <path> add -A
   ```

5. **Verify no build artifacts re-staged**:
   ```bash
   git -C <path> diff --cached --name-status | grep -E "^A\s+.*(build/|\.gradle/)" | wc -l  # should be 0
   ```
   Note: staged **deletions** (status `D`) for build artifacts are expected and
   correct — they are being removed from tracking.

### Step 4: Commit + tag

For each repo, create a dated annotated tag:

```bash
git -C <path> commit -m "snapshot: stable-YYYY-MM-DD — <brief description>"
git -C <path> tag -a stable-YYYY-MM-DD -m "Stable snapshot — <description>"
```

Use **annotated tags** (`-a`) — they store metadata (date, author, message)
and are visible in `git tag -n` listings.

### Step 5: Backup config files (secrets)

Config files with API keys (`.env`, `config.yaml`) must NEVER be committed to
git. Back them up separately:

```bash
mkdir -p ~/.hermes/backups/
cp ~/.hermes/config.yaml ~/.hermes/backups/config.yaml.stable-YYYY-MM-DD
cp ~/.hermes/.env ~/.hermes/backups/.env.stable-YYYY-MM-DD
```

Set file permissions: `chmod 600 ~/.hermes/backups/*stable-*`

### Step 6: Create dev branches

For each repo:

```bash
git -C <path> branch dev
```

Future experimental work happens on `dev`. The stable branch (`main`/`master`)
stays at the tag. Merge `dev` → `main` only after testing.

### Step 7: Verify

Run a single verification block covering all components:

```bash
# For each repo:
git -C <path> tag --list | grep stable-YYYY-MM-DD  # tag exists
git -C <path> status --short | wc -l               # 0 uncommitted
git -C <path> branch --list dev                    # dev branch exists

# Config backup:
ls -la ~/.hermes/backups/*stable-YYYY-MM-DD
```

## Recovery

### Restore code to known-good state

```bash
git -C <path> checkout stable-YYYY-MM-DD
```

### Restore config files

```bash
cp ~/.hermes/backups/config.yaml.stable-YYYY-MM-DD ~/.hermes/config.yaml
cp ~/.hermes/backups/.env.stable-YYYY-MM-DD ~/.hermes/.env
```

### Discard experimental changes on dev

```bash
git -C <path> checkout dev
git -C <path> reset --hard stable-YYYY-MM-DD
```

### Merge tested changes to stable

```bash
git -C <path> checkout main  # or master
git -C <path> merge dev
git -C <path> tag -a stable-YYYY-MM-DD-v2 -m "Stable snapshot — post-merge"
```

## Submodules

When a repo uses git submodules (e.g. `her2code` contains `hermes-agent` as a
submodule), changes inside the submodule must be committed INSIDE FIRST, then
the parent repo pointer updated:

```bash
# 1. Commit inside submodule
cd <parent>/<submodule>
git add -A
git commit -m "..."

# 2. Update parent's submodule pointer
cd <parent>
git add <submodule>
git commit -m "update submodule — ..."
```

Skipping step 1 and only running `git add <submodule>` in the parent stages
the pointer change but the submodule's own changes remain uncommitted. The
parent status will show `(изменено содержимое, неотслеживаемое содержимое)`
until the submodule is clean.

## Pitfalls

- **Submodule may be stale — sync from running version first:** The `her2code`
  repo contains `hermes-agent` as a sanitized submodule that may be far behind
  the actual running version at `~/.hermes/hermes-agent/` (dev branch). When
  user says "сохрани текущую версию", always rsync the running version INTO
  the submodule BEFORE committing. The submodule's sanitized history and the
  running version's dev history are incompatible (different remotes, shallow
  clones) — git fetch/merge fails. Use rsync to sync file contents:
  ```bash
  rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='venv' --exclude='.venv' --exclude='node_modules' \
    --exclude='dist' --exclude='release' \
    ~/.hermes/hermes-agent/ ~/dev/codemes/<SESSION_ID>/her2code/hermes-agent/
  ```
  Symptom of getting this wrong: user says "а это точно полная копия? у нас
  менялся не только фронтенд, но и бэк" — you committed only the submodule
  pointer change but the submodule content was stale.

- **Missing git global config in submodules:** Fresh clones or submodules may
  not inherit `user.name`/`user.email`. Commits inside submodules fail with
  "Author identity unknown." Fix: find identity from another repo's local config:
  ```bash
  git -C ~/.hermes/hermes-agent config user.name   # → Pavel
  git -C ~/.hermes/hermes-agent config user.email  # → ichigec@gmail.com
  git config --global user.name "Pavel"
  git config --global user.email "ichigec@gmail.com"
  ```

- **Build artifacts in initial commit:** Projects committed without `.gitignore`
  accumulate build artifacts in git. `.gitignore` alone only prevents FUTURE
  additions — already-tracked files need `git rm -r --cached` to untrack.
  Symptom: 500+ "uncommitted" files that are all build outputs.

- **`git rm` path errors:** If `build/` doesn't exist at repo root (e.g. only
  `app/build/` exists), `git rm -r --cached build/` fails with "pathspec did not
  match". Only remove paths that exist as tracked files.

- **Never commit `.env`:** Config files with API keys go to `~/.hermes/backups/`,
  not git. Even if `.gitignore` excludes them, double-check `git diff --cached`
  before committing.

- **Verify after staging:** After `git add -A`, always check that build artifacts
  aren't re-staged. Staged **deletions** (D status) for build artifacts are
  correct — staged **additions** (A status) for build artifacts mean `.gitignore`
  is wrong.

- **Multi-component coordination:** A "save everything" request spans multiple
  repos. Track each component's status separately. Don't declare success until
  ALL components are verified — one missed repo means the snapshot is incomplete.

- **Tag naming:** Use `stable-YYYY-MM-DD` format (not `v1.0` or `backup1`).
  Date-based names are self-documenting and sort chronologically. For multiple
  snapshots in one day, append `-v2`, `-v3`.

- **Annotated vs lightweight tags:** Always use `git tag -a` (annotated). 
  Lightweight tags are just pointers — no metadata, no message, harder to
  understand months later.

## References

- `references/gitignore-templates.md` — ready `.gitignore` for Android/Gradle, Node, Python.
- `references/hermes-repo-layout.md` — Pavel's 4-repo Hermes map: which is which, submodule chain, how to find the active one.
