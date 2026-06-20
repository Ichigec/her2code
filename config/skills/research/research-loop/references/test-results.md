# Research Loop — Test Results

## Test 1: DRPO Latest Developments (June 11, 2026)

**Question:** What are the latest developments around DRPO (arXiv:2606.09821) beyond the original paper?

**Setup:** Main agent queried education graph (Neo4j) for bootstrap context → passed to subagent via delegate_task.

### Execution Metrics

| Metric | Value |
|--------|-------|
| Mode | STANDARD |
| Search rounds | 4 |
| Total queries | 20 |
| Engines used | searxng, arxiv, github, hackernews |
| Duration | 130 seconds |
| API calls | 7 (to searchbox MCP) |
| Input tokens | 295,714 |
| Output tokens | 7,790 |

### Pipeline Adherence

- ✅ CLASSIFY: correctly identified as STANDARD (3-day-old paper)
- ✅ PLAN: formulated 4 query rounds targeting different angles
- ✅ SEARCH: used searchbox fan-out (session+search curl commands worked)
- ✅ EVALUATE: identified gaps after each round
- ✅ LOOP: 4 rounds, stopped at sufficient coverage
- ✅ SYNTHESIZE: structured markdown report with findings, sources, gaps

### Key Findings (what education graph didn't have)

1. Paper's real title is "Rethinking the Divergence Regularization in LLM RL" — not "DRPO"
2. Acronym collision: another DRPO paper (arXiv:2510.04474, "Decoupled Reward Policy Optimization")
3. Companion paper: Flow-DPPO (arXiv:2606.11025, same lab, same release window)
4. Prior work by lead author: Future-KL GRPO (arXiv:2601.10201, Jan 2026)
5. Official announcement via @TencentHunyuan on X/Twitter
6. No third-party implementations exist (3 days old)
7. No community discussions anywhere (Reddit, HN, HuggingFace, Zhihu all empty)

### Engine Reliability

| Engine | Performance | Notes |
|--------|------------|-------|
| arxiv | ✅ Excellent | Clean paper results, reliable for academic queries |
| github | ✅ Good | Found the UniRL repo, useful for implementations |
| hackernews | ⚠️ Limited | No discussions found (paper too new) |
| searxng | ⚠️ Noisy | Returned unrelated European retail results for niche queries |

**Recommendation:** For academic topics, use `engines=["arxiv","searxng"]`. Arxiv provides the clean paper results; SearxNG provides web context but is noisy for niche academic terms.

### Education Graph Bootstrap Pattern

```python
# Main agent: query education graph in parallel
education_context = cypher("""
    MATCH (ke:KnowledgeEntity)
    WHERE ke.name IN ['DRPO', 'FlowDPPO', 'Divergence Regularization', ...]
    OPTIONAL MATCH (ke)-[r:RELATES_TO]->(target)
    OPTIONAL MATCH (f:Fact)-[:ABOUT]->(ke)
    RETURN ke.name, ke.type, ke.description, 
           collect(DISTINCT {pred: r.predicate, target: target.name}) AS rels,
           collect(DISTINCT {pred: f.predicate, obj: f.object}) AS facts
""")

# Main agent: compose context string
bootstrap = format_education_context(education_context)

# Main agent: dispatch subagent with context
delegate_task(
    goal="Research topic X",
    context=f"EDUCATION GRAPH BOOTSTRAP:\n{bootstrap}\n\nRESEARCH TOPIC: ...",
    toolsets=["terminal", "web"]
)
```

### Improvements Needed

1. **Searchbox MCP tool not available to subagents** — had to use raw curl commands. If subagents could inherit MCP tools, the research loop would be 2x faster.
2. **Engine-specific fallback** — when searxng returns noise, automatically retry with arxiv-only for academic queries.
3. **Citation extraction** — subagent should extract and deduplicate citations automatically.
