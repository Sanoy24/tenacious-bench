# Path Selection

## Choose Path A

Pick supervised fine-tuning of a generation component when the failure mode is mostly about output quality:

- tone drift
- weak personalization
- formulaic phrasing
- poor use of grounded signals

Evidence to cite:

- traces where the system had the right inputs but produced low-quality language
- style-guide violations
- benchmark failures that are mainly output-text failures rather than process failures

## Choose Path B

Pick a preference-tuned judge or critic when the agent is inconsistent and lacks self-correction:

- it often produces both good and bad answers for similar inputs
- it cannot reliably detect disallowed phrasing or missing grounding
- a rollback, reject, or re-rank layer would plausibly improve production outcomes

Evidence to cite:

- traces showing near-miss outputs
- repeated failure patterns where the generator sometimes succeeds
- production logic that would benefit from gating or rejection sampling

## Choose Path C

Pick a process reward model when the problem is mostly in the trajectory:

- locally acceptable decisions accumulate into a bad end state
- mid-conversation planning mistakes matter more than final phrasing
- recovery requires judging intermediate steps, not just final text

Evidence to cite:

- traces where the final failure starts several steps earlier
- probe sequences that reveal compounding errors
- cases where better end-text alone would not fix the outcome

## Decision rule

Do not pick a path because it sounds interesting. Pick the lightest intervention that directly addresses the dominant failure mode in the Week 10 evidence.
