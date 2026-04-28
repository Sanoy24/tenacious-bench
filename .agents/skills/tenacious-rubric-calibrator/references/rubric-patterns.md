# Rubric Patterns

## Good rubric shape

Each dimension should answer:

- What is being graded?
- What evidence is allowed?
- What passes?
- What fails?
- How is the score encoded?

## Useful Tenacious-style dimensions

- Grounded signal usage
- Tone adherence
- Specificity versus generic filler
- CTA quality
- Constraint obedience
- Hallucination avoidance

## Judge prompt rule

If using an LLM judge, define the scale and the evidence source. Do not ask for a pure vibe check.

## Common fixes

- Split one overloaded dimension into two
- Convert a subjective rule into a banned-list or required-field check
- Add one positive and one negative example
- Remove duplicate dimensions that measure the same thing
