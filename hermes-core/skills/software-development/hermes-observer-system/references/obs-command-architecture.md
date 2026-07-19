# `/obs` Command — Architecture and Fixes (ALL IMPLEMENTED 2026-06-28)

Deep analysis and complete fix of why observer findings were not "injected into the dialog". Based on sessions `20260627_202849_0a0c69` and `20260628_232446_717478`.

**STATUS: ALL 4 LAYERS FIXED + 2 additional fixes discovered during implementation.**

## Code Map

| Component | File | Lines | Role |
|-----------|------|-------|------|
| Command registration | `hermes_cli/commands.py` | 113-114 | `CommandDef("obs", ..., aliases=("observers","observer","findings"))` |
| Dispatch | `cli.py` | 9173-9177 | `elif canonical in ("obs","observers","observer","findings"):` → `_handle_observer_command()` |
| Handler | `cli.py` | 6255-6324 | Queries Neo4j, formats, writes to stdout |
| Desktop allowlist | `apps/desktop/src/lib/desktop-slash-commands.ts` | — | `['/obs', 'Show observer findings for this session']` |

## Handler Internals (`_handle_observer_command`, cli.py:6255-6324)

```
1. Gets session_id from self.session_id or self.agent.session_id
2. Queries Neo4j via raw HTTP (urllib):
   - MATCH (f:AuditFinding) WHERE f.session_id = $sid → 15 most recent
   - MATCH (f:CriticFinding) WHERE f.session_id = $sid → 15 most recent
3. Merges + sorts by timestamp, takes top 15
4. Formats as plain text lines
5. Writes to _sys.stdout.write() — NOT injected into conversation_history
```

## The 4-Layer Problem

### Layer 1: Rich Formatting (FIXED in 20260627_202849_0a0c69)

`_console_print()` (Rich) wrapped lines at 120 chars and added ANSI markup (`[bold]`, `[yellow]`). Fixed by switching to `_sys.stdout.write()`. Also removed `chr(10)→' '`, `chr(13)→''` sanitization (unnecessary — Neo4j data was already clean).

### Layer 2: Session Mismatch ✅ FIXED 2026-06-28

When current session has 0 findings, `_handle_observer_command()` and `_handle_observer_json_command()` now **automatically discover and display** other sessions that have findings:

```
No observer findings for session 32446_717478 yet.
Sessions with findings:
  27_202849_0a0c69: 389 findings — /obs 20260627_202849_0a0c69
  27_201937_4ef575: 40 findings — /obs 20260627_201937_4ef575
  ...
```

Implementation: after querying current session and getting 0 results, runs a Neo4j query for `f.session_id <> $sid` and lists top 5 sessions by count. For the JSON variant (ObserverPanel), includes `other_sessions` field in response. The ObserverPanel (`observer-panel.tsx`) now shows clickable session buttons that reload findings for that session.

### Layer 3: Findings Not Injected into Agent Context ✅ FIXED 2026-06-28

**Established pattern** from `/browser connect` (cli.py:9761-9765) — `_pending_input.put()`:

```python
# After printing findings to stdout, inject as system note:
if hasattr(self, '_pending_input'):
    ctx = ["[System note: The user invoked /obs to review observer findings.",
            "Here are the findings for this session:", ""]
    for f in findings[:10]:
        ctx.append(f"  [{f['type'].upper()}] ({f['severity']}) {f['finding']}")
    ctx.append("")
    ctx.append("Review these findings and suggest concrete actions to address them.]")
    self._pending_input.put("\n".join(ctx))
```

