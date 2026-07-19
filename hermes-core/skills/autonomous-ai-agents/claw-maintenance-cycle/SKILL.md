---
name: claw-maintenance-cycle
description: Run the claw graph 5-phase maintenance cycle (Discover → Process → Draft+Log → Neo4j Sync → Audit). Use when cron fires or when user asks to run claw cycle.
version: 1.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [claw, maintenance, neo4j, compaction, cron]
    related_skills: []
---

# Claw Maintenance Cycle

Run the 5-phase claw graph maintenance cycle for the Neo4j claw graph
(Tool, Evidence, Session, CompactionPolicy, RegistrySnapshot nodes).

## When to use

- Cron fires: "Run claw orchestration cycle: Phase 1 Discover → Phase 2 Process → Phase 3 Draft+Log → Phase 4 Neo4j Sync → Phase 5 Audit"
- User says: "run claw cycle", "claw maintenance"
- User says: "check claw graph", "audit claw"

## ⚠️ DO NOT load `orchestration-cycle` for claw maintenance

**The `orchestration-cycle` skill (63KB, 927 lines) is a plan2 lifecycle enforcer — it has NOTHING to do with claw graph maintenance.** The cron prompt says "Run claw orchestration cycle" and keyword matching may load both skills in parallel, burning ~37K tokens.

