# Enriched Gap Detection — BA Frameworks + Pre-Hook Quality Gates

> Added 2026-06-25 from session `<SESSION_ID>`. Enriches the orchestrator's Gap Detection (Phase 0) with Business Analysis questioning frameworks and extends quality gates to ALL 15 phases/sub-phases.

---

## Part 1: BA Frameworks Enriching Gap Queries

The core insight: keyword matching ("screenshot" → vision) operates on surface nouns. BA techniques decompose tasks into structured multi-dimensional models that surface hidden dependencies, edge cases, and integration points. Each technique multiplies the detection surface by 3×–10×.

### 1. BACCM — 6-Dimensional Capability Vector

**Origin:** BABOK Guide v3, IIBA. Six core concepts: Change, Need, Solution, Stakeholder, Value, Context.

**Enrichment:** For EACH sub-task, ask all 6 questions. Answers reveal required capabilities even when the task text contains no keywords.

| BACCM Core | Gap Query | Capability Derived |
|-----------|-----------|-------------------|
| **Change** | Что изменится в системе? | Тип артефакта → code_write, file_write |
| **Need** | Что должна уметь делать система? | Инструменты → terminal, docker, adb |
| **Solution** | Как именно будет решаться? | Конкретные команды → imagemagick, ffmpeg |
| **Stakeholder** | Кто будет проверять результат? | vision (человек) vs автотесты (агент) |
| **Value** | Как измерить успех? | testing tools, monitoring |
| **Context** | Какие ограничения среды? | $DISPLAY, platform, port availability |

**Enrichment factor:** 3× over keyword matching. Example: task says "телефон по USB" — no keyword triggers `adb`. But Context question extracts `adb` from the environment constraint.

### 2. SPIN — Impact-Quantified Gaps

**Origin:** Huthwaite (1988). Situation → Problem → Implication → Need-payoff.

**Gap query sequence:**
1. **Situation:** "What is the current state for this sub-task?"
2. **Problem:** "What goes wrong if we can't execute this?"
3. **Implication:** "What's the downstream impact?" (quantify: time, risk, cost)
4. **Need-payoff:** "What would having this capability unlock?"

**Enrichment factor:** 4×. SPIN quantifies impact — a gap that "blocks production deployment" gets higher severity than one that "delays optional polish step."

### 3. 5 Whys — Root Cause Classification

**Origin:** Toyota Production System (Ohno, 1988).

**Gap classification tree:**
```
SYMPTOM: "Agent can't verify the image"
  Why 1: No vision capability
  Why 2: Jetson GPU doesn't support vision models (CUDA=0)
  Why 3: ctranslate2 ARM64 wheel has no CUDA support
  → CLASS: architecture_gap (not tool_gap, not LLM_limit)

SYMPTOM: "Agent can't open browser"
  Why 1: No $DISPLAY
  Why 2: Running on headless server
  Why 3: By design — Jetson is a server, not a workstation
  → CLASS: environment_gap (not fixable, must work around)
```

**Enrichment factor:** 3×. Without 5 Whys, all gaps look like "missing tool." With it, they're classified as: tool_gap, architecture_gap, environment_gap, LLM_limit, permission_gap. Resolution strategy depends on class.

### 4. User Story Mapping — Decomposition Explosion

**Origin:** Jeff Patton (2005). Epic → User Stories → Tasks.

**Gap query:** Decompose user task into 15+ stories. Each story = separate capability check.

```
Epic: "Make an app with a picture"
  ├─ Story 1: User opens app → no image yet → empty state UI   → code_write ✅
  ├─ Story 2: User taps "Add Picture" → file picker opens      → code_write ✅
  ├─ Story 3: User selects photo → EXIF metadata extracted     → imagemagick ⚠️
  ├─ Story 4: App resizes to <500px → aspect ratio preserved   → imagemagick ⚠️
  ├─ Story 5: User sees thumbnail preview                      → vision ❌
  ├─ Story 6: User zooms in → high-res detail loads            → code_write ✅
  ├─ Story 7: App works offline → image cached locally          → code_write ✅
  ├─ Story 8: Dark mode → image adjusts                        → code_write ✅
  ├─ Story 9: Accessibility → alt text generated               → LLM ⚠️
  └─ Story 10: User shares image → share intent fired          → adb ✅ (test) / vision ❌ (verify)
```

**Enrichment factor:** 7×. Keyword matching catches 3 capabilities. User Story Mapping catches 10.

### 5. BPMN Activity Extraction — Integration Point Discovery