The `_pending_input` queue is read by the main loop on the next turn. If agent is idle → triggers immediate response. If agent is busy → queued for next turn. The `hasattr(self, '_pending_input')` guard ensures this only fires in CLI/TUI context (NOT slash_worker, where `_pending_input` doesn't exist).

### Layer 4: Auto-Notify Cron Job ✅ DEPLOYED 2026-06-28

Script `~/.hermes/scripts/observer-notify.py` polls Neo4j for new findings since last check. Runs via `no_agent` cron job (script IS the job, no LLM needed):

```bash
hermes cron create 'every 5m' \
  --script ~/.hermes/scripts/observer-notify.py \
  --no-agent \
  --name observer-notify
```

**Delivery semantics with `no_agent=True`:**
- Non-empty stdout → delivered verbatim to the user
- Empty stdout → SILENT (nothing sent to user)
- Non-zero exit → error alert

The script tracks `last_check` timestamp in `~/.hermes/.observer_last_check`. On first run, looks back 15 minutes. On subsequent runs, only finds post-last-check. **Critical**: update the state file BEFORE printing, so a crash mid-output doesn't cause replay on next run.

Cron job ID: `3cd0c9026482`, delivery: `local` (script output saved to session store).
The inline and deep observers (per the 3-tier architecture) DO append notes to the agent's response — these are visible. But session-end findings go only to Neo4j and require `/obs` to retrieve.

## Output Path (Desktop/GUI)

```
User types /obs
  → Desktop composer (TypeScript)
  → requestGateway('slash.exec', {session_id, command: '/obs'})
  → Gateway server.py → SlashWorker stdin
  → SlashWorker: contextlib.redirect_stdout(buf)
  → HermesCLI.process_command('/obs')
  → _handle_observer_command()
  → _sys.stdout.write(...) captured in buf
  → JSON {id, ok, output} written to SlashWorker stdout
  → Gateway → WebSocket → Desktop
  → Displayed as system message in chat
```

**Key insight**: At no point does this output re-enter the agent's message loop. It goes from handler → stdout → captured → sent to UI. The agent's `conversation_history` is never touched.

## New Findings During Implementation

### Finding 5: TUI Slash Output Rendered Gray/Non-Copyable ✅ FIXED

Slash command output in the TUI is rendered with `kind: 'slash'` and `color={t.color.muted}` (gray, dim). Users reported findings were "серый, не копируемый, как будто пока не конечный результат" (gray, non-copyable, looks like intermediate output).

**Root cause**: `ui-tui/src/components/messageLine.tsx` line 134:
```tsx
if (msg.kind === 'slash') {
  return <Text color={t.color.muted}>{msg.text}</Text>  // ← muted = gray
}
```

`t.color.muted` = `ansi256(245)` (gray), `t.color.text` = `ansi256(136)` (normal amber).

**Fix**: Change to normal text color:
```tsx
if (msg.kind === 'slash') {
  return <Text color={t.color.text}>{msg.text}</Text>
}
```

**Rebuild**: `cd ui-tui && npm run build` (~111ms). Restart TUI/desktop required.

### Finding 6: Neo4j Timestamp Type Mismatch (str vs int) ✅ FIXED

`f.timestamp` can be either ISO-8601 string (`"2026-06-27T20:28:..."`) or epoch integer (`1782581330`), depending on which observer wrote the finding. Python's `list.sort()` cannot compare `str < int`, causing:

```
TypeError: '<' not supported between instances of 'str' and 'int'
```

**Fix**: Normalize all timestamps to strings before sorting:

```python
for f in findings:
    ts = f.get("timestamp", "")
    if ts is not None and not isinstance(ts, str):
        ts = str(ts)
    f["timestamp"] = ts or ""
findings.sort(key=lambda f: f.get("timestamp", ""), reverse=True)
```

Applied in BOTH `_handle_observer_command()` and `_handle_observer_json_command()`.

### Finding 7: Cron `deliver=origin` fails for `no_agent` jobs

`no_agent=True` cron jobs with `deliver=origin` produce: `no delivery target resolved for deliver=origin`. The script has no originating session to deliver to. Use `deliver=local` — output is saved to session store, accessible via session list.

## Neo4j Data (verified 2026-06-28)

| Label | Total | With session_id | Without |
|-------|-------|-----------------|---------|
| AuditFinding | 1,215 | 1,075 | 140 |
| CriticFinding | 1,138 | 1,009 | 129 |

**Properties on AuditFinding**: `session_id`, `finding`, `timestamp`, `phase`, `evidence`, `severity`
**Properties on CriticFinding**: `session_id`, `finding`, `timestamp`, `evidence`, `recommendation`, `severity`, `cycle`

**Top sessions by findings**:
| Session (last 16 chars) | Audit | Critic | Total |
|--------------------------|-------|--------|-------|
| 27_202849_0a0c69 | 389 | 330 | 719 |
| 27_201937_4ef575 | 40 | 36 | 76 |
| 27_200005_c511ba | 27 | 28 | 55 |

Session `20260627_202849_0a0c69` holds 719 of ~2,084 session-tagged findings (34%). All other sessions have <80.

## Verification

To verify findings exist for a session:
```bash
python3 -c "
import urllib.request, json, base64
auth = base64.b64encode(b'neo4j:<YOUR_NEO4J_PASSWORD>').decode()
payload = json.dumps({'statements': [{'statement': 
    'MATCH (f:AuditFinding) WHERE f.session_id = \"SESSION_ID\" RETURN count(f) as cnt'
}]})
req = urllib.request.Request('http://127.0.0.1:7474/db/neo4j/tx/commit',
    data=payload.encode(), headers={'Content-Type':'application/json','Authorization':f'Basic {auth}'})
with urllib.request.urlopen(req, timeout=10) as r:
    print(json.loads(r.read())['results'][0]['data'][0]['row'][0])
"
```

To verify `/obs` output for a session (CLI path):
```bash
echo '{"id":1,"command":"/obs"}' | timeout 10 \
  python3 -m tui_gateway.slash_worker --session-key SESSION_ID --model deepseek-v4-pro
```
