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
* **Epochs:** 2
* **Effective Batch Size:** 8
* **Learning Rate:** 5e-5
* **LoRA Rank:** 16
* **LoRA Alpha:** 32
* **Target Modules:** Qwen attention and MLP layers (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`).
* **SimPO Parameters:** $\beta = 2.0$, $\gamma = 1.5$, Margin $\gamma/\beta = 0.75$.

## Evaluation Results
The model was evaluated on a strictly partitioned, sealed held-out dataset of 48 tasks (44 eval pairs; 4 skipped — generated output did not beat rejected score), heavily enriched with hand-authored adversarial edge cases.

* **Baseline Accuracy (Zero-Shot):** 97.73% (43/44 pairs)
* **Prompt-Engineered Accuracy (Delta B):** 97.73% — no lift from rubric system prompt alone
* **Trained Pairwise Accuracy (Delta A):** 100.00% (44/44 pairs), +2.27pp
* **Statistical Significance:** `p=0.372`, CI=[0.0%, 6.8%] — not statistically significant due to high baseline and n=44

## Limitations and Bias
This adapter is highly specialized to the Tenacious style guide and bench format. It is not intended for general-purpose preference judging outside of technical staffing contexts. The baseline Qwen2.5-3B model already exhibits high accuracy on this domain; this adapter specifically patches the remaining nuanced adversarial edge cases where the core model fails to enforce strict logical bounds.