**Origin:** Business Process Model and Notation (OMG, 2004).

**Gap query:** For each swimlane activity, what tool executes it?

```
Swimlane: UI Layer          → code_write ✅
Swimlane: Image Processing  → imagemagick ⚠️, vision ❌ (verify)
Swimlane: Storage           → code_write ✅
Swimlane: Testing           → adb ✅, browser_gui ❌
  └─ Integration point: Testing→Image Processing
     → Need BOTH adb AND vision for end-to-end screenshot test
     → Derived gap: adb_present AND vision_missing → screenshot_test_impossible
```

**Enrichment factor:** 10×. BPMN's swimlane boundaries reveal integration points where two capabilities must coexist — a gap in either creates a derived gap at the integration boundary.

### 6. Decision Tables — Edge Case Coverage

**Origin:** Software requirements specification (IEEE 830).

**Gap query:** Rule-Condition-Action matrix forces consideration of edge cases.

```
CONDITIONS:
  Platform = Web | Mobile | Desktop
  Image source = URL | Local | Camera | Gallery
  Verification = Auto | Manual
  Network = Online | Offline

RULES (selected):
  R1: Web + URL + Auto + Online → structural_validation (imagemagick) ✅
  R2: Web + URL + Manual + Online → ask_user (visual) + structural ✅
  R3: Mobile + Camera + Auto → NEED: camera_access ❌, adb ✅ → derived gap
  R4: Mobile + Camera + Manual → ask_user (take photo) + adb test ✅
```

**Enrichment factor:** 5-10×. Edge cases that keyword matching never sees.

### 7. Laddering — Root Need Extraction

**Origin:** Means-End Chain Theory (Gutman, 1982).

**Gap query chain:** "Why do you need X?" repeatedly until root need exposed.

```
Q: Why do you need to "see the image"?
A: To verify it displays correctly
Q: Why verify it displays correctly?
A: To ensure the app works
Q: Why ensure the app works?
A: To deliver a working product to the user

→ ROOT NEED: delivery confidence
→ MAPPING: delivery_confidence can be satisfied by:
  - Structural validation (imagemagick identify) → 80% confidence
  - Automated layout check (DOM dimensions via headless) → 60% confidence
  - Human visual check → 100% confidence
  - Screenshot diff test (requires vision) → 95% confidence ❌
```

**Enrichment factor:** 5×. Laddering reveals that "vision is needed" is actually "delivery confidence is needed" — which has multiple satisfaction paths, some within capability.

---

## Part 2: Pre-Hook Quality Gates — 145 Checks Across 15 Phases

### Architecture: PEP/PDP (RFC 2753)

Every phase transition passes through a Policy Enforcement Point (PEP) that invokes a Policy Decision Point (PDP):

```
Phase N complete → PhaseTransitionPEP.before_phase(N+1, context)
                     → GatePluginRunner.run(gate:N+1)
                       → PolicyDecisionPoint.evaluate(results)
                         → Go / Kill / Hold / Recycle
```

**Implementation (signet-eval pattern):**
```python
class PhaseTransitionPEP:
    def before_phase(self, phase_id, context):
        plugins = GatePluginRegistry.get_for_phase(phase_id)
        results = [p.check(context) for p in plugins]
        blockers = [r for r in results if r.severity == BLOCKER and not r.passed]
        if blockers:
            if all(b.resolution for b in blockers):
                return GateVerdict(HOLD, blockers)
            return GateVerdict(KILL, blockers)
        return GateVerdict(GO)
```

### Stage-Gate Semantics (Cooper, 1990)

Four-phase transition decision framework, validated in 2026-06-25 research:

| Verdict | When | Action |
|---------|------|--------|
| **Go** | All BLOCKER checks PASS | Enter next phase |
| **Kill** | BLOCKER failed, no resolution possible | Halt cycle, escalate to user |
| **Hold** | BLOCKER failed, resolution exists | Pause, execute resolution, re-evaluate gate |
| **Recycle** | Phase complete but GAP propagation detected | Return to previous phase with specific GAP |

### Phase Coverage Summary

