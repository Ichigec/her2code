# Capability Gap Detection — Task Understanding Depth Framework

> Added 2026-06-25 from session with Pavel. Captures the user's correction: task decomposition without self-capability assessment is incomplete.

## The Core Problem

When an agent decomposes a task, it assumes it CAN execute every sub-task. This is wrong. Example:

**Task:** «Сделай приложение с картинкой»

Hidden capability requirements:
- `code_write` ✅ — can write HTML/JS
- `vision` ❌ — cannot see if the image displays correctly
- `browser_gui` ❌ — no `$DISPLAY`, cannot open browser
- `subjective_judgment` ❌ — cannot decide if image is «beautiful»
- `imagemagick` ⚠️ — may or may not be installed
- `ffmpeg` ✅ — available for metadata check

**Without gap detection:** agent writes code, claims «done», fabricates verification.
**With gap detection:** agent maps gaps → finds workarounds or asks user.

## 5-Level Task Understanding Depth

### Level 0 — Literal Translation (Surface)

Direct word→code without comprehension. Zero questions. Zero decomposition.

```
Task: «сделай приложение с картинкой»
Plan: <img src="picture.jpg">
```

**Signals:** no platform choice, no error handling, no validation.

### Level 1 — Plan-and-Solve (Structural)

Divides into sequential steps. Recognizes ambiguities but picks arbitrary defaults.

```
1. Platform: Web (arbitrary choice)
2. Stack: React (arbitrary choice)
3. Image source: URL (arbitrary choice)
4. UI: container + <img>
5. States: loading, error, empty
```

Paper: Plan-and-Solve (Wang et al., 2305.04091).

### Level 2 — Tree-of-Thoughts (Branching)

Generates alternatives at each step AND evaluates them. Still assumes all sub-tasks are executable.

```
Platform? ├─ Web (8/10) ─ CHOOSE
           ├─ Mobile (7/10)
           └─ Desktop (3/10) ─ REJECT

Source?   ├─ URL (9/10) ─ CHOOSE
           ├─ Local file (6/10)
           ├─ Camera (5/10)
           └─ Gallery (7/10)
```

Paper: Tree of Thoughts (Yao et al., 2305.10601).

### Level 3 — Graph-of-Thoughts + Dependencies (DAG)

Builds dependency DAG, identifies parallelizable sub-tasks, has merge operations and reflection loop.

```
UI component ∥ Image loader ∥ State handler
         └───────────┬───────────┘
                Integration (MERGE)
                      │
                 Reflexion loop
```

Papers: Graph of Thoughts (Besta et al., 2308.09687) + LLMCompiler (Kim et al., 2312.04511).

### Level 4 — MCTS + Capability-Aware (Adaptive Search)

Everything from Level 3 PLUS:
1. **Capability inventory** — agent knows what it CAN and CANNOT do
2. **Gap forecast** — for each sub-task, checks: «can I execute AND verify this?»
3. **Resolution routing** — for each gap: tool_workaround → ask_user → delegate_to_agent → accept_risk
4. **Honest communication** — «This part I can verify; that part only you can»

Papers: AFlow (Zhang et al., 2410.10762) + RAP (Hao et al., 2305.14992).

## Capability Inventory Template

```yaml
# ~/.hermes/agents/capabilities.yaml
capabilities:
  # Always available
  code_write:
    available: true
    source: builtin
  terminal_exec:
    available: true
    source: builtin
  file_read:
    available: true
    source: builtin

  # Environment-dependent (dynamic)
  web_fetch:
    available: false
    workaround: "curl via terminal"
  vision:
    available: false
    workaround: "imagemagick identify + ffprobe for structure"
    fallback: "ask_user — agent cannot visually verify images"
  browser_gui:
    available: false
    workaround: "headless curl + DOM checks"
    note: "no $DISPLAY on server"
  imagemagick:
    available: dynamic
    check: "which identify"
  ffmpeg:
    available: dynamic
    check: "which ffmpeg"

  # Unsolvable
  subjective_judgment:
    available: false
    fallback: "ask_user — cannot assess 'beauty' or 'quality'"
```

## Gap Resolution Strategies (Priority Order)

