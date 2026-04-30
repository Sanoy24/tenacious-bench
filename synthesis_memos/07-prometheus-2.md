# Synthesis Memo 07: Prometheus 2

## Reading

Seungone Kim et al., *Prometheus 2: An Open-Source Language Model Specialized in Evaluating Other Language Models*, EMNLP 2024. `arXiv:2405.01535`

## Thesis

Prometheus 2 builds an open evaluator that matches proprietary judge performance (GPT-4 correlation) by training two specialist models — one for direct assessment (Likert scoring) and one for pairwise ranking — then merging their weights via DARE-Linear interpolation at α = 0.5. The core claim is that merging models trained on different evaluation formats captures complementary judgment capabilities that a single jointly-trained model cannot. The resulting 7B and Mixtral-8x7B judges roughly halve the performance gap with GPT-4-class judges compared to prior open evaluators, with Pearson correlations of 0.665–0.685 on standard benchmarks.

## Useful idea for this project

The most directly applicable idea is the training data design: Prometheus 2 trains on 1,000+ custom evaluation rubrics rather than generic helpfulness/harmlessness categories. Each rubric is specific to an evaluation scenario, and the judge is trained to apply that rubric consistently rather than form a global "quality" judgment. This maps directly onto Tenacious-Bench: the scoring evaluator already encodes 13 check types across 14 failure dimensions. The Path B judge should be trained to apply those check-level rubrics, not to output a general quality score.

The training data pipeline is also instructive: Prometheus 2 uses GPT-4 to generate rubric-specific feedback and scores, then trains a smaller model to replicate that feedback pattern. For Tenacious-Bench, the equivalent is using our deterministic `scoring_evaluator.py` as the ground truth source — it is more reliable than a GPT-4 judge because it applies literal rules without model variance.

## My disagreement

The paper's weight merging approach (DARE-Linear at α = 0.5) is the wrong design choice for Tenacious-Bench. The justification for merging two models is format diversity: direct assessment (Likert 1–5) and pairwise ranking use different input-output structures, and a single model trained on both formats underperforms models specialized on each. Merging recovers the benefits of both.

Tenacious-Bench Path B does not have this format diversity problem. We are training a single judge on preference pairs (chosen/rejected) derived from a single consistent evaluation framework: does the outreach pass the deterministic scoring evaluator? There is no Likert assessment format to merge with. Training two separate models — a direct assessment model and a pairwise ranking model — to then merge them would double the compute and data requirements on a 600–1,200 pair dataset without any format complementarity to recover.

The paper's ablation confirms this: merging two models trained on the **same** format did not yield improvements — the benefit came specifically from merging **different** formats. Tenacious-Bench Path B has one format. The merging procedure adds cost and complexity with no expected benefit.

Prometheus 2 is also evaluated on general benchmarks (Vicuna, MT-Bench, FLASK) where rubric diversity matters. For a single-domain judge covering one company's outreach failures, format diversity is irrelevant. The risk of merging is negative here: weight interpolation between models trained on the same narrow domain could average away the sharpness the judge learned on the most diagnostic dimensions (bench-over-commitment, timezone-fabrication) in favor of smoother general behavior.

## Implementation consequence

I will train a single judge model on preference pairs only. No weight merging. The Prometheus 2 insight I will adopt is the rubric-grounded training data design: every preference pair in `training_data/` is anchored to a specific check type from the scoring evaluator, so the judge learns to apply named failure-mode rules rather than forming a general quality preference. The rejected output for a `bench-over-commitment` pair always fails `no-unavailable-stack-commitment`; the chosen output always passes it. The rubric connection is explicit in the metadata field, not implicit in the training signal.

## Sources

Kim et al., EMNLP 2024. `https://arxiv.org/abs/2405.01535`. Key sections: §3 (model architecture and training), §4 (ablation on merging format variants), §5 (evaluation vs. proprietary judges).