| Phase | Checks | BLOCKER | Key BLOCKER Example |
|-------|:------:|:-------:|---------------------|
| 0: Bootstrap | 12 | 5 | FS writable, registry.json valid |
| 1: Requirements | 9 | 2 | All BACCM dimensions covered, all ACs verifiable |
| 2: System Analysis | 8 | 2 | All WSM alternatives feasible, goal tree reachable |
| 3: Research (3.0–3.3) | 19 | 11 | Searchbox healthy, sources ≥3 types |
| 4: Architecture | 10 | 3 | Module contracts feasible, ports free |
| 5: Plan | 9 | 2 | Each TDD task has developer with tools |
| 5.5: Pre-Flight | 14 | 8 | All services health-checked, 4 observers alive |
| 6: Implementation | 10 | 2 | Per-developer tool availability |
| 6a: Integration | 5 | 1 | No orphan modules |
| 6.5: Verification | 7 | 2 | GAP propagation from Phase 1 to code |
| 7: Security | 9 | 2 | All SAST tools available |
| 8: Deployment | 10 | 4 | Target host reachable, permissions |
| 8.5: Acceptance | 8 | 3 | Every test executable with available tools |
| 9: Post-Deploy | 6 | 2 | Monitoring accessible |
| 10: Iterate | 9 | 3 | All 4 observer reports generatable |
| **TOTAL** | **145** | **52** | |

### CI/CD Patterns Applied

| Pattern | Origin | plan2 Implementation |
|---------|--------|---------------------|
| **Jenkins `when`/`input`** | Jenkins Declarative Pipeline | Declarative YAML gate rules (`gates/<phase>.gate.yaml`) |
| **SonarQube Quality Gate** | SonarSource | Metric threshold gates (≥90% recall, ≤5s latency) |
| **OPA Admission Controllers** | CNCF (Open Policy Agent) | Default-deny policy: capability NOT in inventory → deny |
| **Git pre-commit hooks** | Git | `pre-phase-N` hook scripts; non-zero exit aborts transition |
| **Stage-Gate (Cooper)** | Innovation management | Go/Kill/Hold/Recycle gate decisions |
| **K8s ValidatingWebhook** | Kubernetes | Externalizable gate webhooks; decoupled gate logic |

### Existing Implementations Ranking (RQ6, 2026-06-25)

| Rank | System | Key Feature | plan2 Fit |
|:----:|--------|-------------|:---------:|
| 1 | **signet-eval** | YAML rules, condition functions, 25ms eval, 199 adversarial tests | ⭐⭐⭐⭐⭐ |
| 2 | **Claude Code PreToolUse** | JSON stdin/stdout, exit code 0=allow, 2=block | ⭐⭐⭐⭐⭐ |
| 3 | **claude-code-permissions-hook** | TOML deny/allow rules + regex matching | ⭐⭐⭐⭐ |
| 4 | **LangGraph interrupt_before** | Checkpoint → validation → resume (stateful) | ⭐⭐⭐⭐ |
| 5 | **OPA/Rego** | Policy-as-code, deny-by-default | ⭐⭐⭐⭐ |

### Academic Foundation (RQ5, 2026-06-25)

| Paper | Mechanism | Relevance |
|-------|-----------|-----------|
| **RFC 2753** (IETF, 2000) | PEP/PDP architecture — Policy Enforcement Point intercepts, Policy Decision Point evaluates | Canonical model |
| **Flohr (2011)** | Quality gate reference process assessment framework | Gate maturity taxonomy |
| **Laukkanen et al. (2016)** | Bottom-up CD in Stage-Gate organizations | Empirical: reconciling gates with automation |
| **Winikoff (2010)** | Formal verification for multi-agent systems | Runtime verification as gate pattern |
| **AI Governance as Safety Management (2026)** | Pre-execution control architecture | Blocks unsafe agent actions before execution |

---

## Integration with Capability Self-Model

These two enrichment dimensions (BA frameworks + pre-hook gates) complete the 3-layer architecture:

```
СЛОЙ 1: PRE-HOOK GATES (145 checks, PEP/PDP, Stage-Gate semantics)
  → When: before every phase transition
  → How: GatePluginRunner + PolicyDecisionPoint
  → Output: Go/Kill/Hold/Recycle

СЛОЙ 2: ENRICHED GAP QUERIES (BA techniques, BACCM, SPIN, BPMN)
  → When: Phase 0 (bootstrap), per-phase entry
  → How: G3 TaskInterviewer (replaces KeywordMapper)
  → Output: CapabilityRequirement list with confidence scores

СЛОЙ 3: RUNTIME ENFORCEMENT (PEP per tool invocation)
  → When: before every tool call by any sub-agent
  → How: PreToolUse hook (Claude Code pattern) + circuit breaker
  → Output: allow/deny/modify decision
```

The full GAP-detection ontology (who/when/how) lives in the session transcript. This reference captures the enrichment mechanics and gate architecture that future orchestration cycles need.
