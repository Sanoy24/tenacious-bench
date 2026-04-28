# Python Patterns

## Default posture

Use modern Python, but keep the code plain. This repo benefits more from clarity and reproducibility than from abstraction density.

## Recommended building blocks

- `pathlib.Path` for filesystem work
- `dataclasses.dataclass` for structured in-memory records
- `typing.TypedDict` for JSON payloads that mirror benchmark records
- `argparse` for scripts with file inputs or flags
- `json` and `csv` from the standard library before heavier dependencies
- `logging` when a script has multiple stages or long-running work

## Function shape

Prefer short functions with one job:

- parse or load data
- validate required fields
- transform records
- score outputs
- summarize metrics
- write results

Keep orchestrators thin and helpers reusable.

## Data validation

Validate early when reading external or generated data. Fail fast on missing required fields such as task IDs, source modes, rubric entries, or partition names.

When data quality can vary, return explicit validation errors rather than silently coercing everything.

## CLI shape

For scripts, follow this outline:

1. parse args
2. resolve paths
3. load inputs
4. run pure logic helpers
5. write outputs
6. return a meaningful exit code

## Comments

Comment the why, not the what. Good places for comments in this project:

- why a contamination threshold was chosen
- why a rubric dimension is scored a certain way
- why a dataset transformation preserves or drops a field

## Dependency restraint

Add a package only when:

- the standard library would be awkward or error-prone
- the dependency is already common for the task domain
- the value is durable, not one-off

For validation-heavy schemas, `pydantic` can be justified. For simple records, prefer dataclasses plus explicit checks.
