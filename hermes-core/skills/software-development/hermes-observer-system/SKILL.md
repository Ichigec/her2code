---
name: hermes-observer-system
description: "Design and maintain always-on observer agents for Hermes plan2 — Observer Orchestrator (v5) coordinates Auditor, Critic, Idea Generator, Knowledge Curator — with SDB contract, Neo4j persistence, and hook-based activation independent of agent preset."
version: 1.3.0
tags: [hermes, observers, neo4j, hooks, plugins, plan2, sdb, monitoring]
---

# Hermes Observer System

Design, deploy, and debug the five-observer system for Hermes plan2 orchestrator — Observer Orchestrator (v5) coordinates Auditor, Critic, Idea Generator, and Knowledge Curator. All observers follow SDB contract and persist findings to Neo4j.

## Architecture

```
                    ┌──────────────────────────┐
                    │   Hermes Plugin System    │
                    │   (TUI + CLI + Gateway)   │
                    └──────────┬───────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
    on_session_start    post_llm_call     on_session_end
            │                  │                  │
            ▼                  ▼                  ▼
    ┌───────────┐    ┌───────────────┐    ┌──────────┐
    │ MERGE     │    │ CREATE        │    │ SET      │
    │ :Session  │    │ :AuditFinding │    │ ended_at │
    └───────────┘    │ :Idea (:10)   │    └──────────┘
                     └───────────────┘
                            │
                     Neo4j :7474
```

## Five Observers (v5: +Orchestrator)

| Observer | Agent file | Neo4j label | Role |
|----------|-----------|------------|------|
| **Observer Orchestrator** | `~/.hermes/agents/observer-orchestrator.md` | `(:ObserverRun)` | Coordinates the 4 leaf observers; spawns via `delegate_task(role="orchestrator")`. Does NOT fix code. |
| **Auditor** | `~/.hermes/agents/auditor.md` | `(:AuditFinding)` | Process quality, context completeness, information loss |
| **Critic** | `~/.hermes/agents/critic.md` | `(:CriticFinding)` | Waste, over-engineering, root causes of complexity |
| **Idea Generator** | `~/.hermes/agents/idea-generator.md` | `(:Idea)` + `(:Mutation)` | Unheard ideas, connections, ADAS-style pipeline mutations |
| **Knowledge Curator** | `~/.hermes/agents/knowledge-curator.md` | `(:KnowledgeEntity)` | Entity extraction, cross-cycle knowledge graph maintenance |

## Root Causes: Why Observers Were Empty

The original design had six fatal flaws:

| # | Root Cause | Fix |
|---|-----------|-----|
| 1 | No agent files for Auditor/Critic/Idea Generator | Created `auditor.md`, `critic.md`, `idea-generator.md` |
| 2 | Stateless subagent context — "accumulate in context" impossible | Observers write to Neo4j on every checkpoint |
| 3 | Fire-and-forget checkpoint protocol | Wait for Neo4j writes (30s timeout) |
| 4 | Read-only toolsets (`file_ro` only) | Added `terminal` for curl to Neo4j |
| 5 | Knowledge Curator missing `terminal` tool | Added to toolsets |
| 6 | No one wrote to `auditor_memory.md` | Auditor appends from Neo4j queries |

## SDB Contract (Stochastic-Deterministic Boundary)

Every observer checkpoint implements the four-part SDB contract from Srinivasan (2026):

```
PROPOSER: observer reads artifact → analyzes
VERIFIER: observer validates its own output
COMMIT:   observer writes to Neo4j (curl CREATE/MERGE)
REJECT:   if validation fails → error node in Neo4j
```

This is the load-bearing primitive. 71% of production agent failures localize to weaknesses at this boundary.

## Neo4j Schema

```cypher
// Core observer nodes
(:AuditFinding {cycle, phase, severity, finding, evidence, recommendation, timestamp})
(:CriticFinding {cycle, phase, category, finding, root_cause, preventive, timestamp})
(:Idea {cycle, phase, category, idea, potential_value, target, timestamp})
(:Mutation {target, change, rationale, expected_impact, confidence, status, timestamp})
(:KnowledgeEntity {name, type, description, confidence, source})  // existing, 250+ nodes
(:Session {session_id, agent_preset, platform, started_at, ended_at, total_turns})
(:AFlowVariant {cycle, task, workflow, phases, estimated_score, iterations})

// Relationships
(:AuditFinding)-[:FOUND_IN]->(:Phase)
(:CriticFinding)-[:FOUND_IN]->(:Phase)
(:CriticFinding)-[:SAME_ROOT_CAUSE]->(:CriticFinding)
(:Idea)-[:INSPIRED_BY]->(:KnowledgeEntity)
(:Mutation)-[:APPLIES_TO]->(:Phase)
(:KnowledgeEntity)-[:RELATES_TO {predicate}]->(:KnowledgeEntity)
```

## Hook System (Always-On, Agent-Independent)

### Plugin (TUI + CLI + Gateway)

Location: `~/.hermes/hermes-agent/plugins/observer-hook/`

```yaml
# plugin.yaml
name: observer-hook
version: 1.0.0
hooks:
  - on_session_start
  - post_llm_call
  - on_session_end
```

The `__init__.py` must expose a `register(ctx)` function that calls `ctx.register_hook(...)` for each hook. Follow the pattern from `plugins/disk-cleanup/__init__.py`.

### Gateway Hook (Telegram, Discord, etc.)

Location: `~/.hermes/hooks/observer-hook/`

```yaml
# HOOK.yaml
name: observer-hook
events:
  - agent:end
  - agent:start
  - session:end
```

Handler format: `handler.py` with top-level `def handle(event_type, context)`.

### Hook vs Plugin

| | Plugin hooks | Gateway hooks |
|---|---|---|
| **Fires on** | `on_session_start`, `post_llm_call`, `on_session_end` | `agent:start`, `agent:end`, `session:end` |
| **Works for** | TUI, CLI, Gateway | Gateway only |
| **Location** | `plugins/observer-hook/` | `hooks/observer-hook/` |
| **Registration** | `register(ctx)` in `__init__.py` | Auto-discovered from `HOOK.yaml` |

**Use BOTH** — plugin covers TUI conversations, gateway hook covers messaging platforms.

## Neo4j Access

```bash
# Write AuditFinding
curl -s -u 'neo4j:<YOUR_NEO4J_PASSWORD>' -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"CREATE (f:AuditFinding {session_id:$sid, phase:$phase, severity:$sev, finding:$finding, timestamp:$ts})", "parameters":{...}}]}' \
  http://127.0.0.1:7474/db/neo4j/tx/commit

# Query findings
curl -s -u 'neo4j:<YOUR_NEO4J_PASSWORD>' -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (f:AuditFinding) RETURN f.severity, count(f) AS cnt ORDER BY f.severity"}]}' \
  http://127.0.0.1:7474/db/neo4j/tx/commit
```

## Three-Tier Architecture: Inline + Deep + Session-End

Observers run at THREE levels:

| Tier | Mechanism | Scope | Visible to user | Latency | Frequency |
|------|----------|-------|-----------------|---------|-----------|
| **Inline (per-turn)** | `agent/observer.py` built into conversation loop | Each LLM response | ✅ Appended after `---` | ~0.1s (regex only) | Every turn |
| **Deep (periodic)** | `delegate_task()` from `conversation_loop.py` → 1 LLM subagent | Full session arc so far | ✅ Appended after `---` with 🧠 marker | ~10-20s (1× LLM call) | Turns 1, 5, 10, 15, 20, 25... |
| **Session-end (batch)** | Plugin `observer-hook` + `observer_worker.py` → 4 LLM subagents | Full session arc | ❌ Neo4j only | ~2-3 min (4× LLM calls) | After session end |

### Inline Observer (`agent/observer.py`)

Built into the core agent loop (`conversation_loop.py` line ~4850). Runs ALL 4 observer heuristics on every LLM response and now **returns formatted notes** appended to the user-visible response.

See `references/inline-observer-code-changes.md` for the exact code modifications and `_format_observer_notes()` output format.
- `references/deep-observer-code-changes.md` for the delegate_task integration and programmatic API usage.
- `references/observer-findings-2026-07-01.md` — **NEW (2026-07-01)**. Full observer cascade event: claw-daily → knowledge-curator → session observers. 6 key findings: broken pipeline, observer depth, AGENTS.md noise, claw token waste, Neo4j schema drift, session observer dispatch failures.