| Priority | Strategy | When to use |
|----------|----------|-------------|
| 1 | `tool_workaround` | Gap can be partially closed with available tools (e.g. `imagemagick identify` instead of human vision for structural checks) |
| 2 | `delegate_to_agent` | Another sub-agent has the capability (e.g. Android agent can camera-test) |
| 3 | `ask_user` | Gap cannot be worked around; user MUST verify |
| 4 | `accept_risk` | Gap is non-critical; proceed with documented risk |

## Concrete Example: «Сделай приложение с картинкой»

### Capability Map (before decomposition)

| Sub-task | Required | Status | Resolution |
|----------|----------|:------:|------------|
| UI code | `code_write` | ✅ | — |
| Image loading | `code_write` | ✅ | — |
| Visual verification | `vision` | ❌ CRITICAL | `imagemagick identify` (structural) + ask_user (visual) |
| Cross-browser test | `browser_gui` | ❌ | headless `curl` + ask_user |
| «Is it beautiful?» | `subjective_judgment` | ❌ | ask_user (unsolvable) |
| Image resize <100KB | `imagemagick` | ⚠️ | `which identify` → install if missing |

### Gap Report (injected into every delegate_task context)

```
Capability gaps for this cycle:
  vision ❌ → workaround: imagemagick identify for structure
             → user must verify visually
  browser_gui ❌ → workaround: headless curl checks
                 → user must test in real browser
  subjective_judgment ❌ → user decides (can't automate)

Agent obligation: NEVER claim to have verified something outside capability.
If a sub-agent says «image displays correctly» — REQUIRE the tool output as proof.
```

## Implementation in Orchestration Cycle

**Phase 0.2 (Capability Inventory):** run dynamic checks, produce `capability_report.json`.

**Phase 0.3 (Gap Forecast):** scan user task for keywords implying capabilities. Map gaps to resolutions. Produce `gap_report.json`.

**Phase 1+:** inject `capability_report.json` + `gap_report.json` paths into every `delegate_task` context.

**Auditor check (Phase 10):** did any agent claim to verify something it structurally cannot?

## Pitfalls

| Pitfall | Why it happens | Fix |
|---------|---------------|-----|
| Agent claims «image is correct» | No vision, but fabricates verification | Capability check: «can you actually see this?» |
| Agent opens «browser» | Assumes GUI is available | `$DISPLAY` check → fallback to curl |
| Agent says «looks good to me» | LLM generates plausible text | Require tool output as evidence, not summary |
| Capability inventory is static | Installed tools change over time | Dynamic checks (`which`, `curl` health) at Phase 0 |
| User frustrated by «I can't do X» | Agent reports gaps as failures, not as routing | Frame gaps with resolutions: «I can check structure (A), but you must verify visually (B)» |

## Key Papers

| Paper | arXiv | Insight |
|-------|-------|---------|
| Plan-and-Solve | 2305.04091 | Plan first, then execute; reduces missing-step errors |
| Tree of Thoughts | 2305.10601 | BFS/DFS over reasoning steps; LLM self-evaluates alternatives |
| Graph of Thoughts | 2308.09687 | DAG with merge/refine/generate; generalizes CoT and ToT |
| RAP | 2305.14992 | MCTS where LLM is both world model and value function |
| AFlow | 2410.10762 | MCTS over workflow DAGs; automated agent architecture discovery |
| LLMCompiler | 2312.04511 | Dependency DAG analysis for parallel function calling |
| Reflexion | 2303.11366 | Verbal RL — store failure reflections for future plans |

## Research-Backed Findings (2026-06-25 Deep Plan Research)

Full cycle `<SESSION_ID>`: 6 parallel research agents, 50+ sources, 5-phase plan2 execution.

### What Exists — Academic

| Paper | Year | Relevance | Mechanism |
|-------|------|:---------:|-----------|
| **MUSE** (Valiente & Pilly, 2411.13537) | 2024 | 9/10 | Competence-aware metacognitive agents — explicit competence boundary framework |
| Metacognitive Loop (Anderson & Perlis) | 2005 | 8/10 | Foundational: agents monitor reasoning, detect brittleness, self-correct |
| Emergent Introspective Awareness in LLMs (2601.01828) | 2026 | 8/10 | LLMs detect injected steering vectors at moderate rates; 0% false positives |
| Learning From Failure (Wang et al., 2402.11651) | 2024 | 8/10 | Trains agents on negative examples to learn tool-use boundaries |
| SRCA: Хартия саморефлексивных ИИ (habr, 2025) | 2025 | 9/10 | Russian tech community: defines Self-Reflective Cognitive Agents |

