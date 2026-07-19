# Multi-Teacher Adversarial Distillation (MTAD) Pipeline (2025-2026)

**Date:** 2026-07-13
**Context:** Deep-dive into 5 methods (RO-GRPO, GAD, DES-MoE, Synergistic Regularization, G-OPD) for a multi-teacher adversarial distillation pipeline targeting Qwen3.5-35B-A3B MoE on DGX Spark. Pipeline designed to distill from 5 cloud teachers (GLM-5.2, DeepSeek V4 Pro, GPT-5, Fable 5, Qwen3.7) into a single 35B student with 2 LoRA heads (Code + Test) for adversarial self-play.

---

## G-OPD: Generalized On-Policy Distillation with Reward Extrapolation

**arXiv:** 2602.12125 | **Authors:** RUCBM (Renmin University of China) | **Code:** github.com/RUCBM/G-OPD | **Framework:** verl (v0.6.1)

### Core Insight: OPD is a Special Case of KL-Constrained RL

Standard OPD aligns student with teacher's logit distribution on student-generated trajectories. G-OPD proves OPD = dense KL-constrained RL where reward weight = KL weight (always 1:1). G-OPD generalizes by introducing:

1. **Reward scaling factor λ** — controls relative weight of reward vs KL regularization
2. **Flexible reference model** — can be any model, not just student's initial state

### Reward Extrapolation (ExOPD) — Surpassing the Teacher

```
λ < 1: Reward Interpolation — student moves toward teacher but conservatively
λ = 1: Standard OPD — student matches teacher (ceiling)
λ > 1: Reward Extrapolation (ExOPD) — student AMPLIFIES teacher's distinctive characteristics
```

**Key result:** λ ≈ 1.25 is the sweet spot. Student **surpasses** domain-expert teachers in their own domains.

**Multi-teacher experiment:** Student distilled from math expert + code expert via ExOPD (λ=1.25) outperformed BOTH individual domain experts in their respective domains. This is possible because ExOPD amplifies what distinguishes each teacher from the reference — combining multiple teachers creates emergent capabilities beyond any single teacher.

