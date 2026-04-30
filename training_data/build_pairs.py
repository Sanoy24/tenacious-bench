#!/usr/bin/env python3
"""
training_data/build_pairs.py

Build Path B (SimPO) preference pairs from Tenacious-Bench train + dev partitions.

Rejected = existing candidate_output (intentionally bad, already in the benchmark).
Chosen   = DeepSeek V3.2 rewrite validated by scoring_evaluator.evaluate_task.

Family rotation (preference-leakage prevention per Li et al. 2025):
  - Judge backbone at training time: Qwen 3.5 (0.8B or 2B)
  - Chosen rewrite generator here: DeepSeek V3.2 (non-Qwen family)

Output format: TRL SimPOTrainer chat-message format
  {"prompt": [{"role":"user","content":"..."}],
   "chosen": [{"role":"assistant","content":"..."}],
   "rejected": [{"role":"assistant","content":"..."}],
   "_meta": {...}}

Oversampling: trace-derived tasks repeated 3x before dedup by task_id.
Target: 600-1200 valid pairs across train + dev splits.

Usage:
    uv run python training_data/build_pairs.py
    uv run python training_data/build_pairs.py --limit 10 --dry-run
    uv run python training_data/build_pairs.py --partition train
    uv run python training_data/build_pairs.py --resume   # skip task_ids already in .jsonl
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))
from scoring_evaluator import evaluate_task

ROOT = Path(__file__).parent.parent
BENCH_ROOT = ROOT / "tenacious_bench_v0.1"
OUT_DIR = Path(__file__).parent
BUILD_LOG = OUT_DIR / "build_log.json"
COST_LOG_PATH = OUT_DIR / "build_cost_log.json"

_cost_entries: list[dict] = []

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
REWRITE_MODEL = os.environ.get("REWRITE_MODEL", "deepseek/deepseek-chat-v3-0324")
MAX_RETRIES = int(os.environ.get("REWRITE_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("REWRITE_RETRY_DELAY", "2.0"))
PAIRS_PER_TASK = int(os.environ.get("REWRITE_PAIRS_PER_TASK", "3"))

_RATES: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-chat-v3-0324": (0.14 / 1_000_000, 0.28 / 1_000_000),
    "openai/gpt-4o-mini":             (0.15 / 1_000_000, 0.60 / 1_000_000),
    "openai/gpt-4o":                  (2.50 / 1_000_000, 10.00 / 1_000_000),
}


def log_api_cost(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    p_rate, c_rate = _RATES.get(model, (0.5 / 1_000_000, 1.0 / 1_000_000))
    cost = prompt_tokens * p_rate + completion_tokens * c_rate
    _cost_entries.append({
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost, 6),
    })


SYSTEM_PROMPT = """You are a sales outreach specialist for Tenacious, a B2B technical staffing company.
Your job is to write honest, evidence-calibrated cold outreach emails that follow company policy strictly.

Policy rules you must always follow:
- Never claim capacity for a tech stack that is not on the bench (zero available engineers).
- If the bench has zero engineers for a required stack, explicitly state the gap.
- Never use high-confidence phrasing ("clearly scaling", "rapid growth", "aggressive hiring") unless the signal confidence is HIGH.
- Do not fabricate timezone labels or local times unless the prospect's timezone was explicitly provided.
- Do not reference layoffs, restructuring, or headcount cuts in the opening message.
- Keep the body under 120 words.
- Ask at most one question.
- Reference at least one signal from the provided brief when relevant.

