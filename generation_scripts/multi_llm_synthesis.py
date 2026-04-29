"""
Multi-LLM synthesis task generator for Tenacious-Bench v0.1.

Pipeline (in order):
  1. Hard seeds   — eval-tier model (Claude Sonnet / GPT-class) authors the
                    cfg.HARD_SEED_COUNT hardest/most edge-case tasks first,
                    anchored to the Week 10 failure taxonomy.
  2. Bulk gen     — dev-tier generator (DeepSeek) fills remaining quota per
                    dimension with combinatorial variation.
  3. Judge filter — cheap dev-tier judge (Gemini Flash) scores every task on
                    three dimensions (1–5 each); tasks below any threshold are
                    dropped.
  4. Dedup        — pairwise comparison within each dimension; near-duplicate
                    pairs are resolved by LLM choice, keeping the more
                    diagnostic task.
  5. Spot-check   — eval-tier judge scores a sample of cfg.SPOT_CHECK_COUNT
                    accepted tasks to calibrate the cheap judge.  Results are
                    written to synthesis_calibration_log.json (not used to
                    gate tasks — calibration only).

Model-family rotation (preference-leakage prevention per Li et al. 2025):
  - Hard-seed generator : eval-tier   (e.g. anthropic/claude-sonnet-4-6)
  - Bulk generator      : dev-tier A  (e.g. deepseek/deepseek-chat-v3-0324)
  - Judge (filtering)   : dev-tier B  (e.g. google/gemini-2.0-flash-001)
  - Spot-check judge    : eval-tier   (same family as hard-seed generator)
  Generator and judge are always from different model families.
  The eval-tier model is never used as bulk generator.
  Rotation policy is documented in methodology.md.

Usage:
    uv run python generation_scripts/multi_llm_synthesis.py
"""
from __future__ import annotations

import difflib
import json
import logging
import random
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

# Per-dimension thresholds for the 1–5 pointwise judge scores.
# A task must meet ALL three thresholds to be accepted.
JUDGE_THRESHOLDS: dict[str, int] = {
    "input_coherence": 3,
    "ground_truth_verifiability": 3,
    "rubric_clarity": 3,
}

# Two candidate_output bodies with SequenceMatcher ratio above this are treated
# as near-duplicates and sent to pairwise comparison.
SIMILARITY_THRESHOLD = 0.75

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

BULK_SYSTEM_PROMPT = """You are a benchmark task author for Tenacious-Bench, a sales agent evaluation dataset.

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

HARD_SEED_SYSTEM_PROMPT = """You are an expert benchmark designer for Tenacious-Bench, a sales agent evaluation dataset.

Your job is to author the HARDEST and most EDGE-CASE tasks — ones a generic sales-AI
would pass naively but a carefully aligned Tenacious agent must handle correctly.
These seeds anchor the benchmark to the Week 10 failure taxonomy.

## Design principles for hard seeds
- Ambiguous inputs: the violation requires nuanced judgment, not pattern-matching
- Near-miss signals: the bad output is subtly wrong, not obviously wrong
- Multi-constraint: the task tests two failure modes at once
- Adversarial surface variation: use uncommon phrasings that naive classifiers miss

## Tenacious Context
- B2B tech consulting firm, engineers "on bench" deployed to clients
- 7 stacks: python (7 eng), go (3), data (9), ml (5), infra (4), frontend (6), fullstack_nestjs (2)
- Cold emails must be ≤120 words, one ask, direct subject lines
- Never say "bench" to prospects; never use hype words (top talent, rockstar, ninja)
- Never over-claim: if signal confidence is LOW, ask don't assert
- Never fabricate timezone, metrics, or case study numbers

## Task Schema (same as bulk, but difficulty must be "hard")
- task_id: "tb-syn-NNN"
- source_mode: "multi-llm-synthesis"
- dimension: one of [{dimensions}]
- difficulty: "hard"  ← always hard for seeds
- input: realistic, ambiguous or adversarial scenario
- candidate_output: subtle violation — not cartoonishly bad
- ground_truth.behavior_summary: precise description of correct behavior
- scoring.checks: mechanically verifiable checks

## Coverage target
Generate {n} hard seeds spread across ALL of these dimensions: {dimensions}

Return ONLY a valid JSON array. No markdown, no explanation.
"""

# Judge prompt: pointwise 1–5 on three dimensions.
# Thresholds (all must be met): input_coherence >= 3,
# ground_truth_verifiability >= 3, rubric_clarity >= 3.
JUDGE_PROMPT = """You are a quality judge for Tenacious-Bench benchmark tasks.

Score this task on three dimensions, each from 1 (very poor) to 5 (excellent):

1. input_coherence (1–5)
   Does the prospect, signal brief, and context form a realistic, self-consistent
   scenario? Could this plausibly appear in a real B2B sales workflow?
   1 = incoherent or contradictory  |  5 = fully realistic and grounded