**Limitations:**
- λ > 1.5 → instability, overfitting to noise in log-ratios, longer responses (reward hacking)
- Reward correction (using teacher's pre-RL variant as reference) requires access to teacher's base model — impossible for API-only teachers (GPT, GLM, Fable)
- **White-box only** — requires teacher logits. For API-only teachers, use GAD instead.
- Multi-teacher support currently limited to 2 teachers (per GitHub README)

### verl Implementation

```bash
python3 -m verl.trainer.main_ppo \
    algorithm.adv_estimator=grpo \
    actor_rollout_ref.model.path=Qwen/Qwen3-1.7B \  # student
    +actor_rollout_ref.ref.model.path=Qwen3-4B-RL-Math \  # teacher (white-box)
    +actor_rollout_ref.model.base_model_path=Qwen/Qwen3-1.7B \  # reference
    actor_rollout_ref.actor.policy_loss.only_reverse_kl_advantages=True \  # OPD mode
    actor_rollout_ref.actor.policy_loss.lambda_vals=1.25 \  # ExOPD: λ > 1
    actor_rollout_ref.rollout.name=vllm \
    actor_rollout_ref.rollout.tensor_model_parallel_size=4
```

### Hybrid Approach for Multi-Teacher

For 5 teachers where only 1 is white-box:
- **G-OPD/ExOPD** for Qwen3.7 teacher (architecture-aligned, white-box, logits available) — λ=1.25 for super-teacher boost
- **GAD** for GLM-5.2, DeepSeek, GPT-5, Fable 5 (black-box, API-only) — adversarial discriminator-based

---

## GAD: Generative Adversarial Distillation — Implementation Details

**arXiv:** 2511.10643 | **Authors:** Tianzhu Ye, Li Dong, Zewen Chi, Xun Wu, Shaohan Huang, Furu Wei (**Microsoft Research**)

### Architecture: Two-Player Minimax Game

```
Generator (Student LLM):
  → Generates responses on prompts (ON-POLICY: student's own distribution)
  → Maximize discriminator score
  → Updated via GRPO (reward = discriminator score)

Discriminator (separate model):
  → Trained to distinguish student responses from teacher responses
  → Bradley-Terry pairwise preference loss:
    L_disc = -log σ(s(y_teacher) - s(y_student))
  → Goal: s(y_teacher) > s(y_student)

Teacher (API-only):
  → Generates responses on same prompts
  → Only text output needed, NO logits access
```

### Training Procedure

1. **Warmup (REQUIRED before GAD):** SFT on teacher-generated responses (SeqKD). Without warmup, discriminator is too strong → student can't learn.
2. **GAD Loop:** Student generates → Teacher generates → Train discriminator → Train student via GRPO with discriminator score as reward → Repeat (co-evolution)

### Key Result

Qwen2.5-14B-Instruct (student) trained with GAD became **comparable to** GPT-5-Chat (teacher) on LMSYS-Chat automatic evaluation. 14B model caught up to GPT-5 through adversarial distillation.

### Multi-Teacher GAD Extension

For 5 teachers, use 5 discriminators (one per teacher) or a single multi-class discriminator:

```python
# Multi-Teacher GAD: average reward across all teacher perspectives
for response in student_responses:
    scores = [discriminators[name].score(response) for name in teachers]
    reward = mean(scores)  # student must be indistinguishable from ALL teachers
```

Each teacher provides a different perspective on quality → student learns diverse styles → better generalization than single-teacher.

### GAD vs SeqKD

| Aspect | SeqKD (traditional) | GAD |
|--------|---------------------|-----|
| Policy | Off-policy (teacher data) | On-policy (student generates) |
| Feedback | Static (teacher = ground truth) | Dynamic (discriminator co-evolves) |
| Teacher access | Needs logits or responses | Only text output (black-box) |
| Overfitting | Overfits to local patterns | Discriminator adapts continuously |

---

## Additional Methods for MTAD Pipeline

### TCOD: Temporal Curriculum for On-Policy Distillation (arXiv:2604.24005)

Solves **Trajectory-Level KL Instability**: student trajectories drift from teacher → compounding errors over multi-step reasoning.

**Solution:** Progressive trajectory depth expansion:
- Epoch 1: only 1-2 steps of trajectory (shortest)
- Epoch 2: 3-4 steps
- Epoch 3: 5-7 steps
- Final: 10+ steps (full multi-step)

Prevents KL drift by starting with short trajectories where student stays close to teacher, then gradually increasing depth.

### Agent Distillation: First-Thought Prefix (arXiv:2505.17612, NeurIPS 2025 Spotlight)

**Two innovations:**
1. **First-thought prefix:** Enhance teacher trajectory quality by prepending teacher's initial reasoning as context
2. **Self-consistent trajectory filtering:** Keep only trajectories where teacher is confident (low variance across multiple samples)

Best method for transferring complex multi-step reasoning trajectories from teacher to student.

### Anchored Self-Play (arXiv:2607.03523)

**Problem:** In adversarial self-play (Code LLM vs Test LLM), test generator drifts to unrealistic tests that never appear in real scenarios.

**Solution:** Mix reference bugs from external teachers (collected during multi-teacher trajectory collection phase) into self-play loop. These "anchor" bugs prevent drift:
- Code-embedding similarity reward shapes test generation toward realistic bug patterns
- Reference bugs from 5 teachers = 5 perspectives on common bug types

---

## MTAD Pipeline Architecture

### Design Principles

1. **Multi-teacher diversity:** 5 teachers, each gets tasks where it's strongest
2. **Dual LoRA heads:** LoRA-Code (solver) + LoRA-Test (adversary) on frozen backbone + frozen router
3. **6-layer router protection:** Frozen Router + R3 + RO-GRPO + Synergistic Reg + EPnG + DES-MoE
4. **4-layer forgetting protection:** Frozen Backbone + Mistake Book + DES-MoE + Anchored Self-Play
5. **Black-box + white-box hybrid:** GAD for API teachers, G-OPD/ExOPD for local teacher

### Teacher Task Routing

| Teacher | Strength | Task Pool | Cost |
|---------|----------|-----------|------|
| GLM-5.2 (753B MoE) | SWE-bench Pro 62.1%, Terminal-Bench 81% | Aggressive coding, terminal-heavy, repository-level | $1.40/$4.40 per M tokens (cheapest) |
| DeepSeek V4 Pro | MCP-Atlas 73.6% | Multi-tool agent tasks, MCP-style | Mid-range |
| GPT-5 | Breadth coverage | Diverse languages (Python, C++, Go, Rust), competitive programming | Higher |
| Fable 5 | HLE 64.5%, Design Arena 1350 Elo | Hard reasoning, algorithm design, mathematical reasoning in code | Higher |
| Qwen3.7 | Architecture-aligned | Logit alignment with student (Qwen3.5-35B) → best white-box transfer | Local/cheap |

### 6 Phases

**Phase 0: Multi-Teacher Trajectory Collection (3 days, ~$500 API)**
- 3000 tasks from SWE-Gym + LiveCodeBench + SWE-smith
- Each teacher gets 500-1000 tasks in its strength area
- Collect multi-step trajectories (plan→implement→test→execute→refine, 3-10 steps)
- Agent Distillation filtering: self-consistent trajectories, first-thought prefix
- Each teacher also generates adversarial tests for other teachers' code → diverse test corpus for anchoring

**Phase 1: Cold-Start SFT with Multi-Teacher Data (2 days, local)**
- SFT on all successful trajectories from 5 teachers
- TCOD curriculum: progressive trajectory depth (1-2 → 3-4 → 5-7 steps)
- LoRA rank=128 (doubled from 64 for capacity)
- DES-MoE Phase A (warmup): record expert-code correlation matrix A[expert][domain]
- Synergistic Regularization active (intra-layer spec loss)

**Phase 2: RL Warmup — Single-Step with RO-GRPO (3 days, local)**
- Tasks: HumanEval / MBPP+ (single-step, simple)
- RO-GRPO: R_total = R_task + 0.1 * (entropy_bonus - load_variance)
- All MoE protection layers active: R3, RO-GRPO, Router KL monitor, entropy floor, expert utilization monitor
- DES-MoE Phase B: freeze non-code/non-test experts based on correlation matrix
- Agent-wise advantage normalization (separate baselines for Code LoRA and Test LoRA)
- Go/No-Go gate: pass rate +3%, expert utilization >30% get >5% tokens, router KL < 10⁻³

**Phase 3: Multi-Step RL + Role-Swap Distillation (7 days, ~$300 API)**
- Sub-phase A (4 days): Cloud teachers generate code, Local 35B generates adversarial tests
  - GAD: discriminator distinguishes teacher code from student test quality
  - Multi-teacher GAD: 5 discriminators (one per teacher perspective)
  - Anchored Self-Play: mix reference bugs from 5 teachers
- Sub-phase B (3 days): Role swap — Local 35B generates code, Cloud teachers generate tests
  - 5 teachers each generate tests for local code → 5 perspectives on bugs
  - G-OPD/ExOPD with Qwen3.7 (white-box): λ=1.25 for super-teacher boost
  - TCOD: progressive depth (1-2 → 3-4 → 5-7 → 10+ steps)

**Phase 4: Adversarial Curriculum Escalation (5 days, local)**
- Self-play: Local 35B plays against itself with reinforced experience from 5 teachers
- Difficulty levels: L1 HumanEval → L2 MBPP+ → L3 LiveCodeBench → L4 SWE-bench Verified → L5 SWE-bench Lite
- Transition criterion: pass_rate > 70% on current level
- MT-GRPO with turn-level credit assignment (GAE per step)
- DES-MoE Phase C: progressive freezing of converged experts
- EPnG: continuous LoRA reallocation (prune dead experts, grow active)
- Mistake Book: experience replay every 100 steps

**Phase 5: Final Evaluation & Gating (2 days)**
- Benchmarks: HumanEval, MBPP+, LiveCodeBench V6, SWE-bench Verified/Lite, Terminal-Bench 2.1, Unit Test Generation (CURE), cross-domain MATH/GSM8K/GPQA
- Success: +8-12% HumanEval, +15-20% SWE-bench, +10-15% Terminal-Bench, <2% regression on general
- Reward hacking audit: Isomorphic Perturbation Testing, Countdown-Code diagnostic, hold-out test set
- MoE health: router KL < 10⁻³, expert utilization >30% get >5% tokens, policy entropy > 0.3

### Budget

```
Hardware: DGX Spark (128GB unified memory)
Model: Qwen3.5-35B-A3B MoE (67GB base, fp16)
LoRA: 2× rank=128 = ~12GB → Total ~79GB (49GB headroom)

Phase 0: ~$500 API (GLM-5.2 cheapest at $100 for 1000 tasks)
Phase 1-2: local (5 days)
Phase 3: ~$300 API
Phase 4-5: local (7 days)
Total: ~$800 API + 22 days DGX Spark
```

---

## Method Ranking Summary (from this session)

### Tier 1: MANDATORY (cannot run without)

| # | Method | Score | Why |
|---|--------|-------|-----|
| 1 | RO-GRPO (ICLR 2026) | 23/25 | Without it, GRPO on LoRA-MoE mathematically breaks (routing collapse) |
| 2 | R3 Routing Replay (2510.11370) | 22/25 | Fixes train-inference routing discrepancy, zero overhead |
| 3 | Frozen Router + LoRA-only | 23/25 | Natural MoE protection, free |

### Tier 2: HIGHLY RECOMMENDED

| # | Method | Score | Why |
|---|--------|-------|-----|
| 4 | Multi-Teacher Trajectory Distillation | 20/25 | 5 teachers = 5x diversity, each teacher gets strongest tasks |
| 5 | TCOD Temporal Curriculum (2604.24005) | 21/25 | Progressive trajectory depth, prevents KL drift |
| 6 | DES-MoE 3-Phase (2509.16882) | 21/25 | -89% forgetting, 68% faster convergence, selective expert freezing |
| 7 | Agent Distillation (2505.17612) | 20/25 | First-thought prefix, self-consistent trajectory filtering |
| 8 | GAD Black-box (2511.10643) | 21/25 | Best black-box distillation for API-only teachers |

### Tier 3: OPTIMIZATION

| # | Method | Score | Why |
|---|--------|-------|-----|
| 9 | EPnG Prune-Grow (2607.01789) | 21/25 | Dynamic LoRA reallocation, 140x fewer params |
| 10 | Synergistic Regularization (2602.14159) | 22/25 | Plug-and-play expert differentiation, orthogonal to all |
| 11 | Anchored Self-Play (2607.03523) | 20/25 | Reference bugs prevent test drift |
| 12 | Mistake Book (from Code-A1) | 21/25 | Experience replay every 100 steps |
| 13 | G-OPD/ExOPD (2602.12125) | 18/25 | Super-teacher via λ>1, but white-box only, limited multi-teacher |

### Tier 4: OPTIONAL (capacity only)

| # | Method | Score | Why |
|---|--------|-------|-----|
| 14 | Expert Upcycling (2604.19835) | 14/25 | Add experts via duplication — overkill for LoRA rank=128 |
| 15 | SPRI SVD-Partition (2606.16456) | 14/25 | Add experts via SVD — same, overkill |

### Protection Stacks

**6-Layer Router Protection:**
1. Frozen Router (structural) — router weights never updated
2. R3 (training-inference) — routing masks cached & replayed
3. RO-GRPO (RL reward) — entropy + load_var → scalar reward
4. Synergistic Reg (loss) — force expert differentiation
5. EPnG (dynamic) — reallocate LoRA from dead to active experts
6. DES-MoE (schedule) — freeze non-relevant experts progressively

**4-Layer Forgetting Protection:**
1. Frozen Backbone — original knowledge never overwritten
2. Mistake Book — experience replay every 100 steps
3. DES-MoE Phase B/C — domain-specific gradient isolation
4. Anchored Self-Play — reference bugs from 5 teachers prevent drift

---

## Implementation Patterns (Pseudocode)

### RO-GRPO Reward Function

```python
def compute_reward(task_result, routing_stats):
    R_task = 1.0 if task_result.passed else 0.0

    # Routing entropy (normalized to [0,1])
    H = -sum(p * log(p) for p in routing_stats.expert_probs)
    H_max = log(N_experts)
    entropy_bonus = H / H_max  # 1.0 = perfect diversity

    # Load variance penalty
    load_var = variance(routing_stats.token_frequencies)
    load_penalty = -load_var

    R_routing = entropy_bonus + load_penalty
    return R_task + 0.1 * R_routing  # λ=0.1
```

### DES-MoE 3-Phase Scheduler

```python
class DESMoEScheduler:
    def __init__(self, n_steps, n_experts=128):
        self.T1 = int(0.2 * n_steps)  # Warm-up ends at 20%
        self.T2 = int(0.7 * n_steps)  # Stabilization ends at 70%
        self.correlation = np.zeros((n_experts, 2))  # [code, test]

    def update_correlation(self, expert_id, domain, freq):
        self.correlation[expert_id][domain] = freq

    def get_trainable_experts(self, step):
        if step <= self.T1:       return "all"  # Phase A: warmup
        elif step <= self.T2:     # Phase B: stabilization
            code = {e for e in range(128) if self.correlation[e][0] > 0.15}
            test = {e for e in range(128) if self.correlation[e][1] > 0.15}
            return code | test
        else:                      # Phase C: consolidation
            code_top5 = set(np.argsort(self.correlation[:, 0])[-5:])
            test_top5 = set(np.argsort(self.correlation[:, 1])[-5:])
            return code_top5 | test_top5

    def get_lr(self, step):
        if step <= self.T1:   return 1e-3
        elif step <= self.T2: return 1e-4
        else:                  return 1e-5
```

### Synergistic Regularization Loss

```python
def synergistic_regularization(model, tokens, routing_decisions, alpha=0.1, beta=0.1):
    R_sp = 0.0  # intra-layer specialization
    R_cp = 0.0  # cross-layer coupling
    for layer_idx, layer in enumerate(model.moe_layers):
        acts = layer.get_expert_activations(tokens, routing_decisions[layer_idx])
        for i in range(top_k):
            for j in range(i+1, top_k):
                R_sp += F.cosine_similarity(acts[i], acts[j], dim=-1).mean()
        if layer_idx < len(model.moe_layers) - 1:
            joint = compute_joint_routing_prob(routing_decisions[layer_idx],
                                                routing_decisions[layer_idx+1])
            R_cp += -torch.log(joint + 1e-8).mean()
    return alpha * R_sp + beta * R_cp
```

### Multi-Teacher GAD Loop

```python
discriminators = {name: init_discriminator() for name in teachers}
for iteration in range(N):
    prompts = sample_batch()
    student_responses = student.generate(prompts)  # on-policy
    for name, api in teachers.items():
        teacher_responses = api.generate(prompts)  # API, text only
        discriminators[name].train(positive=teacher_responses, negative=student_responses)
    rewards = [mean([discriminators[n].score(r) for n in teachers]) for r in student_responses]
    grpo_update(student, prompts, student_responses, rewards)
```

### ExOPD Loop (White-Box Teacher Only)

```python
for iteration in range(N):
    trajectories = student.generate(prompts, n=8)  # on-policy
    rewards = []
    for traj in trajectories:
        teacher_logprob = white_box_teacher.logprob(traj)  # needs logits!
        ref_logprob = reference_model.logprob(traj)
        rewards.append(1.25 * (teacher_logprob - ref_logprob))  # λ=1.25
    grpo_update(student, prompts, trajectories, rewards)
```

---

## Cross-References

- `references/moe-routing-stability-rl.md` — RO-GRPO, R3, Synergistic Regularization, EPnG, DES-MoE details (routing-focused)
- `references/on-policy-distillation-2025.md` — GAD, MOPD, PACED, Direct-OPD, self-play methods
- `references/catastrophic-forgetting-2025.md` — DES-MoE, EAFT, Low-Perplexity masking, SSU
- `references/self-play-programming-2025.md` — Code-A1, CURE, ATGen, SAGE, Mistake Book
- `references/code-rl-training-2025.md` — GRPO, P-GRPO, MURPHY, CodeRL+, SWE-RL
