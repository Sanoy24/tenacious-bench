---
name: tenacious-contamination-guard
description: Protect Tenacious-Bench split integrity and contamination resistance. Use when an agent is partitioning tasks, sealing held-out data, checking overlap between train and held_out, validating public-signal time windows, documenting contamination controls, or reviewing whether benchmark artifacts are too similar across splits.
---

# Tenacious Contamination Guard

## Overview

Treat held-out integrity as a product feature, not a cleanup task.

Read `references/heldout-rules.md` when creating or reviewing split logic.

## Workflow

### 1. Protect the held-out slice first

Keep held-out separated in both file layout and workflow. Training and bulk iteration scripts should not casually read from it.

### 2. Run the three required checks

Check:

- n-gram overlap
- embedding similarity
- time-shift validity for public-signal tasks

Document thresholds and keep them stable.

### 3. Check semantic duplication, not just literal duplication

Two tasks can differ on the surface and still be effectively the same benchmark item. Review similar tasks for diagnostic uniqueness.

### 4. Track provenance

Preserve:

- source mode
- seed artifact
- public signal window
- contamination check outputs
- reasons for any manual overrides

### 5. Be suspicious of convenience

If a split choice feels too convenient for training performance, it probably deserves extra scrutiny.

## Output Shape

Prefer a contamination report that states:

- partitions checked
- thresholds used
- violations found
- overrides applied
- final pass or fail conclusion

## Practical Defaults

- Assume near-duplicates are harmful until proven otherwise.
- Keep held-out small enough to protect, large enough to measure.
- Treat contamination prevention as part of publication readiness, not just methodology prose.
