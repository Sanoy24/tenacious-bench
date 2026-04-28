# Synthesis Memo 03: Data Contamination and Dynamic Benchmarking

## Reading

Simin Chen et al., *Benchmarking Large Language Models Under Data Contamination: A Survey from Static to Dynamic Evaluation* (EMNLP 2025). Primary source: ACL Anthology PDF.

## Thesis

This paper is the contamination-control playbook for Week 11. Its most useful contribution is not the taxonomy of benchmark styles by itself, but the criteria in Section 4.3 for evaluating whether a dynamic benchmark is actually good: correctness, scalability, collision, stability of complexity, diversity, and interpretability. For Tenacious-Bench, those criteria tell us exactly how to avoid fooling ourselves with superficially novel but actually leaky or unstable tasks.

## What I am taking from the paper

Section 4.2 is the hinge of the paper. The authors argue that dynamic benchmarks are often praised for freshness but lack standardized criteria for judging whether the benchmark construction process itself is sound. That is the right framing for this project. It is not enough for our sales tasks to look new. We need to know whether they are correct, whether the transformations overlap too much, whether difficulty drifts, and whether the generation process is interpretable enough to audit.

Section 4.3 is directly actionable:

- Correctness means transformed tasks still have valid ground truth.
- Collision means repeated transformations should not collapse into the same examples.
- Stability of complexity means transformed tasks should not become harder or easier for accidental reasons.
- Diversity matters both relative to the seed data and across transformed trials.
- Interpretability matters because opaque task generation raises validation cost.

The paper is especially useful for our public-signal setting because Section 4.4 shows the tradeoffs of the main dynamic-benchmark strategies:

- temporal cutoffs reduce contamination risk but need timestamp discipline
- rule-based generation is interpretable but can reduce diversity
- LLM-based generation increases flexibility but weakens correctness and interpretability unless validation is added
- hybrid pipelines are often the practical middle ground

That is almost a direct description of what Tenacious-Bench should become.

## My disagreement with the paper

My disagreement is with how evenly the paper treats the six criteria in practice. For a week-long benchmark build in a high-stakes business domain, I do not think scalability deserves equal decision weight with correctness and interpretability in the early stages.

Why I disagree:

- the benchmark is evaluating prospect-facing sales behavior, where false positives are expensive
- our seed corpus is small and high-value, not internet-scale
- the paper itself notes that LLM-based methods often only partially support correctness and interpretability

For Tenacious-Bench v0.1, I would explicitly rank the criteria:

1. correctness
2. interpretability
3. collision control
4. stability of complexity
5. diversity
6. scalability

That is not because scalability is unimportant. It is because a benchmark that scales cheaply while silently drifting in truth conditions is worse than a smaller benchmark that can be defended.

I also think the paper is slightly too optimistic about "dynamic" as the general destination. For this project, we still need a semi-static sealed held-out slice for reproducible grading. So the correct adaptation is not a fully live benchmark. It is a hybrid benchmark with dynamic-authoring logic and static evaluation snapshots.

## Design consequence for Tenacious-Bench

This reading gives us a clear benchmark-construction policy:

- use rule-based or structured generation for the core held-out slice whenever possible
- use temporal grounding for tasks derived from layoffs, funding, hiring, or other public signals
- allow LLM-based generation only when the result is filtered by deterministic checks or reviewable constraints
- measure overlap and near-duplication across partitions, not just within one partition
- document the transformation logic clearly enough that another evaluator can inspect it

For this repo, the contamination script should not stop at "overlap found / not found." It should report:

- overlap signals
- which fields were compared
- which tasks are too close
- whether the issue is lexical overlap, semantic similarity, or timestamp risk

That is what turns contamination control into an auditable process instead of a checkbox.

## What I will do because of this reading

1. Keep held-out generation more interpretable than dev generation.
2. Treat timestamped public-signal tasks as special-risk items.
3. Add embedding similarity only as one layer, not the whole contamination story.
4. Prefer hybrid generation over pure open-ended LLM generation.
5. Explain benchmark transforms in human language, not just code.

## Sources

- Chen et al., *Benchmarking Large Language Models Under Data Contamination: A Survey from Static to Dynamic Evaluation*, Sections 4.2, 4.3, and 4.4. `https://aclanthology.org/2025.emnlp-main.511.pdf`
