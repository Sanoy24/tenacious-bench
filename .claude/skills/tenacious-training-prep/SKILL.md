---
name: tenacious-training-prep
description: Convert Tenacious-Bench artifacts into high-quality training inputs for Path A, Path B, or Path C. Use when an agent is formatting chat pairs, preference pairs, step-level labels, quality filters, or path-specific training partitions for LoRA, judge training, or process reward modeling in this project.
---

# Tenacious Training Prep

## Overview

Good training runs start with disciplined training data, not optimistic hyperparameters.

Read `references/path-formats.md` before building or filtering training data.

## Workflow

### 1. Choose the path from evidence

Do not prepare all three formats just in case. Build the format that matches the chosen intervention.

### 2. Filter before formatting

Prefer fewer cleaner examples over many noisy ones. Remove:

- broken records
- ambiguous labels
- low-confidence rewrites
- examples that conflict with the current rubric
- contamination risks against dev or held-out

### 3. Format for the selected path

- Path A: clean input/output chat pairs
- Path B: chosen/rejected preference pairs with leakage-aware generation
- Path C: stepwise trajectories with intermediate correctness labels

Keep formatting explicit and reproducible.

### 4. Preserve provenance

Carry forward:

- source task IDs
- rewrite origin
- quality filter reason
- path designation
- split origin

### 5. Treat flat ablations as a data warning

If a training run does not lift, inspect the training data before touching compute or prompts.

## Output Shape

Prefer machine-friendly exports and a small methodology note that explains:

- what was included
- what was filtered out
- which model family produced any rewrites
- how preference leakage was avoided when relevant

## Practical Defaults

- Quality beats quantity at this project scale.
- Keep path-specific formats simple and inspectable.
- Reuse the evaluator to filter training examples whenever possible.
