# Model Routing Cost Analysis (v2.4)

Based on real token data from session `20260614_223506_e30edf` (177 messages, 10 phases, 20 sub-agents).

## Token Distribution

| Component | Input | Output | Total |
|-----------|-------|--------|-------|
| Orchestrator (main session) | 147 865 | 47 785 | **195 650** |
| 20 sub-agents | 1 164 765 | 361 446 | **1 526 211** |
| **Grand total** | 1 312 630 | 409 231 | **1 721 861** |

Average sub-agent: ~76K tokens (range 29K–154K).

## Model Pricing (June 2026)

| Model | Input $/1M | Output $/1M | Cache read $/1M |
|-------|-----------|-------------|-----------------|
| GPT-5.5 | $2.50 | $10.00 | — |
| Kimi K2.7 | ~$0.60 | ~$2.40 | — |
| DeepSeek V4 Pro | $0.89 | $2.20 | $0.14 |

## Routing Table (v2.4)

| Model | Roles | Est. tokens |
|-------|-------|-------------|
| GPT-5.5 | Orchestrator, Req, SysAn, Architect, Auditor, Critic, IdeaGen | ~560K |
| Kimi K2.7 | Tech Lead, Dev×4, Tester | ~490K |
| DeepSeek V4 Pro | Researcher, Dev×3, Security, Deploy | ~490K |

## Per-Cycle Cost

| Model | Input cost | Output cost | Cache savings | **Net** |
|-------|-----------|-------------|---------------|---------|
| GPT-5.5 | 420K × $2.50 = $1.05 | 140K × $10 = $1.40 | — | **$2.45** |
| Kimi K2.7 | 368K × $0.60 = $0.22 | 122K × $2.40 = $0.29 | — | **$0.52** |
| DeepSeek | 368K × $0.89 = $0.33 | 122K × $2.20 = $0.27 | −10M ×$0.14 = −$1.40 | **−$0.80** |
| **TOTAL** | | | | **~$2.17** |

## Budget Projections

| Budget | Full cycles | Margin |
|--------|------------|--------|
| $10 | 4 | narrow |
| $25 | 11 | comfortable |
| **$50** | **23** | **generous** |
| $100 | 46 | abundant |

DeepSeek's prompt caching (10M cache read tokens in e30edf) more than offsets its own cost — it's essentially free for the orchestrator pattern.
