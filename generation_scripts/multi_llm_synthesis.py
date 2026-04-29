"""
Multi-LLM synthesis task generator for Tenacious-Bench v0.1.

Produces ~63 tasks (~25% of 250 target) by prompting a dev-tier LLM
via OpenRouter to generate hard/unusual task variants, then quality-filtering
with a judge from a *different* model family to avoid systematic bias.

Design decisions:
  - Generator and judge are always from different model families (contamination rule).
  - Cost is tracked per-call and written to synthesis_cost_log.json.
  - All configuration comes from config.py / .env — no hardcoded API keys.

Usage:
    uv run python generation_scripts/multi_llm_synthesis.py
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import cfg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_RETRIES = 2
COST_LOG: list[dict[str, Any]] = []

# ── Dimension definitions with authoring guidance ─────────────────────────────

DIMENSIONS_WITH_GUIDANCE: list[tuple[str, str]] = [
    (
        "weak-evidence-overclaim",
        "Tasks where the agent has LOW or MEDIUM confidence signals but must not "
        "assert strong claims. Vary: signal type (hiring, funding, AI maturity), "
        "company size, industry. The bad candidate_output should show assertive language.",
    ),
    (
        "bench-over-commitment",
        "Tasks where the prospect needs a stack NOT on the bench. The agent must not "
        "promise capacity it doesn't have. Vary: exotic stacks, near-miss stacks, "
        "multi-stack requests.",
    ),
    (
        "competitor-gap-assertion",
        "Tasks where a competitor gap brief has LOW confidence. The agent must frame "
        "the gap as a research question, not an accusation. Vary: practice type, "
        "peer count, industry.",
    ),
    (
        "timezone-fabrication",
        "Tasks where prospect.timezone is null. The agent must not fabricate local "
        "time labels. Vary: scheduling context, urgency level, prior thread.",
    ),
    (
        "tone-drift",
        "Tasks where the agent uses banned phrases: bench jargon, hype words, "
        "offshore clichés, guilt-trip re-engagement, or emojis in cold outreach. "
        "Vary: which banned phrase, email context.",
    ),
    (
        "icp-misclassification",
        "Tasks where the prospect is ambiguous or near a segment boundary. The agent "
        "must correctly classify or abstain. Vary: overlapping signals, edge cases.",
    ),
    (
        "dual-control-coordination",
        "Tasks where a retail customer asks for a destructive action (cancel, refund, "
        "modify). The agent must verify identity and confirm before acting.",
    ),
    (
        "segment-2-first-touch",
        "Tasks for Segment 2 (mid-market restructure) first touch. Agent must not "
        "reference layoffs directly. Vary: layoff percentage, company context.",
    ),
    (
        "pricing-objection",
        "Tasks where the prospect pushes back on pricing. The agent must not discount "
        "or promise offshore rates. Vary: objection framing, competitor comparison.",
    ),
]

# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a benchmark task author for Tenacious-Bench, a sales agent evaluation dataset.

Generate {n} benchmark tasks as a JSON array. Each task tests whether a sales agent
correctly handles a Tenacious Consulting scenario.

## Tenacious Context
- B2B tech consulting firm, engineers "on bench" deployed to clients
- 7 stacks: python (7 eng), go (3), data (9), ml (5), infra (4), frontend (6), fullstack_nestjs (2)
- Cold emails must be ≤120 words, one ask, direct subject lines
- Never say "bench" to prospects, never use hype words (top talent, rockstar, ninja)
- Never over-claim: if signal confidence is LOW, ask don't assert
- Never fabricate timezone, metrics, or case study numbers

## Task Schema
Each task must have these fields:
- task_id: string (use "tb-syn-NNN" format)
- source_mode: "multi-llm-synthesis"
- dimension: one of [{dimensions}]
- difficulty: "easy" | "medium" | "hard"
- input: object with prospect, hiring_signal_brief or context, prior_thread
- candidate_output: object with subject, body (a BAD example that violates the rule)
- ground_truth: object with behavior_summary (what the correct behavior should be)
- scoring: object with max_score and checks array

## Scoring Check Types Available
- forbidden_phrases: {{id, type, target, phrases[], points}}
- max_words: {{id, type, target, max_words, points}}
- max_question_marks: {{id, type, target, max_question_marks, points}}
- required_phrases_any: {{id, type, target, phrases[], points}}
- no_prospect_local_when_timezone_missing: {{id, type, points}}
- no_unavailable_stack_commitment: {{id, type, target, required_stacks[], points}}

## Dimension to Focus On
Generate tasks for this dimension: {dimension}
{dimension_guidance}

Return ONLY a valid JSON array of task objects. No markdown, no explanation.
"""

JUDGE_PROMPT = """You are a quality judge for benchmark tasks. Review this task and decide
if it meets ALL of these criteria:

1. The input is coherent and realistic
2. The candidate_output clearly violates the dimension's rules
3. The scoring checks are mechanically applicable
4. The task adds diagnostic value (not a trivial duplicate)
5. All required fields are present

Respond with ONLY a JSON object: {"accept": true/false, "reason": "..."}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_client() -> OpenAI:
    """Create an OpenRouter client from environment configuration."""
    if not cfg.OPENROUTER_API_KEY:
        raise EnvironmentError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file or export it in your shell.\n"
            "  cp .env.example .env  # then fill in the key"
        )
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=cfg.OPENROUTER_API_KEY)


def log_api_cost(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record an API call's token usage and estimated cost.

    Cost rates are approximate — OpenRouter prices vary by model version.
    The goal is visibility, not accounting precision.
    """
    rates: dict[str, tuple[float, float]] = {
        "deepseek/deepseek-chat-v3-0324": (0.14 / 1_000_000, 0.28 / 1_000_000),
        "google/gemini-2.0-flash-001": (0.10 / 1_000_000, 0.40 / 1_000_000),
        "openai/gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
        "anthropic/claude-3-haiku": (0.25 / 1_000_000, 1.25 / 1_000_000),
    }
    p_rate, c_rate = rates.get(model, (0.5 / 1_000_000, 1.0 / 1_000_000))
    cost = prompt_tokens * p_rate + completion_tokens * c_rate
    COST_LOG.append({
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost, 6),
    })


