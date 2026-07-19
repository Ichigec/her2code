# Self-Play for Reasoning & Programming (2025-2026)

**Date:** 2026-07-13
**Context:** Deep-dive into SPIRAL self-play framework + how adversarial self-play applies to code generation/verification. All papers 2025+.

---

## Part 1: SPIRAL — Self-Play on Zero-Sum Games (arXiv:2506.24119, ICLR 2026)

**GitHub:** `spiral-rl/spiral` — run with `bash cmd/tinker/run_tinker_qwen3_4b.sh`
**Framework:** Oat (modular LLM RL) + UnstableBaselines (LoRA-first PEFT)

### Architecture

Fully online, multi-turn, multi-agent RL. One shared model plays both roles against a continuously improving copy of itself.

```
Player A (role 1) ◄── shared model ──► Player B (role 2)
     │                                      │
     │ "I bet 1"     dialogue          "I fold" │
     ▼                                      ▼
  GAME VERIFIER (deterministic rules)
  reward_A = +1 / -1 / 0   (zero-sum: reward_B = -reward_A)
     │
     ▼
  ROLE-CONDITIONED ADVANTAGE ESTIMATION (RAE)
  Separate baselines per role → advantage per role
     │
     ▼
  GRPO UPDATE (per-role, PPO clip + KL penalty)
  → updated model → next iteration (opponent = previous version)
```

### Key Innovation: Role-Conditioned Advantage Estimation (RAE)

**Problem:** In multi-agent RL, if one role is systematically advantageous (e.g., first mover in Tic-Tac-Toe wins 70%), the model attributes advantage to the ROLE, not to move quality. Gradients become noisy.

**RAE solution:** Maintain separate baselines per role:
```
advantage_role1 = reward - E[reward | role=1]    # separate baseline
advantage_role2 = -reward - E[reward | role=2]   # separate baseline
```

If Player A wins 70% → E[reward|A] ≈ 0.4. A specific win: advantage = 1 - 0.4 = +0.6 (good but not inflated).
If Player B wins 30% → E[reward|B] ≈ -0.4. A specific B win: advantage = 1 - (-0.4) = +1.4 (rare event valued higher).

RAE ensures the model learns to PLAY BETTER in each role, not just exploit advantageous roles.

### Three Games & Transfer Mechanism

| Game | Mechanics | Skill Learned | Why It Transfers |
|------|-----------|---------------|------------------|
| Tic-Tac-Toe | 3×3, perfect info | Strategic planning, minimax | Multi-step reasoning |
| **Kuhn Poker** | 3 cards, hidden info, betting | **Probabilistic reasoning, EV calculation, bluffing** | **Direct transfer to math word problems** |
| Simple Negotiation | Multi-turn, resource division | Multi-step planning, theory of mind | Instruction following, dialogue |

**Why Kuhn Poker is most effective (+8.6% on GSM8K):**
- Each turn requires probability estimation ("P(opponent has King) = 50%")
- Expected value calculation ("EV of fold = 0, EV of call = -1")
- Bluffing teaches strategic thinking
- Adaptive play (reading opponent) transfers to instruction following
- These skills are ISOMORPHIC to math word problem reasoning

### Detailed Results (Qwen3-4B base)

| Benchmark | Base | + SPIRAL (Kuhn Poker) | + SPIRAL (all 3 games) | SFT on 25K expert traj |
|-----------|:---:|:---:|:---:|:---:|
| GSM8K | 68.2% | **76.8% (+8.6)** | **80.3% (+12.1)** | 74.1% (+5.9) |
| MATH-500 | 42.1% | 48.3% (+6.2) | 52.7% (+10.6) | 45.2% (+3.1) |
| General Reasoning | 55.3% | 63.7% (+8.4) | 66.6% (+11.3) | 58.1% (+2.8) |

SPIRAL BEATS SFT on 25K expert trajectories — zero external data beats curated data. Self-play generates more useful learning signal than imitation learning.

Even works on already-strong models: +2.0% avg on DeepSeek-R1-Distill-Qwen-7B (AIME +2.6, MATH-500 +2.8).

### DGX Spark Resources
- Qwen3-4B: 9 GB BF16 → Full FT ~44 GB, LoRA ~14 GB
- GRPO rollout: ~100 parallel games
- Time: 3-5 days for meaningful improvement
- Cap at 2-3 self-play iterations (self-improvement reversal risk)

---

## Part 2: Self-Play for Programming — Adversarial Code-Test Co-Evolution