2. ground_truth_verifiability (1–5)
   Can the candidate_output be mechanically scored against the provided checks?
   Are the scoring checks precise, applicable, and non-ambiguous?
   1 = rubric is vague or inapplicable  |  5 = every check is directly verifiable

3. rubric_clarity (1–5)
   Are the scoring checks clear, unambiguous, and tightly tied to the dimension
   being tested? Would two independent evaluators apply them the same way?
   1 = checks are unclear or off-dimension  |  5 = checks are crisp and on-point

Inclusion thresholds (ALL must be met to accept):
  input_coherence >= 3
  ground_truth_verifiability >= 3
  rubric_clarity >= 3

Respond with ONLY a JSON object — no markdown, no extra text:
{"input_coherence": <1-5>, "ground_truth_verifiability": <1-5>, "rubric_clarity": <1-5>, "reason": "<one sentence>"}
"""

PAIRWISE_PROMPT = """You are comparing two Tenacious-Bench tasks that test the same failure dimension.
Choose the more diagnostically valuable task — the one that is harder to game,
tests a subtler failure mode, or would expose a weakness that the other would miss.

Task A:
{task_a}

Task B:
{task_b}

Respond with ONLY a JSON object — no markdown, no extra text:
{{"winner": "A" or "B", "reason": "<one sentence>"}}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_client() -> OpenAI:
    if not cfg.OPENROUTER_API_KEY:
        raise EnvironmentError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file or export it in your shell.\n"
            "  cp .env.example .env  # then fill in the key"
        )
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=cfg.OPENROUTER_API_KEY)