**Call site** (in `conversation_loop.py`):
```python
from agent.observer import on_post_llm_call as _obs_llm
obs_notes = _obs_llm(agent.session_id, final_response or "", turn_count)
if obs_notes and final_response:
    final_response = final_response + "\n\n---\n" + obs_notes
```

**What gets shown**: Only non-trivial findings:
- 🔍 **Auditor**: HIGH/MEDIUM severity only (fabrication markers, short/long responses, missing tool usage)
- 🎯 **Critic**: Skip "clean" entries; show waste/over-engineering markers
- 💡 **Ideas**: value ≥ 7 (bug patterns, research paper mentions)
- 🧬 **Mutations**: ADAS proposals (max 2 per turn)
- 📚 **Entities**: Extracted KnowledgeEntities (max 5)

If all findings are trivial, nothing is shown — the user sees a clean response.

**Mode control**: `OBSERVER_MODE=light` → only AuditFinding, no inline notes. Default is `full`.

**User preference**: Pavel wants per-turn observer notes visible in the chat. This is the primary visibility mechanism — the session-end worker is supplementary for deep analysis.

### Deep Observer (`conversation_loop.py` + `delegate_task()`)

On every Nth turn (1, 5, 10, 15, 20...), spawns a **single LLM-based observer subagent** via the internal `delegate_task()` API. This runs IN the same session (not a separate `hermes -z` process) and appends findings to the chat.

**Location**: `conversation_loop.py` — right after the inline (lightweight) observer block.

**Key design decisions**:
- ONE subagent covers all 4 observer angles (not 4 parallel subagents) — keeps latency ~10-20s
- Turn-gated: only runs on turns 1, 5, 10, 15, 20... (and every 5 after 20) to limit latency/cost
- `role="leaf"` — no recursive delegation
- `max_iterations=4` — tight leash; observer just reads session via `session_search` and produces bullet points
- Toolsets: `["session_search"]` only — the observer reads the full conversation arc
- Prompt forces brevity: "max 120 words total", "3-5 bullet points, each 1 line"
- Sanity filter: rejects results < 30 chars (failed) or > 800 chars (verbose)

**Programmatic `delegate_task()` call** (NOT through tool layer):
```python
from tools.delegate_tool import delegate_task as _delegate
obs_json = _delegate(
    goal="You are a session observer...",
    context=f"Session {sid}, turn {turn}...",
    toolsets=["session_search"],
    parent_agent=agent,
    role="leaf",
    max_iterations=4,
)
```

The `parent_agent=agent` parameter is critical — it passes the current `AIAgent` instance so the subagent inherits model/provider config and is tracked as a child.

**CRITICAL: Source tagging for deep observer and CLI observer sessions** — See `references/session-source-tagging.md` for the complete resolution chain including the `run_agent.py:509` fix (env var priority flip, 2026-06-27). The env-var approach (`HERMES_SESSION_SOURCE`) was BROKEN until `run_agent.py` was patched to check the env var BEFORE `self.platform`. The delegate path (`platform="observer"` parameter) works independently but the CLI path (`hermes chat -q`) REQUIRES the `run_agent.py` fix because `cli.py:5248` hardcodes `platform="cli"`.

1. **`delegate_task()`** — add `platform: Optional[str] = None` parameter
2. **Single-task dict** — include `"platform": platform` in the task dict
3. **`_build_child_agent()`** — add `platform: Optional[str] = None` parameter
4. **`AIAgent.__init__()`** — change `platform=parent_agent.platform` to `platform=platform or parent_agent.platform`
5. **Caller** (`conversation_loop.py`) — pass `platform="observer"`:

```python
obs_json = _delegate(
    goal=goal,
    context=f"Session {sid}, turn {_obs_turn}...",
    toolsets=["session_search"],
    parent_agent=agent,
    role="leaf",
    max_iterations=4,
    platform="observer",  # <-- the fix
)
```

This is the counterpart to `--source observer` on the CLI path (used by `observer_worker.py`). Without this fix, deep observer sessions appear with `source='cli'` in `state.db` and cannot be filtered by the desktop `excludeSources` mechanism — they clutter the main session list exactly like the cascade bug. The earlier env-var hack was replaced by this proper parameter plumbing on 2026-06-27.

**Output format**:
```
---
🧠 **Deep Observer:**
• Observation 1
• Observation 2
• Observation 3
```

See `references/deep-observer-code-changes.md` for the exact code and prompt template.
See `references/delegate-platform-parameter.md` for the root cause and fix of the `platform` inheritance bug (env-var approach failed, proper fix is parameter plumbing).
See `references/session-source-tagging.md` for the complete source tagging resolution chain including the `run_agent.py:509` priority fix and the `--cli` flag override discovery.
See `references/observer-rest-api.md` for the `/api/observers/recent` REST endpoint, auth bypass, and CORS workaround.
See `references/observer-panel-frontend.md` for the desktop GUI ObserverPanel data flow, statusbar integration, and rebuild cycle.
See `references/desktop-slash-command-development.md` for the 3-layer slash command architecture and Rich Console workaround.
See `references/obs-command-architecture.md` for the `/obs` command internals, the 4-layer problem analysis (Rich formatting → session mismatch → no agent-context injection → no auto-push), concrete fix plan with code patterns (session fallback, `_pending_input.put()` injection, cron auto-notify), and Neo4j data distribution.
See `references/karma-observer-architecture.md` — **NEW (2026-07-01)**. KARMA-style observer verification pipeline: 5-tier gate (Evidence → Contradiction → Calibration → Schema → Cross-Cycle), Verifier agent spec, domain-adaptive prompting, confidence calibration, ACCEPT/FLAG/REJECT verdicts. Based on arXiv:2502.06472.

### Session-End Worker (Plugin)

The existing plugin/worker pipeline (documented below) runs AFTER the session and does deep LLM-based analysis. Results go only to Neo4j. This is for audit trail and cross-session pattern detection, not real-time user feedback.

### Observer Orchestrator (Tier 4 — coordination layer, DEPLOYED v5)

The three tiers above only DIAGNOSE. Tier 4 adds COORDINATION — an orchestrator-level observer (`role="orchestrator"`, has `delegation` toolset) that spawns the 4 leaf observers intelligently instead of spawning all 4 blindly every time.

**Agent file:** `~/.hermes/agents/observer-orchestrator.md`
**Triggered by:** `/obs analyze` (gateway `observer.analyze` method) — spawns orchestrator via `delegate_task(role="orchestrator", toolsets=["session_search", "terminal", "delegation"])`

**What it does:**
1. Reads session via `session_search`
2. Decides WHICH of the 4 observers to spawn (1-4), with focused goals per observer
3. Spawns them via `delegate_task(role="leaf", toolsets=[...])` with `platform="observer"`
4. Aggregates results → creates `:ObserverRun` node in Neo4j
5. Self-audits → writes its own `:AuditFinding` about spawn quality

**Hard constraints (system prompt):**
- ⛔ NEVER spawn developer, security-agent, deployment-agent, tester, techlead, or researcher
- ONLY the 4 observer types: auditor, critic, idea-generator, knowledge-curator
- Max 4 observer spawns per run, max 1 retry per failed observer
- Token budget: ~5K per observer spawn, model: agents-a1-abliterated

**Spawn routing table:**

| Observer | Trigger condition |
|----------|------------------|
| auditor | Always for non-trivial sessions (>5 msgs, tool calls) |
| critic | >10 tool calls, duplicate file reads, over-investigation |
| idea-generator | New patterns, bugs, workflows, non-standard solutions |
| knowledge-curator | ALWAYS when new entities/patterns/facts emerge |

**Model:** `agents-a1-abliterated` via `custom:local` (0.2s latency, no reasoning overhead). Previously used `kimi-k2.7-code` which does NOT exist in LiteLLM — replaced across all 34 agent files on 2026-07-15. Always cross-check model names against `curl http://localhost:4000/v1/models -H 'Authorization: Bearer sk-local'` before hardcoding in agent files.

