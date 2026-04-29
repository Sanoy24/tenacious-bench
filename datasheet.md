# Tenacious-Bench v0.1 Datasheet

## 1. Motivation

### Telescopic

Tenacious-Bench exists to evaluate B2B sales-agent behavior that public benchmarks do not grade well: confidence-aware phrasing, bench-truthfulness, grounded outreach, and non-condescending use of competitor research.

### Periscopic

Week 10 evidence showed a strong cluster of failures around over-claiming weak signals (`P007`, `P008`, `P009`, `P011`, `P032`) plus secondary risks around bench commitment (`P012`-`P014`) and timezone fabrication (`P027`). Those are expensive in a sales workflow because a single wrong outreach email can damage trust with a prospect.

### Microscopic

This release is the interim submission benchmark, containing 242 tasks across 14 failure dimensions, in the brief's 200–300 range. It covers the core failure families identified in the Week 10 audit and validates schema, evaluator behavior, partition integrity, and contamination resistance.

## 2. Composition

### Telescopic

Current composition: **242 tasks** total.

- **train**: 121 tasks (50%)
- **dev**: 73 tasks (30%)
- **held_out**: 48 tasks (20%)

### Periscopic

The dataset covers **14 failure dimensions**:

| Dimension | Count | Source Probes |
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

### Microscopic

Each task includes:

- `task_id` — unique identifier with source-mode prefix
- `partition` — train, dev, or held_out
- `source_mode` — one of: programmatic, trace-derived, multi-llm-synthesis, hand-authored-adversarial
- `dimension` — the failure family being tested
- `difficulty` — easy, medium, or hard
- `input` — structured prospect and signal context
- `candidate_output` — a BAD output that violates the dimension's rules
- `ground_truth` — behavior_summary describing the correct behavior
- `scoring` — machine-verifiable rubric with deterministic checks

## 3. Collection Process

### Telescopic

Tasks were built from Week 10 artifacts already present in the repository, using four generation modes (three offline, one routed multi-LLM with judge filtering).

### Periscopic

Inputs used:

- `trace_log.jsonl` — 1,800+ lines of agent simulation outcomes
- `probe_library.md` — 37 adversarial probes
- `probe_results.json` — actual trigger rates from probe runner
- `failure_taxonomy.md` — 10-category failure classification
- Sample hiring signal and competitor gap briefs
- `layoffs.csv` and `crunchbase_odm_sample.json`
- Tenacious seed docs: style guide, ICP definition, bench summary, pricing sheet, case studies, cold sequence, objection-handling transcripts

### Microscopic

Task provenance by source mode:

| Source Mode | Tasks | Share | API Cost |
|---|---|---|---|
| Programmatic sweeps | 79 | 33% | $0.00 |
| Trace-derived | 68 | 28% | $0.00 |
| Multi-LLM synthesis | 56 | 23% | $0.10 |
| Hand-authored adversarial | 39 | 16% | $0.00 |
| **Total** | **242** | **100%** | **$0.10** |

## 4. Preprocessing / Labeling / Scoring

### Telescopic

This release uses **deterministic rubric checks only** — zero LLM-as-judge scoring.

### Periscopic

Implemented checks (13 types):

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

### Microscopic

Inter-rater agreement: **100% across all 14 dimensions** (30-task stratified sample, two independent evaluator passes). This is expected because all check types are deterministic — the benchmark deliberately avoids subjective rubric dimensions at this stage.

## 5. Uses

### Telescopic

Primary use: benchmark and improve the Week 10 sales agent for the Week 11 challenge.

### Periscopic

Secondary uses:

- Evaluator development and schema validation
- Contamination-protocol testing
- Preference-data design for Path B (judge/critic fine-tuning)
- Training data for LoRA fine-tuning

### Microscopic

This dataset should not be treated as final performance evidence. The multi-LLM synthesis mode (~63 additional tasks) is pending API execution and will be added in the final submission.

## 6. Distribution

### Telescopic

Planned distribution target: Hugging Face dataset release after the benchmark reaches the required scale and quality bar.

### Periscopic

Intended dataset license: `CC-BY-4.0`, unless a later methodology review finds a stronger reason to choose differently.

### Microscopic

The held-out partition will be sealed after the embedding-similarity contamination check completes.

## 7. Maintenance

### Telescopic

This dataset will be expanded, re-labeled, and recalibrated during Acts III-IV of the challenge.

### Periscopic

Planned maintenance steps:

1. Run multi-LLM synthesis to reach 190+ tasks
2. Complete embedding-similarity contamination check
3. If any held_out tasks have cosine > 0.85 to train/dev, paraphrase them
4. Expand to the full 200-300 task benchmark
5. Format preference pairs for Path B training

### Microscopic

Current version: `v0.1-interim`. Final version will be `v1.0` for the public HuggingFace release.