Programming is ideal for self-play because code has **verifiable rewards** (tests pass/fail). The "opponent" is not another player but task difficulty and bugs.

### 2.1. Code-A1: Adversarial Co-Evolution (arXiv:2603.15611, Mar 2026)

**GitHub:** `ZJU-REAL/Code-A1`
**Tested on:** Qwen3-4B, Qwen2.5-7B/14B-Instruct

**Architecture:** Two SEPARATE models with OPPOSING objectives:
- Code LLM (solver): rewarded for passing tests (+1 per pass, -1 per fail)
- Test LLM (attacker): rewarded for exposing bugs (+1 per bug found, -1 per invalid test)
- Execution sandbox runs code against tests → determines rewards
- Both updated via RL (GRPO) in alternating rounds

**Critical problem solved — Self-Collusion:**
```
Previous approaches (Sol-Ver, single-model self-play):
  One model = both solver AND verifier
  → White-box access: verifier sees solver's code
  → Model learns to generate EASY tests that its own code passes
  → "I write easy test → I pass → reward!" → quality does NOT improve

Code-A1:
  Two separate models with opposing goals
  → Test LLM sees code (white-box) but its GOAL is to BREAK it
  → No incentive for self-collusion
  → White-box is SAFE because adversarial objectives prevent it
```

**Mistake Book Mechanism (anti-forgetting for adversarial training):**
```
Without Mistake Book:
  Iter 1: Code LLM passes tests T1 → Iter 2: Test LLM makes harder T2
  Iter 3: Code LLM learns T2, FORGETS T1 → catastrophic forgetting

With Mistake Book:
  Historical failure cases stored, replayed every ~100 steps
  → Old bugs not forgotten → each iteration only adds difficulty
```

**Composite Reward for Test LLM:**
`reward = α × validity + β × difficulty`
- validity: test actually checks the specification (not meaningless)
- difficulty: test catches bugs other tests missed
- Prevents garbage test generation (validity) + encourages edge cases (difficulty)
- Automatic curriculum: tests get harder each iteration

**Results (Qwen3-4B):**
| Benchmark | Base | + Code-A1 | Delta |
|-----------|:---:|:---:|:---:|
| HumanEval (one-shot) | 65.2% | 73.8% | +8.6 |
| MBPP | 58.7% | 66.3% | +7.6 |
| Best-of-N (N=8) | 78.1% | 86.5% | +8.4 |
| Unit Test Generation | 42.1% | 55.8% | +13.7 |

### 2.2. CURE: Co-Evolving Coders and Unit Testers (NeurIPS 2025 Spotlight)

**Key difference from Code-A1:** ONE model (not two), interaction-based rewards WITHOUT ground-truth code.

- Model generates code C, then generates tests T, executes C against T
- Code reward = pass_rate(T, C); Test reward = bug_detection(C, T)
- Both rewards come purely from interaction — no reference solutions needed
- Test-time scaling: generate N test variants, select hardest
- Enables training on NEW domains without any labeled data

### 2.3. ATGen: Adversarial Test Generation (arXiv:2510.14635, ICLR 2026)

**Unique angle:** Test Generator vs Adversarial Code Generator (bug creator).

- Adversary creates code with SUBTLE bugs that pass current tests
- Test Generator must catch them → gets negative reward if bug slips through
- As generator strengthens, adversary must produce harder bugs
- Automatic curriculum: bugs get subtler (off-by-one, race conditions, null pointer, integer overflow)
- Paradoxically improves code WRITING: model learns WHERE bugs arise

### 2.4. SAGE: Setter-Solver Asymmetric Game (arXiv:2603.15255, Mar 2026)

**Asymmetric game for automatic curriculum generation:**
- Setter: generates a problem + predicts whether Solver can solve it
- Solver: attempts to solve the problem
- Setter reward: +1 if prediction is correct (calibration reward)
- Solver reward: +1 for correct solution
- Setter learns to generate problems at the EDGE of Solver's ability → ideal curriculum

**For programming:** Setter generates coding task specifications, Solver implements them. Tests verify correctness. Setter calibrates difficulty to Solver's current level.

### 2.5. Sol-Ver: Solver-Verifier Self-Play (arXiv:2502.14948, NeurIPS 2025)

**Baseline approach:** One model alternates as solver (generates code) and verifier (generates tests). Mutually enhanced: better tests → better code → better tests. No human annotations or teacher models needed.

**Limitation:** Single-model self-play is vulnerable to self-collusion (Code-A1 solves this by splitting into two models).

