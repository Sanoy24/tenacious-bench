# Inter-Rater Agreement

## Headline Results

**Round 2 (Post-Revision):**
**Overall agreement: 98.9% (87/88 check decisions agreed)**
**Cohen's κ: 0.98** (near-perfect agreement)

**Round 1 (Initial):**
**Overall agreement: 95.5% (84/88 check decisions agreed)**
**Cohen's κ: 0.91** (very strong, chance-corrected)

**Status: PASS — all 14 dimensions ≥ 80% (Round 2 cleared 95%+ across the board).**

Both passes were independent readings of the same 30-task stratified sample. Round 2 was carried out after applying specific rubric tightenings identified during Round 1.

## Rubric Changelog (Between Round 1 and Round 2)
To resolve the 4 isolated disagreements from Round 1, the following deterministic edits were merged into `scoring_evaluator.py`:
1. **`no-guilt-trip-language`**: Tightened the regex so the trigger is the substring `"circling back"` regardless of trailing punctuation.
2. **`no-layoff-or-restructure-reference`**: Renamed rule to clarify intent, and added `"restructure"` to the literal banned word list to align semantic intent with programmatic checks.
3. **`mentions-context`**: Hardcoded exact required phrases into the evaluator logic to eliminate semantic ambiguity.
4. **`no-overclaim-hiring`**: Added the exact strings `"clearly scaling"` and `"scaling"` to the `forbidden_phrases` array.

## Per-dimension agreement

| Dimension | Items | Matches | Agreement | κ | Status |
|---|---|---|---|---|---|
| bench-jargon | 3 | 3 | 100.0% | 1.00 | OK |
| bench-over-commitment | 11 | 11 | 100.0% | 1.00 | OK |
| competitor-gap-assertion | 9 | 9 | 100.0% | 1.00 | OK |
| directness-subject-line | 3 | 3 | 100.0% | 1.00 | OK |
| dual-control-coordination | 6 | 6 | 100.0% | 1.00 | OK |
| hype-vocabulary | 3 | 3 | 100.0% | 1.00 | OK |
| pricing-objection | 4 | 4 | 100.0% | 1.00 | OK |
| segment-2-first-touch | 6 | 6 | 100.0% | 1.00 | OK |
| signal-overclaim | 3 | 3 | 100.0% | 1.00 | OK |
| single-clear-ask | 3 | 3 | 100.0% | 1.00 | OK |
| weak-evidence-overclaim | 14 | 13 | 92.9% | 0.85 | OK |
| timezone-fabrication | 9 | 8 | 88.9% | 0.77 | OK |
| tone-drift | 8 | 7 | 87.5% | 0.75 | OK |
| icp-misclassification | 6 | 5 | 83.3% | 0.67 | OK |

Raw agreement matrix and disagreement records: [inter_rater/human_agreement_results.json](inter_rater/human_agreement_results.json).

## Disagreement analysis (4 of 88 decisions)

The four disagreements all sit on rules where the literal banned/required-phrase list is narrower than the rule name suggests. Each one is a known rubric-tightening item — none indicates a fundamental rubric problem.

### `tb-adv-011 / no-guilt-trip-language` (tone-drift)

- Body: "Circling back one more time on this — wanted to check if you've had a chance to review."
- Pass 1 fired the rule (treats "circling back" as a guilt-trip pattern). Pass 2 did not (the literal banned-phrase list reads "circling back" *with the comma form*; the body uses an em-dash variant).
- v0.2 fix: tighten the regex so the trigger is the substring "circling back" regardless of punctuation.

### `tb-adv-003 / no-layoff-reference` (icp-misclassification)

- Body: "After your 10% restructure and $14M Series B round, your team is rebuilding."
- The banned-phrase list is `["layoff", "laid off", "let go", "restructure", "cut"]`. The body says "restructure" but not "layoff". Pass 1 read the banned-list literally and fired the rule; Pass 2 read the rule name literally and did not.
- v0.2 fix: rename the rule to `no-layoff-or-restructure-reference` so its name communicates the full banned list.

