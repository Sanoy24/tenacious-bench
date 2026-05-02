# Tenacious-Bench Methodology

## Objective

Build `Tenacious-Bench v0.1`, a machine-verifiable benchmark for Tenacious-style B2B sales outreach. The benchmark is designed to catch production-relevant failures that a generic public benchmark does not grade well: weak-evidence assertion, bench over-commitment, tone-marker drift, timezone fabrication, and condescending use of competitor-gap research.

## Week 10 Seed Corpus

This benchmark uses the following Week 10 artifacts as the evidence base:

- `week10-data/eval/trace_log.jsonl` — 1,800+ lines of agent simulation outcomes
- `week10-data/eval/probes/probe_library.md` — 37 adversarial probes
- `week10-data/eval/probes/probe_results.json` — actual trigger rates from probe runner
- `week10-data/eval/probes/failure_taxonomy.md` — 10-category failure classification
- `week10-data/outputs/hiring_signal_brief.json`
- `week10-data/outputs/competitor_gap_brief.json`
- `week10-data/layoffs.csv`
- `week10-data/crunchbase_odm_sample.json`
- `week10-data/tenacious_sales_data/seed/` — style_guide.md, icp_definition.md, bench_summary.json, pricing_sheet.md, case_studies.md

## Audit Summary

The highest-concentration failure family is **over-claiming under weak evidence**. The strongest supporting probes:

| Probe | Category | Trigger Rate | Severity |
|---|---|---|---|
| P007 | Signal over-claiming | 3/3 (100%) | P0 |
| P011 | Signal over-claiming | 3/3 (100%) | P1 |
| P027 | Timezone fabrication | 3/3 (100%) | P0 |
| P032 | Gap over-claiming | 3/3 (100%) | P0 |
| P023 | Dual-control coordination | 41/150 (27%) | P0 |
| P024 | Dual-control coordination | 26/150 (17%) | P0 |
| P005 | ICP misclassification | 1/1 (DET:FAIL) | P1 |
| P034 | Gap over-claiming | 1/1 (DET:FAIL) | P0 |

Five concrete Week 10 trace IDs used as preliminary evidence:

- `879ee1fc-7a7f-438e-bb19-054fb43c8637`
- `88bb3cea-1599-471c-9609-27736556d1e0`
- `09f0188f-8567-4e62-b62c-08cc164774e5`
- `ac397276-2c37-4026-94cc-39dc39ac52fa`
- `7463faab-f29c-4617-8229-802300c83c30`

All five are zero-reward traces supporting the "assert before evidence is sufficient" diagnosis.

## Path Declaration

**Path B — Preference-tuned judge/critic (locked).**

Justification: the Week 10 evidence points to an **inconsistency problem**, not a pure generation-quality problem. Probes P007, P011, P027, and P032 show that the system sometimes follows policy and sometimes does not on very similar inputs. The zero-reward traces suggest the agent fails to recognize when available evidence does not justify a strong action or claim. A judge/critic layer is the most defensible intervention for Week 11.

### Paper-grounded rationale for Path B

Two required-reading papers directly inform this choice:

**1. Gu et al., "A Survey on LLM-as-a-Judge" (arXiv:2411.15594)**

Section 4 of the survey catalogues the systematic biases that afflict untuned LLM judges: concreteness bias (favoring specific, confident-sounding answers), authority bias (favoring outputs with numeric claims), and position bias (favoring whichever option is presented first). These are precisely the biases that explain the Week 10 failure pattern. When the sales agent over-claims — asserting hiring velocity on a LOW-confidence signal, fabricating a prospect's local time, or framing a competitor gap as a diagnosis — the outputs *sound more confident and specific*. An untuned judge would reward exactly these properties.

Path B is the direct response to this finding: instead of adding an off-the-shelf judge call, we train a judge/critic on preference pairs derived from the Week 10 probe failures. The training signal is grounded in the failure taxonomy, not in generic "quality" labels. This directly counters the concreteness and authority biases that would otherwise cause a generic judge to grade Tenacious failures as successes.

Section 5 of the survey further shows that multiple evaluation rounds (more robust than single judge calls) and structured rubric scoring (more reliable than freeform narrative) are the improvements with the most consistent empirical support. The scoring evaluator's deterministic check structure embodies exactly this: structured, repeatable, multi-check rubrics rather than single LLM opinion calls.

**2. Liu et al., "Best Practices and Lessons Learned on Synthetic Data for Language Models" (arXiv:2404.07503, COLM 2024)**

Section 4 of this paper explicitly warns that *synthetic alignment data can misrepresent human values* and that this risk is especially high when the labeled pairs are not grounded in real behavioral evidence. The Week 10 evidence provides that grounding: the zero-reward traces and 100% probe trigger rates on P007/P011/P027/P032 give us real failure examples that anchor the preference pairs for Path B training. Without that grounding, preference labels constructed from synthetic variation would risk training a critic that rewards surface-level policy compliance (e.g., avoiding the literal word "aggressively") rather than genuine evidence-calibrated reasoning.

