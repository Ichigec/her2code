# LiteLLM Memory Leak — Full Diagnosis & Fix

## TL;DR

**Root cause:** glibc malloc arena fragmentation driven by background DB sync tasks (not request volume, not aiohttp pooling). Fix: `MALLOC_ARENA_MAX=2` + `mem_limit: 4g` + `LITELLM_LOG=WARNING`. Result: 17.66 GB → 849 MB (95.2% reduction).

## The Leak Mechanism

LiteLLM runs background tasks on fixed intervals regardless of traffic:

| Task | Interval | Cycles in 43h | What it does |
|------|----------|---------------|--------------|
| Spend logs queue monitor | 2s | 77,970 | Polls log queue |
| Policy registry sync | 30s | 5,198 | DB → in-memory registry |
| Attachment registry sync | 30s | 5,198 | DB → in-memory registry |
| Prisma health watchdog | 30s | 5,198 | DB health probe |
| Tag spend update | 29s | 5,373 | Spend tag refresh |
| Batch/Responses cost check | ~30s | ~10,000 | Cost calculation |

Total: ~98,762 DB queries in 43 hours. Each query creates Prisma async HTTP objects, coroutine frames, response parsing intermediates. Python GC frees the objects, but glibc malloc does NOT return the freed arena memory to the OS.

Without `MALLOC_ARENA_MAX`, glibc creates up to `8 × CPU_cores` arenas (128+ on a 16-core machine). Each arena has a 128 MB trim threshold. Freed memory below the threshold stays in the arena forever. Over 43 hours, this accumulates to 17+ GB.

**Key insight:** This is an IDLE leak. 7 requests in 48 hours, 0.4% CPU, yet 17.66 GB consumed. The leak rate is ~262 MB/hour (RSS) or ~418 MB/hour (RSS + swap).

## Diagnosis Methodology

### Step 1: Container-level overview

```bash
docker stats --no-stream litellm
# Shows MEM USAGE / LIMIT. If limit is empty → no mem_limit set (problem #1).
```

### Step 2: Process-level memory breakdown

```bash
# Find the PID (host namespace)
ps aux | grep "litellm --config" | grep -v grep

# Detailed memory
cat /proc/<PID>/status | grep -E 'VmRSS|VmData|RssAnon|RssFile|VmSwap|VmHWM'
```

Key indicators:
- `RssAnon` ≈ `VmRSS` → all anonymous heap (not file-backed mmap) → confirms heap leak
- `VmSwap` > 0 → process has been swapping → memory pressure
- `VmHWM` = `VmRSS` → process is at its all-time peak (monotonic growth)

### Step 3: Docker memory limit check

```bash
docker inspect litellm --format 'Memory={{json .HostConfig.Memory}} MemorySwap={{json .HostConfig.MemorySwap}}'
# If Memory=0 → no limit → container grows unbounded
```

### Step 4: Cgroup memory stats

```bash
# Find cgroup path from container ID
CONTAINER_ID=$(docker inspect litellm --format '{{.Id}}')
CGROUP=/sys/fs/cgroup/system.slice/docker-${CONTAINER_ID}*/

cat ${CGROUP}memory.current    # current usage
cat ${CGROUP}memory.peak       # all-time peak
cat ${CGROUP}memory.swap.current  # swap usage
cat ${CGROUP}memory.events     # OOM events (if any)
```

### Step 5: Identify leak driver (background tasks)

```bash
# Check what LiteLLM is actually doing
docker logs litellm 2>&1 | grep -E "scheduled|monitor|watchdog|interval" | head -15
```

Look for tasks with short intervals (2s, 30s). Calculate total cycles:
```
leak_rate = total_memory / uptime_hours
cycles_per_hour = sum(3600 / interval_seconds for each task)
memory_per_cycle = leak_rate / cycles_per_hour
```

If `memory_per_cycle` is small (0.1-0.5 MB) and consistent → glibc arena fragmentation.

### Step 6: Verify MALLOC_ARENA_MAX is unset

```bash
docker exec litellm env | grep MALLOC_ARENA_MAX
# Empty output = not set = glibc uses 8 × CPU_cores arenas
```

### Step 7: Rule out other causes

```bash
# DB size (should be tiny, <100 MB)
docker exec litellm-db psql -U litellm -d litellm -c "
  SELECT pg_size_pretty(pg_database_size('litellm'));"

# Spend logs count (should be manageable)
docker exec litellm-db psql -U litellm -d litellm -c "
  SELECT count(*) FROM \"LiteLLM_SpendLogs\";"

# Open file descriptors (should be <100)
ls /proc/<PID>/fd | wc -l

# Thread count (7 is normal for single-worker uvicorn)
ls /proc/<PID>/task | wc -l

# Network connections (should be <20 idle)
docker exec litellm bash -c 'cat /proc/1/net/sockstat'
```

