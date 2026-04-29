# Cost Log — Tenacious-Bench v0.1

Budget: $10.00 total

## API Costs

| Date | Step | Model | Calls | Tokens (in/out) | Cost USD |
|---|---|---|---|---|---|
| 2026-04-28 | Programmatic generator | — | 0 | 0 / 0 | $0.00 |
| 2026-04-28 | Trace-derived generator | — | 0 | 0 / 0 | $0.00 |
| 2026-04-28 | Hand-authored adversarial | — | 0 | 0 / 0 | $0.00 |
| 2026-04-28 | Multi-LLM synthesis (gen) | deepseek/deepseek-chat-v3-0324 | — | — | Pending |
| 2026-04-28 | Multi-LLM synthesis (judge) | google/gemini-2.0-flash-001 | — | — | Pending |
| 2026-04-28 | Contamination check (embed) | all-MiniLM-L6-v2 (local) | 1 | local | $0.00 |
| 2026-04-28 | Inter-rater labeling | — | 0 | 0 / 0 | $0.00 |

## Running Total

| Item | Cost |
|---|---|
| Programmatic + trace + adversarial (128 tasks) | $0.00 |
| Multi-LLM synthesis (~63 tasks planned) | Pending (see `generation_scripts/synthesis_cost_log.json`) |
| Contamination check (local model) | $0.00 |
| Inter-rater agreement (evaluator-based) | $0.00 |
| **Total to date** | **$0.00** |
| **Budget remaining** | **$10.00** |

## Notes

- All 128 interim tasks were generated with zero API cost (offline generators only).
- Multi-LLM synthesis costs will be logged automatically to `generation_scripts/synthesis_cost_log.json` when that step runs.
- Embedding model (all-MiniLM-L6-v2) runs locally via sentence-transformers — no API cost.
- Week 10 eval costs ($2.99) are not counted against Week 11 budget.
- Estimated multi-LLM synthesis cost: ~$0.30-0.60 for 63 tasks (DeepSeek V3 + Gemini Flash, both dev-tier).
