# Synthesis Memo 05: Direct Preference Optimization (DPO)

## Reading

Rafael Rafailov et al., *Direct Preference Optimization: Your Language Model is Secretly a Reward Model*, NeurIPS 2023. `arXiv:2305.18290`

## Thesis

DPO shows that the RLHF objective has a closed-form solution directly in terms of language model probabilities — no separate reward model, no policy gradient. By reparameterizing the reward as a log-ratio between the policy and a frozen reference model, the entire alignment pipeline collapses to a binary cross-entropy loss over preference pairs. This makes preference training as cheap as standard supervised fine-tuning.

## Useful idea for this project

The reference model mechanism is the most directly applicable idea. DPO keeps a frozen copy of the SFT checkpoint and penalizes the policy for drifting too far from it via the log-ratio term `β log(π(y|x) / π_ref(y|x))`. For Path B training on 600–1,200 Tenacious preference pairs — a tiny dataset relative to the backbone's pretraining — this constraint prevents the judge from catastrophically overfitting to surface patterns in the preference data and forgetting general language priors. Without it, a small batch of preference pairs can push a model toward degenerate behavior (e.g., always outputting very short texts because the "chosen" rewrites happen to be concise).

## My disagreement

DPO weights all preference pairs uniformly in the loss. The paper's experimental setup uses curated single-source preference datasets (Anthropic HH, TL;DR summarization) where pair quality is approximately uniform. In Tenacious-Bench, the preference pairs span four source modes with very different fidelity:

- Trace-derived pairs (sourced from real zero-reward traces on P007/P011/P027/P032 at 100% trigger rates — trace IDs `879ee1fc`, `88bb3cea`, `09f0188f`) are grounded in actual production failure evidence. These are high-fidelity signal.
- Programmatic pairs are constructed combinatorially; the "rejected" outputs are intentionally bad by template, not by observed failure.
- Synthesis-derived pairs passed a judge filter at ≥3/3/3, but several scored at the bare minimum threshold.

DPO treats all three equally. A pair from trace `879ee1fc` (where P007 fired at 100% and the rejection is a real over-claim) carries the same loss weight as a programmatic pair where the "rejected" output fails a banned-phrase check on a low-stakes template. This flattening is defensible when data quality is uniform; it is not defensible here.

The paper does not address heterogeneous-quality preference data at all. The only quality acknowledgment in the paper is a brief note that "DPO is sensitive to noisy labels," with no recommendation beyond filtering.

## Implementation consequence

I will not use uniform-weight DPO as the primary training objective. The algorithm of choice is SimPO (Meng et al., 2024, see Memo 06) for compute reasons, but the data weighting problem applies regardless of algorithm. Mitigation:

1. Oversample trace-derived pairs (3:1 vs. programmatic) in the training JSONL before any loss is computed.
2. Filter programmatic and synthesis pairs to only those where `scoring_evaluator.py` gives `passed_all_checks: true` on the chosen output **and** `passed_all_checks: false` on the rejected output — making pair quality a binary eligibility gate rather than a weight.
3. Hold trace-derived pairs out of the dev split used for early stopping, so the early-stopping signal is not contaminated by the highest-confidence pairs.

The evidence that this matters comes directly from the probe results: P007/P011/P027/P032 fired at 100% on the zero-reward traces — these are not edge cases, they are the representative failure mode. A training objective that treats them as equivalent to a template edge case will miss the signal those traces carry.

## Sources

Rafailov et al., NeurIPS 2023. `https://arxiv.org/abs/2305.18290`. Key sections: §2 (derivation), §3 (experiments), §4.3 (sensitivity to preference noise).