Respond with ONLY a JSON object in this exact format (no markdown, no extra text):
{"subject": "<email subject line>", "body": "<email body text>"}"""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_user_message(task: dict) -> str:
    """Format task input as a user-facing prompt for the rewrite model."""
    inp = task.get("input", {})
    if not isinstance(inp, dict):
        inp = {}
    prospect = inp.get("prospect", {})
    bench = inp.get("bench_summary", {})
    req_stacks = inp.get("required_stacks", [])
    signal = inp.get("hiring_signal_brief", {})
    prior = inp.get("prior_thread", [])
    gt = task.get("ground_truth", {})

    lines = ["Write a cold outreach email for the following scenario.\n"]

    if prospect:
        if isinstance(prospect, dict):
            lines.append(f"Prospect: {prospect.get('company', '?')} -- {prospect.get('contact_title', '?')}")
            if tz := prospect.get("timezone"):
                lines.append(f"Timezone: {tz}")
        else:
            lines.append(f"Prospect: {prospect}")

    if signal:
        if isinstance(signal, dict):
            conf = signal.get("hiring_confidence", "unknown")
            roles = signal.get("open_eng_roles", "?")
            delta = signal.get("delta_60d", "?")
            lines.append(f"\nHiring signal: {roles} open engineering roles, delta_60d={delta}, confidence={conf}")
        else:
            lines.append(f"\nHiring signal: {signal}")

    if bench and isinstance(bench, dict) and bench.get("stacks"):
        lines.append("\nBench availability:")
        for stack, info in bench["stacks"].items():
            avail = info.get("available_engineers", 0) if isinstance(info, dict) else info
            lines.append(f"  {stack}: {avail} available engineers")

    if req_stacks and isinstance(req_stacks, list):
        lines.append(f"\nRequired stacks requested: {', '.join(str(s) for s in req_stacks)}")

    if prior and isinstance(prior, list):
        lines.append(f"\nPrior thread: {' | '.join(str(m) for m in prior)}")

    if isinstance(gt, dict) and gt.get("behavior_summary"):
        lines.append(f"\nRequired behavior: {gt['behavior_summary']}")

    scoring = task.get("scoring", {})
    checks = scoring.get("checks", []) if isinstance(scoring, dict) else []
    if checks:
        lines.append("\nScoring checks this output must pass:")
        for c in checks:
            if not isinstance(c, dict):
                continue
            ctype = c.get("type", "")
            cid = c.get("id", "")
            pts = c.get("points", 0)
            if ctype == "forbidden_phrases":
                lines.append(f"  [{pts}pts] Must NOT contain: {c.get('phrases', [])}")
            elif ctype == "required_phrases_any":
                lines.append(f"  [{pts}pts] Must contain at least one of: {c.get('phrases', [])}")
            elif ctype == "no_unavailable_stack_commitment":
                lines.append(f"  [{pts}pts] Must not promise capacity for unavailable stacks: {req_stacks}")
            elif ctype == "max_words":
                lines.append(f"  [{pts}pts] Body must be under {c.get('max_words', 120)} words")
            elif ctype == "max_question_marks":
                lines.append(f"  [{pts}pts] At most {c.get('max_question_marks', 1)} question mark(s)")
            else:
                lines.append(f"  [{pts}pts] Check: {cid} ({ctype})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# API + validation
# ---------------------------------------------------------------------------

def call_openrouter(messages: list[dict], model: str = REWRITE_MODEL) -> str | None:
    """Call OpenRouter and return the assistant text, or None on failure."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/yonas-dev/tenacious-bench",
        "X-Title": "Tenacious-Bench training data prep",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            log_api_cost(
                model,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
                continue
            print(f"    [WARN] OpenRouter failed after {MAX_RETRIES} attempts: {exc}", file=sys.stderr)
            return None


def parse_rewrite(raw: str) -> dict | None:
    """Parse LLM response into {subject, body}. Returns None if unparseable."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw_lines = raw.splitlines()
        raw = "\n".join(raw_lines[1:-1] if raw_lines[-1].strip() == "```" else raw_lines[1:])
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and "subject" in obj and "body" in obj:
            return {"subject": str(obj["subject"]), "body": str(obj["body"])}
    except json.JSONDecodeError:
        pass
    return None


def validate_chosen(task: dict, chosen_output: dict) -> bool:
    """Return True if chosen_output passes all checks for this task."""
    test_task = copy.deepcopy(task)
    test_task["candidate_output"] = chosen_output
    result = evaluate_task(test_task)
    return result.get("passed_all_checks", False)


def validate_rejected(task: dict) -> bool:
    """Return True if the existing candidate_output fails at least one check."""
    result = evaluate_task(task)
    return not result.get("passed_all_checks", True)


def format_output_text(output: object) -> str:
    """Format subject+body dict as a single assistant response string."""
    if isinstance(output, dict):
        return f"Subject: {output.get('subject', '')}\n\n{output.get('body', '')}"
    return str(output)


def attempt_chosen_rewrite(
    task: dict, user_msg: str
) -> tuple[str | None, str, dict]:
    """
    Call the rewrite model and validate the result against the scoring evaluator.

    Returns (chosen_text, outcome, extra_log_fields).
    outcome is "accepted" | "failed"; extra_log_fields carries the failure reason.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    raw = call_openrouter(messages)
    if raw is None:
        return None, "failed", {"reason": "OpenRouter call failed"}

    chosen_output = parse_rewrite(raw)
    if chosen_output is None:
        return None, "failed", {"reason": "unparseable response", "raw_response": raw[:200]}

    if not validate_chosen(task, chosen_output):
        return None, "failed", {"reason": "chosen does not pass all checks", "chosen_output": chosen_output}

    chosen_text = format_output_text(chosen_output)
    return chosen_text, "accepted", {"chosen_subject": chosen_output.get("subject", "")}


# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------

def load_accepted_pairs(partition: str) -> set[tuple[str, int]]:
    """
    Return a set of (task_id, pair_index) tuples already written to the partition JSONL.
    Used by --resume to skip (task, pair) combinations already on disk.
    Pairs written before pair_index was tracked are assigned pair_index=0.
    """
    seen: set[tuple[str, int]] = set()
    out_file = OUT_DIR / f"{partition}.jsonl"
    if not out_file.exists():
        return seen
    # Track per-task insertion order for legacy pairs without pair_index
    legacy_counts: dict[str, int] = {}
    for line in out_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pair = json.loads(line)
            meta = pair.get("_meta", {})
            tid = meta.get("task_id", "")
            if not tid:
                continue
            pidx = meta.get("pair_index")
            if pidx is None:
                pidx = legacy_counts.get(tid, 0)
                legacy_counts[tid] = pidx + 1
            seen.add((tid, int(pidx)))
        except json.JSONDecodeError:
            pass
    return seen


# ---------------------------------------------------------------------------
# Main pair-building loop
# ---------------------------------------------------------------------------

def build_pairs_for_partition(
    partition: str,
    dry_run: bool = False,
    limit: int | None = None,
    resume: bool = False,
) -> list[dict]:
    """
    Generate preference pairs for one partition and write them to {partition}.jsonl.

    Each accepted pair is written immediately so a crash does not lose prior work.
    With --resume, (task_id, pair_index) tuples already present in the JSONL are skipped.
    Generates up to PAIRS_PER_TASK distinct chosen rewrites per task occurrence.
    Returns log entries for the current run (not including prior-run entries).
    """
    task_file = BENCH_ROOT / partition / "tasks.json"
    tasks: list[dict] = json.loads(task_file.read_text(encoding="utf-8"))

    # Oversample trace-derived 3:1
    expanded: list[dict] = []
    for t in tasks:
        expanded.append(t)
        if t.get("source_mode") == "trace-derived":
            expanded.append(t)
            expanded.append(t)

    if limit:
        expanded = expanded[:limit]

    accepted_set = load_accepted_pairs(partition) if resume else set()
    if resume:
        print(f"  [resume] {len(accepted_set)} (task_id, pair_index) tuples already on disk; will skip those")

    out_file = OUT_DIR / f"{partition}.jsonl"
    # Open for append so accepted pairs survive crashes mid-partition
    write_mode = "a" if resume and out_file.exists() else "w"
    out_fh = None if dry_run else out_file.open(write_mode, encoding="utf-8")

    log_entries: list[dict] = []
    seen_task_ids: set[str] = set()
    occurrence_index: dict[str, int] = {}
    new_accepted = 0

    print(f"\n--- Partition: {partition} ({len(tasks)} tasks -> {len(expanded)} occurrences, {PAIRS_PER_TASK} pairs/task) ---")

    try:
        for task in expanded:
            task_id = task["task_id"]
            occ = occurrence_index.get(task_id, 0)
            occurrence_index[task_id] = occ + 1

            is_duplicate = task_id in seen_task_ids
            seen_task_ids.add(task_id)
            label = f"{task_id} ({'DUP' if is_duplicate else task['source_mode']})"

            # Gate 1: rejected output must fail the evaluator (check once per occurrence)
            if not validate_rejected(task):
                log_entries.append({
                    "task_id": task_id, "partition": partition,
                    "source_mode": task.get("source_mode"), "dimension": task.get("dimension"),
                    "oversampled": is_duplicate, "outcome": "skipped",
                    "reason": "rejected already passes all checks",
                    "rewrite_model": REWRITE_MODEL,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  SKIP {label}: rejected passes (unexpected)")
                continue

            candidate = task.get("candidate_output")
            if candidate is None:
                log_entries.append({
                    "task_id": task_id, "partition": partition,
                    "source_mode": task.get("source_mode"), "dimension": task.get("dimension"),
                    "oversampled": is_duplicate, "outcome": "skipped",
                    "reason": "task missing candidate_output field",
                    "rewrite_model": REWRITE_MODEL,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  SKIP {label}: no candidate_output")
                continue

            rejected_text = format_output_text(candidate)
            user_msg = build_user_message(task)

            if dry_run:
                log_entries.append({
                    "task_id": task_id, "partition": partition,
                    "source_mode": task.get("source_mode"), "dimension": task.get("dimension"),
                    "oversampled": is_duplicate, "outcome": "dry_run",
                    "rewrite_model": REWRITE_MODEL,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  DRY  {label}: would call {REWRITE_MODEL} x{PAIRS_PER_TASK}")
                continue

            for pair_num in range(PAIRS_PER_TASK):
                # Resume: skip (task_id, pair_index) already on disk
                if resume and (task_id, pair_num) in accepted_set:
                    continue

                pair_label = f"{label} [{pair_num+1}/{PAIRS_PER_TASK}]"
                print(f"  GEN  {pair_label}...", end=" ", flush=True)

                log: dict = {
                    "task_id": task_id,
                    "partition": partition,
                    "source_mode": task.get("source_mode"),
                    "dimension": task.get("dimension"),
                    "oversampled": is_duplicate,
                    "pair_index": pair_num,
                    "outcome": None,
                    "reason": None,
                    "rewrite_model": REWRITE_MODEL,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                chosen_text, outcome, extra = attempt_chosen_rewrite(task, user_msg)
                log["outcome"] = outcome
                log.update(extra)
                log_entries.append(log)

                if outcome != "accepted":
                    print(f"FAIL ({extra.get('reason', 'unknown')})")
                    continue

                pair = {
                    "prompt": [{"role": "user", "content": user_msg}],
                    "chosen": [{"role": "assistant", "content": chosen_text}],
                    "rejected": [{"role": "assistant", "content": rejected_text}],
                    "_meta": {
                        "task_id": task_id,
                        "pair_index": pair_num,
                        "source_mode": task.get("source_mode"),
                        "dimension": task.get("dimension"),
                        "difficulty": task.get("difficulty"),
                        "partition_origin": partition,
                        "oversampled": is_duplicate,
                        "rewrite_model": REWRITE_MODEL,
                    },
                }
                out_fh.write(json.dumps(pair, ensure_ascii=False) + "\n")  # type: ignore[union-attr]
                out_fh.flush()  # type: ignore[union-attr]
                new_accepted += 1
                print("OK")

    finally:
        if out_fh is not None:
            out_fh.close()

    prior_accepted = len(accepted_set) if resume else 0
    total_accepted = prior_accepted + new_accepted
    print(f"\nPartition {partition}: {new_accepted} new pairs written (total on disk: {total_accepted})")
    return log_entries


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Build Path B preference pairs")
    parser.add_argument("--partition", choices=["train", "dev", "both"], default="both")
    parser.add_argument("--limit", type=int, default=None, help="Cap tasks per partition (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls; print what would happen")
    parser.add_argument("--resume", action="store_true", help="Skip task_ids already accepted in existing JSONL")
    args = parser.parse_args()

    if not args.dry_run and not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY is not set. Use --dry-run to test without API calls.", file=sys.stderr)
        return 1

    partitions = ["train", "dev"] if args.partition == "both" else [args.partition]
    all_log: list[dict] = []

    for partition in partitions:
        log_entries = build_pairs_for_partition(
            partition=partition,
            dry_run=args.dry_run,
            limit=args.limit,
            resume=args.resume,
        )
        all_log.extend(log_entries)

    accepted = sum(1 for e in all_log if e.get("outcome") == "accepted")
    skipped = sum(1 for e in all_log if e.get("outcome") == "skipped")
    failed = sum(1 for e in all_log if e.get("outcome") == "failed")
    total = len(all_log)
    print(f"\nSummary: {accepted} accepted / {failed} failed / {skipped} skipped / {total} total (this run)")

    if not args.dry_run:
        # Merge with any existing log entries so the file is cumulative
        existing: list[dict] = []
        if BUILD_LOG.exists():
            try:
                existing = json.loads(BUILD_LOG.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        BUILD_LOG.write_text(
            json.dumps(existing + all_log, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Build log -> {BUILD_LOG}")

        # Write cost log — same format as generation_scripts/synthesis_cost_log.json
        existing_costs: list[dict] = []
        if COST_LOG_PATH.exists():
            try:
                prev = json.loads(COST_LOG_PATH.read_text(encoding="utf-8"))
                existing_costs = prev.get("entries", [])
            except json.JSONDecodeError:
                pass
        all_costs = existing_costs + _cost_entries
        total_cost = sum(e["cost_usd"] for e in all_costs)
        COST_LOG_PATH.write_text(
            json.dumps(
                {"entries": all_costs, "total_cost_usd": round(total_cost, 4), "total_calls": len(all_costs)},
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Cost log  -> {COST_LOG_PATH}  (total: ${total_cost:.4f} over {len(all_costs)} calls)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
