# Cost Log — Tenacious-Bench v0.1

Budget: $10.00 total

## API Costs

| Date | Step | Model | Calls | Cost USD |
|---|---|---|---|---|
| 2026-04-28 | Programmatic generator | — (offline) | 0 | $0.00 |
| 2026-04-28 | Trace-derived generator | — (offline) | 0 | $0.00 |
| 2026-04-28 | Hand-authored adversarial | — (manual) | 0 | $0.00 |
| 2026-04-28 | Multi-LLM synthesis (generator) | deepseek/deepseek-chat-v3-0324 | — | $0.10 (combined) |
| 2026-04-28 | Multi-LLM synthesis (judge) | openai/gpt-4o-mini | — | (in $0.10 above) |
| 2026-04-28 | Contamination check (embeddings) | all-MiniLM-L6-v2 (local) | n/a | $0.00 |
| 2026-04-29 | Re-partitioning (component graph) | all-MiniLM-L6-v2 (local) | n/a | $0.00 |
| 2026-04-29 | Inter-rater human labeling — Pass 1 | rater (manual) | n/a | $0.00 |
| 2026-04-30 | Path B chosen-rewrite generation — Run 1 (initial, ~234 pairs) | deepseek/deepseek-chat-v3-0324 | ~480 | ~$0.09 |
| 2026-04-30 | Path B chosen-rewrite generation — Run 2 (resume to 470 pairs) | deepseek/deepseek-chat-v3-0324 | ~480 | ~$0.09 |
| 2026-04-30 | Path B chosen-rewrite generation — Run 3 (resume to 965 pairs) | deepseek/deepseek-chat-v3-0324 | ~485 | ~$0.10 |

Multi-LLM synthesis details: 351 OpenRouter calls (generator + judge combined), **$0.101 total**. Per-call breakdown in `generation_scripts/synthesis_cost_log.json`.

## Running Total

| Bucket | Cost | Budget |
|---|---|---|
| Dataset authoring (multi-LLM synthesis) | $0.10 | $3–5 |
| Path B chosen-rewrite generation (1445 calls, 2026-04-30) | $0.28 | (in $3–5 above) |
| Local embeddings (contamination + repartition) | $0.00 | included |
| Human labeling | $0.00 | n/a |
| Eval-tier judging (Days 5–6) | $0.00 | $2–3 |
| Training compute (Days 5–6) | $0.00 | $0–5 |
| **Total to date** | **$0.38** | **$10.00** |
| **Remaining** | | **$9.62** |

## Notes

- All offline generators (programmatic, trace-derived, hand-authored) ran at zero API cost.
- Multi-LLM synthesis (56 accepted tasks of ~75 generated) came in at ~$0.10 against a $3–5 envelope. Generator and judge are explicitly different model families per the preference-leakage rule (Li et al., 2025).
- Path B chosen-rewrite generation: 1445 API calls to `deepseek/deepseek-chat-v3-0324` across 3 runs on 2026-04-30 (initial + two resume passes). Produced 965 accepted pairs (618 train / 347 dev). Per-call breakdown in `training_data/build_log.json`. Model is non-Qwen-family (preference-leakage prevention). Cost estimate uses DeepSeek V3.2 OpenRouter pricing (~$0.000196/call blended).
- Embedding model is local (sentence-transformers); used for both contamination check and the component-graph re-partitioner.
- No τ²-Bench retail re-runs (per cost-discipline rule).
- No eval-tier model usage on Days 2–4 (per cost-discipline rule).
- Week 10 eval costs are not counted against the Week 11 budget.