### 2.6. SPC: Self-Play Critic (arXiv:2504.19162, NeurIPS 2025)

**GitHub:** `chen-judge/SPC`

Step-level reasoning assessment via adversarial self-play:
- Sneaky Generator: injects subtle errors into reasoning steps
- Critic: learns to detect which steps are wrong
- Adversarial co-evolution → critic gets better at catching errors, generator gets sneakier
- Eliminates need for manual step-level annotation
- Applies to Chain-of-Thought verification

---

## Comparison Table

| Framework | Architecture | Reward | External Data | Year | Best For |
|-----------|-------------|--------|---------------|------|----------|
| SPIRAL | 1 model, 2 roles, games | Win/loss/draw | 0 (game rules) | ICLR 2026 | General reasoning transfer |
| **Code-A1** | 2 models, adversarial | Pass rate / bug rate | Specs only | Mar 2026 | **Max code quality** |
| CURE | 1 model, co-evolve | Interaction-based | 0 (no ground-truth!) | NeurIPS 2025 | New domains without labels |
| ATGen | Test vs Bug-Generator | Bug detection | Specs only | ICLR 2026 | Testing + edge cases |
| SAGE | Setter vs Solver | Calibration | 0 (generated) | Mar 2026 | Curriculum generation |
| Sol-Ver | 1 model, solver+verifier | Code+test mutual | 0 | NeurIPS 2025 | Baseline self-play |
| SPC | Sneaky gen vs Critic | Step correctness | 0 | NeurIPS 2025 | Step-level reasoning |

---

## Practical Strategy for DGX Spark (128 GB)

### Recommended Composition

```
Stage 1: SPIRAL on Qwen3-4B (3-5 days, 14-44 GB)
  → Base reasoning boost via self-play games
  → Kuhn Poker alone: +8.6% on math
  → Transfer to 35B via Direct-OPD (Stage 3)

Stage 2: Code-A1 — 4B as Test LLM, 35B as Code LLM (3-5 days, 93 GB)
  → Qwen3-4B (frozen, 9 GB) generates adversarial white-box tests
  → Qwen3.5-35B (LoRA, 74 GB) generates code, rewarded for passing
  → Execution sandbox: Docker with Python/C++/Rust
  → Mistake Book: replay failed cases every 100 steps
  → Memory: 74 + 9 + 10 = 93 GB → fits 128 GB ✅

Stage 3: Transfer reasoning to 35B via Direct-OPD (2-3 days, 74 GB)
  → RL policy shift from 4B-SPIRAL → 35B
  → DES-MoE anti-forgetting during transfer

Stage 4 (optional): MOPD multi-teacher on-policy distillation (20-30h, $100-150 API)
  → Cloud teachers (GPT-4o, DeepSeek V4, GLM-5.2) for domain specialization
```

### Why Qwen3-4B is the Ideal Sparring Partner for 35B

| Property | Qwen3-4B | Qwen3.5-35B |
|----------|----------|-------------|
| Memory (BF16) | 9 GB | 67 GB |
| LoRA training | 14 GB | 74 GB |
| Rollout speed | ~150 tok/s | ~40 tok/s |
| Role | Test LLM (fast test gen) | Code LLM (quality code gen) |
| Architecture | Same Qwen3.5 family | — |
| Tokenizer | Compatible | — |

4B generates tests ~4× faster than 35B → eliminates bottleneck. 35B focuses on code quality, 4B on test generation speed. Both in memory: 74 + 9 = 83 GB training, 93 GB with sandbox.

### Code-A1 on DGX Spark — Conceptual Pipeline

```python
# Phase 1: Train Test LLM on Qwen3-4B (1-2 days, 44 GB)
#   GRPO: Test LLM rewarded for finding bugs
#   Data: specs from HumanEval/MBPP/LiveCodeBench
#   Result: Qwen3-4B-Tester (generates hard tests)

# Phase 2: Train Code LLM on Qwen3.5-35B LoRA (2-3 days, 74 GB)
#   Load Qwen3-4B-Tester (frozen, 9 GB) as opponent
#   35B generates code → 4B-Tester generates white-box adversarial tests
#   Execution sandbox: Docker container
#   Code reward: +1 pass, -1 fail
#   Mistake Book: store failed cases, replay every 100 steps
#   Total memory: 74 + 9 + 10 = 93 GB ✅

# Phase 3: Iterate (optional, cap 2-3)
#   Retrain Tester on 4B with updated Code LLM
#   Retrain Code LLM with updated Tester
```
