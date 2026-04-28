# Held-Out Rules

## Required checks

Run all three:

- n-gram overlap
- embedding similarity
- time-shift validation

## Split discipline

- Keep held-out in a separate location.
- Do not let bulk training scripts consume it.
- Record any manual movement of tasks across partitions.

## Override rule

If a task barely passes a threshold but still feels like a duplicate, treat reviewer judgment as a reason to exclude it or rewrite it.
