# Challenge Map

## Core outcome

Build a Tenacious-specific benchmark and a small trained component that improves a Week 10 sales agent on a clearly named failure mode.

## Hard constraints

- Treat the dataset as the main engineering problem.
- Reuse any existing Week 10 benchmark scores; do not spend budget re-running the older retail bench.
- Keep the new benchmark machine-verifiable.
- Publish benchmark artifacts with reproducibility, attribution, and documentation.

## Delivery order

1. Audit Week 10 evidence and name the Tenacious-specific benchmark gap.
2. Design the schema and evaluator before scaling dataset generation.
3. Author and filter the dataset.
4. Prepare path-specific training data.
5. Train one small intervention and compare it against baseline and prompt-only alternatives.
6. Package the dataset, method notes, and public artifacts.

## Required benchmark properties

- 200-300 tasks total.
- Multiple authoring modes, not just one synthesis path.
- Three partitions: train, dev, held_out.
- Contamination controls for the held-out split.
- Datasheet-quality documentation.
- Evidence traceability for every headline number.

## Act-to-artifact map

### Act I

- `audit_memo.md`
- `schema.json`
- `scoring_evaluator.py`
- initial `methodology.md`

### Act II

- `tenacious_bench_v0.1/`
- `datasheet.md`
- contamination output
- inter-rater agreement notes

### Act III

- `training_data/`
- `methodology_rationale.md`

### Act IV

- training logs
- `ablation_results.json`
- held-out scoring traces

### Act V

- public dataset and model cards where applicable
- technical blog post
- community-engagement artifact
- two-page executive memo