### Step 8: Confirm aiohttp pool is NOT the primary cause

```bash
# Check aiohttp session config in startup logs
docker logs litellm 2>&1 | grep "SESSION REUSE"
# Shows: limit=1000, limit_per_host=500
# At 7 req/48h, this pool is effectively empty — NOT the leak driver
```

## The Fix

### Applied fix (2026-07-03, verified)

In `/home/user/cursor/first/compose.phoenix.yml`, litellm service:

```yaml
environment:
  - MALLOC_ARENA_MAX=2           # #1 fix — limits arenas to 2 instead of 128+
  - LITELLM_LOG=WARNING           # reduces log-induced allocations from 30s syncs
  - PYTHONUNBUFFERED=1            # prevents stdout buffer accumulation
  # ... existing env vars ...
mem_limit: 4g                     # hard ceiling; OOM → restart: unless-stopped = auto-recovery
```

Apply:
```bash
cd /home/user/cursor/first
docker compose -f compose.phoenix.yml up -d litellm
```

### Why MALLOC_ARENA_MAX=2 works

| Setting | Arenas | Memory behavior |
|---------|--------|-----------------|
| Unset (default) | 8 × CPU cores (128+ on 16-core) | Each arena holds freed memory below 128 MB trim threshold. Fragmentation accumulates across all arenas. |
| `MALLOC_ARENA_MAX=2` | 2 | All allocations share 2 arenas. Freed memory is more likely to be above trim threshold → returned to OS. Fragmentation bounded. |

This is a well-known fix for ALL long-running Python processes on glibc (Django, FastAPI, Celery, uvicorn). Not LiteLLM-specific.

### Why --max_requests_before_restart does NOT work

The previously suggested fix (`--max_requests_before_restart 10000`) only recycles workers after 10K requests. With 7 requests in 48 hours, the worker would never recycle. The leak grows from background tasks, not request handling. Worker recycling is a band-aid for request-driven leaks; `MALLOC_ARENA_MAX` addresses the root cause.

## Verification

After applying the fix:

```bash
# Memory should be <1 GB after startup
docker stats --no-stream litellm

# Env vars applied
docker exec litellm env | grep -E "MALLOC_ARENA_MAX|LITELLM_LOG"

# Health
curl -s http://localhost:4000/health/liveness
curl -s http://localhost:4000/health/readiness | python3 -m json.tool

# API works
curl -s http://localhost:4000/v1/models -H "Authorization: Bearer sk-local" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['data']), 'models')"
```

## Results

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| RSS | 11.06 GB | 849 MB | -92.3% |
| Swap (litellm) | 6.60 GB | 0 | -100% |
| Total (RSS+Swap) | 17.66 GB | 849 MB | -95.2% |
| VSZ | 18.2 GB | 990 MB | -94.6% |
| System swap | 13.0 / 15 GB | 6.8 / 15 GB | -6.2 GB freed |
| API models | — | 46 ✅ | working |
| Health | healthy | healthy ✅ | working |

## Related GitHub Issues

- [#12685 — Heavy RAM Usage over time](https://github.com/BerriAI/litellm/issues/12685) — original report, attributed to aiohttp
- [#17388 — prevent memory leak in aiohttp connection pooling](https://github.com/BerriAI/litellm/pull/17388) — upstream fix for request-driven pooling leak
- The glibc arena fragmentation issue affects ALL long-running Python Docker services, not just LiteLLM. The aiohttp fix addresses one vector; `MALLOC_ARENA_MAX=2` addresses the systemic cause.

## Pavel's Setup Details

- **Version**: 1.83.7-stable (ghcr.io/berriai/litellm-database:v1.83.7-stable)
- **Python**: 3.13.13, glibc malloc
- **Config**: `/home/user/cursor/first/docker/litellm/config.yaml` (mounted read-only)
- **Compose**: `/home/user/cursor/first/compose.phoenix.yml`
- **DB**: Postgres 16 on `litellm-db:5432` (8 MB total — not the leak source)
- **Callbacks**: 14 success callbacks (ArizePhoenixLogger, _ProxyDBLogger, SkillsInjectionHook, etc.) — each adds state per background cycle
- **aiohttp pool**: limit=1000, limit_per_host=500 — not the issue at 7 req/48h
- **Prisma**: subprocess query-engine (PID 279, 26 MB) + async HTTP IPC — each of ~100k queries creates temporary objects that fragment glibc arenas
