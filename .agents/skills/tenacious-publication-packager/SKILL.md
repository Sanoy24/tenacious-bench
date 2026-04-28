---
name: tenacious-publication-packager
description: Package Tenacious-Bench outputs into public, reviewer-friendly artifacts. Use when an agent is preparing a Hugging Face dataset or model card, datasheet, README, technical blog draft, publication checklist, executive memo support files, or community-engagement materials for this project.
---

# Tenacious Publication Packager

## Overview

Ship public artifacts that are clear, reproducible, and not embarrassing a day later.

Read `references/public-artifact-checklist.md` before finalizing anything that will leave the repo.

## Workflow

### 1. Start with reproducibility

A stranger should be able to understand what the artifact is, how it was built, and how to reproduce the headline result.

### 2. Package the benchmark, not just the files

Include:

- what the benchmark measures
- how the partitions work
- what the evaluator expects
- what the baseline is
- what the known limitations are

### 3. Keep the public story honest

The blog post, README, model card, and memo should all agree on the same core facts.

### 4. Check the boring details

Verify license, attribution, seed handling, sealed-slice rules, and artifact links before publishing.

### 5. Write for an external reader

Assume the reader does not know the cohort context. Name the problem, the method, the result, and the caveats plainly.

## Output Shape

Prefer concise, linked artifacts over narrative sprawl:

- README with quickstart
- datasheet with real substance
- model card where applicable
- blog draft with evidence-backed claims
- community artifact text that points to the benchmark gap and contribution

## Practical Defaults

- Public artifact quality is part of the grade.
- A smaller, cleaner publication beats a sprawling under-explained one.
- Treat consistency across artifacts as a release requirement.
