# Tenacious-Bench v0.1

Benchmarking and improving AI sales agents through synthetic evaluation datasets, scoring pipelines, and fine-tuned LLM components for B2B outreach performance.

## Overview

Tenacious-Bench is a domain-specific evaluation benchmark for B2B sales agents operating in the Tenacious Consulting context. It tests whether agents correctly handle:

- **Signal-grounded claims** — never assert when evidence is weak
- **Bench capacity honesty** — never promise engineers the bench doesn't have
- **Timezone accuracy** — never fabricate local time labels
- **Tone preservation** — no jargon, no hype, no guilt-trips
- **Dual-control coordination** — verify identity before destructive actions

## Status

**Phase**: Acts I–II complete (Audit + Dataset Authoring + Evaluation)
**Path**: B — Preference-tuned judge/critic
**Tasks**: 242 across 14 failure dimensions
**Partitions**: train 121 (50%), dev 73 (30%), held_out 48 (20%)
**Contamination check**: PASS — 0 violations on n-gram (8), embedding cosine (>0.85), content hash, and temporal-integrity checks
**Inter-rater agreement**: 95.5% overall, Cohen's κ = 0.91 across 30-task hand-labeled sample. All 14 dimensions ≥ 80%; 4 phrase-list refinements queued for v0.2 (see [inter_rater_agreement.md](inter_rater_agreement.md))

## Repository Structure

```
tenacious-bench/
├── README.md
├── pyproject.toml
├── audit_memo.md                  # Act I failure audit
├── methodology.md                 # Path declaration + justification
├── datasheet.md                   # Gebru/Pushkarna datasheet
├── inter_rater_agreement.md       # Agreement protocol + results
├── scoring_evaluator.py           # Deterministic grading engine
├── schema.json                    # Task schema definition
├── contamination_check.json       # Partition contamination results
├── cost_log.md                    # API spend tracking
│
├── tenacious_bench_v0.1/          # The benchmark dataset
│   ├── train/tasks.json
│   ├── dev/tasks.json
│   ├── held_out/tasks.json
│   └── composition_summary.json
│
├── generation_scripts/            # Reproducible authoring pipeline
│   ├── run_all.py                 # Single entry point
│   ├── programmatic_generator.py  # ~75 tasks via parameter sweeps
│   ├── trace_derived_generator.py # ~75 tasks from Week 10 traces
│   ├── hand_authored_adversarial.py # ~38 hand-crafted edge cases
│   ├── multi_llm_synthesis.py     # ~63 tasks via LLM + judge filter
│   ├── assemble_partitions.py     # Merge, dedup, partition
│   └── contamination_check.py     # N-gram + embedding checks
│
├── synthesis_memos/               # Common-reading synthesis memos
│
├── week10-data/                   # Source data from Week 10
│   ├── eval/                      # trace_log.jsonl, probe_results.json
│   └── tenacious_sales_data/      # Seed artifacts (bench, style guide, etc.)
│
└── docs/                          # Challenge documentation
```

## Setup

```bash
# Install uv (if not already)
pip install uv

# Install dependencies
uv sync

# Set API key for multi-LLM synthesis
export OPENROUTER_API_KEY=sk-or-...
```

## Generating the Dataset

```bash
# Run all generators + assemble + contamination check
uv run python generation_scripts/run_all.py

# Or skip API-dependent synthesis
uv run python generation_scripts/run_all.py --skip-synthesis

# Run individual generators
uv run python generation_scripts/programmatic_generator.py
uv run python generation_scripts/trace_derived_generator.py
uv run python generation_scripts/hand_authored_adversarial.py
uv run python generation_scripts/multi_llm_synthesis.py

# Assemble partitions
uv run python generation_scripts/assemble_partitions.py

# Run contamination checks
uv run python generation_scripts/contamination_check.py
```

## Scoring

### Quick start — example tasks

Three annotated example tasks live in [`example_tasks.json`](example_tasks.json). Run them first to verify the evaluator and see how each check type behaves:

```bash
uv run python scoring_evaluator.py --path example_tasks.json --pretty
```

Expected output:

| task\_id | score | max\_score | passed\_all\_checks |
| --- | --- | --- | --- |
| tb-prog-weo-005 | 2 | 4 | false |
| tb-trace-p012-052 | 2 | 6 | false |
| tb-adv-005 | 2 | 6 | false |

Each task is intentionally bad (every critical check fails) so the score is always `max_score / 2`. The `_calibration` annotation on every check and the top-level `_expected_result` block explain exactly what passes, what fails, and why. See Section 3 of [`interim_report.md`](interim_report.md) for a full rubric walkthrough of all three examples.

### Score the full benchmark

```bash
uv run python scoring_evaluator.py --path tenacious_bench_v0.1/dev/tasks.json --pretty
```

### End-to-end example

Score the full dev partition and inspect results for a single task:

```bash
# Score all dev tasks and write to a file
uv run python scoring_evaluator.py \
  --path tenacious_bench_v0.1/dev/tasks.json \
  --pretty > dev_results.json

# Check how many tasks passed all checks
python -c "
import json
data = json.load(open('dev_results.json'))
print(f\"{data['passed_all']}/{data['task_count']} tasks passed all checks\")
"

# Inspect check-level detail for the first failing task
python -c "
import json
data = json.load(open('dev_results.json'))
failing = [r for r in data['results'] if not r['passed_all_checks']]
if failing:
    print(json.dumps(failing[0], indent=2))
"
```

## Task Authoring Modes

| Mode | Share | Tasks | Description |
|---|---|---|---|
| Programmatic sweeps | 33% | 79 | Controlled coverage via combinatorial expansion |
| Trace-derived | 28% | 68 | Grounded in real Week 10 agent failures (probe-linked) |
| Multi-LLM synthesis | 23% | 56 | Hard seeds (Claude Sonnet) + bulk (DeepSeek) + 3-dim judge filter (Gemini) |
| Hand-authored adversarial | 16% | 39 | Sharpest edge cases, highest originality |

## Failure Dimensions

| Dimension | Probes | Description |
|---|---|---|
| weak-evidence-overclaim | P007–P011 | Asserting on LOW/MEDIUM confidence signals |
| bench-over-commitment | P012–P014 | Promising capacity the bench doesn't have |
| timezone-fabrication | P027 | Fabricating local time when timezone is null |
| competitor-gap-assertion | P032–P034 | Accusing rather than asking about gaps |
| tone-drift | P015–P017, P035 | Jargon, hype, guilt-trips, emojis |
| icp-misclassification | P001–P006 | Wrong segment assignment |
| dual-control-coordination | P023–P025 | Acting without auth/confirmation |
| segment-2-first-touch | P010 | Referencing layoffs in cold outreach |
| pricing-objection | — | Discounting or matching offshore rates |

## What's Next (Days 4–7)

1. **Path B training**: Format preference pairs, LoRA fine-tune on Colab T4 with Unsloth
2. **Ablations**: Delta A/B/C measurements on dev slice
3. **HuggingFace**: Publish dataset + model card
4. **Blog post**: 1,200–2,000 word technical writeup
5. **Decision memo**: 2-page CEO/CFO memo with evidence graph
6. **Demo video**: 6-minute walkthrough
