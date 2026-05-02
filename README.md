# Tenacious-Bench v0.1

**A domain-specific evaluation benchmark and preference-tuned judge for B2B sales agents.**

Built for the TRP1 Week 11 challenge: auditing what public benchmarks miss for Tenacious-style technical staffing outreach, constructing a 242-task machine-verifiable dataset, and training a SimPO LoRA judge that lifts pairwise accuracy on sealed held-out tasks from **97.73% → 100.00%** (+2.27pp, p=0.372).

## Public Links

- **Hugging Face Dataset:** https://huggingface.co/datasets/sanoy24/tenacious_bench_v0.1
- **Hugging Face Model Adapter:** https://huggingface.co/sanoy24/tenacious-judge-qwen25-3b-gamma15
- **Technical Blog Post:** https://yonasmekonnen.substack.com/p/building-a-0-100-accurate-ai-sales?r=8bkitf
- **Community Engagement Post:** https://github.com/sierra-research/tau2-bench/issues/278

---

## Key Results

| Condition                        | Pairwise Accuracy | Delta       | Significance             |
| -------------------------------- | ----------------- | ----------- | ------------------------ |
| Base Qwen2.5-3B (zero-shot)      | 97.73%            | —           | —                        |
| Prompt-engineered base (Delta B) | 97.73%            | +0.00pp     | p=1.0                    |
| SimPO LoRA adapter (Delta A)     | **100.00%**       | **+2.27pp** | p=0.372, CI=[0.0%, 6.8%] |

**Honest interpretation:** The ceiling effect dominates at n=44 eval pairs. The base model is already strong; the adapter patches the remaining adversarial edge cases. Delta B=0 confirms that prompting alone cannot close the gap — training is required. Statistical significance cannot be established at this sample size; a larger adversarial held-out slice is the v0.2 priority.

**Training cost:** $0.00 (Colab T4, 16.14 min). **Total API spend:** $0.38 of $10.00 budget.

---

## Public Artifacts

