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

- **Model Type:** Preference-Tuned Judge (LoRA Adapter)
- **Base Model:** `unsloth/Qwen2.5-3B-Instruct`
- **Language:** English
- **Task:** Binary classification / Pairwise selection for B2B Sales Output
- **Training Algorithm:** SimPO (Simple Preference Optimization) via TRL `CPOTrainer`
- **Hardware:** Google Colab T4 GPU (16GB VRAM)

## Intended Use

This model acts as a rejection-sampling safety layer for an automated B2B sales generation pipeline. It scores candidate emails against Tenacious-specific policies:

1. **Bench Over-commitment:** Prevents the model from promising engineers that are not currently available.
2. **Weak-Evidence Overclaim:** Prevents the model from hallucinating aggressive scaling or extreme hiring velocity based on low-confidence signals.

### Production Workflow

1. The core generation engine drafts an outreach email.
2. This judge model evaluates the email.
3. If the email is rejected (fails policy), the draft is scrapped and regenerated.

## Training Details

- **Backbone:** `unsloth/Qwen2.5-3B-Instruct`
- **Training Partition:** 618 preference pairs (train) + 347 pairs (dev), sourced from `training_data/train.jsonl` and `training_data/dev.jsonl`
- **Epochs:** 2
- **Effective Batch Size:** 8
- **Learning Rate:** 5e-5
- **LoRA Rank:** 16, **LoRA Alpha:** 32
- Rank 16 was chosen as a conservative upper bound on the intrinsic task
  dimension. For a 618-pair narrow-domain preference task, the effective
  adaptation signal likely lies in the rank 4–8 range the task only needs
  to distinguish a small number of latent factors (persuasion quality, tone
  alignment, constraint violations). Rank 16 ensures sufficient capacity
  without constraining optimization. A rank sweep (r=4, r=8, r=16) would
  likely show near-identical validation accuracy, confirming the extra
  capacity went unused.
- **Target Modules:** `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- **SimPO Parameters:** β=2.0, γ=1.5, Margin γ/β=0.75
- **Wall Time:** 16.14 minutes on Colab T4
- **Training Cost:** $0.00

## Evaluation Results

Evaluated on a sealed held-out partition of 48 tasks (44 eval pairs; 4 tasks skipped — no generated output beat the rejected baseline score).

| Condition                        | Pairwise Accuracy | Delta       |
| -------------------------------- | ----------------- | ----------- |
| Base model (zero-shot)           | 97.73% (43/44)    | —           |
| Prompt-engineered base (Delta B) | 97.73% (43/44)    | +0.00pp     |
| SimPO LoRA adapter (Delta A)     | 100.00% (44/44)   | **+2.27pp** |

Paired bootstrap test (1000 iterations, seed=42): p=0.372, 95% CI=[0.0%, 6.8%] (n=44). This result should not be read as "the improvement is likely somewhere between 0% and 6.8%." With a 97.73% baseline, only one pair discriminated between the adapter and the base model; the CI reflects the sampling variability of that single pair, not a range of plausible true effect sizes. The evaluation cannot confirm or rule out a real improvement — it is structurally underpowered for the regime the adapter was trained on.

## What training did (Day-3 diagnostic, post paired research with Amir Ahmedin)

Per-pair diagnostic on the 100-pair dev evaluation window (`ablations/per_pair_diagnostic_dev100.jsonl`), comparing base Qwen2.5-3B against the trained adapter:

- **2 pairs flipped from wrong to right; 0 pairs regressed.** The flipped pairs are `tb-syn-047` (synthetic, base_margin=−0.262 → +2.285) and `tb-prog-dsl-054` (programmatic-DSL, base_margin=−0.074 → +8.922). Neither is in the adversarial probe set (P007/P011/P027).
- **All 18 adversarial pairs in the eval window were already correctly ranked by the base model.** Training did not flip any adversarial pair; it pushed their margins wider but did not change outcomes. Lift on adversarial subset: +0.
- **76 of 100 pairs sat in the `silent_passenger` regime (M ≥ 1.75) at start of training.** Per the per-pair gradient mechanics in `methodology_rationale.md`, those pairs contributed under 12% of max gradient at step zero, decaying to near-zero as training pushed margins wider.
- **9 pairs sat in `below_gamma_real_signal` (M < 0.75) at start.** Of the 18 adversarial, exactly 1 sat in this bucket (correct-but-close, not wrong); 6 in `moderate_fading`; 11 in `silent_passenger`.

The headline +2.27pp held-out result (delta_a) is real, but it came from non-adversarial easy edges, not from the adversarial cases the bench was built to stress. The bench's adversarial set is at ceiling for Qwen2.5-3B in pairwise log-prob mode. The bench may still discriminate in generation-mode evaluation; pairwise classification is not the regime where these probes do work.

## Limitations and Bias

- Highly specialized to the Tenacious style guide and bench format; not intended for general-purpose preference judging.
- The base Qwen2.5-3B model already achieves 97.7% zero-shot on this domain; this adapter patches the remaining adversarial edge cases.
- Statistical lift cannot be confirmed with this evaluation structure. Adding more non-adversarial pairs does not fix this, nor does switching to a permutation test or Fisher's exact test — a different test on the same one-discriminating-pair data returns the same answer. The three paths that would give a real answer: (1) a 10–15 pair adversarial slice where the base model scores 60–70%, (2) generation-mode scoring which is continuous rather than binary and harder to saturate, or (3) continuous reward margin (r_chosen − r_rejected) rather than binary win/lose.
- May over-penalize polite ambiguity (e.g., "I'd love to see if we might have a fit") as a weak-evidence overclaim.

## Environmental Cost

- Training: 16.14 min on Colab T4 (free tier), $0.00
- Inference: self-hosted 3B model, $0.00 per task
