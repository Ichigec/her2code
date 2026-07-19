# start.sh start_gui() — Triple Bug (FIXED 2026-07-08)

> **STATUS: FIXED.** All three bugs were patched in `start.sh` on 2026-07-08.
> This file documents the bugs for historical reference and verification.

## Verification (bugs are FIXED)

```bash
# These lines should now show the CORRECT values:
sed -n '672p' ~/dev/hermes_portable/start.sh   # PORT_DASH (was PORT_GW)
sed -n '674p' ~/dev/hermes_portable/start.sh   # DASH_TOKEN (was gw_api_key)
sed -n '690p' ~/dev/hermes_portable/start.sh   # --disable-gpu --disable-software-rasterizer --no-sandbox
sed -n '664,666p' ~/dev/hermes_portable/start.sh  # comments now correct
```

If any of these show the OLD values, you're running a stale copy (e.g. old USB backup).

## The three bugs (historical)

All three were in `start_gui()` function, `~/dev/hermes_portable/start.sh`.

### Bug 1: Wrong port (line 680 → now ~672)

| | Was (wrong) | Now (correct) |
|---|---|---|
| Code | `${PORT_GW}` (gateway :18649) | `${PORT_DASH}` (dashboard :9123) |
| Effect | `waitForHermes()` polls `/api/status` → gateway returns 404 → 45s timeout → boot fail | Dashboard serves `/api/status` → 200 → boot succeeds |

### Bug 2: Wrong token (line 682 → now ~674)

| | Was (wrong) | Now (correct) |
|---|---|---|
| Code | `${gw_api_key}` = API_SERVER_KEY (64-hex) | `${DASH_TOKEN}` = `sk-docker-b` |
| Effect | Dashboard rejects with `401: Unauthorized` on every API call | Dashboard authenticates correctly |

### Bug 3: Missing GPU flags (line 697 → now ~690)

| | Was (wrong) | Now (correct) |
|---|---|---|
| Code | `--no-sandbox` only | `--disable-gpu --disable-software-rasterizer --no-sandbox` |
| Effect | Chromium GPU sandbox crashes (error_code=1002 → FATAL) on ARM64 Jetson | GPU sandbox bypassed, GUI starts |

### The misleading comments (lines 664–666 — REWRITTEN)

Old comments actively lied (asserted gateway port + API_SERVER_KEY were correct).
Now they correctly document dashboard port + DASH_TOKEN.