For fix-loop architectures (closing the fix gap by spawning developers), see `references/orchestrator-observer-variants.md` — 4 variant designs from minimal Triage Scheduler to autonomous ADAS loop. These are separate from the coordination orchestrator and require different safety constraints.

## Current Deployment (2026-06-29)

**Status: ACTIVE v4** — config-toggle system, ObserverManager singleton, desktop toggle UI, `/obs on|off|status|analyze`.

| Component | Path | Status |
|-----------|------|--------|
| ObserverManager | `agent/observer_manager.py` | ✅ v4 |
| Config section | `hermes_cli/config.py` DEFAULT_CONFIG | ✅ v4 |
| Inline observer | `agent/observer.py` | ✅ v4 |
| Deep observer | `agent/conversation_loop.py` | ✅ v4 (leaf, fast) |
| **Observer Orchestrator** | `~/.hermes/agents/observer-orchestrator.md` | ✅ v5 — coordinates 4 observers via `observer.analyze` |
| **Gateway analyze** | `tui_gateway/server.py:observer.analyze` | ✅ v5 — spawns orchestrator (`role="orchestrator"`, `delegation` toolset) |
| Plugin | `plugins/observer-hook/__init__.py` | ✅ v4 |
| Worker | `scripts/observer_worker.py` | ✅ v3 |
| `/obs` command | `cli.py:6255-6435` | ✅ v4 — sub-commands: `on`, `off`, `status`, `analyze` |
| Gateway methods | `tui_gateway/server.py` | ✅ v4 — `observer.toggle`, `observer.status`, `observer.analyze` |
| **Dashboard methods** | `hermes_cli/web_server.py` | ❌ **MISSING** — only `GET /api/observers/recent`. GUI connects HERE, not to TUI gateway. `observer.analyze/toggle/status` fail silently. See `references/dashboard-observer-method-gap.md`. |
| ObserverPanel | `apps/desktop/src/app/shell/observer-panel.tsx` | ✅ v4 — toggle ON/OFF, tier indicators, Analyze Now button, refresh |
| Desktop slash | `apps/desktop/src/lib/desktop-slash-commands.ts` | ✅ updated — `/obs on|off|status|analyze` |
| TUI rendering | `ui-tui/src/components/messageLine.tsx:134` | ✅ fixed — slash output uses `t.color.text` (not muted) |
| Auto-notify cron | `scripts/observer-notify.py`, cron `3cd0c9026482` | ✅ deployed — polls Neo4j every 5min, `no_agent` mode |

## ObserverManager & Config Toggle (v4, 2026-06-29)

Observers can now be enabled/disabled at runtime without file renames. A singleton `ObserverManager` reads `observer.*` from `config.yaml` (with `DEFAULT_CONFIG` fallback) and gates all three observer tiers.

### Config schema (`hermes_cli/config.py` DEFAULT_CONFIG)

```yaml
observer:
  enabled: true        # master switch — disables ALL observers when false
  inline: true         # lightweight regex heuristics (~0.1s per turn)
  deep: true           # LLM subagent every Nth turn (~10-20s)
  deep_interval: 5     # deep observer interval (turns 1, 5, 10, 15, 20...)
  session_end: true    # post-session: plugin → 4 LLM subagents (~2-3 min)
```

### ObserverManager API

```python
from agent.observer_manager import ObserverManager

# Read config (lazy load from config.yaml, DEFAULT_CONFIG fallback)
ObserverManager.is_enabled()           # False → ALL tiers skip
ObserverManager.is_inline_enabled()    # gates agent/observer.py
ObserverManager.is_deep_enabled(turn)  # gates conversation_loop.py deep observer
ObserverManager.is_session_end_enabled() # gates plugin observer-hook

# Toggle + persist to config.yaml
ObserverManager.toggle("enabled")      # flip and save
ObserverManager.set("deep", False)     # set and save
ObserverManager.get_config()           # full dict for UI display
ObserverManager.reload()               # force re-read from config.yaml
```

### Wiring (three checkpoints)

| Tier | File | Guard |
|------|------|-------|
| Inline | `agent/observer.py` → `on_post_llm_call()` | `if not ObserverManager.is_inline_enabled(): return ""` |
| Deep | `agent/conversation_loop.py` ~L4860 | `if not ObserverManager.is_deep_enabled(_obs_turn): skip` |
| Session-end | `plugins/observer-hook/__init__.py` → `on_session_end()` | `if not ObserverManager.is_session_end_enabled(): return` |

All three import `ObserverManager` lazily inside try/except to avoid import-time side effects.

### Toggle paths

| Path | Mechanism | Persistence |
|------|-----------|-------------|
| **Desktop GUI** | ObserverPanel toggle button → `requestGateway('observer.toggle', {key})` | Writes to config.yaml via `ObserverManager.toggle()` |
| **CLI** | `/obs on`, `/obs off` → `ObserverManager.set("enabled", val)` | Writes to config.yaml |
| **Gateway** | `observer.toggle` JSON-RPC method | Writes to config.yaml |
| **Direct** | Edit `config.yaml` → restart hermes gui (or `ObserverManager.reload()`) | Manual |

### Desktop GUI ObserverPanel (v4)

```
┌─────────────────────────────┐
│ 👁 Observers         ⬤ ON  │  ← toggle (green=ON, gray=OFF)
│ Inline: ✓  Deep: ✓  S-End: ✓│  ← tier status indicators
│ ─────────────────────────── │
│ ▶ Deep Analyze Now          │  ← manual trigger (sends observer.analyze)
│ ─────────────────────────── │
│ ↻ 12 findings — click to... │  ← refresh button + findings list
│   🛡 [AUDIT] ...            │
│   🔍 [CRITIC] ...           │
└─────────────────────────────┘
```

Icon: `Eye` when ON, `EyeOff` when OFF. Panel width: `w-72`.

### `/obs` sub-commands (v4)

```
/obs           — show findings for current session (original behaviour)
/obs on        — enable all observers (ObserverManager.set("enabled", True))
/obs off       — disable all observers (ObserverManager.set("enabled", False))
/obs status    — show {enabled, inline, deep, deep_interval, session_end} with ✅/⛔
/obs analyze   — spawn Observer Orchestrator (role="orchestrator") via delegate_task. Orchestrator reads session, decides which of the 4 observers to spawn, coordinates them, and aggregates results.
```

**Desktop dispatch** (`tui_gateway/server.py` `command.dispatch`): sub-commands `on`, `off`, `status`, `analyze` are handled directly (no slash_worker). The `analyze` sub-command spawns `delegate_task()` with `platform="observer"` and returns findings as a chat message.

### Gateway methods (v4)

| Method | Params | Returns |
|--------|--------|---------|
| `observer.toggle` | `{key: "enabled"\|"inline"\|"deep"\|"session_end"}` | `{key, value}` |
| `observer.status` | `{}` | `{config: {enabled, inline, deep, deep_interval, session_end}}` |
| `observer.analyze` | `{session_id}` | `{type: "send", message: "👁 Observer Orchestrator: ...", status: "completed"\|"no_result"}` | Spawns orchestrator (`role="orchestrator"`, `toolsets=["session_search","terminal","delegation"]`, `max_iterations=12`) which coordinates the 4 leaf observers. See `~/.hermes/agents/observer-orchestrator.md`. |

