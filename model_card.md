---
language: en
tags:
- alignment
- peft
- simpo
- judge
- b2b-sales
base_model: unsloth/Qwen2.5-3B-Instruct
---

# Tenacious Sales Judge (Qwen2.5-3B-SimPO)

## Model Details

* **Model Type:** Preference-Tuned Judge (LoRA Adapter)
* **Base Model:** `unsloth/Qwen2.5-3B-Instruct`
* **Language:** English
* **Task:** Binary classification / Pairwise selection for B2B Sales Output
* **Training Algorithm:** SimPO (Simple Preference Optimization) via TRL `CPOTrainer`
* **Hardware:** Google Colab T4 GPU (16GB VRAM)

## Intended Use

This model acts as a rejection-sampling safety layer for an automated B2B sales generation pipeline. It scores candidate emails against Tenacious-specific policies:

1. **Bench Over-commitment:** Prevents the model from promising engineers that are not currently available.
2. **Weak-Evidence Overclaim:** Prevents the model from hallucinating aggressive scaling or extreme hiring velocity based on low-confidence signals.

### Production Workflow

1. The core generation engine drafts an outreach email.
2. This judge model evaluates the email.
3. If the email is rejected (fails policy), the draft is scrapped and regenerated.

## Training Details

* **Backbone:** `unsloth/Qwen2.5-3B-Instruct`
* **Training Partition:** 618 preference pairs (train) + 347 pairs (dev), sourced from `training_data/train.jsonl` and `training_data/dev.jsonl`
* **Epochs:** 2
* **Effective Batch Size:** 8
* **Learning Rate:** 5e-5
* **LoRA Rank:** 16, **LoRA Alpha:** 32
* **Target Modules:** `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
* **SimPO Parameters:** β=2.0, γ=1.5, Margin γ/β=0.75
* **Wall Time:** 16.14 minutes on Colab T4
* **Training Cost:** $0.00

## Evaluation Results

Evaluated on a sealed held-out partition of 48 tasks (44 eval pairs; 4 tasks skipped — no generated output beat the rejected baseline score).

| Condition | Pairwise Accuracy | Delta |
|---|---|---|
| Base model (zero-shot) | 97.73% (43/44) | — |
| Prompt-engineered base (Delta B) | 97.73% (43/44) | +0.00pp |
| SimPO LoRA adapter (Delta A) | 100.00% (44/44) | **+2.27pp** |

Paired bootstrap test (1000 iterations, seed=42): p=0.372, 95% CI=[0.0%, 6.8%] — not statistically significant due to high baseline and n=44. The ceiling effect is the primary constraint; see blog post for full interpretation.

## Limitations and Bias

* Highly specialized to the Tenacious style guide and bench format; not intended for general-purpose preference judging.
* The base Qwen2.5-3B model already achieves 97.7% zero-shot on this domain; this adapter patches the remaining adversarial edge cases.
* Statistical lift cannot be proven at n=44; a larger adversarial held-out slice is needed for conclusive measurement.
* May over-penalize polite ambiguity (e.g., "I'd love to see if we might have a fit") as a weak-evidence overclaim.

## Environmental Cost

* Training: 16.14 min on Colab T4 (free tier), $0.00
* Inference: self-hosted 3B model, $0.00 per task
