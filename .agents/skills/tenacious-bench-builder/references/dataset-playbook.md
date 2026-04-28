# Dataset Playbook

## Recommended authoring mix

- Trace-derived: around 30%
- Programmatic parameter sweeps: around 30%
- Multi-LLM synthesis: around 25%
- Hand-authored adversarial: around 15%

Treat the percentages as targets, not shackles. Shift them only when the audit shows a different failure concentration.

## Minimum task metadata

Every task should carry:

- `task_id`
- `partition`
- `dimension`
- `difficulty`
- `source_mode`
- `seed_artifact`
- `input`
- `candidate_output` or expected-output scaffolding
- `rubric`
- `scoring_method`

Add `public_signal_window`, `judge_scores`, or `contamination_flags` whenever they matter.

## Rubric design rules

- Convert brand or tone requirements into concrete markers.
- Prefer extracted-field checks over free-form textual judgments.
- Use judge scoring only for the parts that resist deterministic checks.
- Keep the scoring narrative short enough that another agent can apply it consistently.

## Quality gates

Before accepting a task:

1. Confirm the input is coherent and realistic.
2. Confirm the expected score can be justified from the supplied evidence.
3. Confirm the rubric is specific enough to apply repeatedly.
4. Confirm the task is not a near-duplicate of an existing training task.

## Contamination checks

Apply all three before sealing held-out:

1. N-gram overlap threshold between held-out and training.
2. Embedding-similarity threshold between held-out and training.
3. Time-shift validation for any public-signal task.

Document the thresholds you choose and keep them stable across reruns.

## Inter-rater agreement

Hand-label a 30-task sample twice, with time separation. If agreement is weak on a rubric dimension, revise the rubric before expanding the dataset further.

## Evaluator-first rule

If you catch yourself generating dozens of tasks before the evaluator is credible, stop and repair the evaluator. Cheap task generation can hide expensive scoring ambiguity.
