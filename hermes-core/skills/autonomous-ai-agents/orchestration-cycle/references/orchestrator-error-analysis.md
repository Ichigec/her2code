# Orchestrator Error Analysis — «Санитизация Hermes» Case Study

> **Source cycle:** PID `<SESSION_ID>`, Docker infrastructure for `her2code/`
> **Date:** 2026-06-20
> **Evidence base:** Physical artifacts in `her2code/` (entrypoint.sh, status-proxy.py, docker-compose.yml, DOCKER.md, BUILD.md, Makefile)
> **Full requirements doc:** `~/dev/codemes/<SESSION_ID>/docs/requirements/orchestrator-improvement.md`

---

## The 7 Errors

### Error 1: Implement Before Research

**Symptom:** Orchestrator started writing `docker-entrypoint.sh` and `docker-compose.yml` before verifying the API contract between Desktop GUI and Hermes Gateway.

**Code proof:**
- `her2code/status-proxy.py` (34 lines) — HTTP proxy mapping `/api/status` → `{"status":"ok"}`, assuming Desktop needs this endpoint
- Gateway natively exposes `/health` (verified via `hermes-desktop-extension/SKILL.md` and `curl`)
- Orchestrator never loaded `hermes-desktop-extension/SKILL.md` to check the Desktop-Gateway contract

**Root cause:** Assumed endpoint contract instead of researching it.

---

### Error 2: Treating Symptoms Instead of Root Cause

**Symptom:** Instead of fixing the endpoint mismatch, wrote a proxy layer.

**Code proof:** `status-proxy.py` is a standalone HTTP server on port 18648 that:
1. Returns hardcoded JSON for `/api/status`
2. Proxies all other requests to `http://localhost:8648`
3. Is NOT integrated into `docker-compose.yml` — must be run manually

**Root cause:** "Desktop can't connect → add a proxy" instead of "what endpoint does Desktop expect? what does Gateway expose? fix the mismatch."

---

### Error 3: Repeating the Same Error (No Learning Loop)

**Symptom:** `docker-entrypoint.sh` corrupted `config.yaml` 3 times before stabilizing.

**Code proof (`her2code/docker-entrypoint.sh` lines 8-15):**
```python
cfg = yaml.safe_load(open(...)) or {}
gw = cfg.get('gateway', {})
gw.get('platforms', {}).pop('telegram', None)
gw.pop('telegram', None)
yaml.dump(cfg, open(..., 'w'), default_flow_style=False)
```

Problems:
1. **No backup:** modifies `config.yaml` in-place irreversibly
2. **No key existence check:** `pop('telegram', None)` if key missing → silently skips
3. **YAML format change:** dump uses different formatting than original
4. **No error handling:** Python errors swallowed by `2>/dev/null`
5. **Run on every start:** config is re-modified every time container starts

**Root cause:** No test matrix (with Telegram / without / `gateway.platforms=null` / malformed YAML). Each "it broke" → patch → "broke differently."

---

### Error 4: No Contracts Before Integration

**Symptom:** 3 components (Docker image, Desktop GUI, Gateway) integrated without formal interface contracts.

**Contracts that should have been checked BEFORE implementation:**

| Contract | Assumed | Reality | Impact |
|----------|---------|---------|--------|
| Desktop health endpoint | `/api/status` | `/health` | status-proxy.py written unnecessarily |
| Desktop expected port | 18648 (arbitrary) | 8648 (standard) | Port mismatch, proxy needed |
| Gateway config path | `/opt/data/config.yaml` | Depends on `HERMES_HOME` | Volume mount issues |
| Docker network mode | `bridge` (iteration 1) | `host` (iteration 3) | 3 compose rewrites |

**Root cause:** Integration started before interface boundaries were documented. Each mismatch was discovered at runtime, not design time.

---

### Error 5: Skipping Observers on Timeout

**Symptom:** HEALTHCHECK was configured but its results were never acted upon by the orchestrator.

**Code proof (`her2code/docker-compose.yml`):**
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:18648/health || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 12
  start_period: 120s
