---
name: tenacious-bench-builder
description: Build or extend Tenacious-Bench and its supporting Week 11 artifacts for the Sales Agent Evaluation Bench challenge. Use when an agent needs to turn Week 10 sales-agent traces, probes, style guidance, or public-signal inputs into a machine-verifiable benchmark, scoring evaluator, partitioned dataset, contamination checks, training-data prep, methodology docs, or publication-ready benchmark collateral.
---

# Tenacious Bench Builder

## Overview

Turn the challenge brief into a concrete delivery loop: audit the Week 10 evidence, design a machine-verifiable schema, author the dataset, enforce contamination and quality gates, and prepare the training/evaluation artifacts without drifting into vague benchmark language.

Keep the evaluator and the dataset structure ahead of bulk generation. If a rubric cannot be scored mechanically, tighten it before authoring more tasks.

Read only the reference file that matches the current step:

- `references/challenge-map.md` for deliverables, hard constraints, and sequencing.
- `references/dataset-playbook.md` for task mix, rubric design, partitions, and quality gates.
- `references/path-selection.md` for mapping Week 10 failure evidence to Path A, B, or C.

Use `scripts/validate_bench_layout.py` after creating or revising dataset partitions to confirm the bench folder is structurally sane and that task metadata is present.

## Workflow

### 1. Inventory the evidence first

Start from the Week 10 artifacts before inventing anything:

- `trace_log.jsonl` for trace-derived tasks and path justification.
- `probe_library.md` for adversarial seeds and expansion axes.
- `failure_taxonomy.md` for benchmark dimensions and rubric categories.
- style-guide examples, briefs, pricing sheets, and synthetic transcripts for grounding fields.

If the repo does not yet contain those artifacts, state the gap clearly and build the next artifact around whatever evidence is available instead of pretending the corpus exists.

### 2. Decide the immediate target artifact

Choose one artifact and optimize for forward progress on that artifact:

- `audit_memo.md` when the current need is problem framing and gap analysis.
- `schema.json` plus `scoring_evaluator.py` when the current need is benchmark definition.
- `tenacious_bench_v0.1/` when the current need is dataset authoring and partitioning.
- `training_data/` and `methodology_rationale.md` when the current need is path-specific training prep.
- public docs when the current need is packaging and publication.

Avoid scattering partial drafts across every deliverable at once. Finish the dependency chain in order: audit -> schema/evaluator -> dataset -> training prep -> ablations/publication.

### 3. Make the rubric mechanically gradable

Rewrite fuzzy benchmark language into explicit checks. Prefer rules such as:

- presence or absence of banned phrases
- required mention of a supplied signal
- structural requirements such as CTA or calendar link
- extracted fields that can be matched exactly
- judge-scored dimensions with a named rubric and a calibrated threshold

Do not let "on-brand" or "good outreach" remain an unscored intuition. Every task should carry enough rubric detail that the evaluator can return a score without a human in the loop.

### 4. Author tasks across the four modes

Target the challenge mix unless the evidence argues for a different weighting:

- about 30% trace-derived
- about 30% programmatic sweeps
- about 25% multi-LLM synthesis
- about 15% hand-authored adversarial

Stamp each task with machine-readable metadata at creation time:

- `task_id`
- `dimension`
- `difficulty`
- `source_mode`
- `seed_artifact`
- `public_signal_window` when external data matters
- `judge_scores` or filtering evidence when applicable

### 5. Enforce quality gates before calling the dataset done

Before a task enters the final dataset, check:

1. Input coherence
2. Ground-truth verifiability
3. Rubric-application clarity
4. Contamination separation from the training split
5. Preference-leakage avoidance when LLM generation and judging are both involved

Use a different model family for generation and judgment whenever possible. Document the rotation policy in methodology notes rather than leaving it implicit.

### 6. Partition with intent

Keep the benchmark split aligned with the brief:

- `train`: 50%
- `dev`: 30%
- `held_out`: 20%

Seal the held-out slice conceptually and operationally. Do not let training scripts read from it. Release only what the project plan allows.

Run `python scripts/validate_bench_layout.py <bench-dir>` after each major dataset revision.

### 7. Pick the training path from failure evidence

Let the Week 10 failure mode choose the intervention:

- choose Path A when the issue is generation quality, tone drift, or weak signal grounding
- choose Path B when the system is often wrong and also bad at noticing it
- choose Path C when locally plausible steps compound into bad outcomes over a trajectory

Cite concrete trace IDs and the papers that support the choice. Treat the path declaration as an evidence-backed engineering decision, not a preference.

### 8. Keep the public artifacts honest

Report Delta A, Delta B, and cost/latency tradeoffs even when the result is disappointing. A trained component that loses to a careful prompt is still a valid result if the evidence is clear and reproducible.

## File Conventions

Prefer this layout unless the repo already has a stronger local convention:

```text
audit_memo.md
schema.json
scoring_evaluator.py
methodology.md
methodology_rationale.md
tenacious_bench_v0.1/
  train/
  dev/
  held_out/
generation_scripts/
training_data/
ablations/
synthesis_memos/
```

If a different layout already exists, adapt to it and keep names consistent enough that a reviewer can find the required artifacts quickly.

## Practical Defaults

- Keep the benchmark between 200 and 300 tasks unless the user explicitly decides otherwise.
- Build the evaluator before scaling synthesis volume.
- Reuse Week 10 traces as the highest-fidelity source.
- Spend human time on adversarial tasks where originality matters most.
- Use the dev-tier judge for bulk filtering and the eval-tier judge for spot checks or sealed-slice evaluation.
- Log cost, seed, and model-route metadata as first-class outputs.
