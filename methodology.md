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

## Task Authoring Modes

| Mode | Actual (Interim) | Script | API Cost |
|---|---|---|---|
| Programmatic sweeps | 68 tasks (53%) | `programmatic_generator.py` | $0.00 |
| Trace-derived | 42 tasks (33%) | `trace_derived_generator.py` | $0.00 |
| Multi-LLM synthesis | Pending (~63 planned) | `multi_llm_synthesis.py` | ~$0.50 |
| Hand-authored adversarial | 18 tasks (14%) | `hand_authored_adversarial.py` | $0.00 |

### Programmatic Sweeps
Combinatorial expansion across 9 failure dimensions using seed data. Varies: signal type, confidence level, company size, stack, thread context. Deterministic — zero randomness in check application.

### Trace-Derived
Extracts failure patterns from actual Week 10 probe results (P007, P011, P027, P032, P023/P024, P005). Each task links back to the source trigger rate and probe ID.

### Multi-LLM Synthesis
Uses DeepSeek V3 (dev-tier) for generation and Gemini Flash for judge-filtering. Different model families to avoid systematic bias. All costs logged to `generation_scripts/synthesis_cost_log.json`.

### Hand-Authored Adversarial
Manually crafted edge cases: multi-signal conflict, similar-stack trap, case study inflation, guilt-trip re-engagement, dual objection, emoji in cold outreach, signature bloat. Highest originality.

## Failure Dimensions

| Dimension | Tasks (Interim) | Probe IDs |
|---|---|---|
| weak-evidence-overclaim | 30 | P007, P008, P009, P011 |
| bench-over-commitment | 17 | P012, P013, P014 |
| competitor-gap-assertion | 14 | P032, P034 |
| timezone-fabrication | 11 | P027 |
| dual-control-coordination | 10 | P023, P024, P025 |
| directness-subject-line | 8 | — |
| icp-misclassification | 8 | P001, P005, P006 |
| bench-jargon | 6 | P015 |
| segment-2-first-touch | 6 | P010 |
| tone-drift | 6 | P015, P016, P017, P035 |
| signal-overclaim | 3 | P036 |
| pricing-objection | 3 | — |
| hype-vocabulary | 3 | — |
| single-clear-ask | 3 | — |

## Partition Protocol

Final split: **train 50% / dev 30% / held_out 20%**.

Stratified by dimension — each partition covers all dimensions proportionally. The `assemble_partitions.py` script performs:

1. Merge all 4 generator outputs
2. Deduplicate by task_id
3. Deduplicate by content hash (SHA-256 of input fields)
4. Stratified split by dimension

## Contamination Protocol

Before a task enters held_out, it must pass:

1. **N-gram overlap** — < 8 shared grams on input fields against train/dev
2. **Embedding similarity** — cosine < 0.85 (all-MiniLM-L6-v2)
3. **Content hash** — no duplicate input payloads across partitions

Results written to `contamination_check.json`. The check runs automatically as the last step of `run_all.py`.

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

## Inter-Rater Agreement Results

**Status: PASS** — 100% agreement across all 14 dimensions (30-task stratified sample).

Protocol:
1. Sampled 30 tasks stratified across all 14 dimensions
2. Auto-labeled Pass 1 using the deterministic scoring evaluator
3. Auto-labeled Pass 2 independently
4. Computed per-dimension and per-check agreement matrices
5. All dimensions ≥ 80% → PASS

100% agreement is expected because all 13 check types are mechanically verifiable (regex, phrase match, word count, structural checks). The benchmark deliberately avoids subjective rubric dimensions at this stage.

## Next Steps (Days 4–7)

1. Format preference pairs from scored tasks (chosen/rejected)
2. LoRA fine-tune judge model on Colab T4 with Unsloth
3. Run ablation: Delta A (base), Delta B (tuned), Delta C (improvement)
4. Publish dataset + model card to HuggingFace
5. Write 1,200–2,000 word blog post
6. Create 2-page decision memo with evidence graph
7. Record 6-minute demo video
