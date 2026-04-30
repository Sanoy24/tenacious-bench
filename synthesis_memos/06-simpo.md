# Synthesis Memo 06: SimPO — Simple Preference Optimization

## Reading

Yuchen Meng, Cheng-Ping Xia, and Danqi Chen, *SimPO: Simple Preference Optimization with a Reference-Free Reward*, NeurIPS 2024. `arXiv:2405.14734`

## Thesis

SimPO eliminates the reference model from DPO entirely. Instead of optimizing the log-ratio `π(y|x) / π_ref(y|x)`, SimPO directly optimizes the difference in raw model log-probabilities `log π(y_w|x) − log π(y_l|x)`, scaled by a margin parameter γ. The claim is that the reference model in DPO is unnecessary overhead — a correctly scaled margin loss achieves equal or better performance with fewer compute requirements and simpler implementation. Empirically, SimPO matches or slightly exceeds DPO on MT-Bench and Alpaca Eval at 7B–13B scale.

## Useful idea for this project

SimPO is the right choice for Path B training on Colab T4. Removing the reference model halves the memory footprint of each training step: DPO requires two forward passes per batch (policy + reference), while SimPO requires one. On a T4 (16 GB VRAM) with a Qwen 3.5 0.8B or 2B backbone and LoRA, that difference matters. The smaller memory budget allows a larger effective batch size, which stabilizes preference training on a small dataset (600–1,200 pairs).

The γ parameter is also more interpretable than DPO's β. γ directly sets the target margin between winning and losing log-probabilities. SimPO recommends γ ≈ 2.5 as the empirical sweet spot, giving a concrete starting point rather than requiring extensive search.

## My disagreement

SimPO's removal of the reference model assumes the model has strong enough general priors that distribution drift from SFT initialization is not a serious risk. This assumption holds in SimPO's evaluation setup: 7B–13B models trained on general instruction-following datasets, where the backbone's priors cover the preference domain well.

It does not hold cleanly for Tenacious-Bench Path B. The judge backbone is Qwen 3.5 0.8B or 2B — a general language model with no Tenacious-specific priors. The preference domain is narrow and highly domain-specific: B2B sales outreach quality, bench-commitment honesty, evidence calibration. Both the "chosen" (corrected hedged outreach) and "rejected" (overclaiming outreach) outputs are fluent English sentences of similar length and syntactic complexity. The backbone's prior log-probabilities for both are essentially equal — neither output is unusual from the model's perspective.

In this regime, SimPO's margin signal starts from near-zero separation. Without a reference model to bound drift, the training loop may amplify spurious statistical patterns in the 600–1,200 pairs (e.g., chosen outputs being slightly shorter on average) rather than learning the actual evidence-calibration distinction that makes an outreach correct or incorrect. DPO's reference model would at least prevent the policy from drifting far from the SFT baseline; SimPO provides no equivalent guardrail.

The paper does not test on narrow single-domain preference datasets at small scale. Its smallest evaluation is on 7B models with general-domain preference data. The claim that reference models are unnecessary does not transfer directly to sub-2B domain-specific judge training.

## Implementation consequence

I will use SimPO for compute reasons (Colab T4 fits without a reference model) but add a dev-set guard that compensates for the missing reference constraint:

- Evaluate `scoring_evaluator.py` agreement on the 73-task dev partition every 100 training steps.
- If evaluator agreement drops below the SFT baseline at any checkpoint, roll back to the previous checkpoint — this replaces the reference model's distributional bound with a task-level performance floor.
- Log γ sensitivity with two values (γ = 1.5 and γ = 2.5) and report which achieves better dev-set agreement in `ablations/ablation_results.json`.

This is a deliberate departure from SimPO's design: the reference model is replaced by an external performance monitor rather than eliminated entirely. The Tenacious data distribution is too narrow for the reference-free assumption to hold without compensation.

## Sources

Meng, Xia, and Chen, NeurIPS 2024. `https://arxiv.org/abs/2405.14734`. Key sections: §3 (method), §4.3 (reference model ablation), §5 (γ sensitivity).
