# Teaching LLMs to Write Complex Code: RL & Trajectory Training (2025-2026)

**Date:** 2026-07-12
**Context:** Research pass restricted to papers from January 2025+. Covers RL for code generation, SWE-bench training, agentic code training, and code reasoning models.

---

## RL for Code Generation (2025-2026)

### DeepSeek-R1 — GRPO with Rule-Based Rewards (arXiv:2501.12948, Jan 2025, Nature)
Foundation of R1-style RL. GRPO: sample G=8 answers, advantage = normalized reward in group. No value network. Reward = test pass/fail (rule-based, no learned reward model). R1-Zero: pure RL without SFT. R1: multi-stage (cold-start SFT → RL → SFT on RL outputs → RL).

### P-GRPO — Posterior-GRPO (arXiv:2508.05170, Aug 2025)
Process-based rewards **only on successful rollouts** (posterior conditioning). Avoids reward hacking. 7B model outperforms outcome-only RL. Introduces CRPL (Contrastive Reasoning-Process Reward Learning) and CG-GRPO (Consistency-Gated GRPO).

### MURPHY — Multi-Turn GRPO (arXiv:2511.07833, Nov 2025)
Extends GRPO to multi-turn agentic settings. Feedback-aware GRPO with retrospective credit assignment. Model learns to debug code iteratively: generate → run → read errors → fix → repeat. Significant improvement on self-correcting code generation.

### CodeRL+ — Execution Semantics Alignment (arXiv:2510.18471, ACL 2026)
Integrates variable-level execution trajectories into RLVR. Dense reward from execution traces, not just pass/fail. Drop-in for GRPO, PPO, REINFORCE++. Tested on Qwen2.5-Coder-7B/1.5B and LLaMA-3.1-8B.

### VeRPO — Dense Graded Rewards (arXiv:2601.03525, Jan 2026)
Converts partial test passes, execution traces, error patterns into graded dense rewards instead of binary pass/fail.

### DRIVE — Data Curation for RLVR (arXiv:2511.06307, Nov 2025)
Best practices for RLVR in competitive programming: difficulty curriculum (easy→hard), entropy expansion (prevent mode collapse), prompt quality filtering. **Data curation impacts more than algorithm changes.**

### RLVR Implicitly Incentivizes Reasoning (arXiv:2506.14245, ICLR 2026)
Proves RLVR gives genuine reasoning improvement, not just sampling efficiency. RL with verifiable rewards truly improves reasoning ability.

---

## SWE-bench Training (2025-2026 SOTA)

| Method | arXiv | Date | SWE-bench Verified | Technique |
|--------|-------|------|:------------------:|-----------|
| SWE-RL (Meta) | 2502.18449 | Feb 2025 | improvement | GRPO on GitHub PRs, sequence-level reward |
| SWE-smith (Princeton) | 2504.21798 | Apr 2025 | SOTA (open) | 50K instances from 128 repos |
| Self-Play SWE-RL (Meta) | 2512.18552 | Dec 2025 | scalable | Bug injector + bug fixer, NO human data |
| Kimi K2 | 2507.20534 | Jul 2025 | 65.8% | 1T MoE, agentic RL with tool use |
| GLM-5 | 2602.15763 | Feb 2026 | competitive | Real-environment agentic training |

### SWE-RL (arXiv:2502.18449, NeurIPS 2025)
Meta. GRPO on GitHub PR data. Sequence-level reward from pass-to-pass and fail-to-pass tests. **Transfer effect: SWE RL also improves math/logic reasoning.**

### SWE-smith (arXiv:2504.21798, NeurIPS 2025 D&B)
Princeton. Pipeline for generating SWE training data at scale: 50K+ task instances from 128 GitHub repos. Auto-constructs execution environments, synthesizes task instances. Open-source toolkit. SWE-agent-LM-32B = SOTA for open-source agent LMs.

### Self-Play SWE-RL (arXiv:2512.18552, Dec 2025)
Meta. One agent injects bugs into repo, another finds and fixes them. Co-evolution. **No human data needed** — only sandboxed repos with source code and dependencies.

---

## Agentic Code Training Frameworks (2025-2026)

### Polar (arXiv:2605.24220, NVIDIA, May 2026)
Rollout framework for scalable RL over **any agent harness** (Codex, Claude Code, Qwen Code). Proxies LLM API calls, reconstructs token-faithful trajectories. +20 points on unfamiliar harnesses. No need to rewrite harness for RL.

### ProRL Agent (arXiv:2603.18815, NVIDIA, Mar 2026)
**Rollout-as-a-Service:** decouples I/O-intensive rollout generation from GPU-intensive training. Standalone HTTP service managing full rollout lifecycle. Critical for multi-turn agentic RL on limited hardware (DGX Spark).

### Practitioner's Guide to Multi-Turn Agentic RL (arXiv:2510.01132, Oct 2025)
Three pillars: environment design, reward shaping, policy optimization. Co-design all three. Open training scripts + model weights.

### GLM-5 (arXiv:2602.15763, Feb 2026)
Zhipu AI. Paradigm shift from "vibe coding" to "agentic engineering." Trains in real development environments (not synthetic). Agentic RL with asynchronous training frameworks. Hybrid reward systems (verifiable + learned).

---

## Code Reasoning Models & Datasets

### OpenCodeReasoning (arXiv:2504.01943, NVIDIA, Apr 2025)
**Largest reasoning dataset for code:** 735K samples, 28K competitive programming questions. DeepSeek-R1-generated reasoning traces. Trains Nemotron-7B/32B on Qwen2.5. **Publicly available on HuggingFace.**

### OpenCodeReasoning-II (arXiv:2507.09075, Jul 2025)
2.5M question-solution-**critique** triples. Self-critique test-time scaling: generate → critique → regenerate. Significant improvement without additional training.

### STeCa — Step-Level Trajectory Calibration (arXiv:2502.14276, ACL 2025)
Identifies suboptimal steps via step-level reward comparison → replaces bad steps via LLM reflection. Combines calibrated + successful trajectories. For long-horizon coding sessions.

---

## Practical Pipeline for Qwen3-4B on DGX Spark

```
1. SFT on quality code + CoT (10K examples, data pruning critical)
   → ~20h

2. RFT (Rejection Sampling FT): generate N → test → keep passing → SFT
   → ~10h per iteration, 2-3 iterations
   → SWE-Gym/SWE-smith data, OpenCodeReasoning dataset

3. GRPO with execution rewards (Unsloth/TRL GRPOTrainer)
   + CodeRL+ execution semantics (dense reward)
   + P-GRPO anti-hacking (process rewards on successful rollouts only)
   + DRIVE curriculum (easy→hard, entropy expansion)
   → ~15h

4. Multi-turn agentic RL (MURPHY)
   generate → run → read errors → fix → repeat
   SWE-smith data or Self-Play SWE-RL (bug injector+fixer)
   Framework: Polar (any harness) or ProRL Agent (rollout-as-a-service)
   → ~20h

5. Deploy + self-critique at inference (OpenCodeReasoning-II)
   generate → critique → regenerate = free improvement
```

### Key Datasets (all on HuggingFace)
- **OpenCodeReasoning**: 735K code reasoning samples (NVIDIA, R1-generated)
- **OpenCodeReasoning-II**: 2.5M solution-critique triples
- **SWE-smith**: 50K SWE training instances from 128 repos
- **nebius/SWE-agent-trajectories**: 67K OpenHands trajectories from Qwen3-Coder-480B
