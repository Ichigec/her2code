# Anthropic Multi-Agent Research Blueprint

> Source: Anthropic Engineering Blog, "How we built our multi-agent research system" (Jun 13, 2025)
> Full article at: https://www.anthropic.com/engineering/multi-agent-research-system

## Key Numbers

| Metric | Value |
|--------|-------|
| Multi-agent vs single-agent improvement | **90.2%** (Opus 4 lead + Sonnet 4 subagents vs single Opus 4) |
| Token multiplier (multi-agent vs chat) | **15×** more tokens |
| Parallelization speed improvement | **90%** reduction in research time for complex queries |
| Performance variance explained by token usage | **80%** (remaining: tool calls + model choice) |
| Self-improving tool descriptions | **40%** decrease in task completion time |

## Architecture

```
User Query → LeadResearcher (Orchestrator)
  │
  ├─ Think + save plan to Memory (persists beyond 200K context window)
  ├─ Spawn Subagents (3-5 in parallel)
  │   ├─ Subagent 1: web_search → interleaved thinking → evaluate → repeat
  │   ├─ Subagent 2: web_search → interleaved thinking → evaluate → repeat
  │   └─ Subagent N: ...
  ├─ Synthesize results
  ├─ Decide: more research needed? → spawn more subagents
  └─ CitationAgent: separate pass to verify and attach citations
```

## 8 Critical Design Decisions

### 1. Prompt Engineering Principles

- **Think like your agents** — build simulations with exact prompts and tools, watch agents step-by-step
- **Teach orchestrator to delegate** — each subagent needs: objective, output format, tool/source guidance, clear task boundaries
- **Scale effort to query complexity** — simple=1 agent/3-10 calls, comparison=2-4 agents, complex=10+ agents
- **Start wide, then narrow** — mirror expert human research: short broad queries first, progressively narrow
- **Guide the thinking process** — extended thinking as controllable scratchpad
- **Parallel tool calling** — subagents should use 3+ tools in parallel

### 2. Tool Design

- Agent-tool interfaces are as critical as human-computer interfaces
- Bad tool descriptions send agents down wrong paths
- Each tool needs a distinct purpose and clear description
- **Self-improving agents:** Claude 4 models can debug their own prompts. Create a tool-testing agent that uses the tool dozens of times and rewrites descriptions.

### 3. CitationAgent — Separate Pass

Citation verification is NOT part of the synthesizer. It's a separate agent pass that:
- Processes documents and research report
- Identifies specific locations for citations
- Ensures all claims are properly attributed

### 4. Memory Module

Lead agent saves plan to external memory because context windows are limited (200K tokens). When context is truncated, the plan is retrieved from memory rather than lost.

### 5. LLM-as-Judge Evaluation

Single LLM call evaluating 5 criteria (better than multiple judges):
- factual_accuracy (claims match sources?)
- citation_accuracy (cited sources match claims?)
- completeness (all aspects covered?)
- source_quality (primary sources over SEO content?)
- tool_efficiency (right tools, reasonable number of calls?)

### 6. Production Reliability

- **Stateful agents, errors compound** — need durable execution, checkpointing
- **Rainbow deployments** — gradual traffic shift, don't break running agents
- **Full production tracing** — monitor agent decision patterns and interaction structures
- **Synchronous execution is bottleneck** — subagents block lead agent; async would enable more parallelism

### 7. Evaluation Strategy

- **Start small** — 20 test cases show dramatic impacts immediately (30%→80% success)
- **LLM-as-judge scales** — single rubric prompt, 0.0-1.0 + pass/fail
- **Human evaluation catches what automation misses** — edge cases, SEO content farm bias, hallucinated answers
- **End-state evaluation** — judge final state, not turn-by-turn process

### 8. Filesystem as Subagent Output

Subagents write to filesystem directly (bypassing lead agent):
- Prevents "game of telephone" information loss
- Reduces token overhead from copying large outputs through conversation history
- Particularly good for structured outputs (code, reports, visualizations)

## Prompt Heuristics (from Anthropic)

- Decompose difficult questions into smaller tasks
- Evaluate source quality carefully
- Adjust search approach based on new information
- Recognize depth vs breadth: investigate one topic deeply OR explore many in parallel
- Set explicit guardrails to prevent spiraling
- Fast iteration loop with observability and test cases

## Token Economics

- Agent interactions: 4× more tokens than chats
- Multi-agent systems: 15× more tokens than chats
- Claude Sonnet 4 upgrade > doubling token budget on Sonnet 3.7
- Multi-agent systems need tasks where value justifies cost
- Coding tasks involve fewer parallelizable tasks than research