```

- `start_period: 120s` — 2 minutes of blind waiting before first check
- `retries: 12 × 10s = 120s` after start_period — total 4 minutes before unhealthy
- No one runs `docker inspect --format='{{.State.Health.Status}}'` after `docker compose up`
- Orchestrator assumed "compose up returned → service is running"

**Root cause:** Health checks were added but their results were never consumed in the pipeline. Docker knows the container is unhealthy; the orchestrator doesn't check.

---

### Error 6: Clock-Based Timing Instead of Reactive Probes

**Symptom:** Fixed delays (`sleep`, `start_period`) instead of reactive readiness checks.

**Code proof (`her2code/docker-entrypoint.sh` line 5):**
```bash
while [ ! -f "$CONFIG" ]; do sleep 1; done
```

This is an **infinite busy-wait with no timeout.** If the volume mount fails and `config.yaml` never appears, the entrypoint hangs forever. Docker HEALTHCHECK will eventually mark it unhealthy after 4 minutes — but the orchestrator isn't watching.

**Correct approach:**
```bash
timeout 30 bash -c 'while [ ! -f "$CONFIG" ]; do sleep 1; done' || { echo "FATAL: config not found"; exit 1; }
```

---

### Error 7: Over-Engineering — Bridge+Proxy+Entrypoint Instead of `network_mode: host`

**Symptom:** 3+ iterations of Docker architecture before arriving at the simplest solution.

**Iteration path:**
1. `network_mode: bridge` → Desktop can't reach Gateway directly
2. Add `status-proxy.py` to bridge the gap → now two services to manage
3. Add `docker-entrypoint.sh` to strip Telegram from config → in-place YAML corruption
4. Finally: `network_mode: host` — one service, direct access, no proxy, no entrypoint hack

**Dead code remaining after iteration 3:**
- `status-proxy.py` — not in `docker-compose.yml`, must be run manually
- `docker-entrypoint.sh` — modifies config in-place, fragile
- `DOCKER.md` — documents proxy that doesn't exist in compose

**Root cause:** Each problem was solved by ADDING a layer, never by asking "can I remove layers instead?" The YAGNI principle was violated at every step.

---

## The 5 SMART Requirements (What Should Have Happened)

| REQ | Gate | When | Prevents Errors |
|-----|------|------|-----------------|
| REQ-1: Research-Before-Implement | All AGENTS.md read, contracts verified | Phase 6 ENTRY | #1, #4 |
| REQ-2: Check-Contracts | `contracts-*.md` with curl output | Phase 3 (Research) | #2, #4, #7 |
| REQ-3: Fail-Fast | Timeouts on all waits, `set -euo pipefail` | Phase 6 EXIT | #3, #5, #6 |
| REQ-4: Never-Skip-Observers | `docker inspect healthy` before declaring done | Phase 8 EXIT | #5, #6 |
| REQ-5: KISS/YAGNI | Deviation log entry for every new file | Phase 4 + 6 EXIT | #7 |

---

## Detection Patterns for Future Cycles

When auditing an orchestrator's work, look for these artifacts:

| Artifact | What it signals |
|----------|----------------|
| A proxy/translator/adapter between two components that talk the same protocol | Contract wasn't checked (Error #2) |
| A shell script with `while sleep` and no `timeout` | Fail-fast missing (Error #3) |
| A config file that's modified in-place at startup | Error 3 pattern — add backup + verify |
| A `docker-compose.yml` with `start_period` > 60s and no external health watcher | Observer skip (Error #5) |
| 3+ root-level scripts that aren't wired into compose | Over-engineering (Error #7) |
| `curl` in HEALTHCHECK but no `docker inspect` in deployment docs | Observers configured but ignored (Error #5) |

---

## Cost of These Errors

| Error | Direct cost | Indirect cost |
|-------|------------|---------------|
| #1 (no research) | ~1 hour writing `status-proxy.py` | 34 lines of dead code |
| #2 (symptoms) | ~30 min debugging proxy | Masked the real problem |
| #3 (repeat errors) | 3 cycles × ~20 min = ~1 hour | Fragile entrypoint that could break on next config change |
| #4 (no contracts) | 3 compose iterations × ~15 min = ~45 min | Arbitrary port 18648 will confuse future users |
| #5 (skip observers) | Unmeasurable | False confidence; broken service unknown |
| #6 (clock timing) | 4 min × N starts wasted | Infinite hang risk on mount failure |
| #7 (over-engineering) | 3 architecture iterations | 2 dead files, confusing documentation |
| **Total waste** | **~4 hours + 2 dead files + 1 fragility bomb** | |
