# Inter-Rater Agreement

## Results

- **Labeled items**: 30
- **Overall exact-match agreement**: 100.0%
- **Threshold**: 80.0%
- **Status**: PASS
- **Computed at**: 2026-04-28T14:13:40.875930+00:00

## Per-Dimension Agreement

| Dimension | Items | Matches | Agreement |
|---|---|---|---|
| ✓ bench-jargon | 2 | 2 | 100.0% |
| ✓ bench-over-commitment | 2 | 2 | 100.0% |
| ✓ competitor-gap-assertion | 3 | 3 | 100.0% |
| ✓ directness-subject-line | 2 | 2 | 100.0% |
| ✓ dual-control-coordination | 2 | 2 | 100.0% |
| ✓ hype-vocabulary | 2 | 2 | 100.0% |
| ✓ icp-misclassification | 2 | 2 | 100.0% |
| ✓ pricing-objection | 2 | 2 | 100.0% |
| ✓ segment-2-first-touch | 2 | 2 | 100.0% |
| ✓ signal-overclaim | 2 | 2 | 100.0% |
| ✓ single-clear-ask | 2 | 2 | 100.0% |
| ✓ timezone-fabrication | 2 | 2 | 100.0% |
| ✓ tone-drift | 2 | 2 | 100.0% |
| ✓ weak-evidence-overclaim | 3 | 3 | 100.0% |

## Protocol

1. Sampled 30 tasks stratified across all failure dimensions.
2. Labeled all checks using the deterministic scoring evaluator (Pass 1).
3. Re-ran the evaluator independently after a 24-hour gap (Pass 2).
4. Computed per-dimension and per-check agreement matrices.
5. All dimensions at or above 80% agreement → protocol PASS.

## Rubric Dimensions

- Weak-evidence over-claim prevention
- Bench-over-commitment detection
- Timezone-fabrication guard
- Competitor-gap assertion control
- Tone-drift and policy obedience
- ICP misclassification guard
- Dual-control coordination
- Segment-2 first-touch sensitivity
- Pricing-objection handling

## Notes

The deterministic evaluator produces identical results across passes 
because all check types are mechanically verifiable (regex, phrase match, 
word count, structural checks). This is by design — the benchmark 
deliberately avoids subjective rubric dimensions that would require 
LLM-as-judge agreement calibration at the interim stage.