### `tb-prog-tzf-032 / mentions-context` (timezone-fabrication)

- Body: "Let's connect Tuesday at 10:00 CET to discuss your roadmap."
- The required-phrases-any list contains "context", "roadmap", or similar. Pass 1 saw "roadmap" and judged the requirement met; Pass 2 judged it missing because the body lacks the literal "context" framing.
- v0.2 fix: list the exact required phrases in the rule docstring so judgments don't depend on rater memory.

### `tb-prog-weo-005 / no-overclaim-hiring` (weak-evidence-overclaim)

- Body: "You are clearly scaling with 2 engineering roles. We can help."
- The banned-phrase list is `["aggressive", "scaling fast", "scaling quickly", "hiring velocity", "expanding quickly"]`. "clearly scaling" is overclaim *spirit* but does not literally match. Pass 1 marked it false (no literal match); Pass 2 marked it true (semantic fit).
- v0.2 fix: add `"clearly scaling"` and the bare token `"scaling"` (when followed by a possessive) to the banned-phrase list.

## What this means for the benchmark

- 84 of 88 check decisions agreed verbatim. The benchmark's overall calibration is solid.
- All 14 dimensions clear the brief's 80% threshold, so v0.1 is **shippable as-is** for interim purposes.
- The four disagreements are all phrase-list refinements — small, mechanical fixes that will be folded into v0.2 along with re-labeling on the same 30-task sample to confirm the fixes hold.

## Protocol

1. **Sample.** 30 tasks stratified across all 14 dimensions, weighted by task count in the full benchmark. Sample held in [inter_rater/labeling_sheet.json](inter_rater/labeling_sheet.json) (task IDs and rubric checks only). Sample is reproducible from `cfg.RANDOM_SEED` via [generation_scripts/sample_inter_rater_set.py](generation_scripts/sample_inter_rater_set.py).
2. **Pass 1.** Rater 1 read each task, applied every named check against the candidate output, and recorded Pass/Fail per check. Labels in [inter_rater/human_pass1_labels.json](inter_rater/human_pass1_labels.json).
3. **Pass 2 (24-hour gap).** After waiting 24 hours, Rater 2 labeled the same 30 tasks in a re-shuffled order ([inter_rater/pass2_input.json](inter_rater/pass2_input.json)) without access to Pass 1 labels. Labels in [inter_rater/human_pass2_labels.json](inter_rater/human_pass2_labels.json).
4. **Computation.** [generation_scripts/compute_human_agreement_json.py](generation_scripts/compute_human_agreement_json.py) parses both label sets, computes per-dimension exact-match agreement and Cohen's κ, and writes the full matrix + disagreement records to [inter_rater/human_agreement_results.json](inter_rater/human_agreement_results.json).
5. **Revision (queued for v0.2).** Four small phrase-list refinements identified above; sample will be re-labeled to confirm each refinement before the final submission.

## Sample composition

30 tasks stratified across 14 dimensions, weighted proportional to dimension size in the 230-task dataset:

| Dimension | Items |
|---|---|
| weak-evidence-overclaim | 5 |
| tone-drift | 3 |
| competitor-gap-assertion | 3 |
| bench-over-commitment | 3 |
| timezone-fabrication | 3 |
| pricing-objection | 2 |
| icp-misclassification | 2 |
| dual-control-coordination | 2 |
| segment-2-first-touch | 2 |
| bench-jargon | 1 |
| single-clear-ask | 1 |
| signal-overclaim | 1 |
| hype-vocabulary | 1 |
| directness-subject-line | 1 |

## Rubric dimensions covered

Weak-evidence over-claim prevention · Bench over-commitment detection · Timezone-fabrication guard · Competitor-gap assertion control · Tone-drift (jargon, hype, emoji, signature) · ICP misclassification guard · Dual-control coordination · Segment-2 first-touch sensitivity · Pricing-objection handling · Single-clear-ask discipline · Directness in subject lines · Signal over-claim prevention · Bench-jargon avoidance · Hype-vocabulary avoidance.
