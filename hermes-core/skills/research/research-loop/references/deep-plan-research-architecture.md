# Deep Plan Research — Architecture Reference

> Конденсированный референс архитектуры Deep Plan Research для plan2.
> Загружается когда задача касается "deep research", "research plan", "research gates", "developer query research".

## Pipeline: 4 sub-phases + 4 gates

```
3.0 RESEARCH PLAN → GATE A (user approval)
3.1 PARALLEL EXEC → GATE B (source quality, 5 LLM-judge criteria)
3.2 SYNTHESIS     → GATE C (completeness, 5 structural checks)
3.3 CITATIONS      → GATE D (citation enforcement, ≥90% valid)
```

Plus **Cost Gate** before 3.1: ≤2 simple RQs → SINGLE agent; 2-4 RQs → BALANCED (3-5); ≥5 → QUALITY (5-7 + debate).

## Agent file

`~/.hermes/agents/deep-plan-researcher.md` — single agent with two modes:
- **Mode A (plan2):** receives System Analysis context, runs pipeline, returns artifact for Phase 4
- **Mode B (standalone):** receives raw question, formulates RQs itself, GATE A via `clarify`

## Sub-agents spawned in 3.1

| Agent | File | When | Model |
|-------|------|------|-------|
| Academic Researcher | `research/academic-researcher.md` | Always | deepseek-v4-pro |
| Code Researcher | `research/code-researcher.md` | Always | kimi-k2.7-code |
| Community Researcher | `research/community-researcher.md` | Always | deepseek-v4-pro |
| Vendor Docs Researcher | `research/vendor-docs-researcher.md` | Always | deepseek-v4-pro |
| Claw Analyzer | `research/claw-analyzer.md` | Always (if Neo4j available) | kimi-k2.7-code |
| Codebase Analyzer | `research/codebase-analyzer.md` | Task touches Hermes code | deepseek-v4-pro |
| Education Graph Analyzer | `research/education-graph-analyzer.md` | Topic exists in Edu Graph | deepseek-v4-pro |
| Debate Agent | `research/debate-agent.md` | HIGH-priority RQs (paired) | kimi-k2.7-code |
| CitationAgent | `research/citation-agent.md` | Phase 3.3 | kimi-k2.7-code |

## Gate scripts

| Gate | Script | Threshold |
|------|--------|-----------|
| B — Source Quality | `research_quality_gate.py` | avg ≥0.6/1.0 (5 criteria) |
| C — Completeness | `research_completeness_gate.py` | 5/5 checks |
| D — Citations | `citation_enforcement_gate.py` | ≥90% cited, ≥90% valid |

All gates integrated into `orchestrator_gate.py` as 7th check `research_deep`.

## Developer Query Protocol

Phase 6 developers query Deep Research with structured context:

```markdown
## Developer Research Query
### Что уже исследовано [...] ### Что хочется найти [...]
### Что не хватает [...] ### Что мешает [...] ### Бюджет: 5 min, 3 agents
```

Response: mini-report (500-2000 words, citations, 3-5 min). GATE A skipped, GATE B+D mandatory.

## Claw Integration

Bidirectional: Claw writes `#research-needed` tags → Deep Research reads them as RQs.  
Deep Research writes `#research-finding` tags → Claw Orchestrator adds to claw graph.

## Design rules (from user corrections)

- **Add, don't replace.** Legacy agents (plan.md, researcher_old.md) stay. New agents are parallel tracks.
- **One agent, two modes > two nearly-identical agents.** Merged standalone-deep-researcher into deep-plan-researcher.
- **Don't stop mid-task for summaries.** Continuous progress until task complete or explicit stop.
