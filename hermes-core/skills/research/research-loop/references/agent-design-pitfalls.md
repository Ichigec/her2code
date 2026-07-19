# Agent Design Pitfalls — Deep Plan Research v2–v3

Lessons learned from building the Deep Plan Research system (June 2026).

## 1. Merge near-identical agents, don't duplicate

**Symptom:** `standalone-deep-researcher.md` was created with >80% overlap with `deep-plan-researcher.md`.

**Fix:** Deleted standalone. Added Mode B (standalone) and Mode B' (developer query) to the main agent via context flags. Mode switches are cheaper than maintaining two near-identical agent files.

**Rule:** Before creating a new agent, ask: could the existing agent handle this with a context flag?

## 2. Preserve legacy agents when adding new ones

**Symptom:** Proposed replacing `plan.md` with `plan2.md` content. User corrected: keep both.

**Fix:** `plan.md` untouched (legacy, basic research). `plan2.md` enhanced (Deep Plan Research). Two independent pipelines: `/agent plan` and `/agent plan2`.

**Rule:** Add, don't replace. Legacy systems have users who depend on them. New features go in new agents/files.

## 3. Deprecate old agents explicitly

**Symptom:** `researcher.md` (Vane 9-stage pipeline) was still in the registry alongside the new `deep-plan-researcher.md`, creating confusion about which to use.

**Fix:** Renamed to `researcher_old.md` — clear signal it's deprecated. Registry auto-picks it up as `researcher_old`.

**Rule:** Rename deprecated agents with `_old` suffix. Don't delete — someone might need the reference implementation.

## 4. Explain new concepts before building them

**Symptom:** User asked "что за третий?" about `deep-explore` (OpenCode+ agent) vs the two new Hermes agents. Confusion about which agents are ours vs external.

**Rule:** When introducing new agents, list ALL existing agents in the namespace and clarify ownership (ours vs external).

## 5. Test gate scripts before integration

**Symptom:** Two bugs found in GATE C during integration testing:
- RQ Coverage matched "RQ" in table headers (false positive)
- Citation Mapping counted paragraphs outside `## RQ Answers` section

**Fix:** Added state-machine table parsing + section boundary detection (`### Source Quality Matrix` as end marker).

**Rule:** Run each gate script independently against a test artifact BEFORE wiring it into the orchestrator gate. Integration testing catches parser bugs.

## 6. Don't blindly adapt external architectures

**Symptom:** "Cost Gate" from Anthropic article was added to the plan but the user didn't understand what it was when reading the spec. The concept needed explanation with concrete examples.

**Rule:** External research findings need translation into concrete examples users can relate to. "15× more tokens than chat" → concrete: "3,000 tokens vs 45,000 tokens". "64% of tasks" → concrete: "simple fact-checks don't need 7 sub-agents".

## 7. Factor out citation enforcement

**Symptom:** Initially had citations as part of Synthesizer. User requested: "на каждый факт ссылку на источник. Если подряд идут несколько фактов из одного источника то обобщить и в конце набора фактов поставить один источник."

**Fix:** Created separate CitationAgent (matching Anthropic's pattern of a separate citation pass). Added GATE D for enforcement.

**Rule:** Citation verification is a distinct concern. It needs its own agent with its own gate — not buried inside synthesis.

## 8. Search across languages

**Symptom:** Research on one language misses sources in other languages. Russian sources (habr, khabr) invisible to English queries and vice versa.

**Fix:** Multi-language paraphrasing in Phase 3.0: 4-6 search queries per RQ (EN direct, EN technical, EN precise, RU direct, RU technical). Dedup by normalized URL in Synthesizer.

**Rule:** Always generate queries in the user's language AND English. Russian queries target habr/khabr/forums; English queries target arxiv/github/HN.