Liu et al. also distinguish between *coverage* and *fidelity* in synthetic data (Section 3). Coverage without fidelity produces noisy training signal; fidelity without coverage produces a brittle model. This distinction directly informed the four-mode generation strategy: programmatic sweeps provide coverage (controlled combinatorial variation), trace-derived tasks provide fidelity (grounded in real failure evidence), and adversarial tasks stress-test the decision boundary. Path B preference pairs are generated in the same priority order: trace-derived pairs first, programmatic second, adversarial third — fidelity before coverage.

## Task Authoring Modes

| Mode | Actual (Interim) | Script | API Cost |
|---|---|---|---|
| Programmatic sweeps | 79 tasks (33%) | `programmatic_generator.py` | $0.00 |
| Trace-derived | 68 tasks (28%) | `trace_derived_generator.py` | $0.00 |
| Multi-LLM synthesis | 56 tasks (23%) | `multi_llm_synthesis.py` | logged in `generation_scripts/synthesis_cost_log.json` |
| Hand-authored adversarial | 39 tasks (16%) | `hand_authored_adversarial.py` | $0.00 |

**Total: 242 tasks.** Mix tracks the brief's targets (≈30/30/25/15) within ±3pp on every mode.

### Programmatic Sweeps
Combinatorial expansion across 9 failure dimensions using seed data. Varies: signal type, confidence level, company size, stack, thread context. Deterministic — zero randomness in check application.

### Trace-Derived
Extracts failure patterns from actual Week 10 probe results (P007, P011, P027, P032, P023/P024, P005). Each task links back to the source trigger rate and probe ID.

### Multi-LLM Synthesis

Four-stage pipeline documented in `generation_scripts/multi_llm_synthesis.py`:

1. **Hard seeds** — eval-tier model (`anthropic/claude-sonnet-4-6`) authors 40 high-difficulty edge-case tasks spread across all 9 dimensions. These are the hardest seeds anchored to the Week 10 failure taxonomy.
2. **Bulk generation** — dev-tier generator (`deepseek/deepseek-chat-v3-0324`) fills remaining quota per dimension via combinatorial variation.
3. **Judge filter** — cheap dev-tier judge (`google/gemini-2.0-flash-001`) scores every task on three dimensions (1–5 each): `input_coherence`, `ground_truth_verifiability`, `rubric_clarity`. Thresholds: all ≥ 3. Tasks below any threshold are dropped.
4. **Pairwise dedup** — within each dimension, pairs of tasks with `SequenceMatcher` ratio > 0.75 on `candidate_output.body` are sent to the cheap judge for pairwise comparison; the less diagnostic task is dropped.
5. **Spot-check calibration** — 50 accepted tasks are re-scored with the eval-tier model. Results written to `synthesis_calibration_log.json` for methodology documentation (calibration only — does not gate tasks).

**Model-family rotation policy (preference-leakage prevention — Li et al. 2025):**

- Hard-seed generator : eval-tier family (Anthropic)
- Bulk generator      : dev-tier A (DeepSeek)
- Judge (filtering)   : dev-tier B (Google)
- Spot-check judge    : eval-tier family (Anthropic)

Generator and judge are always from different model families. The eval-tier model is never used as a bulk generator.

**Model role → risk profile mapping:**

| Role | Model | Cost tier | Primary bias risk | Primary failure mode |
|---|---|---|---|---|
| Hard-seed generator | claude-sonnet-4-6 | High | Self-preference on Anthropic outputs | Narrow stylistic range |
| Bulk generator | deepseek-chat-v3-0324 | Low | Instruction-following over originality | Template repetition |
| Judge (filter) | gemini-2.0-flash-001 | Low | Verbosity/length bias | Passing over-specific tasks that sound plausible |
| Spot-check judge | claude-sonnet-4-6 | High | Familiarity with own seed style | Over-accepting hard seeds |

The rotation policy directly counters the top risk in each column: using a different family for generation and judging prevents the judge from rewarding outputs that match its own generation style.

All costs logged to `generation_scripts/synthesis_cost_log.json`. Calibration results in `generation_scripts/synthesis_calibration_log.json`.

### Hand-Authored Adversarial
Manually crafted edge cases: multi-signal conflict, similar-stack trap, case study inflation, guilt-trip re-engagement, dual objection, emoji in cold outreach, signature bloat. Highest originality.

## Failure Dimensions

| Dimension | Tasks (Interim) | Probe IDs |
|---|---|---|
| weak-evidence-overclaim | 39 | P007, P008, P009, P011 |
| bench-over-commitment | 26 | P012, P013, P014 |
| tone-drift | 30 | P015, P016, P017, P035 |
| competitor-gap-assertion | 26 | P032, P034 |
| timezone-fabrication | 25 | P026, P027 |
| icp-misclassification | 19 | P001, P005, P006 |
| dual-control-coordination | 16 | P023, P024, P025 |
| segment-2-first-touch | 12 | P010 |
| pricing-objection | 12 | — |
| signal-overclaim | 10 | P020, P036 |
| directness-subject-line | 8 | — |
| bench-jargon | 6 | P015 |
| single-clear-ask | 3 | — |
| hype-vocabulary | 10 | — |

