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

Multi-LLM synthesis details: 351 OpenRouter calls (generator + judge combined), **$0.101 total**. Per-call breakdown in `generation_scripts/synthesis_cost_log.json`.

## Running Total

| Bucket | Cost | Budget |
|---|---|---|
| Dataset authoring (multi-LLM synthesis) | $0.10 | $3–5 |
| Local embeddings (contamination + repartition) | $0.00 | included |
| Human labeling | $0.00 | n/a |
| Eval-tier judging (Days 5–6) | $0.00 | $2–3 |
| Training compute (Days 5–6) | $0.00 | $0–5 |
| **Total to date** | **$0.10** | **$10.00** |
| **Remaining** | | **$9.90** |

## Notes

- All offline generators (programmatic, trace-derived, hand-authored) ran at zero API cost.
- Multi-LLM synthesis (56 accepted tasks of ~75 generated) came in at ~$0.10 against a $3–5 envelope. Generator and judge are explicitly different model families per the preference-leakage rule (Li et al., 2025).
- Embedding model is local (sentence-transformers); used for both contamination check and the component-graph re-partitioner.
- No τ²-Bench retail re-runs (per cost-discipline rule).
- No eval-tier model usage on Days 2–3 (per cost-discipline rule).
- Week 10 eval costs are not counted against the Week 11 budget.