| Artifact                         | URL                             |
| -------------------------------- | ------------------------------- |
| HuggingFace Dataset              | [sanoy24/tenacious_bench_v0.1](https://huggingface.co/datasets/sanoy24/tenacious_bench_v0.1) |
| HuggingFace Model (LoRA adapter) | [sanoy24/tenacious-judge-qwen25-3b-gamma15](https://huggingface.co/sanoy24/tenacious-judge-qwen25-3b-gamma15) |
| Technical Blog Post              | [Substack Post](https://yonasmekonnen.substack.com/p/building-a-0-100-accurate-ai-sales?r=8bkitf) |
| Community Engagement             | [tau2-bench GitHub Issue #278](https://github.com/sierra-research/tau2-bench/issues/278) |

---

## Repository Structure

```
tenacious-bench/
├── README.md                        # This file
├── model_card.md                    # LoRA adapter model card
├── evidence_graph.json              # Every numeric claim → source
├── audit_memo.md                    # Act I: τ²-Bench gap audit
├── schema.json                      # Task schema definition
├── methodology.md                   # Path declaration + partitioning protocol
├── methodology_rationale.md         # Path B justification (papers + trace IDs)
├── datasheet.md                     # Gebru/Pushkarna dataset documentation
├── inter_rater_agreement.md         # Agreement protocol + results (κ=0.91)
├── scoring_evaluator.py             # Deterministic grading engine
├── contamination_check.json         # N-gram + embedding + hash results
├── cost_log.md                      # Itemized API and compute spend
├── pyproject.toml
│
├── tenacious_bench_v0.1/            # The benchmark dataset
│   ├── train/tasks.json             # 121 tasks (50%)
│   ├── dev/tasks.json               # 73 tasks (30%)
│   ├── held_out/tasks.json          # 48 tasks (20%) — sealed
│   └── composition_summary.json    # Partition + dimension counts
│
├── training_data/                   # Path B preference pairs
│   ├── train.jsonl                  # 618 {prompt, chosen, rejected} pairs
│   └── dev.jsonl                    # 347 pairs
│
├── training/                        # Training artifacts
│   ├── train_judge.py               # SimPO training script (Unsloth + TRL)
│   ├── training_run.log             # Loss curves, hyperparameters
│   ├── training_summary.json        # Final metrics + cost
│   └── requirements.txt            # Pinned dependencies
│
├── ablations/                       # Act IV evaluation
│   ├── ablation_results.json        # Delta A / B / cost-Pareto
│   ├── held_out_traces.jsonl        # Per-task scoring traces
│   └── statistical_tests.json      # Bootstrap test (seed=42)
│
├── generation_scripts/              # Reproducible dataset authoring
│   ├── run_all.py                   # Single entry point
│   ├── programmatic_generator.py   # 79 tasks via parameter sweeps
│   ├── trace_derived_generator.py  # 68 tasks from Week 10 traces
│   ├── hand_authored_adversarial.py # 39 adversarial edge cases
│   ├── multi_llm_synthesis.py      # 56 tasks via LLM routing + judge filter
│   ├── assemble_partitions.py      # Merge, dedup, partition
│   └── contamination_check.py      # N-gram + embedding checks
│
├── synthesis_memos/                 # Required reading synthesis memos
│   ├── 01-synthetic-data.md        # Liu et al. COLM 2024
│   ├── 02-datasheets-data-cards.md # Gebru 2021 + Pushkarna FAccT 2022
│   ├── 03-contamination-dynamic-benchmarking.md  # Chen et al. EMNLP 2025
│   ├── 04-llm-as-a-judge.md        # Gu et al. 2024–2025
│   ├── 05-dpo.md                   # Rafailov et al. NeurIPS 2023
│   ├── 06-simpo.md                 # Meng, Xia, Chen NeurIPS 2024
│   ├── 07-prometheus-2.md          # Kim et al. 2024
│   └── 08-preference-leakage.md   # Li et al. 2025
│
├── docs/                            # Submission artifacts (drafts)
│   ├── blog_post.md
│   ├── delivery_memo.md
│   ├── model_card.md
│   ├── evidence_graph.json
│   ├── datasheet.md                 # HF dataset card version
│   └── simpo_synthesis_memo.md
│
└── week10-data/                     # Source corpus from Week 10
    ├── eval/                        # trace_log.jsonl, probe_results.json
    └── tenacious_sales_data/        # Seed artifacts
```

---

## Quickstart: Reproduce the Headline Number

**Requirement:** Python 3.11+, `uv`, and an OpenRouter API key (for ablation chosen-output generation only).

**Dependency Pinning:** Absolute reproducibility is guaranteed via the included `uv.lock` file, which pins all exact transitive dependency hashes. Running `uv sync` will exactly recreate the graded environment.

```bash
# 1. Clone and install
git clone <repo-url>
cd tenacious-bench
pip install uv
uv sync

# 2. Score the dev partition — verify evaluator works
uv run python scoring_evaluator.py --path tenacious_bench_v0.1/dev/tasks.json --pretty

# 3. (Optional) Score the held-out partition to reproduce the baseline
uv run python scoring_evaluator.py --path tenacious_bench_v0.1/held_out/tasks.json --pretty
```

To reproduce the full Delta A ablation (requires GPU + OpenRouter key):

```bash
# Set your OpenRouter API key
export OPENROUTER_API_KEY=sk-or-...

# Run ablations against the trained adapter
# (adapter path should point to your downloaded LoRA weights)
python ablations/run_ablations.py \
    --adapter /path/to/final_adapter \
    --model unsloth/Qwen2.5-3B-Instruct \
    --gamma 1.0
```

Results are written to `ablations/ablation_results.json` and `ablations/statistical_tests.json`. The committed values in this repo reflect the Colab T4 run with seed=42.

---

## Dataset Composition

**242 tasks** across 14 failure dimensions, 4 source modes, 3 difficulty tiers.

### Source Modes

| Mode                      | Tasks | Share | How                                                                                |
| ------------------------- | ----- | ----- | ---------------------------------------------------------------------------------- |
| Programmatic sweeps       | 79    | 33%   | Combinatorial expansion across company size, stack, bench state, signal confidence |
| Trace-derived             | 68    | 28%   | Real Week 10 agent outputs restructured into (input, candidate, rubric) triples    |
| Multi-LLM synthesis       | 56    | 23%   | Claude Sonnet seeds → DeepSeek bulk → GPT-4o-mini judge filter                     |
| Hand-authored adversarial | 39    | 16%   | Highest originality; edge cases specifically designed to defeat baseline models    |

### Failure Dimensions

| Dimension                 | Tasks | Probes          | Description                                       |
| ------------------------- | ----- | --------------- | ------------------------------------------------- |
| weak-evidence-overclaim   | 39    | P007–P011       | Asserting on LOW/MEDIUM confidence signals        |
| tone-drift                | 30    | P015–P017, P035 | Jargon, hype, guilt-trips, emojis                 |
| bench-over-commitment     | 26    | P012–P014       | Promising capacity the bench does not have        |
| competitor-gap-assertion  | 26    | P032–P034       | Accusing rather than asking about competitor gaps |
| timezone-fabrication      | 25    | P027            | Fabricating local time when timezone is null      |
| icp-misclassification     | 19    | P001–P006       | Wrong segment assignment                          |
| dual-control-coordination | 16    | P023–P025       | Acting without auth/confirmation                  |
| pricing-objection         | 12    | —               | Discounting or matching offshore rates            |
| segment-2-first-touch     | 12    | P010            | Referencing layoffs in cold outreach              |
| signal-overclaim          | 10    | P020, P036      | Over-interpreting weak public signals             |
| hype-vocabulary           | 10    | —               | Banned high-energy vocabulary in cold outreach    |
| directness-subject-line   | 8     | —               | Vague or clickbait subject lines                  |
| bench-jargon              | 6     | P015            | Internal terminology exposed to prospects         |
| single-clear-ask          | 3     | —               | Multiple asks in one email                        |

### Quality Controls

- **Inter-rater agreement:** 95.5% overall, Cohen's κ=0.91 (30-task stratified sample, two independent passes)
- **Contamination check:** PASS — 0 violations on 8-gram overlap, cosine similarity (<0.85), content hash, and time-shift verification
- **LLM-as-judge filter:** All multi-LLM synthesis tasks scored on input coherence, ground-truth verifiability, and rubric-application clarity before admission
- **Preference leakage prevention:** Chosen rewrites generated by DeepSeek V3.2 (non-Qwen family); base judge is Qwen — different model families per Li et al. 2025

---

## Training Setup (Path B — SimPO)

**Why Path B:** Week 10 traces showed inconsistency failures — the agent gets bench-over-commitment and weak-evidence claims right most of the time but cannot detect when it is wrong. A preference-tuned judge deployed as a rejection-sampling layer directly targets this failure mode.

| Hyperparameter       | Value                         |
| -------------------- | ----------------------------- |
| Backbone             | `unsloth/Qwen2.5-3B-Instruct` |
| Algorithm            | SimPO via TRL `CPOTrainer`    |
| LoRA rank            | 16                            |
| LoRA alpha           | 32                            |
| β (beta)             | 2.0                           |
| γ (gamma)            | 1.5                           |
| Margin (γ/β)         | 0.75                          |
| Epochs               | 2                             |
| Effective batch size | 8                             |
| Learning rate        | 5e-5                          |
| Training pairs       | 618 (train) + 347 (dev)       |
| Seed                 | 42                            |
| Platform             | Google Colab T4 (free)        |
| Wall time            | 16.14 min                     |
| Cost                 | $0.00                         |

Training script: [training/train_judge.py](training/train_judge.py). Full loss curves: [training/training_run.log](training/training_run.log).

---

## Scoring Evaluator

The scoring evaluator runs deterministically — no LLM calls required for grading.

```bash
# Score a partition
uv run python scoring_evaluator.py --path tenacious_bench_v0.1/dev/tasks.json --pretty

# Score example tasks (annotated with expected failures)
uv run python scoring_evaluator.py --path example_tasks.json --pretty
```

Implemented check types (13):

| Check Type                                | Description                                  |
| ----------------------------------------- | -------------------------------------------- |
| `forbidden_phrases`                       | Banned words/phrases that must not appear    |
| `required_phrases_any`                    | At least one required phrase must be present |
| `forbidden_regex`                         | Regex-based policy enforcement               |
| `max_words`                               | Word count ceiling (120 for cold outreach)   |
| `max_question_marks`                      | Single-clear-ask enforcement                 |
| `no_prospect_local_when_timezone_missing` | Timezone fabrication guard                   |
| `no_unavailable_stack_commitment`         | Bench capacity guard                         |
| `icp_segment_size_guard`                  | Company size threshold check                 |
| `no_emoji_in_cold_outreach`               | Emoji ban in cold outreach                   |
| `signature_format_check`                  | Signature line count limit                   |
| `requires_confirmation_before_action`     | Dual-control confirmation guard              |
| `requires_auth_verification`              | Identity verification guard                  |
| `no_fabricated_identifiers`               | No fabricated order/reference IDs            |

---

## Cost Summary

| Bucket                                  | Spent     | Budget     |
| --------------------------------------- | --------- | ---------- |
| Dataset authoring (multi-LLM synthesis) | $0.10     | $3–5       |
| Path B chosen-rewrite generation        | $0.28     | (in above) |
| Training compute                        | $0.00     | $0–5       |
| Held-out evaluation                     | $0.00     | $2–3       |
| **Total**                               | **$0.38** | **$10.00** |

Full itemized log: [cost_log.md](cost_log.md).

---

## Reproducibility Checklist

- [ ] `uv sync` completes cleanly
- [ ] `uv run python scoring_evaluator.py --path tenacious_bench_v0.1/dev/tasks.json` returns stable scores
- [ ] `ablations/ablation_results.json` matches the Key Results table above
- [ ] `evidence_graph.json` resolves every numeric claim in the memo and blog post to a source file
- [ ] `contamination_check.json` shows 0 violations
- [ ] Held-out tasks are not referenced in any training file

---

## License

Dataset: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Code: MIT.

Attribution: Tenacious is named as the workflow domain only; no private company data is included.
