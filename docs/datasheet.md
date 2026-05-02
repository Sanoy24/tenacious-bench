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

## Preprocessing/cleaning/labeling
**Was any preprocessing/cleaning/labeling of the data performed?**
Yes. For the multi-LLM synthesis partition, a lightweight dev-tier model (Gemini 2.0 Flash) was used as a pointwise judge. It scored all generated tasks on a 1-5 scale for `input_coherence`, `ground_truth_verifiability`, and `rubric_clarity`. Any task scoring below a 3 on any dimension was dropped. Near-duplicate tasks were also resolved via pairwise deduplication.

**Is the software used to preprocess/clean/label the instances available?**
Yes. The complete source code is available in `generation_scripts/multi_llm_synthesis.py`.

## Uses
**What tasks could the dataset be used for?**
The primary intended use case is **Preference Tuning (DPO/SimPO/ORPO)**. The dataset is specifically structured with hard-negative pairs designed to teach small, efficient models (like Qwen 3B or Llama-3-8B) how to act as deterministic rejection-sampling judges. By penalizing the exact failure modes identified in the Tenacious failure taxonomy—such as timezone fabrication, competitor-gap assertions, and bench over-commitment—the dataset acts as a direct alignment signal.

A secondary use case is **LLM-as-a-Judge Evaluation**. The held-out dataset serves as an unbiased benchmark to score the reliability and policy-compliance of external generative outreach agents before they are deployed to production.

**What tasks should the dataset NOT be used for? (Misuses)**
* **General Sales Training:** Do not use this dataset to train general-purpose SDR agents. The policies embedded here (e.g., maximum word counts, aggressive tone bans, and strict technical stack matching) are proprietary to the Tenacious brand voice. Applying these strict rules to an unrelated SaaS or retail sales pipeline will artificially degrade performance and restrict necessary sales behaviors.
* **Factual Extraction:** The prospect names, companies, and "bench states" included in this dataset are largely synthesized or structurally anonymized. They do not represent real people or current economic realities. Using this dataset to extract factual B2B lead lists will result in 100% hallucinated outputs.

**Is there anything about the composition of the dataset or the way it was collected and preprocessed/cleaned/labeled that might impact future uses?**
The baseline models score highly on this dataset (e.g., Qwen2.5-3B-Instruct achieves 98.4% zero-shot accuracy). This high baseline ceiling means future iterations of this dataset will need to drastically scale the volume of "hand-authored adversarial" cases to effectively separate frontier models.

## Limitations and Bias
**What are the known limitations and biases of the dataset?**
1. **Statistical Power (Size Constraint):** The `held_out` partition currently contains exactly 48 tasks. While this strictly follows the 20% validation split rule for our 242-task dataset, this small `N` restricts the statistical power (p-value) when measuring pairwise performance deltas between highly capable models. A 100% pairwise accuracy on 48 tasks still yields a 95% confidence interval up to ~6.8%, meaning we cannot statistically guarantee absolute perfection in production.
2. **Domain Narrowness:** The dataset is hyper-specific to the Tenacious B2B technical staffing domain. It penalizes behaviors (like utilizing competitor gaps to sell) that are considered standard practice in other sales disciplines, leading to a domain-specific bias.
3. **LLM Assessor Bias (The "Gemini Effect"):** The synthesized portion of the dataset was filtered using `google/gemini-2.0-flash-001`. While cross-family generation was used to prevent direct preference leakage, the filter may still induce subtle structural biases, such as favoring emails with bulleted lists or specific professional sign-offs that align with Gemini's implicit preferences.
4. **Public Proxy Lossiness:** Because the dataset grounds truth in public signals (layoffs.fyi, Crunchbase), it inherently penalizes the kind of nuanced risk-taking that top human sales reps execute using private CRM intuition. This "lossiness" biases the dataset toward rewarding overly conservative, formulaic outreach over personalized intuition.

## Distribution
**Will the dataset be distributed to third parties outside of the entity on behalf of which the dataset was created?**
Yes. To contribute to the broader open evaluation and alignment community, the dataset partitions (train and dev) are hosted publicly on Hugging Face.

**What license applies?**
CC-BY-4.0. We deliberately chose this permissive license to allow researchers to freely integrate these adversarial B2B examples into larger multi-domain alignment datasets (e.g., ToolBench or AgentBench) without restrictive commercial caveats.

## Maintenance
**Who is maintaining the dataset?**
The dataset is maintained by the core Tenacious engineering team as part of the TRP1 Challenge suite.

**How can the maintainer be contacted?**
Maintenance requests, errata submissions, and pull requests can be directed to the primary GitHub repository (Issue Tracker) or via the Hugging Face Community Discussion tab on the dataset page.

**Is there an erratum?**
No erratum exists for v0.1. Any future errata will be published as a unified JSON log in the repository root and linked directly from the top of this datasheet.

**Will the dataset be updated?**
Yes. While this represents the static v0.1 release for the Week 11 challenge, a v0.2 update is already scheduled. The planned v0.2 release will:
1. Increase the dataset size to >1,000 tasks to solve the statistical power limitation.
2. Incorporate the Round 2 Inter-Rater Agreement findings, specifically tightening phrase-list regexes for rules like `no-guilt-trip-language` and `no-layoff-or-restructure-reference`.
3. Introduce dynamic real-time temporal verification for public signals.
