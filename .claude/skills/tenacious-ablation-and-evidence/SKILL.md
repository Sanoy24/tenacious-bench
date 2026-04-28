---
name: tenacious-ablation-and-evidence
description: Structure ablations, statistical comparisons, and evidence tracing for Tenacious-Bench results. Use when an agent is preparing Delta A, Delta B, or Delta C comparisons, held-out scoring traces, confidence intervals, cost or latency comparisons, evidence graphs, or benchmark claims for reports and publication in this project.
---

# Tenacious Ablation And Evidence

## Overview

Make performance claims that survive scrutiny.

Read `references/reporting-checklist.md` before writing results into the repo, memo, or blog.

## Workflow

### 1. Define the comparison cleanly

State exactly what differs between systems:

- trained component versus Week 10 baseline
- trained component versus prompt-only intervention
- Tenacious-specific gain versus any reused general benchmark reference
- cost and latency with and without the new component

### 2. Keep the sealed slice sealed

Use held-out evaluation sparingly and document every pass.

### 3. Tie every number to an artifact

Each reported claim should resolve to:

- task IDs
- raw traces
- evaluation outputs
- statistical summaries
- cost logs

### 4. Report negative results honestly

If Delta B is flat or negative, say so clearly. A cleanly measured non-win still teaches something.

### 5. Separate mechanism from vibes

Avoid language like `it feels better`. Prefer evidence such as lift by dimension, failure-mode reduction, confidence interval separation, and cost delta.

## Output Shape

Prefer:

- `ablation_results.json`
- `held_out_traces.jsonl`
- statistical test notes
- `evidence_graph.json`
- concise prose that cites the artifacts above

## Practical Defaults

- Compare one change at a time whenever possible.
- Keep raw scoring traces.
- Make the grader's skeptical questions easy to answer from files already in the repo.
