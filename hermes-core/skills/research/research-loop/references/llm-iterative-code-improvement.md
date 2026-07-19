# LLM Iterative Code Improvement: Research Knowledge Bank

> Condensed from 8 papers (2023–2026). Bootstrap context for research on whether LLMs can iteratively clean/improve code, especially weaker models.

## Core Papers

| # | Paper | Venue | Date | Key Claim |
|---|-------|-------|------|-----------|
| 1 | Self-Refine (Madaan et al.) | NeurIPS 2023 | Mar 2023 | Same-model feedback+refine: +5–40% across tasks |
| 2 | Self-Repair is NOT a Silver Bullet (Olausson et al.) | ICLR 2024 | Jun 2023 | GPT-3.5 self-repair marginal; weaker models HARMED |
| 3 | Progress or Regress? (Wu et al.) | ICLR 2025 | Jul 2024 | pass@1↑ but diversity↓, OOD↓ — self-improvement reversal |
| 4 | Debugging Decay Index (Adnan & Kuhn) | Nature SciRep | Jun 2025 | Exponential decay: 60–80% capability lost in 2–3 attempts |
| 5 | LLMLOOP (Ravi et al.) | ICSME 2025 | Mar 2026 | 5 external-tool feedback loops: pass@10 76→90% |
| 6 | Iterative Self-Repair Across Scales (Arimbur) | arXiv | Apr 2026 | Modern models (2024+): self-repair UNIVERSALLY works, even 8B |
| 7 | Self-Improvement Can Self-Regress (Lin, Meta) | arXiv | Jun 2026 | RL code training: rise-then-collapse (81%→0%) |
| 8 | When AI Reviews Its Own Code (Song et al.) | arXiv | Jun 2026 | AI-self-gate → rubber-stamping → collapse; need EXOGENOUS verification |

## Decision Matrix: When Iterative Improvement Works

### ✅ WORKS

| Condition | Why | Evidence |
|-----------|-----|----------|
| **External tool feedback** (compiler, linter, tests) | Doesn't depend on model's self-diagnosis ability | LLMLOOP: +14pp pass@10; Static Analysis Loop: security issues 40%→near-zero |
| **First 2–3 iterations only** | Exponential decay after (DDI framework) | DDI: GPT-4 loses all effectiveness by iter 3; GPT-3.5 by iter 4 |
| **Modern models (2024+)** with instruction tuning | Better error comprehension from tracebacks | Arimbur 2026: Llama 3.1 8B +9.8pp, Gemini Pro +17.1pp |
| **CoT/explain-then-fix prompting** | +5.5pp additional repair gain over minimal prompt | Arimbur 2026 prompt ablation (70B model) |
| **Diverse initial samples** (np ≥ 5) | More starting points → repair finds better solutions | Olausson et al.: GPT-3.5 only gains at np ≥ 10 |
| **Strong model fixes weak model's code** | Removes self-diagnosis bottleneck | Olausson et al.: GPT-4 feedback on Code Llama → significant boost |
| **Human-provided feedback** | Best possible feedback quality | Olausson et al.: +57% repair success for GPT-4 with human feedback |

### ❌ DOESN'T WORK

| Condition | Why | Evidence |
|-----------|-----|----------|
| **Model evaluates own code** (no external tools) | Can't diagnose logical errors; rubber-stamping | Song et al.: AI-self-gate→collapse; Olausson: assertion errors ~45% repair vs name errors ~77% |
| **Weak models pre-2024** (<7B, no instruction tuning) | Can't understand what went wrong → break code more | Olausson: Code Llama 13B negative gains; GPT-3.5 marginal on APPS |
| **>3–5 iterations** | Exponential decay + cost > benefit | DDI: E(t) = E₀e^(-λt); most λ values make iter 5+ worthless |
| **Logical errors** (AssertionError) | Require reasoning correction, not pattern matching | Arimbur 2026: 45% repair rate vs 77% for NameError |
| **RL self-training without external reward** | Rise-then-collapse: policy over-optimization | Lin: Qwen 2.5 3B/7B pass@1 25%→81%→0% in 200 steps |
| **Iterative fine-tuning on own outputs** | Diversity collapse, OOD degradation | Wu et al. ICLR 2025: pass@1↑ while solution diversity and OOD gen↓ |
| **AI-self-gate review** (perplexity, self-scoring) | Acceptance criterion drifts with model | Song et al.: binary self-gate→"rubber stamp regime" |

## Key Mechanisms

