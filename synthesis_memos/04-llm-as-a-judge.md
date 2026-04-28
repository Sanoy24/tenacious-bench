# Synthesis Memo 04: LLM-as-a-Judge

## Reading

Jiawei Gu et al., *A Survey on LLM-as-a-Judge* (latest arXiv revision listed in the challenge doc). Primary source: `arXiv:2411.15594`.

## Thesis

This paper matters because Tenacious-Bench is not just a dataset problem; it is also an evaluator-design problem. The survey makes two things clear. First, LLM judges are useful, especially when the evaluation target is qualitative and hard to reduce to exact matching. Second, they are unreliable by default. Bias, weak robustness, and prompt sensitivity are not edge cases; they are core design constraints. For this project, the right lesson is to use LLM judges sparingly and only where deterministic checks cannot carry the load.

## What I am taking from the paper

Section 2.5 is the most practical part for immediate use. It describes a "quick practice" loop:

- define the evaluation objective clearly
- design prompts around explicit scoring dimensions
- choose the model deliberately
- constrain outputs into standardized formats
- iterate with tests

That is exactly how our evaluator should evolve. The survey is not telling us to ask a judge for vibes. It is telling us to turn judging into a structured measurement procedure.

Section 3 is also important because it shows where reliability can be improved:

- prompt design and decomposition
- model-side optimization
- post-processing of results

The project-level takeaway is that judge quality is an engineered property, not a base-model property.

Section 4 is the warning label. The survey says evaluation quality should be judged by agreement with humans, but also by bias and adversarial robustness. This is crucial for Tenacious-Bench because our target failures are highly vulnerable to judge distortions. A weak judge might reward exactly the wrong things: concreteness bias could favor over-specific competitor-gap claims; length or authority bias could reward fabricated numbers; nested-instruction or reference bias could distort pairwise comparisons.

Most useful of all is the paper's own meta-evaluation result. In the reported Table 2 discussion, not all common improvement strategies help. Explanations can make outcomes worse, self-validation has minimal effect, and multiple rounds can help more consistently. That is much more actionable than generic "prompt carefully" advice.

## My disagreement with the paper

My disagreement is with a common practical inference one might draw from the survey: that if we can access a strong enough judge, we should let it carry most of the evaluation burden.

I do not think that is the right choice for Tenacious-Bench v0.1.

Why I disagree:

- Section 4 shows bias and adversarial fragility are still serious.
- Section 4.3 shows evaluators can be manipulated by irrelevant phrasing.
- The survey's own meta-evaluation says explanation prompting and self-validation do not reliably improve outcomes.
- Our benchmark targets several dimensions that are actually better expressed as hard constraints than soft judgments.

For example:

- "do not invent a local timezone label" should be deterministic
- "do not promise unavailable stack capacity" should be deterministic
- "do not use banned phrasing" should be deterministic

If we hand those to an LLM judge, we are paying more to get a noisier answer.

So my disagreement is not with LLM-as-a-judge as a technique. It is with overextending it. In this project, the judge should sit on top of deterministic checks, not replace them.

## Design consequence for Tenacious-Bench

This reading points to a hybrid evaluator architecture:

- deterministic rules for factual, lexical, and policy constraints
- LLM-judge only for dimensions that are genuinely hard to encode, such as nuanced tone-marker scoring
- structured outputs only
- pairwise or rubric-bounded scoring, not freeform narrative evaluation
- repeated or aggregated judge calls only when the dimension is important enough to justify the extra cost

It also affects training-data prep for Path B. If we use a judge or critic model later, we should not assume synthetic preference labels are trustworthy just because a strong model produced them. The survey supports adding calibration passes and human spot-checks before training on those labels.

## What I will do because of this reading

1. Keep the benchmark evaluator mostly deterministic in v0.1.
2. Add LLM-judge components only for the residual dimensions that truly need them.
3. Avoid freeform explanation-heavy judging as the default.
4. Use agreement with human labels as the main acceptance criterion for any future judge expansion.
5. Treat bias checks and robustness checks as first-class judge requirements, not later polish.

## Sources

- Gu et al., *A Survey on LLM-as-a-Judge*, Sections 2.5, 3, 4.1, 4.2, 4.3, and the Table 2 discussion in Section 5. `https://arxiv.org/abs/2411.15594`
