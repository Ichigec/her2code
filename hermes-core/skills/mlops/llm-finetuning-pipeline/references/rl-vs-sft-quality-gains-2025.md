# RL vs SFT: Quality Gains, Mechanisms, and Limits (2025-2026)

Condensed knowledge bank from a July 2026 deep research session investigating the hypothesis "RL gives a greater quality improvement than SFT." Verdict: **confirmed with caveats** — RL gives bigger pass@1 gains, but the mechanism is sampling efficiency, not new capability creation.

## Key Papers (all 2025+)

### 1. DeepSeek-R1-Zero: Pure RL Breakthrough (Jan 2025, Nature)

arXiv:2501.12948. GRPO RL directly on DeepSeek-V3-Base, NO SFT.

| Metric | V3-Base | R1-Zero (pure RL) | Gain |
|---|---|---|---|
| AIME 2024 (pass@1) | 15.6% | 71.0% | +55.4 pp |
| MATH-500 (pass@1) | — | 95.9% | — |
| GPQA Diamond (pass@1) | — | 73.3% | — |

Full R1 (cold-start SFT + multi-stage RL): AIME 79.8%, MATH-500 97.3% — matches OpenAI o1.
Emergent behaviors from RL alone: self-verification, reflection, extended CoT.

### 2. SFT Memorizes, RL Generalizes (ICML 2025)

arXiv:2501.17161. Chu et al. Systematic comparison on GeneralPoints (card game) + V-IRL (navigation).
- RL consistently improves OOD performance on ALL tasks (text + multimodal)
- SFT memorizes training data, struggles with unseen variants
- RL improves underlying visual recognition capabilities; SFT does not

### 3. Limit of RLVR (NeurIPS 2025) — CRITICAL CAVEAT

arXiv:2504.13837. Yang et al. The most important counterpoint.

**Finding:** RLVR does NOT elicit fundamentally new reasoning patterns. RL improves sampling efficiency — makes correct answers more probable at pass@1 — but does NOT expand the set of solutions the model can produce.

**pass@k analysis:**
- At k=1: RL model >> base model (RL wins)
- At large k: base model catches up or surpasses RL model (base has wider solution coverage)
- RL narrows the solution space (good for pass@1, bad for diversity)

**Distillation vs RLVR:** Distillation (SFT on teacher outputs) CAN introduce genuinely new reasoning patterns. RLVR cannot. This means:
- New capabilities → distillation (SFT on strong model traces)
- Better sampling of existing capabilities → RL
- Best practice: distillation to expand, then RL to focus

### 4. RL Is Neither a Panacea Nor a Mirage (Aug 2025)

arXiv:2508.16546. Jin et al. Spectral analysis of weight matrices.

**Finding:** RL-FT primarily counteracts SFT-induced directional drift rather than finding new solutions.
- Llama-1B: SFT dropped OOD to 8.97% → RL recovered to 15.38%
- Qwen-7B: SFT dropped OOD to 17.09% → RL recovered to 19.66%
- If SFT causes severe overfitting, RL cannot fully recover

**Practical implication:** Don't overtrain SFT. Short SFT → RL is better than long SFT → RL. Cheaper alternatives (low-rank UV merging, shallow-layer resets) can partially substitute for RL.

### 5. RL Squeezes, SFT Expands (ICLR 2026)

arXiv:2509.21128. Matsutani et al. Reasoning graph topology analysis.

- **RL compresses** incorrect trajectories (narrows distribution → fewer errors)
- **SFT expands** correct trajectories (widens → more correct paths available)
- They are **complementary**: SFT expands the set of correct paths, RL focuses the model on them
- This explains why SFT → RL (best practice) works: expand then focus

### 6. Why Does RL Generalize Better? (CVPR 2026)

arXiv:2603.13985. Data-centric perspective.

**Mechanism:** SFT applies uniform gradient updates across all training data. RL implicitly prioritizes samples by difficulty — harder examples get larger gradient signals. This difficulty-aware weighting explains RL's superior OOD generalization.

### 7. Quagmires in SFT-RL Post-Training (NeurIPS 2025/2026)

arXiv:2510.01624. Meta AI.

**Finding:** High SFT benchmark scores do NOT predict subsequent RL success. In some cases, RL on models with better SFT performance produced WORSE outcomes than RL on the base model without SFT.
- SFT on "easy" examples gives high scores but damages the model's RL-readiness
- SFT on shortest examples → faster SFT convergence but worse RL final performance
- Recommendation: use pass@k (not pass@1) and OOD metrics to evaluate SFT readiness for RL

### 8. BRIDGE: Cooperative SFT and RL (ICLR 2026, Microsoft)

arXiv:2509.06948. Bilevel optimization: SFT + RL simultaneously.

**Finding:** "SFT promotes rapid initial learning, while RL achieves better final performance."
Joint SFT+RL training surpasses either alone. The cooperative gain (advantage over RL-only) is explicitly maximized.

### 9. Kimi K1.5: Scaling RL (Jan 2025)

arXiv:2501.12599. RL with 128K context window.
- Continued performance improvement with increased context length
- Long2short transfer: RL on long CoT → compress to short without quality loss
- SFT cannot achieve this kind of transfer

## Synthesis: When RL Gives Bigger Gains

| Factor | RL wins | SFT wins / comparable |
|---|---|---|
| Task type | Math, code, logic (verifiable rewards) | Open dialogue, creativity |
| Base model strength | Strong base with latent reasoning | Weak base without needed patterns |
| Metric | pass@1 (single attempt) | pass@k (many samples) |
| Generalization | OOD generalization | In-distribution performance |
| New capabilities | Does NOT create new patterns | Distillation CAN add new patterns |
| Forgetting | RL preserves better (mode-seeking) | SFT overwrites (memorizes) |
| Speed | Slower, unstable | Fast, stable |

## Mechanism Summary

```
Base Model (latent reasoning capacity)
    │
    ├── SFT ──→ EXPANDS correct trajectories + introduces new patterns (if distillation)
    │            BUT: memorizes data, damages OOD, uniform updates
    │
    ├── RL  ──→ SQUEEZES incorrect trajectories + prioritizes hard examples
    │            BUT: does NOT create new patterns, narrows solution space
    │
    └── SFT → RL (best practice): expand then focus
         Distillation → RL: add new patterns then focus on them
```

Three mechanisms of RL's advantage:
1. **Difficulty-aware weighting** — RL gives larger gradients on hard examples (CVPR 2026)
2. **Sampling efficiency** — RL raises P(correct) at pass@1 without expanding solution set (NeurIPS 2025)
3. **OOD recovery** — RL restores generalization lost to SFT (Aug 2025)

## Implications for DGX Spark Pipeline

1. **Phase 1 (distillation/SFT)** is where NEW capabilities enter the model. Choose teacher wisely.
2. **Phase 2 (RL/GRPO)** focuses the model on correct paths but cannot add what wasn't distilled.
3. **Don't overtrain SFT** — excessive SFT makes RL less effective (Quagmires paper).
4. **pass@k evaluation** during SFT phase predicts RL-readiness better than pass@1.
5. **If base model already has the capability** (e.g., math reasoning in Qwen3), pure RL (R1-Zero style) can unlock it without any SFT.
6. **If base model lacks the capability**, no amount of RL will create it — need distillation first.
