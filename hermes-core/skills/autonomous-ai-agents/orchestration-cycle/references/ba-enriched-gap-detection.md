# BA-Enriched Gap Detection — Business Analysis Frameworks for Agent Capability Discovery

> Reference for `orchestration-cycle` skill.
> Research: RQ1 (BA frameworks mapping), RQ4 (enriching gap queries), session `20260624_231458_498092`.

## Why BA Frameworks?

Keyword matching ("screenshot"→vision) has ~60% accuracy and misses context. BA frameworks decompose tasks into structured, multi-dimensional models that surface hidden dependencies, edge cases, and integration points — raising accuracy to 85-90%.

## Framework Mappings

| Framework | Gap Detection Role | Enrichment | Example |
|-----------|-------------------|:----------:|---------|
| **BACCM** | 6-D capability vector: Change/Need/Solution/Stakeholder/Value/Context | 3× | "Stakeholder=user" → vision needed for visual check |
| **SPIN** | Quantified impact: Situation→Problem→Implication→Need-payoff | 4× | "No vision → can't verify screenshots → risk of shipping broken UI" |
| **CATWOE** | Holistic system view: catches assumption gaps | 4× | "Weltanschauung: developer assumes Docker available → it's not" |
| **5 Whys** | Root cause: symptom → tool_gap|arch_gap|LLM_limit | 3× | "Why can't verify? → No vision. Why? → No GPU. Why? → ARM64." |
| **MoSCoW** | Priority triage: Must/Should/Could/Won't | 3× | Must: vision, Should: browser_gui, Could: cuda |
| **Laddering** | "Why do you need X?" → root capability domain | 5× | "Need screenshot? → to verify UI → need vision" |
| **User Story Mapping** | Epic → 15+ stories → each = capability check | 7× | "App with picture" → 15 discrete capability requirements |
| **BPMN** | Swimlane → activity-level tool extraction | 10× | Catches integration points keyword matching misses |

## Enriched vs Keyword: Before/After

### Keyword only (L1, ~60%)
```
"screenshot" → vision ❌
"phone" → adb ✅
Missed: browser_gui (UI verification), web_fetch (image loading)
```

### BACCM-enriched (L2, ~85%)
```
Change: new app with image → code_write ✅
Need: display image, load from URL → web_fetch ❌
Solution: UI + fetch + display → browser_gui ❌
Stakeholder: user verifies visually → vision ❌
Context: phone, USB, Android → adb ✅
→ 2 extra GAPs found that keyword missed
```

## Integration in plan2

G3 TaskInterviewer runs both levels:
1. L1: keyword matching (fast, cheap)
2. L2: BACCM structural inference (slower, richer)

Combined output fed to G4 CompositionEngine for derived gaps.
