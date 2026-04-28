# Repo Shape

## Likely Python surfaces in this project

- `scoring_evaluator.py`
- dataset generation or transformation scripts
- contamination checks
- partition validators
- training-data formatters
- ablation summarizers

## What matters most here

### Benchmark integrity

Scoring logic must be inspectable and stable. A slightly longer function is acceptable if it keeps rubric behavior obvious.

### Reproducibility

Outputs should be reproducible from the same inputs, seeds, and flags. Name those parameters explicitly.

### Auditability

Reviewers should be able to trace a metric back to records or logs. Preserve task IDs and source metadata through transformations.

### Small-batch maintainability

This is a project repo, not a platform. Prefer directness over architecture. Organize files by artifact purpose.

## Suggested module boundaries

- `io_*` or `load_*` helpers for reading artifacts
- evaluator modules for score logic
- dedicated validation scripts for split or contamination checks
- dedicated formatting scripts for training exports

Avoid a generic catch-all `helpers.py` if the functions naturally belong next to the artifact they support.
