# Agent Design Pitfalls

## One Agent, Multiple Modes > Two Near-Identical Agents

**Pattern:** When two agents share >80% pipeline, merge them into one with mode flags.

**Example (2026-06-24):** `deep-plan-researcher.md` and `standalone-deep-researcher.md` were created as separate agents. They had identical pipelines (3.0→3.3, 4 gates). The only difference was context source: plan2 provides System Analysis, standalone takes a raw question. The fix: merged into one `deep-plan-researcher.md` with mode detection — if context contains System Analysis → plan2-mode, else → standalone-mode. Developer query is a third mode with mini-report output.

**Rule:** Before creating a new agent file, ask:
1. Could the existing agent handle this with a context flag?
2. Is the pipeline actually different, or just the input source?
3. Mode switches are cheaper to maintain than duplicate near-identical agent personas.