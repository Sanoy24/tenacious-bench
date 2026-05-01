---
license: cc-by-4.0
task_categories:
- text-classification
language:
- en
tags:
- b2b-sales
- alignment
- preference-tuning
---

# Datasheet: Tenacious Bench v0.1

## Quickstart

You can load this dataset directly in Python using the Hugging Face `datasets` library. The dataset contains three splits: `train`, `dev`, and `held_out`.

```python
from datasets import load_dataset

# Load the dataset
dataset = load_dataset("sanoy24/tenacious_bench_v0.1")

# View a single training example
print(dataset["train"][0]["prompt"])
print(dataset["train"][0]["chosen"])
print(dataset["train"][0]["rejected"])
```

## Baseline and Target Scores

This benchmark is designed to evaluate B2B sales agents on hard policy constraints (e.g., hallucinating engineering capacity).

* **Week 10 Agent Baseline:** The raw Week 10 generative agent frequently violated policy on edge cases (0% pass rate on adversarial strict evaluation).
* **Qwen2.5-3B-Instruct Baseline:** The pre-trained 3B parameter model achieves a **98.44% pairwise accuracy** on the held-out partition zero-shot.
* **Top-of-Leaderboard Target:** The target is **100.00% pairwise accuracy**, successfully achieved by our SimPO-tuned LoRA adapter (`sanoy24/tenacious-judge-qwen25-3b`).

---

## Motivation
**For what purpose was the dataset created?**
This dataset trains and evaluates a preference-based Judge model for Tenacious, a B2B technical staffing company. Existing open datasets do not cover the domain-specific logic required for technical staffing outreach, such as matching required stacks with real-time bench availability.

**Who created the dataset?**
The dataset was authored as part of the TRP1 Week 11 Sales Agent Evaluation Bench challenge.

## Composition
**What do the instances that comprise the dataset represent?**
The instances represent B2B outreach scenarios. Each instance contains a `prompt` (context detailing the prospect, hiring signals, and available bench capacity), a `chosen` response (a rubric-compliant email), and a `rejected` response (an email that violates Tenacious policy). 

**How many instances are there in total?**
Approximately 300 pairs, heavily filtered for quality.
* `train` (50%): Pairs used for preference tuning.
* `dev` (30%): Public validation.
* `held_out` (20%): Sealed 64-record evaluation set.

**Does the dataset contain all possible instances or is it a sample?**
It is a targeted synthetic sample focused exclusively on specific failure modes: `bench-over-commitment` and `weak-evidence-overclaim`.

## Collection Process
**How was the data associated with each instance acquired?**
The dataset uses a four-mode authoring blend:
1. **Trace-derived (~30%):** Restructured from real Week 10 Conversion Engine traces.
2. **Programmatic (~30%):** Parameter sweeps modifying stacks, company size, and hiring signals.
3. **Multi-LLM Synthesis (~25%):** OpenRouter-routed synthetic scenarios validated by an LLM-as-a-judge quality filter.
4. **Hand-authored Adversarial (~15%):** Edge cases injected specifically to trick baseline models, where candidate responses look professional but subtly violate the rubric.

**What mechanisms were used to prevent contamination?**
The 64-record `held_out` partition is strictly sealed. We manually injected adversarial edge cases only into the `held_out` partition to ensure zero data leakage between the evaluation slice and the training slice.

## Uses
**What tasks could the dataset be used for?**
* **Preference Tuning (DPO/SimPO/ORPO):** Teaching small models to penalize confident hallucinations in a sales context.
* **LLM-as-a-Judge Evaluation:** Scoring the reliability of generative outreach agents.

**Is there anything about the composition of the dataset or the way it was collected and preprocessed/cleaned/labeled that might impact future uses?**
The baseline models score highly on this dataset. A baseline 3B-parameter model achieves 98.4% zero-shot accuracy. Future expansions should drastically scale the volume of "hand-authored adversarial" cases to lower the baseline ceiling.

## Distribution
**Will the dataset be distributed to third parties outside of the entity on behalf of which the dataset was created?**
Yes, it is designed to be hosted publicly on Hugging Face to contribute to the open evaluation community.

**What license applies?**
CC-BY-4.0.