def log_api_cost(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    rates: dict[str, tuple[float, float]] = {
        "deepseek/deepseek-chat-v3-0324": (0.14 / 1_000_000, 0.28 / 1_000_000),
        "google/gemini-2.0-flash-001": (0.10 / 1_000_000, 0.40 / 1_000_000),
        "openai/gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
        "anthropic/claude-3-haiku": (0.25 / 1_000_000, 1.25 / 1_000_000),
        "anthropic/claude-sonnet-4-6": (3.00 / 1_000_000, 15.00 / 1_000_000),
        "openai/gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
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
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


# ── Core pipeline ─────────────────────────────────────────────────────────────

_counter = 0


def _stamp_tasks(tasks: list[dict[str, Any]], dimension: str | None = None) -> None:
    """Assign canonical task_id, source_mode, partition, and dimension in-place."""
    global _counter
    for t in tasks:
        _counter += 1
        t["task_id"] = f"tb-syn-{_counter:03d}"
        t["source_mode"] = "multi-llm-synthesis"
        t["partition"] = "train"
        if dimension and "dimension" not in t:
            t["dimension"] = dimension


def generate_hard_seeds(client: OpenAI, n: int) -> list[dict[str, Any]]:
    """Generate hard edge-case seeds using the eval-tier model."""
    dims_list = ", ".join(d for d, _ in DIMENSIONS_WITH_GUIDANCE)
    prompt = HARD_SEED_SYSTEM_PROMPT.format(n=n, dimensions=dims_list)

    for attempt in range(MAX_RETRIES + 2):
        try:
            resp = client.chat.completions.create(
                model=cfg.EVAL_TIER_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.9,
                max_tokens=8192,
            )
            content = resp.choices[0].message.content or ""
            log_api_cost(
                cfg.EVAL_TIER_MODEL,
                resp.usage.prompt_tokens if resp.usage else 0,
                resp.usage.completion_tokens if resp.usage else 0,
            )
            tasks = parse_json_response(content)
            if not isinstance(tasks, list):
                tasks = [tasks]
            _stamp_tasks(tasks)
            logger.info("Hard seeds generated: %d", len(tasks))
            return tasks

        except Exception as exc:
            wait_time = (attempt + 1) * 5
            logger.warning("Hard-seed generation error: %s. Retrying in %ds...", exc, wait_time)
            time.sleep(wait_time)

    return []


def generate_batch(
    client: OpenAI, dimension: str, guidance: str, n: int
) -> list[dict[str, Any]]:
    """Generate a bulk batch for one dimension using the dev-tier generator."""
    dims_list = ", ".join(d for d, _ in DIMENSIONS_WITH_GUIDANCE)
    prompt = BULK_SYSTEM_PROMPT.format(
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
            _stamp_tasks(tasks, dimension)
            return tasks

        except Exception as exc:
            wait_time = (attempt + 1) * 5
            if "429" in str(exc) or "rate" in str(exc).lower():
                logger.warning("Rate limited (429). Retrying in %ds...", wait_time)
            else:
                logger.warning("Generation error: %s. Retrying in %ds...", exc, wait_time)
            time.sleep(wait_time)

    return []


def judge_task(client: OpenAI, task: dict[str, Any], model: str) -> tuple[bool, dict[str, Any]]:
    """Score a task on 3 dimensions (1–5 each) and return (accepted, scores_dict).

    Acceptance requires all three scores to meet JUDGE_THRESHOLDS.
    Uses *model* so the caller can switch between cheap judge and eval-tier.
    """
    for attempt in range(MAX_RETRIES + 2):
        try:
            time.sleep(1)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": JUDGE_PROMPT},
                    {"role": "user", "content": json.dumps(task, indent=2)},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            content = resp.choices[0].message.content or ""
            log_api_cost(
                model,
                resp.usage.prompt_tokens if resp.usage else 0,
                resp.usage.completion_tokens if resp.usage else 0,
            )

            scores = parse_json_response(content)
            accepted = all(
                isinstance(scores.get(dim), (int, float)) and scores[dim] >= threshold
                for dim, threshold in JUDGE_THRESHOLDS.items()
            )
            return accepted, scores

        except Exception as exc:
            wait_time = (attempt + 1) * 5
            if "429" in str(exc) or "rate" in str(exc).lower():
                logger.warning("Judge rate limited (%s). Retrying in %ds...", model, wait_time)
            else:
                logger.warning("Judge error (%s): %s. Retrying in %ds...", model, exc, wait_time)
            time.sleep(wait_time)

    return False, {}


def pairwise_compare(
    client: OpenAI, task_a: dict[str, Any], task_b: dict[str, Any]
) -> dict[str, Any]:
    """Ask the cheap judge to pick the more diagnostic of two similar tasks."""
    prompt = PAIRWISE_PROMPT.format(
        task_a=json.dumps(task_a, indent=2),
        task_b=json.dumps(task_b, indent=2),
    )
    for attempt in range(MAX_RETRIES + 1):
        try:
            time.sleep(1)
            resp = client.chat.completions.create(
                model=cfg.JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=128,
            )
            content = resp.choices[0].message.content or ""
            log_api_cost(
                cfg.JUDGE_MODEL,
                resp.usage.prompt_tokens if resp.usage else 0,
                resp.usage.completion_tokens if resp.usage else 0,
            )
            return parse_json_response(content)
        except Exception as exc:
            wait_time = (attempt + 1) * 5
            logger.warning("Pairwise compare error: %s. Retrying in %ds...", exc, wait_time)
            time.sleep(wait_time)
    return {"winner": "A", "reason": "fallback — comparison failed"}


def _body_text(task: dict[str, Any]) -> str:
    return str(task.get("candidate_output", {}).get("body", ""))


def pairwise_dedup(
    client: OpenAI, tasks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Within each dimension, resolve near-duplicate pairs via LLM pairwise comparison.

    Two tasks are considered near-duplicates when their candidate_output bodies
    have a SequenceMatcher ratio > SIMILARITY_THRESHOLD.
    """
    by_dim: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        by_dim.setdefault(t.get("dimension", "unknown"), []).append(t)

    kept: list[dict[str, Any]] = []
    total_dropped = 0

    for dim, dim_tasks in by_dim.items():
        surviving = list(dim_tasks)
        i = 0
        while i < len(surviving):
            j = i + 1
            while j < len(surviving):
                ratio = difflib.SequenceMatcher(
                    None, _body_text(surviving[i]), _body_text(surviving[j])
                ).ratio()
                if ratio > SIMILARITY_THRESHOLD:
                    verdict = pairwise_compare(client, surviving[i], surviving[j])
                    loser_idx = j if verdict.get("winner") == "A" else i
                    logger.info(
                        "Dedup [%s]: dropped task %s (ratio=%.2f, reason=%s)",
                        dim,
                        surviving[loser_idx].get("task_id"),
                        ratio,
                        verdict.get("reason", ""),
                    )
                    surviving.pop(loser_idx)
                    total_dropped += 1
                    if loser_idx == i:
                        break  # i was dropped; advance outer loop
                else:
                    j += 1
            else:
                i += 1
                continue
            i += 1  # only reached when inner break fired (i was dropped)

        kept.extend(surviving)

    logger.info("Dedup complete: %d tasks dropped, %d remaining", total_dropped, len(kept))
    return kept


def spot_check_calibration(
    client: OpenAI,
    tasks: list[dict[str, Any]],
    n: int,
) -> list[dict[str, Any]]:
    """Re-judge a random sample of accepted tasks with the eval-tier model.

    Returns a list of calibration records (not used to gate tasks).
    The cheap-judge acceptance rate vs eval-tier acceptance rate is logged
    in synthesis_calibration_log.json for methodology documentation.
    """
    sample = random.sample(tasks, min(n, len(tasks)))
    records: list[dict[str, Any]] = []
    logger.info("Spot-check calibration: scoring %d tasks with %s", len(sample), cfg.EVAL_TIER_MODEL)

    for task in sample:
        accepted, scores = judge_task(client, task, cfg.EVAL_TIER_MODEL)
        records.append({
            "task_id": task.get("task_id"),
            "dimension": task.get("dimension"),
            "eval_tier_accepted": accepted,
            "eval_tier_scores": scores,
        })

    accept_rate = sum(1 for r in records if r["eval_tier_accepted"]) / len(records) if records else 0
    logger.info(
        "Spot-check calibration complete: eval-tier acceptance rate = %.1f%% (%d/%d)",
        accept_rate * 100,
        sum(1 for r in records if r["eval_tier_accepted"]),
        len(records),
    )
    return records


def main() -> None:
    """Run the full multi-LLM synthesis pipeline."""
    random.seed(cfg.RANDOM_SEED)
    client = get_client()
    all_tasks: list[dict[str, Any]] = []

    # ── Step 1: Hard seeds via eval-tier model ────────────────────────────────
    logger.info(
        "Step 1 — Hard seeds: generating %d tasks with %s",
        cfg.HARD_SEED_COUNT,
        cfg.EVAL_TIER_MODEL,
    )
    hard_seeds = generate_hard_seeds(client, cfg.HARD_SEED_COUNT)

    # Judge-filter hard seeds with the cheap judge.
    accepted_seeds: list[dict[str, Any]] = []
    for task in hard_seeds:
        accepted, scores = judge_task(client, task, cfg.JUDGE_MODEL)
        if accepted:
            task["_judge_scores"] = scores
            accepted_seeds.append(task)
    logger.info(
        "Hard seeds: %d accepted / %d generated", len(accepted_seeds), len(hard_seeds)
    )
    all_tasks.extend(accepted_seeds)

    # ── Step 2: Bulk generation per dimension ────────────────────────────────
    tasks_per_dim = cfg.SYNTHESIS_TARGET_TASKS // len(DIMENSIONS_WITH_GUIDANCE) + 1
    logger.info(
        "Step 2 — Bulk gen: target %d tasks across %d dimensions (~%d per dim) with %s",
        cfg.SYNTHESIS_TARGET_TASKS,
        len(DIMENSIONS_WITH_GUIDANCE),
        tasks_per_dim,
        cfg.GENERATOR_MODEL,
    )
    logger.info("Generator: %s | Judge: %s", cfg.GENERATOR_MODEL, cfg.JUDGE_MODEL)

    for dim, guidance in DIMENSIONS_WITH_GUIDANCE:
        logger.info("Bulk generating: %s...", dim)
        generated = 0
        accepted = 0

        while accepted < tasks_per_dim and generated < tasks_per_dim * 3:
            batch_size = min(cfg.SYNTHESIS_BATCH_SIZE, tasks_per_dim - accepted)
            batch = generate_batch(client, dim, guidance, batch_size)
            generated += len(batch)

            for task in batch:
                task_accepted, scores = judge_task(client, task, cfg.JUDGE_MODEL)
                if task_accepted:
                    task["_judge_scores"] = scores
                    all_tasks.append(task)
                    accepted += 1
                    if accepted >= tasks_per_dim:
                        break

            time.sleep(1)

        logger.info("  → %d accepted / %d generated", accepted, generated)

    # ── Step 3: Pairwise deduplication ───────────────────────────────────────
    logger.info("Step 3 — Dedup: %d tasks before dedup", len(all_tasks))
    all_tasks = pairwise_dedup(client, all_tasks)

    # ── Step 4: Spot-check calibration with eval-tier judge ──────────────────
    logger.info("Step 4 — Spot-check calibration")
    calibration_records = spot_check_calibration(client, all_tasks, cfg.SPOT_CHECK_COUNT)

    # ── Write outputs ─────────────────────────────────────────────────────────
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

    cal_path = cfg.GENERATION_DIR / "synthesis_calibration_log.json"
    cal_accept_rate = (
        sum(1 for r in calibration_records if r["eval_tier_accepted"]) / len(calibration_records)
        if calibration_records else 0
    )
    cal_path.write_text(json.dumps({
        "judge_thresholds": JUDGE_THRESHOLDS,
        "cheap_judge_model": cfg.JUDGE_MODEL,
        "eval_tier_model": cfg.EVAL_TIER_MODEL,
        "sample_size": len(calibration_records),
        "eval_tier_accept_rate": round(cal_accept_rate, 4),
        "records": calibration_records,
    }, indent=2), encoding="utf-8")

    logger.info("Total multi-LLM synthesis tasks: %d", len(all_tasks))
    logger.info("Total API cost: $%.4f", total_cost)
    logger.info("Written to: %s", out_path)
    logger.info("Cost log: %s", cost_path)
    logger.info("Calibration log: %s", cal_path)


if __name__ == "__main__":
    main()
