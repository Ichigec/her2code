# LiteLLM Proxy — Operational Notes

Common operational issues with LiteLLM Proxy in local inference stacks.

## Memory Leak — 21 GB After 2 Days

**Symptom**: LiteLLM Docker container uses 20+ GB RSS after running for days.
Single anonymous memory region dominates the heap.

**Diagnosis steps**:
```bash
# Check container memory
docker stats litellm --no-stream

# Check process memory breakdown
docker exec litellm cat /proc/1/status | grep -E 'VmRSS|VmSize|RssAnon'
docker exec litellm cat /proc/1/smaps_rollup | head -15

# Verify it's NOT the DB (DB is typically tiny — 8 MB)
docker exec litellm-db psql -U litellm -d litellm \
  -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
      FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"
```

**Root cause**: Known bug — [Issue #12685](https://github.com/BerriAI/litellm/issues/12685),
aiohttp connection pooling memory leak. PR fix: [#17388](https://github.com/BerriAI/litellm/pull/17388).
Affects v1.83.x and earlier.

**Immediate fix** — restart the container:
```bash
docker restart litellm
```

**Permanent fix** — add worker recycling to the Docker command:

```yaml
# In docker-compose.yml or equivalent:
command:
  - "--config"
  - "/app/config.yaml"
  - "--port"
  - "4000"
  - "--host"
  - "0.0.0.0"
  - "--num_workers"
  - "1"
  - "--max_requests_before_restart"
  - "10000"
```

Alternatively, set memory limit so Docker kills + restarts when threshold exceeded:
```yaml
deploy:
  resources:
    limits:
      memory: 4G
```

**Version note**: Upgrade to latest LiteLLM when possible — PR #17388 may be merged.

## Useful Inspection Commands

```bash
# List all configured models
docker exec litellm cat /app/config.yaml

# Check LiteLLM version
docker exec litellm pip show litellm | grep Version

# View recent logs (spam alert — sync loops every 30s)
docker logs litellm --tail 30

# Database size
docker exec litellm-db psql -U litellm -d litellm \
  -c "SELECT pg_size_pretty(pg_database_size('litellm'));"
```
