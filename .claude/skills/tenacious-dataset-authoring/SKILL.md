---
name: tenacious-dataset-authoring
description: Create, expand, or review Tenacious-Bench tasks across the required authoring modes. Use when an agent is turning Week 10 traces, probe seeds, public-signal inputs, or sales artifacts into benchmark tasks, partition-ready records, metadata-rich JSON or JSONL examples, or adversarial cases for this project.
---

# Tenacious Dataset Authoring

## Overview

Author tasks that are diagnostic, not just plentiful.

Read `references/authoring-modes.md` before scaling task creation.

## Workflow

### 1. Start from a benchmark dimension

Tie each task to a named failure mode from the audit or taxonomy. Avoid tasks that look realistic but teach the benchmark nothing new.

### 2. Pick the right authoring mode

- use trace-derived tasks for fidelity
- use programmatic sweeps for coverage
- use multi-LLM synthesis for hard variants
- use hand-authored adversarial tasks for originality and edge cases

Do not default everything to synthesis.

### 3. Stamp metadata immediately

Every task should include:

- `task_id`
- `dimension`
- `difficulty`
- `source_mode`
- `seed_artifact`
- input payload fields
- rubric or rubric reference

If the task depends on a public signal, capture the relevant time window.

### 4. Favor diagnostic contrast

When expanding tasks, vary only a few levers at a time:

- segment
- company size
- hiring urgency
- signal confidence
- bench state
- AI maturity
- competitor context

That makes failures easier to explain and compare.

### 5. Filter before promoting

Before a task joins the dataset, confirm:

- the input is coherent
- the rubric can be applied
- the task is not a duplicate
- the task adds diagnostic value beyond existing records

## Output Shape

Prefer compact, reviewer-friendly records. Keep the text fields realistic, but keep metadata explicit and machine-readable.

## Practical Defaults

- Anchor to Week 10 evidence first.
- Expand one strong seed into a family of variants.
- Keep the held-out slice in mind while authoring so you do not backload all originality.
- Prefer fewer strong adversarial tasks over many shallow synthetic ones.