**Критический пробел:** российская академия — **ноль публикаций** по metacognition/self-modeling agents. Все русскоязычные источники — habr.com.

### What Exists — Production Code

| Framework | Strategy | Mechanism |
|-----------|----------|-----------|
| **Claude Code** (Anthropic) | Boundary Detection | PreToolUse/PostToolUse hooks with matcher patterns; auto-disable capability on rejection; `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` |
| **Aider** | Static Profiling | `models.py` hardcoded model-name pattern matching → capability flags; fallback chains (weak_model → editor_model); `sanity_check_models()` validates at startup |
| **Codex CLI** (OpenAI) | Configuration Gating | `HookToolName` with canonical names + Claude Code-compatible matcher aliases; explicit enable/disable |
| **LangChain** | LLM-Based Tool Selection | `LLMToolSelectorMiddleware` filters tools before model calls; `DYNAMIC_TOOL_ERROR_TEMPLATE` lists unknown tools + available alternatives |
| **AutoGen** (Microsoft) | Workbench Discovery | `Workbench.list_tools()` — dynamic capability listing; `is_error=True` results for missing tools |
| **CrewAI** | Dict Lookup + Hooks | `tool_name_to_tool_map` sanitized lookup; before/after hooks can block execution |

**Главный вывод:** ни у кого нет pre-flight capability checking. Все проверяют доступность в рантайме.

### What Exists — Analogous Patterns

| Domain | Pattern | Agent Mapping |
|--------|---------|---------------|
| **K8s** | Readiness/Liveness Probes | Two-tier capability status: `reachable` (liveness) + `usable` (readiness); separate exit codes |
| **Web** | Modernizr Feature Detection | Probe, don't sniff: runtime `check` command, never trust model name/version |
| **OS** | PCI Enumeration | Bootstrap sequence: enumerate → match (probe) → expose (report) |
| **API** | GraphQL Introspection | Self-describing `__schema` query — agent should expose its capability manifest |
| **Microservices** | Circuit Breaker | CLOSED→OPEN→HALF_OPEN per capability; cooldown + recovery probe |
| **Robotics** | ROS Node Advertising | Nodes announce «I can provide X, Y, Z» — agent tools as ROS topics |
| **Plugin** | VST `canDo()` | Host queries plugin capabilities; plugin returns supported feature set |

### Architecture Decision Record

These 5 patterns were selected for the plan2 capability-self-model subsystem:

1. **K8s two-tier readiness/liveness** — every capability has `reachable` (does it respond?) AND `usable` (is it functional?)
2. **Claude Code boundary detection + circuit breaker** — per-capability CLOSED→OPEN→HALF_OPEN; failed probe → auto-mark unavailable
3. **Modernizr feature detection** — every dynamic capability has a `check` command executed at runtime; never trust model name sniffing
4. **PCI enumeration** — bootstrap: ENUMERATE (scan YAML → load records) → MATCH (run probes) → EXPOSE (format report)
5. **MUSE competence boundaries** — explicit `capability_composition.yaml` rules; natural-language explanation when boundary is reached

### Concrete Architecture (plan2 Phase 0.2-0.3)

```
Phase 0.2 — Capability Inventory:
  G0: CapabilityGate       — entry point for orchestrator
  G1: CapabilityLoader     — static inventory → dataclasses
  G2: CapabilityProber     — live probes with circuit breakers
  → capability_report.json

Phase 0.3 — Gap Forecast:
  G3: KeywordMapper        — task keywords → required capabilities
  G4: CompositionEngine    — compositional reasoning (MUSE boundaries)
  G5: GapResolver          — for each gap: что-можно / что-нельзя / что-сложно
  G6: FabricationGuard     — scan plan for impossible verification steps
  G7: ReportBuilder        — pre-flight report ≤50 lines
  → gap_report.json → user (confirm/override/add/cancel)
```

Full implementation plan: 10 modules, 27 files, 17 TDD tasks.
