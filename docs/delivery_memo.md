# Delivery Memo: Tenacious Sales Judge Deployment

## Page 1: The Decision

**Executive Summary**  
We built a preference-tuned judge model (Qwen2.5-3B) using SimPO to act as a rejection-sampling safety layer for the Tenacious sales generation engine. The model catches hallucinated capacity claims and over-asserted hiring velocities that prompt engineering failed to stop. Because we stripped out the reference model during training, the run fit on a free Colab GPU and cost nothing, resulting in a free safety layer that hit 100% accuracy on our held-out test set.

**Evaluation Results**  
* **Delta A (Trained Model vs Baseline):** +2.27pp (100.00% vs 97.73%). Paired bootstrap test returns `significant=False (p=0.372, CI=[0.0%, 6.8%])` due to a small eval set (44 pairs from 48 held-out tasks) and a high baseline.
* **Delta B (Prompt Engineering vs Baseline):** +0.00%. Adding strict rubric rules to the system prompt failed to catch the remaining adversarial edge cases.

**Cost Pareto**  
* **Training Cost:** $0.00 (Run on free Colab T4).
* **Inference Cost Per Task:** $0.00 (Self-hosted 3B parameter model).
* **Cost vs Baseline:** Running the baseline generative agent costs ~$0.05 per email via OpenRouter API. Adding this local rejection layer adds zero API costs while preventing non-compliant emails from reaching prospects.

**Recommendation: Deploy with Caveat**  
We should deploy this judge model immediately as a pre-send filter. The caveat is that we cannot mathematically prove the adapter's lift is statistically significant yet. Before we trust it to catch 100% of errors in the wild, we need to author a much larger adversarial dataset to truly map the model's ceiling.

---

## Page 2: The Skeptic's Appendix

**Failure Modes Tenacious-Bench v0.1 Still Misses**  
1. **Temporal Awareness:** The current bench summary says "3 available." It doesn't test if the agent promises an engineer for "next Tuesday" when the bench clears "next Friday." v0.2 needs temporal conflict tasks.
2. **Multi-Threading Context Loss:** Our tasks use single-turn prior threads. We don't test if the agent forgets a constraint mentioned five emails ago. v0.2 needs long-context trajectories.
3. **Tone Drift on Correction:** We check for policy violations, but we don't check if the agent sounds panicked or overly apologetic when admitting a missing stack.
4. **Competitor Hallucination:** The current benchmark focuses on our own bench. We don't test if the agent makes up fake weaknesses about competitors during a pitch.

**Public-Signal Lossiness in Ground Truth**  
Our training data relies heavily on LinkedIn job postings and Crunchbase funding rounds to determine "hiring velocity." This is inherently lossy. A company posting a role doesn't mean they have budget, and an unannounced funding round won't show up in Crunchbase. We are training the model to treat a noisy proxy as ground truth, which means it might reject an email that happens to be factually correct in the real world.

**One Honest Unresolved Failure**  
The model occasionally over-penalizes polite ambiguity. If an agent writes, "I'd love to see if we might have a fit," the judge sometimes flags it as a "weak-evidence overclaim" because it assumes any outreach without hard proof is a violation. It is too rigid on edge cases where a human salesperson would just casually fish for information.

**Kill-Switch Trigger Condition**  
If the judge model rejects more than 30% of generated drafts in a single day, the automated pipeline automatically pauses. A 30% rejection rate implies either the generative engine has suffered a massive degradation, or the judge model is hallucinating false positives. Either way, pipeline control reverts to human review until the anomaly is diagnosed.
