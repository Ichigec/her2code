# her2code Distribution Cycle — Lessons Learned

> From the full orchestration cycle on her2code (<SESSION_ID>), 2026-06-19 through 2026-06-21.

## PII Sanitization — Second Pass Required

Security Agent 1 found PII the first pass missed:

| Missed PII | Location | Why missed |
|-----------|----------|------------|
| `pavel` username (7 places) | opencode-plus systemd, README, scripts | Regex only matched `pavel_`, not standalone `pavel` |
| `<YOUR_HARDCODED_TOKEN>...` API key | opencode-android SettingsDataStore.kt:32 | Sanitizer didn't scan .kt files |
| PID in PlantUML | 3 .puml files | `.puml` not in text_file_extensions list |
| `changeme` defaults (runtime) | compose files, Python scripts | Only documented, not fixed in code |

### Fix pattern

1. Spawn Security Agent 1 (PII Monitor) + Security Agent 2 (SAST) BEFORE Phase 1
2. PII Monitor scans git diff after EVERY phase
3. SAST Auditor reviews all artifacts for security anti-patterns

## Docker Testing — The 5-Gate Smoke Test

Before ANY GitHub push:

```bash
# Gate 1: Container starts
docker compose up -d

# Gate 2: Health endpoint responds (wait up to 180s on ARM64)
for i in $(seq 1 90); do curl -sf localhost:18648/health && break; sleep 2; done

# Gate 3: Models endpoint works
curl -s localhost:18648/v1/models -H "Authorization: Bearer ***"

# Gate 4: Chat completion works (with valid model)
curl -s localhost:18648/v1/chat/completions \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -d '{"model":"...","messages":[{"role":"user","content":"Hi"}]}'

# Gate 5: Clean shutdown
docker compose down
```

## Critical Architecture Rules

1. **NEVER put real keys in distribution** — `.env.example` with placeholders only
2. **NEVER push to GitHub before smoke test** — all 5 gates must pass
3. **`~` in docker-compose.yml** — doesn't expand in sandboxed shell. Use absolute paths.
4. **`network_mode: host`** — only way for Docker to access host services (llama.cpp, etc.)
5. **Config persistence** — Hermes overwrites config.yaml on startup. Re-apply custom config after `up`.

## Observer Pattern

4 observers spawned BEFORE Phase 1, report AFTER Phase 10:
- Auditor — delegation quality, information loss
- Critic — dead code, over-engineering
- Idea Generator — unheard ideas, missing connections, pipeline optimization
- Knowledge Curator — new entities, knowledge gaps, graph integration

Observers caught: 7 PII items, 2 CRITICAL security findings, skipped phases 7-9,
"Implement before Research" anti-pattern.