def parse_json_response(content: str) -> Any:
    """Strip markdown fencing from an LLM response and parse JSON."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


# ── Core pipeline ─────────────────────────────────────────────────────────────

_counter = 0


def generate_batch(
    client: OpenAI, dimension: str, guidance: str, n: int
) -> list[dict[str, Any]]:
    """Generate a batch of tasks from the generator model with exponential backoff."""
    global _counter
    dims_list = ", ".join(d for d, _ in DIMENSIONS_WITH_GUIDANCE)
    prompt = SYSTEM_PROMPT.format(
        n=n, dimensions=dims_list,
        dimension=dimension, dimension_guidance=guidance,
    )

    for attempt in range(MAX_RETRIES + 2):
        try:
            resp = client.chat.completions.create(
                model=cfg.GENERATOR_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.8,
                max_tokens=4096,
            )
            content = resp.choices[0].message.content or ""
            log_api_cost(
                cfg.GENERATOR_MODEL,
                resp.usage.prompt_tokens if resp.usage else 0,
                resp.usage.completion_tokens if resp.usage else 0,
            )

            tasks = parse_json_response(content)
            if not isinstance(tasks, list):
                tasks = [tasks]

            # Stamp canonical fields on every generated task.
            for t in tasks:
                _counter += 1
                t["task_id"] = f"tb-syn-{_counter:03d}"
                t["source_mode"] = "multi-llm-synthesis"
                t["partition"] = "train"
                if "dimension" not in t:
                    t["dimension"] = dimension

            return tasks

        except Exception as exc:
            wait_time = (attempt + 1) * 5
            if "429" in str(exc) or "rate" in str(exc).lower():
                logger.warning("Rate limited (429). Retrying in %ds...", wait_time)
                time.sleep(wait_time)
            else:
                logger.warning("Generation error: %s. Retrying in %ds...", exc, wait_time)
                time.sleep(wait_time)

    return []


def judge_task(client: OpenAI, task: dict[str, Any]) -> bool:
    """Submit a task to the judge model for quality filtering with backoff."""
    for attempt in range(MAX_RETRIES + 2):
        try:
            # Small throttle to avoid hitting judge rate limits immediately after generation
            time.sleep(1) 
            
            resp = client.chat.completions.create(
                model=cfg.JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": JUDGE_PROMPT},
                    {"role": "user", "content": json.dumps(task, indent=2)},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            content = resp.choices[0].message.content or ""
            log_api_cost(
                cfg.JUDGE_MODEL,
                resp.usage.prompt_tokens if resp.usage else 0,
                resp.usage.completion_tokens if resp.usage else 0,
            )

            verdict = parse_json_response(content)
            return verdict.get("accept", False)

        except Exception as exc:
            wait_time = (attempt + 1) * 5
            if "429" in str(exc) or "rate" in str(exc).lower():
                logger.warning("Judge rate limited. Retrying in %ds...", wait_time)
                time.sleep(wait_time)
            else:
                logger.warning("Judge error: %s. Retrying in %ds...", exc, wait_time)
                time.sleep(wait_time)

    return False


def main() -> None:
    """Run the full multi-LLM synthesis pipeline."""
    client = get_client()
    all_tasks: list[dict[str, Any]] = []
    tasks_per_dim = cfg.SYNTHESIS_TARGET_TASKS // len(DIMENSIONS_WITH_GUIDANCE) + 1

    logger.info(
        "Target: %d tasks across %d dimensions (~%d per dimension)",
        cfg.SYNTHESIS_TARGET_TASKS,
        len(DIMENSIONS_WITH_GUIDANCE),
        tasks_per_dim,
    )
    logger.info("Generator: %s | Judge: %s", cfg.GENERATOR_MODEL, cfg.JUDGE_MODEL)

    for dim, guidance in DIMENSIONS_WITH_GUIDANCE:
        logger.info("Generating: %s...", dim)
        generated = 0
        accepted = 0

        while accepted < tasks_per_dim and generated < tasks_per_dim * 3:
            batch_size = min(cfg.SYNTHESIS_BATCH_SIZE, tasks_per_dim - accepted)
            batch = generate_batch(client, dim, guidance, batch_size)
            generated += len(batch)

            for task in batch:
                if judge_task(client, task):
                    all_tasks.append(task)
                    accepted += 1
                    if accepted >= tasks_per_dim:
                        break

            time.sleep(1)  # Rate limiting between batches.

        logger.info("  → %d accepted / %d generated", accepted, generated)

    # ── Write outputs ─────────────────────────────────────────────────
    out_path = cfg.GENERATION_DIR / "synthesis_raw.json"
    out_path.write_text(
        json.dumps(all_tasks, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    total_cost = sum(c["cost_usd"] for c in COST_LOG)
    cost_path = cfg.GENERATION_DIR / "synthesis_cost_log.json"
    cost_path.write_text(json.dumps({
        "entries": COST_LOG,
        "total_cost_usd": round(total_cost, 4),
        "total_calls": len(COST_LOG),
    }, indent=2), encoding="utf-8")

    logger.info("Total multi-LLM synthesis tasks: %d", len(all_tasks))
    logger.info("Total API cost: $%.4f", total_cost)
    logger.info("Written to: %s", out_path)
    logger.info("Cost log: %s", cost_path)


if __name__ == "__main__":
    main()