**Activation flow (v3 — session-level):**
1. `on_session_start` hook fires → MERGEs Session node in Neo4j (skipped for observer subagent sessions)
2. `post_llm_call` hook fires → just counts turns (lightweight, no queue, no spawn)
3. `on_session_end` hook fires → queries `state.db` for `message_count`, `tool_call_count`, `input_tokens`
4. **Activity gate**: skips if `msgs < 5 AND tools < 2 AND tokens < 5000` (trivial sessions don't waste 4 LLM calls)
5. If meaningful → writes context JSON to `/tmp/hermes_observer_ctx_<sid>.json` → spawns `observer_worker.py --session-id <sid> --context-file <path>`
6. Worker reads context (rich: turns, msgs, tools, tokens, preset, platform), acquires lock, spawns 4 observers in parallel
7. Each observer gets FULL session context in prompt: stats + instructions to use `session_search` for the complete conversation arc
8. Worker marks session 'observer_reviewed' in Neo4j

**What changed from v2:**
- `post_llm_call` no longer queues tasks or spawns workers (was cascade trigger)
- `on_session_end` now queries real stats from `state.db` instead of tracking only turns
- Activity gate: ~60% of sessions (trivial chats) are skipped, saving 4 deepseek-v4-pro calls each
- Worker receives rich context via JSON file (stats, preset, platform) — no need to query Neo4j
- Observer prompt rewritten: focuses on session ARC (goal, failures, patterns, ideas) not individual turns

1. **Subagents cannot accumulate context between turns** — context is volatile. Always write to durable storage (Neo4j) at every checkpoint, never "accumulate for later."
2. **`custom:kimi` provider unavailable for delegation** — `kimi-k2.7-code` does NOT exist in LiteLLM. All observer agent files now use `agents-a1-abliterated` via `provider="custom:local"` (replaced across 34 files 2026-07-15). The orchestrator observer spawn model must be verified against `curl http://localhost:4000/v1/models -H 'Authorization: Bearer sk-local'` before use.
3. **`file` toolset unnecessary for Neo4j-only observers** — observers only need `terminal` for curl. Remove `file` from their toolsets.
4. **Gateway hooks don't fire for TUI** — the `~/.hermes/hooks/` system is gateway-only. For TUI coverage, use the plugin system (`plugins/observer-hook/`).
5. **Plugin hook argument names must match** — `on_session_start` receives `session_id`, `agent_prompt_label`, `platform`. Use `**kwargs` catch-all to be safe.
6. **Persona.md should NOT contain observer spawning logic** — it's handled by hooks. Persona should be clean (tone + behavior only).
## Pitfall: Clarify tool dialog doesn't appear in GUI (2026-06-29)

The `clarify()` tool's dialog (choices overlay) does not render in the Hermes Desktop GUI. The `clarify.request` WebSocket event is sent but never reaches the `ClarifyTool` component. Agents blocked on `clarify.respond` hang indefinitely. Workaround: use plain-text questions when running through GUI. See `references/clarify-gui-dialog-bug.md` for full diagnostic chain and fix candidates.

## Pitfall: Dashboard doesn't register observer.analyze/toggle/status methods (2026-06-29)

The Hermes GUI connects to `hermes dashboard` (`hermes_cli/web_server.py`), but `observer.analyze`, `observer.toggle`, and `observer.status` are ONLY registered in `tui_gateway/server.py` — a separate server. The dashboard only has `GET /api/observers/recent` (read-only). Result: "Deep Analyse Now" button and ON/OFF toggle fail silently via WebSocket JSON-RPC.

**Status (2026-06-29): RESOLVED.** The dashboard delegates WebSocket handling to `tui_gateway/ws.py → server.dispatch`, which means ALL `@method` registrations in `server.py` (including `observer.analyze`, `observer.toggle`, `observer.status`) are automatically available through the dashboard WebSocket. No porting needed. Verified: `GET /api/observers/recent` returns findings via HTTP; `observer.analyze` reachable through the WS dispatch chain.

## Pitfall: «Deep Analyse Now» returns \"session not found\" (2026-06-29)

The `ObserverPanel`'s `useEffect` and post-analyze refresh call `requestGateway('slash.exec', {command: 'observer_json'})` — which internally calls `_get_session()` / `_sess_nowait()` looking for the session in the dashboard `_sessions` dict. If the session isn't an active agent session (e.g. browsing old chats), `_sess_nowait()` returns error 4001 \"session not found\".

**Fix:** Use `requestGateway('observer.recent', {session_id, limit: 30})` directly — it queries Neo4j, no agent session required. Already implemented in `observer-panel.tsx`.

**Check:** `get_messages_as_conversation(sid)` works with ANY session_id from `state.db` (tested: 468 messages from `20260629_214814_df13d0`). The Neo4j `observer.recent` endpoint filters by `session_id` in Cypher.

The button calls `observer.analyze` → spawns observer orchestrator via `delegate_task()` → which requires a working LLM connection. If the configured LLM endpoint is down (e.g., llama.cpp on :8092 not running), `delegate_task` fails, the error is caught by `runAnalyze()` in `observer-panel.tsx`, and displayed as an error string in the panel. User sees nothing happen if the error display is missed.

**Check:** `curl http://localhost:8092/health` — if dead, `observer.analyze` will always fail. The deep/session-end observers use `conversation_loop.py`'s internal `delegate_task()` which uses the SAME LLM connection. If LLM is down, ALL observer tiers are broken.

**Verify observers work independently:** hit `GET /api/observers/recent` — if findings exist, observers HAVE been writing to Neo4j. The "Deep Analyze Now" button is just a manual trigger; automatic observers (inline/deep/session-end) run independently.

The `hermes-agent` Docker image (container `hermes-test`) running `gateway run` had an outdated `tui_gateway/server.py` — missing `observer.analyze`, `observer.toggle`, `observer.status`. The Hermes GUI however connects to `hermes dashboard` (port 9120), not the Docker gateway (port 18648). Two separate servers; neither had working observer methods at investigation time. Fixed by removing all Docker hermes images and using the native dashboard.

**Cleanup command:**
```bash
docker stop hermes-test && docker rm hermes-test
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | grep hermes | while read img id; do docker rmi -f "$id"; done
```

The Hermes GUI connects to `hermes dashboard` (`hermes_cli/web_server.py`), but `observer.analyze`, `observer.toggle`, and `observer.status` are ONLY registered in `tui_gateway/server.py` — a separate server. The dashboard only has `GET /api/observers/recent` (read-only). Result: "Deep Analyse Now" button and ON/OFF toggle fail silently via WebSocket JSON-RPC.

**Status (2026-06-29): RESOLVED.** The dashboard delegates WebSocket handling to `tui_gateway/ws.py → server.dispatch`, which means ALL `@method` registrations in `server.py` (including `observer.analyze`, `observer.toggle`, `observer.status`) are automatically available through the dashboard WebSocket. No porting needed. Verified: `GET /api/observers/recent` returns findings via HTTP; `observer.analyze` reachable through the WS dispatch chain.

7. **CRITICAL: Observer cascade via post_llm_call spawn** — DO NOT call `_spawn_observer_worker()` from `post_llm_call`. It was removed on 2026-06-27 after it caused a session multiplication cascade: each observer subagent session (`hermes -z`) triggered `on_session_start` → `post_llm_call` → spawned MORE workers → more subagent sessions → exponential growth. In 37 minutes: 209 garbage sessions created, `state.db` bloated to 810 MB, 24 parallel `hermes -z` processes consuming resources. **Fix**: (a) remove worker spawn from `post_llm_call`, (b) add `_is_observer_session()` guard that checks `agent_prompt_label` and `system_prompt` for observer agent names (auditor/critic/idea-generator/knowledge-curator) and skips all hooks for observer subagent sessions. Worker spawning should only happen on `on_session_end` or via manual/cron trigger.

7b. **Observer v2 Neo4j schema mismatch with idea-generator.md** — The inline observer (`agent/observer.py` v2.1) writes `Idea` nodes with `session_id` field, but `idea-generator.md` agent definition (used by session-end worker) expects `cycle`, `phase`, `category`, `idea`, `potential_value` fields. Result: inline Ideas have null semantic fields when queried by the Idea Generator subagent. **Fix**: (a) align observer.py Cypher to use `cycle`+`phase` (requires passing cycle context to `on_post_llm_call`), or (b) update idea-generator.md to query by `session_id` for per-session analysis. Discovered in session `20260627_200005_c511ba` where `MATCH (i:Idea) RETURN i.idea` returned null for all observer v2 rows.

7c. **AGENTS.md context bloat from subdirectory discovery** — Every tool call touching `~/.hermes/` or `~/.hermes/hermes-agent/` triggers AGENTS.md auto-loading (subdirectory context discovery). In session `20260627_200005_c511ba`, 24K chars of AGENTS.md (2 copies) were injected into context via terminal/read_file calls to observer files — completely irrelevant to the task. **Mitigation**: observer.py should not trigger AGENTS.md discovery on import; the subdirectory context engine should filter out `.hermes/` paths or make discovery opt-in per toolset.

7c. **Deep observer cascade via delegate_task (FIXED 2026-07-10)** — The deep observer at
   ``conversation_loop.py:4866`` checks ``_should_deep`` but does NOT guard against
   ``platform == "observer"``. When a deep observer subagent completes, ITS ``run_conversation()``
   also reaches the deep observer checkpoint with turn=1 → ``is_deep_enabled(1)`` returns True →
   spawns another observer subagent → cascade (observer → observer-of-observer → …).

   **Fix** (one line at line 4866):
   ```python
   if _should_deep and getattr(agent, "platform", "") != "observer":
   ```
   This is DIFFERENT from the earlier ``_is_observer_session()`` fix (pitfall #7a) — that guard
   protects the PLUGIN path (``post_llm_call`` → worker spawn). This new guard protects the
   BUILT-IN deep observer path (``conversation_loop.py`` → ``delegate_task``).

   **Verification**: After fix, agent.log shows exactly one observer session per main session
   (not a cascade chain). Main session with ``platform=tui`` → observer session with
   ``platform=observer`` → STOP. No observer-of-observer. — The original guard only checked `agent_prompt_label` and `system_prompt` kwargs, missing bare `hermes -z` invocations from the worker. Now has:
   1. **Env-var gate**: `HERMES_OBSERVER_SUBAGENT=1` — set by `observer_worker.py` in subprocess env
   2. **Agent preset gate**: observer agent names (auditor/critic/idea-generator/knowledge-curator/observer-orchestrator) in preset label
   3. **System prompt gate**: observer mentions in system prompt text
   4. **User message gate**: catches "session" + "observer" in the first user message (covers both `hermes -z` "Session analysis for..." prompts and `delegate_task()` "You are a session observer..." goals)
   Worker also sets `HERMES_OBSERVER_SUBAGENT=1` in the env dict passed to `subprocess.run()`.
8. **Post-cascade cleanup**: After a cascade event, kill all observer processes (`ps aux | grep observer | awk '{print $2}' | xargs kill`), delete garbage sessions from `state.db`, VACUUM the DB, clean `:ObserverTask` nodes from Neo4j, empty `observer_queue.jsonl`, and remove stale lock files from `/tmp/hermes_observer_locks/`. **Full cleanup SQL recipes** (including TUI observer sessions, message-pattern matching, and verification queries) are in `references/session-cleanup-sql.md`. The old `system_prompt LIKE '%observer%'` pattern misses CLI sessions where the system_prompt is NULL — use first-user-message patterns instead (e.g. `m.content LIKE 'Session analysis for% observer%'`).

9. **Desktop rebuild cycle**: After ANY code change, the restart requirements differ by file type:
   - **Python files** (`conversation_loop.py`, `delegate_tool.py`, `run_agent.py`, `web_server.py`, `observer_worker.py`, `public_paths.py`, plugin `__init__.py`): Require dashboard restart — close and reopen `hermes gui`.
   - **TypeScript files** (`observer-panel.tsx`, `desktop-controller.tsx`, `store/session.ts`, `use-statusbar-items.tsx`): Require `npm run pack` in `apps/desktop/` to rebuild `app.asar` + dashboard restart.
   - **Both changed**: do `npm run pack` first, then restart `hermes gui`.
   - **Verification**: after restart, the observer panel's session ID display (shown in empty-state footer) should match the current session. If the new code isn't showing, check that `npm run pack` completed without errors and that the dashboard process PID changed after restart.

## Observer Worker (Queue-Based Processing)

Plugin hooks cannot spawn subagents directly — hooks are lightweight interceptors without LLM access. Solution: **queue → worker → spawn**.

### Worker script: `~/.hermes/scripts/observer_worker.py`

Reads sessions with `status = 'pending_observer_review'` from Neo4j and spawns all 4 observer subagents via `hermes` CLI batch mode:

```bash
python3 ~/.hermes/scripts/observer_worker.py
```

Each observer subagent is spawned via:
```bash
hermes chat -q "Session analysis for {name}. Session: {sid}..." \
  --yolo -m deepseek-v4-pro --provider deepseek \
  --source observer
```
The `--source observer` flag is **critical** — it marks observer sessions so the desktop GUI can filter them out of the main session list (same pattern as `--source cron` for cron jobs).

**IMPORTANT**: Do NOT add `--cli` to this command. The `--cli` flag sets `self.platform='cli'` in the agent, which takes priority over `--source observer` in `run_agent.py:509` (`source = self.platform or env.get("HERMES_SESSION_SOURCE", "cli")`). Also add `HERMES_SESSION_SOURCE=observer` to the subprocess env dict as a belt-and-suspenders fallback. See `references/session-source-tagging.md` for the full resolution chain.

### Queue flow

```
1. Plugin: on_session_end → SET s.status = 'pending_observer_review'
2. Plugin: post_llm_call → CREATE (:ObserverTask {status:'queued'})
3. Worker: reads pending sessions → spawns 4 observers
4. Worker: marks session 'observer_reviewed'
```

The worker can be triggered manually after important sessions or via cron for batch processing. The plugin does NOT block — it only marks sessions for later review.

## Pitfall: Orchestrator gate false-fails on observer PID files (FIXED 2026-07-15)

`orchestrator_gate.py:check_observers()` searched `/tmp/observer_*.pid` and returned FAIL when none found. But plan2 spawns observers via `delegate_task` (in-process, not daemonized) — no PID files are ever written. This made Pre-Flight Gate always BLOCK at Phase 5.5.

**Fix (applied):** Gate now reads `config.yaml → observer.enabled`:
- If `observer.enabled: false` → PASS with "Observers disabled (GUI toggle OFF)"
- If `observer.enabled: true` but no PID files → PASS with WARNING ("plan2 spawns via delegate_task at Phase 0, not daemonized")
- Dead daemon PIDs → WARNING (not blocker), since in-process observers still work

## Pitfall: Observer daemon and worker NOT in cron (as of 2026-07-15)

`observer_daemon.py` and `observer_worker.py` are standalone scripts but are NOT registered in `cron/jobs.json`. Session-end Tier 3 observers only fire via the in-process plugin hook (`plugins/observer-hook/`), not via cron-triggered workers. If cron-based batch observer analysis is needed, register the worker manually:

```bash
hermes cron add --schedule "*/30 * * * *" --command "python3 ~/.hermes/scripts/observer_worker.py" --deliver local
```

## Integration with plan2

Observers are spawned at Phase 0 alongside AFlow Orchestrator:

```
Phase 0: Project Bootstrap
  ├── Create project dir
  ├── Spawn AFlow Orchestrator (parallel, searches alternative workflows)
  └── Spawn 4 observers (fire-and-forget, write to Neo4j on every checkpoint)

Phase 1-9: Main lifecycle
  └── After each phase: observer checkpoint batch
      ├── Auditor → CREATE (:AuditFinding)
      ├── Critic → CREATE (:CriticFinding)
      ├── Idea Generator → CREATE (:Idea) + CREATE (:Mutation)
      └── Knowledge Curator → MERGE (:KnowledgeEntity)

Phase 10: Synthesis
  ├── Observers query Neo4j (MATCH) and synthesize reports
  ├── AFlow comparison: main workflow vs AFlow variant
  └── Auditor updates auditor_memory.md
```

## ADAS Connection

The Idea Generator implements an ADAS-style evolutionary loop:
1. Each cycle generates `(:Mutation)` proposals
2. Auditor evaluates them (accept/reject) in the next cycle
3. Accepted mutations are applied to plan2 via `patch`
4. The cycle repeats: generate → evaluate → select → apply

This turns plan2 into a self-evolving orchestrator.

## Desktop GUI Integration (Source-Based Filtering)

Observer sessions use `source='observer'` (set via `--source observer` on the `hermes -z` CLI invocation in `observer_worker.py`). The desktop GUI filters them out of the main session list using the same pattern as cron sessions.

### How it works

1. **CLI path** (`observer_worker.py` → `hermes -z`): sets `--source observer` flag on the CLI invocation
2. **Delegate path** (`conversation_loop.py` → `delegate_task()`): passes `platform="observer"` parameter. This flows through `delegate_task()` → task dict → `_build_child_agent()` → `AIAgent(platform="observer")`. The child session gets `source='observer'` in `state.db`. **Do NOT use the env-var hack** (`HERMES_SESSION_SOURCE`) — it doesn't work because `platform=parent_agent.platform` (line 1157) takes precedence in `run_agent.py:509`.
3. **`desktop-controller.tsx`** excludes observer sessions from the main recents list:
   ```ts
   excludeSources: ['cron', 'observer']
   ```
4. **Observer sessions are fetched separately** into `$observerSessions` atom (like `$cronSessions`)
5. **ObserverPanel** component renders a dropdown from the statusbar (Eye icon 👁) — positioned left of the 🧠 Agents button. The panel fetches observer findings from Neo4j via the public `/api/observers/recent` endpoint. **Important**: (a) the endpoint MUST be in `dashboard_auth/public_paths.py` to bypass auth, (b) use `window.hermesDesktop.api()` (not `fetch()`) — `fetch()` is blocked by CORS (`access-control-allow-origin: localhost:5174` only). See `references/observer-rest-api.md` for the full endpoint spec and auth/CORS details.

### Files involved

| File | Change |
|------|--------|
| `observer_worker.py` | `--source observer` flag on hermes CLI spawn |
| `conversation_loop.py` | `platform="observer"` passed to `delegate_task()` for deep observer |
| `tools/delegate_tool.py` | `platform` param in `delegate_task()` → `_build_child_agent()` |
| `desktop-controller.tsx` | `excludeSources: ['cron', 'observer']` + `refreshObserverSessions()` + `observerItem` |
| `store/session.ts` | `$observerSessions` atom + `OBSERVER_SECTION_LIMIT` + `setObserverSessions()` |
| `shell/observer-panel.tsx` | Dropdown panel fetching findings from `/api/observers/recent` (Neo4j) |
| `shell/hooks/use-statusbar-items.tsx` | `observerItem` param inserted into `coreLeftStatusbarItems` |
| `store/session.ts` | `$observerConfig` atom + `ObserverConfigState` interface (v4 — drives statusbar icon state) |
| `agent/observer_manager.py` | 🆕 ObserverManager singleton (v4 — config-backed enable/disable toggle) |
| `hermes_cli/config.py` | `observer` section in `DEFAULT_CONFIG` (v4) |
| `hermes_cli/web_server.py` | `GET /api/observers/recent` endpoint querying Neo4j for AuditFindings + CriticFindings |
| `hermes_cli/dashboard_auth/public_paths.py` | `/api/observers/recent` added to public paths (no auth needed) |

### Dynamic statusbar icon pattern (v4)

The observer statusbar item now reflects state in real time via a nanostores atom:

```
Controller:  useStore($observerConfig) → observerItem.useMemo()
Store:       $observerConfig atom {enabled, inline, deep, ...}
Panel:       toggle → requestGateway('observer.toggle') → $observerConfig.set()
```

| State | Icon | Color | Label |
|-------|------|-------|-------|
| ON | `Eye` | `text-(--color-green-400)` | (none) |
| OFF | `EyeOff` | `opacity-50` | `OFF` |

The panel and statusbar icon share the same `$observerConfig` atom — toggling in the panel instantly updates the icon without a re-fetch. The atom is initialized via `refreshObserverConfig()` on mount (calls `observer.status` gateway method).

See `hermes-cross-stack` skill → references/dynamic-statusbar-items.md for the reusable pattern.

**Full frontend architecture:** `references/observer-panel-frontend.md` — component data flow, statusbar item pattern, rebuild cycle, API auth pitfall.

### Adding observer-like panels for other session sources

The pattern is reusable for any session source:
1. Add `--source <tag>` to the CLI spawn command
2. Add `source: '<tag>'` to the separate fetch in `desktop-controller.tsx`
3. Add `<tag>` to `excludeSources` in the main sessions fetch
4. Create a `$<tag>Sessions` atom + setter
5. Add a statusbar item with a dropdown panel

Follow the phased approach: CLI sessions → empty shells → short observer TUI → verify remaining are real conversations.

## Pitfall: TUI Slash Output Rendered Gray (Non-Copyable) (FIXED 2026-06-28)

All slash command output in the TUI is rendered with `kind: 'slash'` and `color={t.color.muted}` (ansi256(245) = gray). Users perceive findings as "серый, не копируемый, не конечный результат."

**Root cause**: `ui-tui/src/components/messageLine.tsx` line 134:
```tsx
if (msg.kind === 'slash') {
  return <Text color={t.color.muted}>{msg.text}</Text>  // muted = gray
}
```

**Fix**: Change to normal text color:
```tsx
<Text color={t.color.text}>{msg.text}</Text>   // text = ansi256(136) = amber
```

Rebuild with `cd ui-tui && npm run build` (~111ms). Restart TUI/desktop to apply.

## Pitfall: Neo4j Timestamp Type Mismatch (FIXED 2026-06-28)

`f.timestamp` can be either ISO-8601 string (`"2026-06-27T20:28:..."`) or epoch integer (`1782581330`), depending on which observer wrote the finding. `list.sort()` fails with `TypeError: '<' not supported between instances of 'str' and 'int'`.

**Fix**: Normalize all timestamps to strings before sorting:
```python
for f in findings:
    ts = f.get("timestamp", "")
    if ts is not None and not isinstance(ts, str):
        ts = str(ts)
    f["timestamp"] = ts or ""
findings.sort(key=lambda f: f.get("timestamp", ""), reverse=True)
```

**Check**: Two hit sites — `_handle_observer_command()` and `_handle_observer_json_command()` in cli.py. Both must be patched.

## Pitfall: Cron `deliver=origin` Fails for `no_agent` Jobs

`no_agent=True` cron jobs have no originating session to deliver to. `deliver=origin` produces: `no delivery target resolved for deliver=origin`. Use `deliver=local` for script-only jobs — output is saved to session store, accessible via session list.

## Pitfall: `_pending_input.put()` Context Injection Pattern

When a slash command needs the agent to "see" and discuss its output, use the established pattern from `/browser connect` (cli.py:9761):

```python
if hasattr(self, '_pending_input'):
    self._pending_input.put(
        "[System note: The user invoked /obs. "
        "Here are the observer findings: ...]\n\n"
        "Review these findings and suggest concrete actions.]"
    )
```

The `hasattr` guard is critical — it prevents the injection from firing in slash_worker context (where `_pending_input` doesn't exist). The message is queued for the next agent turn; if agent is idle it triggers immediate response.

The slash_worker (`tui_gateway/slash_worker.py` line 36) creates a Rich Console:
```python
cli.console = Console(file=buf, force_terminal=True, width=120)
```
**All `self._console_print()` calls go through Rich, which inserts newlines at column 120.** This corrupts:
- JSON output (newlines in middle of JSON strings break `JSON.parse`)
- Long finding texts (Rich wraps them mid-sentence)

**Fix**: Use `sys.stdout.write()` directly instead of `self._console_print()` for programmatic/structured output:
```python
import sys as _sys
_sys.stdout.write("clean text\n")       # bypasses Rich entirely
_sys.stdout.write(json.dumps(data) + "\n")  # no line wrapping
```
The slash_worker already redirects stdout to the output buffer (`contextlib.redirect_stdout(buf)`) so `sys.stdout.write()` goes to the same destination — just without Rich interference.

Also strip Rich markup (`[bold]`, `[yellow]`, `[dim]`) from all slash command output — the desktop GUI does not render ANSI/Rich markup in chat messages.

## Pitfall: Desktop slash command allowlist (`desktop-slash-commands.ts`)

The desktop GUI has its OWN command allowlist in `apps/desktop/src/lib/desktop-slash-commands.ts` (`DESKTOP_COMMAND_META` array). A slash command must be in BOTH `hermes_cli/commands.py` (CLI registry) AND `desktop-slash-commands.ts` for the desktop to route it to the slash_worker.

**Without the desktop entry**, `isDesktopSlashCommand()` returns `false` (because `isKnownHermesSlashCommand()` returns `true` for registered CLI commands), and the desktop sends the command as raw text to the AI agent instead of routing to the slash_worker.

Fix: add the command to `DESKTOP_COMMAND_META`:
```ts
['/obs', 'Show observer findings for this session'],
```

## Pitfall: Subagent event payload bloat causes OOM kill (2026-07-02)

`_build_child_progress_callback()` in `tools/delegate_tool.py` (line 763) includes
the FULL `goal` text (~1200 bytes for observer subagents) in EVERY subagent event
payload via `_identity_kwargs()`:

```python
def _identity_kwargs() -> Dict[str, Any]:
    kw: Dict[str, Any] = {
        "task_index": task_index,
        "task_count": task_count,
        "goal": goal_label,   # ← FULL GOAL TEXT IN EVERY PAYLOAD
    }
```

Every `subagent.tool`, `subagent.progress`, `subagent.thinking`, and
`subagent.start` event repeats the entire goal. With 16+ `session_search` calls
per observer subagent, this creates a flood of large JSON events relayed through
the gateway to the Electron frontend.

**Crash evidence (2026-07-02):** `desktop.log` line 24083:
```
[renderer] render-process-gone reason=killed exitCode=9
```
Exit code 9 = SIGKILL (OOM killer). Swap was at 12/15 GB. The Electron renderer
process was killed by the system due to memory pressure from accumulating
subagent event payloads.

**Three contributing factors:**
1. **Payload bloat** — each event carries ~1200 bytes of redundant goal text
2. **Boot-loop stress** — 4 boot cycles in quick succession, each creating new
   backend processes with accumulating pending events
3. **Compression failure** — `glm-4.7` returned "Unknown Model" (error 1211)
   for context compression, leaving ~219K tokens uncompressed

**Fix (proposed, not yet applied):** Remove `goal` from `_identity_kwargs()`.
The `subagent_id` is sufficient for the TUI to reconstruct the spawn tree. Keep
`goal` only in the `subagent.start` event (line 804) where it's sent once.

```python
def _identity_kwargs() -> Dict[str, Any]:
    kw: Dict[str, Any] = {
        "task_index": task_index,
        "task_count": task_count,
        # goal removed — subagent_id is sufficient for tree reconstruction.
        # Goal is sent once on subagent.start.
    }
```

This fix also benefits ALL delegate_task usage, not just observers — any
parallel batch with long goals produces the same payload multiplication.

## Pitfall: Stats-first presentation loses Pavel (2026-06-29)

When presenting observer findings in response to «что выявили наблюдатели?», leading with statistical tables (counts, severity distributions, bar charts) was rejected as «ничего не понятно». Pavel needs the **narrative story arc** — how failures cascaded across sessions chronologically, with full finding texts as evidence. Stats support the story, they don't replace it.

Accepted format: «Акт 1. Павел спросил агента... Акт 2. Наблюдатели попытались... Акт 3. Мета-наблюдатели...» — chronological, causal, with full finding texts.

The detailed presentation pattern is in `references/observer-analysis-queries.md` § Presentation Pattern.

## Pitfall: CORS blocks `fetch()` from Electron; use `window.hermesDesktop.api()`

The dashboard returns `access-control-allow-origin: http://localhost:5174` (Vite dev server). The Electron renderer uses a different origin (`file://` or `app://`), so `fetch()` calls are blocked by CORS.

**Fix**: Use `window.hermesDesktop.api({path, timeoutMs})` which goes through Electron IPC → main process → HTTP, bypassing CORS entirely.

Also: custom API endpoints must be added to `hermes_cli/dashboard_auth/public_paths.py` (`PUBLIC_API_PATHS` frozenset) to bypass the dashboard's session-token authentication. Without this, even `window.hermesDesktop.api()` gets 401.

## Implemented Fixes: State-Poisoning & AGENTS.md Pollution (2026-07-01)

See `references/gap-fixes-state-poisoning-and-agentsmd.md` for the full fix plan with before/after code, exact line numbers, and verification steps. Summary:

| Gap | File | Lines | Fix |
|-----|------|-------|-----|
| State-poisoning | `~/.hermes/scripts/knowledge-curator-ingest-llm.py` | 206-218 | `entities is None → continue` instead of unconditional `state[pstr] = h` |
| AGENTS.md in tool output | `agent/tool_executor.py` | 1387-1393 | Gate `SubdirectoryHintTracker` on `not agent.skip_context_files` |
| AGENTS.md for observer CLI | `agent/agent_init.py` | ~299 | `HERMES_OBSERVER_SUBAGENT=1 → skip_context_files=True` |

## Pitfall: session_search blocks observer workflows (2026-06-29)

Three compounding defects in `tools/session_search_tool.py` that cause observer silent deaths:

### 1. Read-mode truncation without pagination

`_read_session()` at line 177 uses hardcoded `head=20, tail=10`. A session with 37 messages and large tool outputs is truncated to first 20 + last 10 — the observer loses the middle where the assistant's final answer lives. There is NO `offset`/`limit` parameter to request the next chunk.

**Fix**: Add `offset`/`limit` params to `_read_session()` and expose them through `session_search()` at line 564.

### 2. Lineage rejection in `_scroll()` blocks observer reads

`_scroll()` at line 301-308 rejects scroll when `current_session_id` and target session share a root ancestor. But observer sessions (`source="observer"`) are spawned FROM the parent session — they share the same root. Every observer scroll is rejected.

**Fix**: Check `current_meta.get("source") != "observer"` before applying lineage rejection. Observer sessions read OTHER sessions, not their own context.

### 3. Message ID confusion between observer and target sessions

Observer uses `session_search(session_id=TARGET)` to read a session, gets message objects with bare `id` fields, then tries to `scroll(session_id=OBSERVER_OWN, around_message_id=TARGET_MSG_ID)` — it crosses session boundaries because IDs look identical.

**Fix**: `_shape_message()` should include `_session_id` field on every message. Observer prompt should instruct: "Message IDs with _session_id belong to THAT session. Do not use them with a different session_id for scrolling."

## Pitfall: apply_agent() doesn't inject agent identity into LLM context (2026-06-29)

**Root cause of the entire observer cascade on 2026-06-29.** `apply_agent()` in `agent/agents.py:653-723` mutates `agent_obj.enabled_toolsets`, `reasoning_effort`, `model`, `ephemeral_system_prompt` — but the LLM NEVER sees these metadata fields in its system prompt. Result: when user asks "кто я? какой пресет?", agent reads 10+ source files and delivers ZERO answers. This triggers observer sessions which themselves fail due to session_search bugs.

**Fix**: After line 713 in `agent/agents.py`, prepend an identity block to `ephemeral_system_prompt`:

```python
_identity = [
    "[Agent Identity]",
    f"Active preset: {agent_def.label or agent_def.id}",
    f"Preset ID: {agent_def.id}",
    f"Toolsets: {', '.join(agent_def.toolsets) if agent_def.toolsets else 'default'}",
    f"Reasoning: {agent_def.reasoning or 'default'}",
]
if agent_def.model:
    _identity.append(f"Model: {agent_def.model}")
if hasattr(agent_obj, 'platform'):
    _identity.append(f"Platform: {agent_obj.platform or 'unknown'}")
if hasattr(agent_obj, 'session_id'):
    _identity.append(f"Session: {agent_obj.session_id}")

_identity_block = "\n".join(_identity) + "\n\n"
existing = agent_obj.ephemeral_system_prompt or ""
agent_obj.ephemeral_system_prompt = _identity_block + existing
```

Effect: agent instantly knows its preset, model, toolsets from system prompt — 0 tool calls for self-referential questions.

## Pitfall: Stale desktop-controller.tsx comment about agent switching (2026-06-29)

The Critic finding that "desktop uses text injection for agent switching" is **OUTDATED**. `desktop-controller.tsx:264` already uses `requestGateway('agents.activate', { id: presetId })` — the RPC method. But the comment at lines 249-252 still says "inserting the `/agent <id>` command into the composer."

**Fix**: Update the comment:
```typescript
// Switch the active preset via agents.activate RPC. The gateway applies
// the full AgentDef (toolsets, reasoning, model, system prompt) server-side.
```

## Pitfall: Patch tool `\\n` double-escaping in Python f-strings (2026-06-29)

When using the `patch` tool to edit Python source files that contain f-strings with `\n` escape sequences, the `new_string` parameter interprets `\\n` as LITERAL `\\n` (two characters: backslash + n) in the file, NOT as a single escape sequence `\n`. This corrupts f-strings: instead of containing actual newlines, they contain literal `\n` text.

**Symptom:** After patching, Python f-strings like `f"text\n"` become `f"text\\n"` (four characters in source: `\`, `\`, `n`). At runtime this produces literal `\n` instead of newline. AST parse still passes (no syntax error) but string content is wrong.

**Fix:** Use `\n` (single backslash-n) in the `new_string` — it becomes a real escape sequence in the file. Verify with:
```python
# Check for double-escaped newlines
import re
double_escaped = re.findall(r'\\\\n', file_content)  # should be 0
```

**Check:** Always verify after patching Python f-strings by reading the file back and checking for `\\\\n` (double-escaped) patterns. The `read_file` tool shows escaped representations — `\\\\n` in output = double-escaped in file (WRONG), `\\n` in output = single-escaped (CORRECT).

## Pitfall: Observer recursion depth — 3-level chains with no limit (2026-07-01)

**Finding:** Today's observer cycle revealed a 3-level chain: `cron → observer → observer-of-observer`. The observer-of-observer adds ZERO incremental insight — it restates the same 4 bullet points from the first observer. No depth cap exists; chains can grow unbounded.

**Fix:**
1. Add `observer_max_depth: 1` to config.yaml — observers cannot spawn further observers
2. Track observer chain depth in session metadata (`observer_depth` field)
3. Observer-of-observer should be a **dedicated deep-observer** (tier 2, full investigation tools), not a surface observer recursively applying the same 120-word template
4. Two-tier depth: surface observer (120 words, no tools) → deep observer (unlimited, with terminal/file_ro/web) — deep observer is opt-in, not automatic recursion

## Pitfall: AGENTS.md noise in observer/cron tool output (2026-07-01)

**Finding:** Every `terminal()` call in observer/cron sessions injects AGENTS.md (12KB) into the output via `SubdirectoryHintTracker`. Observers and knowledge curators don't need project conventions — they need clean tool output. At 4 observer sessions per cycle, this wastes ~48K tokens.

**Root cause:** `agent/tool_executor.py:1387-1393` — `SubdirectoryHintTracker` fires unconditionally for all agent types.

**Fix (designed, not yet implemented):** Gate `SubdirectoryHintTracker` on `not agent.skip_context_files`. Set `skip_context_files=True` for observer agents. For CLI observer spawns: check `HERMES_OBSERVER_SUBAGENT=1` env var and set `skip_context_files=True` in `agent_init.py`.

**Mitigation (today):** The `hermes-observer-system` skill now documents this. The fix implementation plan is in `references/gap-fixes-state-poisoning-and-agentsmd.md`.

Long agent responses (~3500 words, ~18K chars) can be truncated in delivery through the gateway. User sees only the final portion — the bulk of the analysis is lost.

**Evidence:** AuditFinding #24033 in Neo4j. Full analysis of observer-orchestrator architecture (4 variants, comparison tables, code snippets, roadmap) was generated but user reported: "я не вижу вывода. Запиши это как баг который надо исправить. Я вижу только твой вопрос."

**Root cause:** Likely gateway message assembly truncation at large message sizes — not model generation failure (model produced the content).

**Mitigation:**
1. For responses expected to exceed ~2000 words, break into multiple messages or add a "response truncated" indicator
2. Investigate gateway `final_response` handling for size limits
3. Add integration test: generate 5000+ word response, verify full delivery
4. Check if the truncation is in the gateway's `_on_tool_progress` payload assembly or in the Electron IPC bridge

**Note:** The orchestrator observer's spawn model may exacerbate this — each spawned observer returns a summary, and the orchestrator aggregates them, potentially producing very long final outputs.

## Bulk Analysis: Querying Observer Findings

When asked to "analyze observer findings," "show key findings," or "what did observers find" — run aggregate Neo4j queries across all finding types. Do NOT spawn new observer subagents (they produce duplicate findings). Query existing data directly.

See `references/observer-analysis-queries.md` for battle-tested Cypher queries covering:
- Global statistics (counts by type, severity, fix ratio)
- Top CRITICAL/HIGH findings with cascade filtering
- Theme categorization (recurring patterns)
- Mutation status distribution (the fix gap)
- Session/source attribution
- Presentation pattern for Pavel

When asked to propose solutions for patterns found by observers, load
`references/observer-root-cause-solutions.md` — it contains concrete code fixes
for the 5 root cause patterns discovered on 2026-06-29 (agent self-awareness,
observer graceful degradation, session_search bugs, agent switching asymmetry,
and the diagnosis→implementation fix gap). Fixes #1-#4b were IMPLEMENTED on
2026-06-29 (identity injection, observer fallback+watchdog, session_search
pagination+lineage+session_id, desktop comment fix + persistentAtom).

After implementing fixes, delete the corresponding obsolete findings from Neo4j
so only fresh issues remain. See `references/observer-cleanup-queries.md` for
the full workflow: identify findings by keyword → collect IDs → batch delete →
verify remaining counts. This prevents stale findings from cluttering the
ObserverPanel and future analysis.

Key presentation rules: data-driven (real Cypher output), `█` bar charts for density, 200-250 char excerpts, priority actions ranked by severity × recurrence.

## Quick debugging: \"Why are observer sessions still cluttering my sidebar?\""\n\nWhen observer sessions keep appearing in the desktop sidebar despite `excludeSources: ['cron', 'observer']`:\n\n1. **Check source in state.db**:\n   ```bash\n   sqlite3 ~/.hermes/state.db \"SELECT source, COUNT(*) FROM sessions GROUP BY source\"\n   ```\n   If `source='cli'` sessions are accumulating → source tagging is broken.\n\n2. **Identify the spawning path**:\n   ```bash\n   sqlite3 ~/.hermes/state.db \"SELECT s.id, substr(m.content,1,120) FROM sessions s JOIN messages m ON m.session_id=s.id WHERE s.source='cli' AND m.role='user' LIMIT 5\"\n   ```\n   - \"Session analysis for critic observer...\" → `observer_worker.py` CLI spawn (check for `--cli` flag bug)\n   - \"You are a session observer...\" → `conversation_loop.py` deep observer (check `platform='observer'` parameter)\n   - Other content → delegate_task subagents from normal agent operation (not observer-related)\n\n3. **Verify fixes**:\n   - `observer_worker.py`: no `--cli` flag, has `HERMES_SESSION_SOURCE=observer` in env\n   - `conversation_loop.py`: deep observer passes `platform='observer'` to `_delegate()`\n   - `delegate_tool.py`: `_build_child_agent` uses `platform or parent_agent.platform`\n\n4. **Restart the dashboard**: Python code changes to `observer_worker.py`, `conversation_loop.py`, and `delegate_tool.py` require the dashboard process to restart. Closing and reopening `hermes gui` restarts both the Electron frontend and the Python dashboard.

When observer sessions flood the DB or the user wants them off temporarily:

### Quick pause (GUI toggle — preferred, v4+)

Click the 👁 button in the desktop statusbar → toggle OFF. Or type `/obs off` in the chat. This sets `observer.enabled: false` in config.yaml and all three tiers stop immediately. No process cleanup needed.

### Quick pause (kill running processes, no config change — legacy)

```
# Kill all observer workers (stops new hermes -z spawns)
pkill -f observer_worker.py

# Kill all running observer subagents (hermes -z processes)
pkill -f "hermes -z.*observer"

# Clean up stale lock files
rm -f /tmp/hermes_observer_locks/observer_*.lock
```

### Permanent disable (plugin-level, survives restart — legacy, prefer config toggle)

Remove or rename the plugin so it doesn't load:

```bash
mv ~/.hermes/hermes-agent/plugins/observer-hook ~/.hermes/hermes-agent/plugins/observer-hook.disabled
```

Then restart Hermes. Prefer `observer.enabled: false` in config.yaml instead — it survives restart and can be toggled from the GUI without touching the filesystem.

### Note on slash_workers

`slash_worker` processes are NOT part of the observer system — they are TUI gateway workers that keep sessions alive in the desktop sidebar. Each worker references a session key. When you delete sessions from `state.db`, the workers DON'T know and keep running as ghosts. They are harmless but clutter `ps aux`. Kill them with `pkill -f slash_worker` after session cleanup.
