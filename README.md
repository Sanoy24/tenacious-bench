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
**Tasks**: 128 (interim) across 14 failure dimensions  
**Partitions**: train (61), dev (35), held_out (32)  
**Inter-rater**: 100% agreement across all dimensions (30-task sample)

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

```bash
uv run python scoring_evaluator.py --partition dev
```

## Task Authoring Modes

| Mode | Share | Tasks | Description |
|---|---|---|---|
| Programmatic sweeps | 53% | 68 | Controlled coverage via combinatorial expansion |
| Trace-derived | 33% | 42 | Grounded in real Week 10 agent failures |
| Hand-authored adversarial | 14% | 18 | Sharpest edge cases, highest originality |
| Multi-LLM synthesis | Pending | ~63 | Hard variants generated + judge-filtered |

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
