# Static Site — GitHub Pages

## gh CLI Auth (Device Flow)

When deploying programmatically to GitHub Pages, the `gh` CLI must be authenticated. The device flow is the way to do this in headless/remote environments:

```bash
# Run persistently — DO NOT kill before user enters code
ssh user@vps '
gh auth login --hostname github.com --git-protocol ssh 2>&1 | tee /tmp/gh_code
'

# Output will show:
# ! First copy your one-time code: XXXX-XXXX
# Open this URL to continue: https://github.com/login/device
```

User enters code at `https://github.com/login/device`. Process completes with exit 0.

Verify: `gh auth status` → `✓ Logged in to github.com account <user>`

**Critical pitfalls:**
- Each restart of `gh auth login` generates a NEW code — keep the original process alive
- Multiple concurrent gh auth processes cause chaos — kill stale ones with `pkill -f "gh auth"`
- The code expires if user takes too long

## Repo creation

```bash
gh repo create USER/REPO --public --description '...'
gh repo clone USER/REPO
```

## Pages activation

```bash
gh api repos/USER/REPO/pages --method POST \
  -f 'source[branch]=main' \
  -f 'source[path]=/'
```

Check build status:
```bash
gh api repos/USER/REPO/pages | jq .status
# "building" → "built" (10-30 seconds)
```

URL: `https://USER.github.io/REPO/`

## Yandex Metrika Domain Format

When using the GitHub Pages URL in Yandex Metrika, enter WITHOUT protocol:
```
✅ USER.github.io/REPO/
❌ https://USER.github.io/REPO/
```

See also: `yandex-metrika-setup` skill.
