---
name: tenacious-rubric-calibrator
description: Design, tighten, or review machine-verifiable scoring rubrics for Tenacious-Bench tasks. Use when an agent is creating or revising schema fields, scoring evaluator logic, judge prompts, rubric dimensions, banned-phrase checks, grounding requirements, or inter-rater agreement fixes for benchmark tasks in this project.
---

# Tenacious Rubric Calibrator

## Overview

Turn fuzzy sales-quality expectations into scoring rules another agent can apply consistently.

Read `references/rubric-patterns.md` when defining a new rubric or repairing a weak one.

## Workflow

### 1. Start from the failure mode

Name what the task is actually supposed to catch:

- missing grounded signal
- off-brand tone
- over-commitment
- weak CTA
- hallucinated company facts
- process failure masked by polished language

If the failure mode is unclear, clarify it before writing more scoring logic.

### 2. Split deterministic checks from judge checks

Prefer deterministic checks whenever possible:

- banned phrases
- required signal mentions
- required structural elements such as CTA or calendar link
- extracted fields that must match expected values
- length ceilings or formatting rules when relevant

Use an LLM judge only for the residue that cannot be scored reliably with rules, such as tone markers or nuanced alignment dimensions.

### 3. Make each dimension independently scorable

For each dimension, define:

- what evidence the evaluator reads
- what passes
- what fails
- what output shape the evaluator returns
- whether the check is deterministic or judge-based

Avoid one giant `quality` bucket.

### 4. Calibrate for consistency

When a rubric feels subjective:

- add positive and negative examples
- reduce overlapping dimensions
- sharpen threshold language
- specify which supplied artifacts count as valid evidence

If inter-rater agreement is weak on a dimension, rewrite the rubric before scaling the dataset.

### 5. Keep the evaluator honest

The rubric must be detailed enough that `scoring_evaluator.py` can apply it without hidden human judgment.

When you use a judge prompt:

- state the scale clearly
- define each score level briefly
- tell the judge what evidence sources are allowed
- require short rationale fields if that helps debugging

## Output Shape

Prefer rubric artifacts that are easy to code against:

- named dimensions
- threshold values
- allowed evidence fields
- explicit pass/fail or numeric scoring rules
- examples only when they reduce ambiguity

## Practical Defaults

- Keep dimension names short and stable.
- Prefer several narrow dimensions over one vague holistic grade.
- Use deterministic checks first.
- Treat weak inter-rater agreement as a rubric bug, not a labeling inconvenience.