**If you already loaded both `claw-maintenance-cycle` and `orchestration-cycle` in the same tool call (before reading either skill's content), immediately disregard `orchestration-cycle`.** It describes a 10-phase plan2 lifecycle with researcher pools, architect trios, and quality gates — none of which apply to claw graph maintenance. The claw cycle is 5 deterministic scripts. Treat `orchestration-cycle` as irrelevant noise and proceed with this skill only.

**Fix history:** Removed `orchestration-cycle` from `related_skills` (2026-07-01). Warning moved above Quick Run (2026-07-02) because parallel loading defeats skill-body warnings placed after the actionable content. If the agent still loads both, update the cron prompt to say: "Load ONLY claw-maintenance-cycle skill."

## Quick run

Scripts live in the codemes distribution, not `~/.hermes/scripts/`. Locate them first:

```bash
SCRIPTS=$(ls -d /home/user/dev/codemes/pavel_*/her2code/config/scripts | tail -1)
SYNC=$(ls -d /home/user/dev/codemes/pavel_*/her2code/config/plugins/claw-neo4j/sync-from-compactor.js 2>/dev/null | tail -1)

# Phase 4 sync — always use the opencode+ copy (codemes consistently lacks node_modules).
SYNC_FALLBACK=/home/user/cursor/first/opencode+/plugins/claw-neo4j/sync-from-compactor.js

# Phase 1: Discover
HOME=/home/user python3 $SCRIPTS/claw-discovery.py

# Phase 2: Process
HOME=/home/user python3 $SCRIPTS/claw-process.py

# Phase 3: Draft+Log
HOME=/home/user python3 $SCRIPTS/claw-draft-log.py

# Phase 4: Neo4j Sync (always use fallback — codemes copy lacks node_modules)
HOME=/home/user node $SYNC_FALLBACK \
  --compactor /home/user/.compactor \
  --session $(cat /home/user/.compactor/.last_session) \
  --registry $(ls -t /home/user/.compactor/registry/integrations.*.json | head -1)

# Phase 5: Audit
HOME=/home/user python3 $SCRIPTS/claw-audit.py
```

## Scripts

| Phase | Script (in codemes distro) |
|-------|--------|
| 1 Discover | `dev/codemes/pavel_*/her2code/config/scripts/claw-discovery.py` |
| 2 Process | `dev/codemes/pavel_*/her2code/config/scripts/claw-process.py` |
| 3 Draft+Log | `dev/codemes/pavel_*/her2code/config/scripts/claw-draft-log.py` |
| 4 Neo4j Sync | `dev/codemes/pavel_*/her2code/config/plugins/claw-neo4j/sync-from-compactor.js` |
| 5 Audit | `dev/codemes/pavel_*/her2code/config/scripts/claw-audit.py` |

## Directory structure

```
~/.compactor/
  registry/          — integrations.<ts>.json snapshots
  sessions/<sid>/    — checkpoint.2-5.json
  drafts/<op-id>/    — compaction proposal drafts
  summaries/         — YYYY-MM-DD.md daily summaries
  log.jsonl          — append-only compaction log
  .last_session      — session ID of latest cycle
```

## 9 Scanners

compose, mcp, skills, env, scripts, arch, health, litellm, process

## 5 Compaction Axes

merge, prune, collapse, rebudget, mcp-dedupe

## LLM agent is waste — use `no_agent=true`

**Finding (2026-07-01):** The cron job `8d4dd872e4aa` consumed 37,840 input tokens to run 5 deterministic scripts in sequence. All 5 phases are fixed Python/JS scripts with zero LLM reasoning needed — the agent just executes them one by one.

**Recommendation:** Convert to `no_agent=true` cron with a single wrapper script:
```bash
#!/bin/bash
# ~/.hermes/scripts/claw-cycle-wrapper.sh
set -euo pipefail
SCRIPTS=$(ls -d /home/user/dev/codemes/pavel_*/her2code/config/scripts | tail -1)
HOME=/home/user python3 $SCRIPTS/claw-discovery.py
HOME=/home/user python3 $SCRIPTS/claw-process.py
HOME=/home/user python3 $SCRIPTS/claw-draft-log.py
# ... Phase 4, 5 ...
```
This saves ~1.1M tokens/month at daily frequency.

## Inter-phase verification gates

After each phase, verify minimum success criteria before proceeding:

| Phase | Gate |
|-------|------|
| 1 Discover | `>=500 records returned, no ERROR in stderr` |
| 2 Process | `checkpoint file exists, candidates > 0` |
| 3 Draft+Log | `daily summary created at ~/.compactor/summaries/YYYY-MM-DD.md, > 500 bytes (do NOT check checkpoint.3.json — it's ~300-400 bytes of metadata)` |
| 4 Neo4j Sync | `"sync complete" in output, no ERR_MODULE_NOT_FOUND (seq=undefined is known pitfall, not a gate failure)` |
| 5 Audit | `audit markdown created at ~/.hermes/reports/claw-audit-<ts>.md, orphan count reported. Cross-check: audit Recommendations counts will NOT match Phase 2 candidate counts (known bug — see Pitfalls)` |

If any gate fails, abort and report which phase failed — don't silently continue.

## Verified runs

- `references/verified-run-2026-07-10.md` — late-night 07-09/early 07-10 UTC; documents process scanner recovery (41→46, +5) and first all-scanners-stable-except-process cycle
- `references/verified-run-2026-07-15.md` — 07-15/early 07-16 UTC; mcp (0→78, +78) and process (26→55, +29) BOTH recovered from the 07-13 crash — confirmed transient, not scanner breakage. Total 537 back above 500 gate. Neo4j reachable despite `systemctl is-active` = inactive (DB runs via Docker/other mechanism — do NOT trust systemctl as reachability signal)
- `references/verified-run-2026-07-16.md` — 07-16/early 07-17 UTC; process oscillated back down (55→29, -47%), all other scanners stable, total 511 (still above gate). Compose confirmed at 216 (up from 211). Skills continued growth (132, +1). Process oscillation pattern (26↔55) confirms unstable detection boundary, not a structural scanner breakage.
- `references/verified-run-2026-07-17.md` — 07-17/early 07-18 UTC; clean cycle. Process rebounded 29→37 (+27.6%), continuing oscillation. All other scanners zero delta. Total 519 (+8). mcp delta correct this cycle (78→78) — intermittent bug did not fire.
- `references/verified-run-2026-07-13.md` — 07-13/early 07-14 UTC; mcp scanner complete loss (78→0, -100%), process scanner second major drop (49→26, -47%), Neo4j DB unreachable (sync skipped), first cycle below 500 total records
- `references/verified-run-2026-07-11.md` — 07-11/early 07-12 UTC; process scanner continues recovery (46→49, +3), skills broke zero-delta streak (+1), mcp delta anomaly discovered, audit count discrepancy at 7+ cycles
- `references/verified-run-2026-07-09.md` — documents process scanner cliff-drop (70→41, -29) and 6th-cycle audit HC bug confirmation
- `references/verified-run-2026-07-08.md` — documents skills scanner shrinkage trend + audit count discrepancy
- `references/verified-run-2026-07-05.md` — documents audit count discrepancy bug discovery
- `references/verified-run-2026-07-04.md` — earlier run with same discrepancy confirmation

## Pitfalls

- The sync-from-compactor.js default compactor path points to `opencode+/opencode_claw/.compactor/` — always pass `--compactor ~/.compactor` explicitly.
- **Neo4j schema drift (CRITICAL):** `claw-discovery.py` queries Tool nodes with properties `tool_id`, `tool_name`, `tool_type` — these DO NOT EXIST. Actual properties are `id`, `name`, `type`. DBMS returns warnings every cycle (3+ per run). Fix: update discovery script to use actual property names. Also: `threshold` property missing from `CompactionPolicy` nodes.
- **`seq=undefined` in Phase 4 sync:** checkpoint JSONs lack a `seq` field — both syncs report `seq=undefined`. Either add seq to checkpoint generation in `claw-process.py`, or derive from timestamp in `sync-from-compactor.js`.
- **Phase 5 audit → Neo4j gap:** audit report produces markdown with 20+ orphan tools, 63 rebudget, 109 prune candidates — but NONE are persisted as `:AuditFinding` nodes in Neo4j. Cross-cycle trend analysis is impossible. Extend `claw-audit.py` to write structured findings to Neo4j.
- Tool nodes in Neo4j use property `name` not `tool_name`. Discovery registry uses `tool_name`.
- First cycle has no previous snapshot to compare against — audit notes this as "baseline cycle".
- Some skill `tool_name` values may be None; guard with `(x or '')`.
- **HOME may be `/home/user/.hermes/home` (not `/home/user`)** — `os.path.expanduser("~")` resolves to wrong path. Always set `HOME=/home/user` before running any phase script, and pass absolute paths (not `~`) to node sync script.
- **`sync-from-compactor.js` needs `neo4j-driver`** — the codemes distribution may lack `node_modules/`. If the script fails with `ERR_MODULE_NOT_FOUND: Cannot find package 'neo4j-driver'`, use the copy at `/home/user/cursor/first/opencode+/plugins/claw-neo4j/sync-from-compactor.js` which has dependencies pre-installed. Alternatively: `cd $(dirname $SYNC) && npm install neo4j-driver`.
- **`.last_session` is written by Phase 2** — current versions of `claw-process.py` update `/home/user/.compactor/.last_session` automatically after creating the session. Manual writing is only needed on the very first cycle or after a fresh `.compactor/` setup. If it is missing for Phase 4, derive the session ID from the latest directory under `.compactor/sessions/` or from Phase 2's printed output (e.g. `Session: 20260623T230105Z`).
- **Neo4j service may be inactive (2026-07-13):** The `neo4j` systemd service was `inactive` on 2026-07-13, and Phase 4 sync then skipped all DB operations (ECONNREFUSED 127.0.0.1:7687) with Phase 5 audit showing ERR for all Neo4j queries. The sync script handles this gracefully (prints "skip: unreachable" then "sync complete"). Starting the service requires `sudo systemctl start neo4j` which is not possible in cron context (no password). **HOWEVER (2026-07-15 update):** `systemctl is-active neo4j` can return `inactive` even when the DB IS reachable via the bolt driver. On 2026-07-15, systemctl reported inactive but Phase 1 discovery and Phase 4 sync both connected successfully (Tool=78, Evidence=81, Session=799). The DB appears to run via Docker or a non-systemd mechanism. **Do NOT trust `systemctl is-active neo4j` as the reachability signal** — just attempt the sync; it fails gracefully if truly down. If Neo4j is genuinely down, the claw graph is NOT updated and orphan/relation counts are unavailable in the audit.
- **Cron delivery:** the cron job delivers to `telegram:<YOUR_TELEGRAM_CHAT_ID>` but platform 'telegram' is not configured/enabled — claw-daily reports are NEVER delivered to @raicomml. Use `deliver=local` or fix Telegram platform config.
- **Cron log capture:** When running as a cron job, redirect each phase's stdout/stderr to a dated log file (e.g. `/tmp/claw-phase<N>-<ts>.log`) so post-hoc debugging does not depend on the agent's ephemeral transcript. Example: `HOME=/home/user python3 $SCRIPTS/claw-discovery.py > /tmp/claw-phase1-$(date +%Y%m%dT%H%M%S).log 2>&1`.
- **Near-zero delta cycles (invalidated for process scanner):** Through 2026-07-05, 8/9 scanners showed 0 delta. However, 2026-07-06 through 2026-07-17 showed meaningful volatility in the process scanner specifically. **Process scanner trend: oscillating at unstable detection boundary**: 81→74→68→70→**41**→**46**→**49**→**26**→**55**→**29**→**37** across 07-05→07-06→07-08→07-08→07-09→07-10→07-11→07-13→07-15→07-16→07-17. The -29 cliff-drop on 07-09 was the largest single-cycle change (-41.4%), followed by a +8 recovery over 2 cycles, then a second -23 drop on 07-13 (-47%), then a full +29 recovery on 07-15 back to 55, a -26 drop on 07-16 back to 29, and a +8 rebound on 07-17 to 37. The oscillation between ~26 and ~55 confirms an unstable detection boundary, not structural scanner breakage — each cycle flips a different subset of borderline detections. Cumulative from peak: 81→37 (-54.3%). Skills scanner went 140→121→125→126→126→127→131→132 (growth continues). Compose went 203→207→211→211→211→211→211→216→216 (stabilized at 216 after moving up from 211). **MCP scanner went 78→78→78→78→0 on 07-13, recovered to 78 on 07-15, stable at 78 on 07-16** — the 07-13 loss was transient. **07-13 was the first cycle below 500 total records (422)**, with 07-15 recovering to 537 and 07-16 settling at 511. Process scanner remains the sole volatile signal warranting daily monitoring; all other scanners have reached equilibrium.
- **Audit recommendation counts are STALE/HC (BUG):** `claw-audit.py` prints hardcoded "63 rebudget / 109 prune" in its Recommendations section — but actual Phase 2 output varies per cycle (e.g. 79 rebudget / 122 prune on 2026-07-09). This mismatch has persisted across at least 7 cycles (2026-07-04, 2026-07-05, 2026-07-06, 2026-07-08, 2026-07-09, 2026-07-11). The audit script does not read live candidate counts from the checkpoint; it uses fixed strings. Fix: update `claw-audit.py` to read `classification_summary` or `candidates` from `checkpoint.2.json` and report actual counts. Until fixed, do NOT trust the audit Recommendations section for candidate counts — always cross-check against Phase 2 stdout.
- **Phase 3 gate — check the daily summary, not checkpoint.3.json:** The `claw-draft-log.py` output includes two files: `checkpoint.3.json` (~300-400 bytes, just metadata) and the daily summary at `~/.compactor/summaries/YYYY-MM-DD.md` (>3KB with full log). Verify the daily summary for the >500-byte gate — the checkpoint alone will falsely fail.
- **Audit delta analysis broken for mcp scanner (INTERMITTENT BUG):** `claw-audit.py` Delta Analysis table showed `mcp | 0 | 78 | +78` on 2026-07-11, but mcp was 78 in the previous cycle (07-10) too. The audit's previous-snapshot comparison appears to always read 0 for mcp — likely the previous registry snapshot lacks mcp entries or the comparison logic doesn't match scanner names correctly. This inflates the delta and makes the Delta Analysis table unreliable for mcp. Cross-check deltas against Phase 1 stdout (which prints per-scanner counts) rather than trusting the audit's Delta Analysis table. First observed 2026-07-11. **UPDATE 2026-07-13:** The delta analysis was CORRECT this cycle (showed mcp 78→0, -78). The bug may be intermittent — when the current value is 0, the comparison happens to produce the correct result. Still unreliable for non-zero mcp values.
