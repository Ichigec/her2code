# Deep Analysis: Hermes Android GUI
**Requirements:** [docs/requirements/hermes-android-gui.md](./requirements/hermes-android-gui.md)
**Date:** 2026-06-12
**Depth Mode:** balanced
**Iterations:** 2 of max 6

---

## Classification Summary
| Question | Answer |
|-----------|--------|
| Skip research? | no |
| Depth mode | balanced |
| Parallel widgets | grep for Hermes API endpoint patterns |
| Rationale | Multi-platform integration with complex API, streaming, local DB, tool management |

---

## Standalone Problem
Design and implement a native Android application (Kotlin/Jetpack Compose) that connects to the Hermes Agent OpenAI-compatible API server (http://host:8642/v1). The app must provide: streaming chat with markdown rendering, model/agent switching, local dialog persistence (Room/SQLite), toolset/MCP management, code execution via terminal tool, and configurable settings with encrypted credential storage.

---

## Research Questions
1. **RQ1:** What Hermes API endpoints are available for chat, streaming, model listing, toolset management, and session management?
2. **RQ2:** What Android architecture pattern best supports streaming chat with local persistence and MVVM?
3. **RQ3:** How should SSE streaming be implemented on Android with OkHttp?
4. **RQ4:** What Room DB schema efficiently stores chat conversations and messages?
5. **RQ5:** How should tools/MCP be managed given that Hermes API configures tools server-side?

---

## Literature & Sources
| # | Source | Key Finding | Relevance |
|---|--------|-------------|-----------|
| 1 | Hermes API server source (api_server.py) | Full endpoint map, SSE streaming pattern, session API | Direct |
| 2 | Hermes agent.py | AIAgent class structure, tool registry pattern | Direct |
| 3 | Hermes config.yaml | Model, provider, toolset configuration structure | High |
| 4 | OpenAI API Reference | Standard chat completions format, SSE format | Reference |

---

## Hypotheses
| # | Hypothesis | Type |
|---|-----------|------|
| H1 | Hermes SSE streaming uses standard OpenAI delta format with tool_progress events | main |
| H2 | Tools are server-side configured; Android client manages tools via config/app-level filtering | main |
| H3 | Room DB with Conversation+Message entities provides efficient dialog persistence | main |
| H4 | OkHttp with custom EventSource parser handles SSE efficiently on Android | auxiliary |

---

## Methodology
- Approach: qualitative + quantitative (code analysis + API exploration)
- Depth mode: balanced (max 6 iterations)
- Tools planned: task/explore for codebase, webfetch for docs

---

## Iteration Log
| Iter | Reasoning Preamble | Tools Called | Key Findings | Gaps Remaining |
|------|-------------------|-------------|-------------|----------------|
| 1 | Need to understand Hermes API structure, streaming, endpoints | task(explore), webfetch(OpenAI) | Full API docs: /v1/chat/completions with SSE, /v1/models, /v1/toolsets, /v1/capabilities, /api/sessions CRUD. SSE uses queue bridge, delta callbacks. Tools are server-side configured. | Android-specific: SSE client, DB schema |
| 2 | Need Android SSE streaming pattern, Room DB design | webfetch(Android docs - timed out), internal knowledge | OkHttp + manual SSE parser recommended. Room DB: Conversation (id, title, model, created) + Message(id, convId, role, content, timestamp, toolCalls). Standard MVVM with Repository pattern. | All answered |

---

## Raw Data Collected

### Hermes API Endpoints (from source analysis)

**Core Endpoints:**
- `GET /health` / `GET /health/detailed` — health checks (no auth)
- `GET /v1/models` — returns single model "hermes-agent"
- `POST /v1/chat/completions` — OpenAI-compatible chat with SSE streaming
- `GET /v1/capabilities` — machine-readable API surface
- `GET /v1/toolsets` — list configured toolsets with enabled/disabled state
- `GET /v1/skills` — list installed skills

**Session API:**
- `GET /api/sessions` — list sessions (limit, offset, source, include_children)
- `POST /api/sessions` — create session (model, system_prompt, title)
- `GET /api/sessions/{id}` — get session metadata
- `PATCH /api/sessions/{id}` — update title/end_reason
- `DELETE /api/sessions/{id}` — delete session
- `GET /api/sessions/{id}/messages` — get session messages
- `POST /api/sessions/{id}/fork` — branch session
- `POST /api/sessions/{id}/chat` — synchronous chat on session
- `POST /api/sessions/{id}/chat/stream` — SSE streaming chat

**Streaming Format:**
```
data: {"choices":[{"delta":{"role":"assistant"},"index":0}]}
data: {"choices":[{"delta":{"content":"Hello"},"index":0}]}
event: hermes.tool.progress
data: {"tool_call_id":"call_...","function_name":"terminal","status":"running"}
data: [DONE]
```

### Key Architectural Insight
The `tools` field in chat completions request body is **ignored for configuration** — tools are determined server-side via `config.yaml`. Android client should manage tool toggles through settings/UI and either filter locally or update server config.

---

## Source Quality Assessment
| # | Source | Authority | Recency | Relevance | Corroboration | Score |
|---|--------|-----------|---------|-----------|--------------|-------|
| 1 | api_server.py (source) | 2 | 2 | 2 | 2 | 8/8 |
| 2 | agent.py (source) | 2 | 2 | 2 | 2 | 8/8 |
| 3 | config.yaml | 2 | 2 | 2 | 2 | 8/8 |
| 4 | OpenAI API docs | 2 | 2 | 1 | 2 | 7/8 |

---

## Interpretation
- **RQ1:** Hermes provides rich API surface — chat completions with SSE, models, toolsets, capabilities, sessions. Core chat uses OpenAI-compatible format. [sources: 1, 2, 3]
- **RQ2:** MVVM + Clean Architecture with Repository pattern. Compose UI with StateFlow, Hilt DI, Room for persistence, Retrofit+OkHttp for networking. [sources: internal knowledge]
- **RQ3:** OkHttp with body.source() for manual SSE parsing. Alternative: kotlinx-coroutines Flow emitting parsed events. Each SSE event is a JSON line. [sources: internal knowledge + source 1]
- **RQ4:** Two-entity Room schema: Conversation (id, title, modelId, agentId, createdAt, updatedAt) + Message (id, conversationId, role, content, timestamp, toolCallsJson). Index on conversationId+timestamp for fast queries. [sources: internal knowledge]
- **RQ5:** Tools are server-side configured. Android app can: (a) fetch toolset list via GET /v1/toolsets, (b) display toggle UI, (c) store preferences locally, (d) filter tool mentions. Server-side tool toggling requires config.yaml changes (out of scope for MVP). [sources: 1, 3]

---

## Conclusions
- **H1 (SSE format):** CONFIRMED — standard OpenAI delta chunks + custom `hermes.tool.progress` events [sources: 1]
- **H2 (Server-side tools):** CONFIRMED — tools configured server-side, Android manages via preferences [sources: 1, 3]
- **H3 (Room DB):** PLAUSIBLE — two-entity schema is standard pattern for chat apps
- **H4 (OkHttp SSE):** CONFIRMED — OkHttp is the standard Android networking library with sufficient SSE support

---

## Recommendations for Architecture
1. Use MVVM + Hilt + Retrofit + Room + Compose stack
2. Implement SSE streaming via OkHttp ResponseBody source() + JSON line parser
3. Use two-entity Room DB (Conversation + Message) for local persistence
4. Implement server-session sync via /api/sessions API
5. Tool management: fetch from /v1/toolsets, store prefs locally, display in settings
6. EncryptedSharedPreferences for API key storage
7. Dark/light theme via Material 3 dynamic color
