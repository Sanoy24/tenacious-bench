---
name: tenacious-python-code
description: Write, review, or refactor Python code for the Tenacious Bench project using clean, modern, and maintainable patterns. Use when an agent is adding or editing Python modules, CLI scripts, evaluators, dataset builders, contamination checks, training-data preparation, or analysis utilities in this repo and needs consistent typing, structure, reproducibility, and clear error handling.
---

# Tenacious Python Code

## Overview

Write Python that is easy to trust a month later: typed, small in scope, deterministic where it matters, and boring in the good way.

Favor standard-library solutions first. Add a dependency only when it removes real complexity or matches a pattern already established in the repo.

Read `references/python-patterns.md` for implementation conventions and `references/repo-shape.md` for how those conventions map to this benchmark project.

## Workflow

### 1. Start from the artifact, not the abstraction

Identify what the file needs to do in this repo:

- score benchmark tasks
- generate or transform dataset records
- validate partitions and contamination checks
- prepare training examples
- summarize metrics or ablation outputs

Keep the design shaped around that job. Avoid building framework-like layers for one-off scripts.

### 2. Choose the smallest solid structure

Use:

- a few pure functions for transformations
- a small dataclass or `TypedDict` for record structure
- a `main()` entrypoint for scripts
- one level of orchestration, not three

Reach for classes only when there is durable state or multiple related operations sharing invariants.

### 3. Type the boundaries

Add type hints to:

- public functions
- dataclass fields
- return values from parsing and scoring helpers
- dictionary-like records that cross file boundaries

Prefer:

- `Path` over raw path strings
- `dataclass` for lightweight structured data
- `TypedDict` when interacting with JSON-like task payloads
- `Iterable` or `Sequence` when the exact container type does not matter

Avoid type noise that makes simple code harder to read.

### 4. Make scripts reproducible

For benchmark, training, and scoring utilities:

- accept explicit inputs and output locations
- avoid hidden global state
- pin random seeds when randomness exists
- sort outputs when order should be stable
- write JSON with consistent formatting
- log enough context to reproduce results

Do not bake credentials, model names, or local absolute paths into code.

### 5. Separate IO from logic

Keep parsing, filesystem access, and network calls thin. Put the actual scoring, filtering, normalization, and comparison logic into testable functions.

Good shape:

- `load_*()` functions read files
- `build_*()` or `score_*()` functions perform logic
- `write_*()` functions emit results
- `main()` wires them together

### 6. Handle errors like a teammate

Raise clear exceptions for programmer errors. For user-facing scripts, catch them near `main()` and print actionable messages.

Include the file path, task ID, or field name in error messages when possible.

Avoid broad `except Exception:` unless re-raising with useful context.

### 7. Keep data formats explicit

When working with JSON or JSONL benchmark data:

- document required fields near the parsing code
- validate important keys early
- tolerate optional metadata only when the downstream logic truly can
- preserve unknown fields unless the script is intentionally normalizing schema

If a schema is evolving, prefer additive changes over silent shape changes.

### 8. Write code that is easy to test

Prefer deterministic inputs and pure helpers so tests can cover:

- rubric scoring
- record normalization
- partition counting
- overlap or contamination checks
- training-data formatting

For small scripts, a few focused tests or a smoke-test command is enough. Broaden coverage when the code touches shared scoring behavior or publication artifacts.

### 9. Modern style defaults

Prefer:

- Python 3.11+ features already supported by the project
- f-strings
- `pathlib.Path`
- `collections.Counter`, `defaultdict`, and standard-library parsing tools
- comprehensions when they stay readable
- `argparse` for CLIs

Avoid:

- giant functions
- hidden mutation across helpers
- manual stringly-typed path handling
- ad hoc shelling out when Python can do the job directly
- clever one-liners that obscure benchmark logic

## Review Checklist

Before finishing Python changes, check:

1. Are names specific to benchmark or training intent?
2. Are inputs, outputs, and side effects obvious?
3. Is the core logic testable without touching the filesystem?
4. Are types present where another engineer would need them?
5. Will rerunning this script produce stable output?
6. Would a new teammate understand failures from the error messages?

## Practical Defaults For This Repo

- Keep benchmark scripts as plain modules or CLIs, not services.
- Use JSON or JSONL for task artifacts unless an existing format already wins.
- Keep scoring rules explicit and inspectable.
- Prefer small helper modules over one massive `utils.py`.
- Add comments only where benchmark methodology or scoring logic is non-obvious.