## Partition Protocol

Final split: **train 50% (121) / dev 30% (73) / held_out 20% (48)** — tracks the 50/30/20 target within ±1pp on every partition.

Pipeline:

1. `assemble_partitions.py` — merge all 4 generator outputs, dedupe by `task_id`, then by SHA-256 content hash on input fields, then stratified split by dimension.
2. `repartition.py` — second pass that builds a **near-duplicate component graph** over all assembled tasks (edge iff two tasks share any 8-gram on input *values* OR have cosine similarity > 0.85), then assigns whole components to partitions. This guarantees no contamination edge crosses a partition boundary — programmatic-template siblings stay together.

The component pass was added after the first contamination run flagged 334 within-template-family overlaps (mostly programmatic boilerplate); after re-partitioning, the contamination check returns 0 violations on all four checks.

## Contamination Protocol

Four checks run after partitioning, all on the **values of input fields only** (JSON keys / schema scaffolding stripped):

1. **N-gram overlap** — no shared 8-grams on input values across any partition pair.
2. **Embedding similarity** — cosine < 0.85 between any cross-partition pair (all-MiniLM-L6-v2).
3. **Content hash** — no duplicate input payloads across partitions.
4. **Temporal integrity (Time-Shift Verification)** — only tasks that explicitly declare a public-data source (via `metadata.signal_source` ∈ {`layoffs.fyi`, `crunchbase`, `sec_edgar`, …}) must carry a valid `metadata.time_window`. 
   * **Explicit Signal Window Assumption:** For v0.1, we assume the valid signal window for time-sensitive public data is strictly between the years **2024 and 2026**. 
   * **Inclusion Gating:** Any task referencing a public data source without a time window, or with a time window that falls outside this explicitly allowed 2024-2026 boundary (e.g., historical 2022 data), is strictly gated and excluded from the final partitions to prevent temporal leakage. Synthetic-signal tasks are exempted.

**Current status: PASS, 0 violations** across all four checks. Report committed to `contamination_check.json`. Re-running `repartition.py` is the canonical way to regenerate partitions if new tasks are added.

## Scoring Design

`scoring_evaluator.py` implements 13 deterministic check types:

| Check Type | Description |
|---|---|
| `forbidden_phrases` | Banned words/phrases in target field |
| `required_phrases_any` | At least one required phrase present |
| `forbidden_regex` | Regex-based policy checks |
| `max_words` | Word count ceiling (120 for cold outreach) |
| `max_question_marks` | One-clear-ask enforcement |
| `no_prospect_local_when_timezone_missing` | Timezone fabrication guard |
| `no_unavailable_stack_commitment` | Bench capacity guard |
| `icp_segment_size_guard` | Company size threshold for segments |
| `no_emoji_in_cold_outreach` | Emoji ban in cold emails |
| `signature_format_check` | Signature line count limit |
| `requires_confirmation_before_action` | Dual-control confirmation |
| `requires_auth_verification` | Identity verification before action |
| `no_fabricated_identifiers` | No fabricated order/reference IDs |

## Inter-Rater Agreement

A stratified 30-task sample covering all 14 failure dimensions was hand-labeled twice with a 24-hour gap and a re-shuffled task order, with no access to Pass 1 labels during Pass 2.

Overall agreement: **95.5%** (84/88 check decisions agreed). Cohen's κ: **0.91**. **All 14 dimensions clear the brief's 80% threshold**, so v0.1 ships as-is for the interim submission.

The four remaining disagreements all sit on rules where the literal banned/required-phrase list is narrower than the rule name suggests — small phrase-list refinements queued for v0.2. Full per-dimension matrix, disagreement records, and revision plan in [inter_rater_agreement.md](inter_rater_agreement.md).

## Ablation Baseline

The probe trigger rates from Week 10 establish the pre-intervention baseline that Path B is measured against:

| Probe | Failure | Trigger Rate (baseline) |
|---|---|---|
| P007 | Signal over-claiming | 3/3 (100%) |
| P011 | Signal over-claiming | 3/3 (100%) |
| P027 | Timezone fabrication | 3/3 (100%) |
| P032 | Gap over-claiming | 3/3 (100%) |
| P023 | Dual-control failure | 41/150 (27%) |
| P024 | Dual-control failure | 26/150 (17%) |

Delta A/B/C ablation results (base → judge-augmented → LoRA-tuned) will be added after Days 4–7 training runs complete. The target improvement per dimension is ≥20pp trigger-rate reduction on P007, P011, P027, and P032 — the four P0 probes that drove the Path B selection.

## Next Steps (Days 4–7)

1. Format preference pairs from scored tasks (chosen/rejected)
2. LoRA fine-tune judge model on Colab T4 with Unsloth
3. Run ablation: Delta A (base), Delta B (tuned), Delta C (improvement)
4. Publish dataset + model card to HuggingFace
5. Write 1,200–2,000 word blog post
6. Create 2-page decision memo with evidence graph
7. Record 6-minute demo video