### 1. Self-Diagnosis Bottleneck (Olausson et al., ICLR 2024)
The fundamental limit of self-repair: a model's ability to FIX code is bounded by its ability to UNDERSTAND what's wrong. Weak models fail at diagnosis → repair is counterproductive. This is why external feedback (tools, stronger models, humans) unlocks repair for weak generators.

### 2. Debugging Decay (Adnan & Kuhn, 2025)
E(t) = E₀ · e^(-λt)

| Model | E₀ (initial) | λ (decay rate) | Half-life |
|-------|:---:|:---:|:---:|
| Claude 3.7 Sonnet | 93.9% | — | Too strong to measure |
| CodeGemma 7B | 51.2% | 0.93 | <1 attempt |
| CodeLlama 7B | 21.3% | 0.25 | ~2.8 attempts |
| GPT-4 | — | — | Exhausted by iter 3 |
| GPT-3.5 | — | — | Exhausted by iter 4 |
| Qwen2.5-Coder | — | — | Holds to iter 5 |

**Key insight:** models with LOW λ (slow decay) + HIGH E₀ are ideal. Low E₀ + low λ = "consistently mediocre." High E₀ + high λ = "brilliant but fragile."

### 3. Rise-Then-Collapse (Lin, Meta, 2026)
Under RL with verifiable reward on code tasks:
- Policy entropy collapses → exploration dies
- Model overfits to reward-correlated patterns
- Pass@1 peaks at ~50 steps, then crashes to near-zero by step 200
- KL regularization and EWC do NOT prevent it
- GRPO raises floor but doesn't close the cliff
- Only early stopping (peak_step + 3) reliably preserves gains

### 4. Gated Self-Training Degeneration (Song et al., 2026)
Formal model of recursive training with review gates:
- Ungated: trains on all generated code → fastest collapse
- Human-gate (compile checks, static analysis): slows but doesn't stop collapse
- AI-self-gate (perplexity, self-scoring): initially effective, then degenerates to p_θ(c|x) ∝ p_θ(c|x)·r(x,c) where r→constant → equivalent to ungated

**Mathematical condition for gate failure:** when r(x,c) becomes constant on the generator's support, gated training ≡ ungated training.

## Practical Deployment Recipe

For a WEAK model improving code:

```
1. Generate 5–10 diverse initial solutions (temp=0.8)
2. Filter: keep solutions that compile + pass basic tests
3. Pick best candidate (most tests passed)
4. Run external analyzers: mypy/ruff/bandit/semgrep
5. Feed analyzer output + traceback → model fixes (max 3 rounds)
6. After each round: verify compilation + tests
7. If round 3 fails → discard, start fresh (fresh-start DDI strategy)
8. Optional: strong model reviews weak model's fix attempt
```

**Never:** let the model judge its own code quality. Always use external verifiers.

## Error-Type Repair Rates (Arimbur 2026)

| Error Type | Repair Success | Implication |
|-----------|:---:|-----|
| NameError | ~77% | Missing imports/refs — easy fix |
| SyntaxError | High | Formatting — easy fix |
| TypeError/ValueError | Medium | Type mismatches — moderate |
| IndexError/KeyError | Medium | Edge cases — moderate |
| **AssertionError** | **~45%** | **Logical errors — HARD** |
| Timeout | Low | Infinite loops — usually needs rewrite |

## Model Scale vs Self-Repair Gain (Arimbur 2026)

| Model | Scale | Arch | HumanEval Δ |
|-------|-------|------|:---:|
| Llama 3.1 8B | 8B | Dense | +9.8pp |
| Scout 17B | 17B active | MoE (16E) | +14.0pp |
| Llama 3.3 70B | 70B | Dense | +10.4pp |
| Maverick 17B | 17B active | MoE (128E) | +6.7pp |
| Qwen3 32B | 32B | Dense | +4.9pp |
| Gemini 2.5 Flash | — | Proprietary | +9.8pp |
| Gemini 2.5 Pro | — | Proprietary | +17.1pp |

**Note:** More parameters ≠ more repair gain. MoE with 16 experts (Scout) outperforms 70B dense. High base pass@1 (Qwen3 87.8%) leaves less room for repair gain. The repair Δ ceiling is bounded by the gap to 100%.

## Open Questions / Gaps

- No study on models <3B doing iterative code improvement (Qwen 2.5 3B was RL training, not inference-time repair)
- Interaction between quantization and self-repair capability unexplored
- No Russian-language models tested in any study
- Cost-token analysis for modern models missing (Olausson did this for 2023 models)
- Multi-file/project-level self-repair not studied (all papers use single-function benchmarks)
