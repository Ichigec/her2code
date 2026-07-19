# Distillation for 35B+ Student Models

**Date:** 2026-07-11
**Question:** Can a 35B model be a STUDENT for distillation from a cloud teacher?

## VERDICT: YES — 35B is a sweet spot for distillation

35B MoE models have enough capacity to absorb complex reasoning from GPT-4o/GLM-5.2 class teachers, unlike 7B models that may just mimic style without substance.

---

## Method Comparison for 35B Students

| Method | Works w/ Cloud API? | Signal Richness | Compute Cost | ROI |
|---|:---:|:---:|:---:|:---:|
| Response SFT | ✅ | Low-Medium | Low | ⭐⭐⭐⭐⭐ |
| Logit KD | ❌ (needs open teacher) | High | Medium | ⭐⭐⭐ |
| Feature-based | ❌ | Highest | High | ⭐⭐ |
| Multi-teacher | ✅ | Medium | Medium | ⭐⭐⭐⭐ |
| On-policy (GKD) | ✅ | High | Medium-High | ⭐⭐⭐⭐ |
| Contrastive (DistiLLM-2) | ✅ | High | Medium-High | ⭐⭐⭐ |

---

## Phase 1: Response SFT (80% of value, 1-2 days)

Simplest, most proven approach. Cloud teacher generates (prompt, response) pairs → student fine-tuned via SFT.

**Key principles (Predibase playbook, scaled to 35B):**
1. Maximize teacher quality — GPT-4o/GLM-5.2; iterate on prompts before generating data
2. Data quality > quantity — 1K-10K good examples > 100K noisy ones
3. Diversity and balance — varied task types, difficulty levels
4. Start simple — SFT baseline before complex methods
5. Diminishing returns beyond 10K-50K examples
6. Include chain-of-thought (CoT) reasoning traces for reasoning tasks

**Implementation:** See SKILL.md Quick Start code patterns. Use QLoRA (20GB, ~20h) or BAdam Full FT (84GB, ~5-8 days).

---

## Phase 2: Multi-Teacher Distillation (+5-10%)

Combine outputs from multiple cloud teachers:

| Method | Description |
|---|---|
| Ensemble voting | For classification: majority vote across GPT-4o, GLM-5.2, DeepSeek V4 |
| Teacher specialization | GPT-4o for reasoning, GLM-5.2 for multilingual, DeepSeek V4 for code |
| Quality scoring | Use one teacher to generate, another to score/rank outputs |
| Data enrichment | Multiple teachers generate diverse outputs for same prompt |

```python
TEACHERS = {
    "reasoning": ("gpt-4o", "https://api.openai.com/v1"),
    "multilingual": ("glm-5.2", "https://api.z.ai/api/paas/v4"),
    "coding": ("deepseek-coder", "https://api.deepseek.com/v1"),
}
```

---

## Phase 3: On-Policy GKD (+2-5% on reasoning)

**Paper:** "On-Policy Distillation of Language Models" (Google DeepMind, ICLR 2024 Spotlight)
**arXiv:** search "GKD Agarwal 2024"

**Key idea:** Student generates its OWN outputs → Teacher evaluates/corrects → Student learns from its own mistakes.

**Critical advantage:** Works with black-box API teachers (only needs teacher evaluation, not logits).

```python
# GKD-style training loop
for iteration in range(num_iterations):
    # 1. Student generates on-policy outputs
    student_outputs = qwen35b.generate(training_prompts)
    
    # 2. Teacher (GPT-4o) evaluates student outputs
    teacher_feedback = gpt4o.evaluate(prompts, student_outputs)
    
    # 3. Train student on (prompt, student_output=rejected, teacher_output=chosen)
    # Using DPO (Direct Preference Optimization)
    dpo_trainer.train(prompts, student_outputs, teacher_corrections)
```

**GKD loss:** KL(student || teacher) on student-generated sequences (on-policy). Unlike standard KD which uses fixed dataset distribution.

---

## DistiLLM-2 (Contrastive Approach)

**Paper:** arXiv:2503.07067 (NAVER AI Lab)

**Key innovation:** Contrastive loss — student learns to DISCRIMINATE good (teacher) vs bad (student-generated) outputs, rather than just maximizing likelihood.

- Positive example: teacher output
- Negative: student's own output or noised version
- Richer signal than token-level cross-entropy
- Better at avoiding "style mimicry without substance"

---

## Expected Quality Gains (Qwen3.5-35B-A3B / Agents-A1 as Student)

| Domain | Pre-trained Baseline | After GPT-4o Distillation | Gain |
|---|---|---|---|
| Instruction Following | IFBench 80.6 | ~90-95% | +10-15% |
| Math Reasoning (GSM8K) | ~85% | ~90-93% | +5-8% |
| Domain-specific tasks | Weak | Strong | +30-50% |
| General Knowledge (MMLU) | ~75% | ~80-83% | +5-8% |
| Code Generation | Moderate | Strong | +15-25% |
| Function Calling | IFEval 94.8 | ~97% | +2-3% |

---

## Cloud Teacher → 35B Student: Memory Budget

| Component | QLoRA (4-bit) | LoRA (BF16) | BAdam Full FT |
|---|---:|---:|---:|
| Student weights | 20 GB | 67 GB | 67 GB |
| Gradients | 0 (frozen) | 0 (frozen) | 67 GB |
| Optimizer states | ~1 GB | ~7 GB | 14 GB (active block) |
| Activations | ~3 GB | ~5 GB | ~5 GB |
| **Total** | **~24 GB** | **~79 GB** | **~84 GB** |
| **Free (of 128 GB)** | **104 GB** | **49 GB** | **44 GB** |

QLoRA leaves 104 GB free — could run a local teacher (27B = 54GB) simultaneously for KD-logit phase.

---

## Cost-Benefit

| Phase | Time | API Cost | Electricity | Quality Gain |
|---|---|---|---|---|
| Phase 1 (SFT) | 1-2 days | $50-100 | ~$20 | +15-30% (80% of value) |
| Phase 2 (Multi-teacher) | +2-3 days | +$50-100 | +$10 | +5-10% |
| Phase 3 (GKD) | +3-5 days | +$30-50 | +$20 | +2-5% |

**Recommendation:** Start with Phase 1 and evaluate. Most use cases get sufficient value from well-executed SFT distillation. Only invest in Phases 2-3 if Phase 1 results don't meet requirements.

---

## Sources

- Predibase LLM Distillation Playbook: https://github.com/predibase/llm_distillation_playbook
- GKD paper: Google DeepMind, ICLR 2024 Spotlight
- DistiLLM-2: arXiv:2503.07067
- "False Promise of Imitating Proprietary LLMs": arXiv:2305.15717
- Orca paper: arXiv:2306.02707
- Gemma 2 distillation: Google technical report
