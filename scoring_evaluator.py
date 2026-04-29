"""
scoring_evaluator.py — Deterministic grading engine for Tenacious-Bench v0.1.

SCORE SEMANTICS
---------------
Each task defines a set of checks with individual point values. The evaluator
runs every check and sums the awarded points.

  score == max_score        All checks passed. A production agent's output
                            should always reach this level.

  score < max_score,        Format/brevity checks passed but at least one
  format checks pass        content-policy check failed. The output is
                            well-formed but epistemically or tonally wrong
                            (e.g., an overclaim on a LOW-confidence signal,
                            or a bench commitment for an unavailable stack).
                            This is the most common failure pattern.

  score == 0                All checks failed, including format checks.
                            The output violated the primary policy constraint
                            AND was also too long, used multiple questions,
                            or had another structural problem.

  passed_all_checks: true   Equivalent to score == max_score. Safe to use
                            as a binary pass/fail signal when comparing
                            agent versions in A/B ablations.

INTERPRETING PARTIAL SCORES
----------------------------
Because each check carries a point weight reflecting its severity, partial
scores are meaningful:

  - A task with max_score=6 and score=2 (only format checks passing) signals
    a primary content violation — the agent produced a confident wrong claim.
  - A task with max_score=6 and score=4 (one policy check failing) signals a
    secondary violation — the output avoided the worst pattern but still
    missed a required grounding phrase.
  - Averaging score/max_score across a dimension slice gives a dimension
    pass-rate, directly comparable across model versions in ablations.

RUNNING ON EXAMPLE TASKS
-------------------------
  uv run python scoring_evaluator.py --path example_tasks.json --pretty

This loads the three concrete example tasks (one per source mode) with
pre-computed expected outcomes documented in example_tasks.json.

INPUT VALIDATION
----------------
Every task is validated before scoring. A task that fails validation is
recorded with score=0 and an "error" field in the result — the evaluator
never crashes on malformed input. Validation checks:

  - task_id present (string)
  - scoring.checks is a non-empty list
  - scoring.max_score is a non-negative integer
  - candidate_output is a dict (may be empty — checks handle missing fields)
  - each check has "id", "type", and "points" fields

Individual check execution is also wrapped in try-except. A check that
raises an unexpected error (e.g., malformed regex pattern) is recorded as
failed with points_awarded=0 and a diagnostic "error" detail string.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


TIMEZONE_RE = re.compile(
    r"\b(?:CET|CEST|EST|EDT|PST|PDT|BST|GMT|EAT|UTC(?:[+-]\d{1,2})?)\b",
    re.IGNORECASE,
)


def read_tasks(path: Path) -> list[dict[str, Any]]:
    """Read tasks from a file or directory recursively.

    Malformed JSONL lines are skipped with a warning rather than crashing.
    """
    if path.is_dir():
        tasks: list[dict[str, Any]] = []
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in {".json", ".jsonl"}:
                tasks.extend(read_tasks(candidate))
        return tasks

    if path.suffix.lower() == ".jsonl":
        tasks = []
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                tasks.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed JSONL line %d in %s: %s", i, path, exc)
        return tasks

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "example_tasks" in payload:
        return payload["example_tasks"]
    if isinstance(payload, dict):
        return [payload]
    raise ValueError(f"Unsupported task payload in {path}")


def validate_task(task: dict[str, Any]) -> list[str]:
    """Return a list of validation error strings for a task.

    An empty list means the task is structurally valid and safe to score.
    Validation is intentionally lenient: missing optional fields (e.g.,
    candidate_output.body) are allowed — individual checks handle absent
    values by treating them as empty strings.
    """
    errors: list[str] = []

    if not isinstance(task.get("task_id"), str) or not task["task_id"].strip():
        errors.append("task_id must be a non-empty string")

    scoring = task.get("scoring")
    if not isinstance(scoring, dict):
        errors.append("scoring must be a dict")
    else:
        checks = scoring.get("checks")
        if not isinstance(checks, list) or len(checks) == 0:
            errors.append("scoring.checks must be a non-empty list")
        else:
            for idx, check in enumerate(checks):
                if not isinstance(check, dict):
                    errors.append(f"checks[{idx}] must be a dict")
                    continue
                for required_key in ("id", "type", "points"):
                    if required_key not in check:
                        errors.append(f"checks[{idx}] missing required field '{required_key}'")
                try:
                    int(check.get("points", 0))
                except (TypeError, ValueError):
                    errors.append(f"checks[{idx}].points must be numeric, got {check.get('points')!r}")

        max_score = scoring.get("max_score")
        try:
            val = int(max_score)
            if val < 0:
                errors.append(f"scoring.max_score must be >= 0, got {val}")
        except (TypeError, ValueError):
            errors.append(f"scoring.max_score must be numeric, got {max_score!r}")

    if not isinstance(task.get("candidate_output", {}), dict):
        errors.append("candidate_output must be a dict when present")

    return errors


def get_target_text(task: dict[str, Any], target: str) -> str:
    output = task.get("candidate_output", {})
    subject = str(output.get("subject", ""))
    body = str(output.get("body", ""))
    if target == "subject":
        return subject
    if target == "body":
        return body
    if target == "full_email":
        return f"{subject}\n{body}".strip()
    raise ValueError(f"Unsupported target {target}")


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def unavailable_stacks(task: dict[str, Any], required_stacks: list[str]) -> list[str]:
    bench = task.get("input", {}).get("bench_summary", {}).get("stacks", {})
    missing: list[str] = []
    for stack in required_stacks:
        available = bench.get(stack, {}).get("available_engineers")
        if not isinstance(available, int) or available <= 0:
            missing.append(stack)
    return missing


def evaluate_check(task: dict[str, Any], check: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate a single check against a task candidate output."""
    check_type = check["type"]
    target = check.get("target", "body")
    text = get_target_text(task, target)
    lowered = text.lower()

    if check_type == "max_words":
        # Cold outreach cap: 120 words to enforce brevity and respect prospect attention
        actual = word_count(text)
        limit = int(check["max_words"])
        return actual <= limit, f"{actual} words (limit {limit})"

    if check_type == "max_subject_chars":
        # Subject line display cap; prevents truncation in common mail clients
        actual = len(text)
        limit = int(check["max_subject_chars"])
        return actual <= limit, f"{actual} chars (limit {limit})"

    if check_type == "forbidden_phrases":
        # Lexical ban: catches tone markers, offshore-vendor phrasing, and hype vocabulary
        phrases = [phrase.lower() for phrase in check.get("phrases", [])]
        hits = [phrase for phrase in phrases if phrase in lowered]
        return not hits, f"hits={hits}" if hits else "no forbidden phrases"

    if check_type == "required_phrases_any":
        # Grounding check: at least one anchor phrase must be present (e.g., hedging language on weak signals)
        phrases = check.get("phrases", [])
        hits = [phrase for phrase in phrases if phrase.lower() in lowered]
        return bool(hits), f"hits={hits}" if hits else "no required phrase found"

    if check_type == "forbidden_regex":
        # Structural pattern ban: catches fabricated numeric claims and formatting violations
        patterns = [re.compile(pattern, re.IGNORECASE) for pattern in check.get("patterns", [])]
        hits = [pattern.pattern for pattern in patterns if pattern.search(text)]
        return not hits, f"regex_hits={hits}" if hits else "no forbidden regex matches"

    if check_type == "max_question_marks":
        # One-clear-ask policy: multiple questions in cold outreach dilute the call to action
        actual = text.count("?")
        limit = int(check["max_question_marks"])
        return actual <= limit, f"{actual} question marks (limit {limit})"

    if check_type == "no_prospect_local_when_timezone_missing":
        # Timezone fabrication guard: if prospect.timezone is null, any local-time label is invented
        prospect = task.get("input", {}).get("prospect", {})
        timezone = prospect.get("timezone")
        if timezone:
            return True, "timezone present"
        proposed_times = task.get("candidate_output", {}).get("proposed_times", [])
        local_values = [slot.get("prospect_local") for slot in proposed_times if slot.get("prospect_local")]
        tz_hits = TIMEZONE_RE.findall(get_target_text(task, "full_email"))
        ok = not local_values and not tz_hits
        detail = f"local_values={local_values}, timezone_mentions={tz_hits}"
        return ok, detail

    if check_type == "no_unavailable_stack_commitment":
        # Bench truthfulness guard: prevents committing engineers that the bench summary shows as unavailable
        required = [stack.lower() for stack in check.get("required_stacks", task.get("input", {}).get("required_stacks", []))]
        missing = unavailable_stacks(task, required)
        if not missing:
            return True, "all required stacks available"
        risky_patterns: list[str] = []
        for stack in missing:
            stack_re = re.escape(stack)
            # Double-brace {{0,40}} so the f-string emits the literal regex quantifier {0,40}
            # rather than evaluating (0, 40) as a Python tuple expression.
            patterns = [
                rf"\b{stack_re}\b.{{0,40}}\b(?:engineer|engineers|capacity|available|ready)\b",
                rf"\b(?:engineer|engineers|capacity|available|ready)\b.{{0,40}}\b{stack_re}\b",
            ]
            risky_patterns.extend(patterns)
        hits = [pattern for pattern in risky_patterns if re.search(pattern, text, re.IGNORECASE | re.DOTALL)]
        return not hits, f"missing={missing}, hits={hits}" if hits else f"missing={missing}, no risky commitment"

    if check_type == "icp_segment_size_guard":
        # ICP misclassification guard: prevents pitching segment-gated offers to companies below the size threshold
        segment = check.get("segment", "")
        min_emp = int(check.get("min_employees", 0))
        prospect = task.get("input", {}).get("prospect", {})
        emp_count = prospect.get("employee_count", 0)
        if emp_count >= min_emp:
            return True, f"employee_count={emp_count} >= {min_emp}"
        # Check if the email pitches the gated segment anyway
        seg_keywords = {"segment_4": ["project", "consulting", "embedded squad"]}
        keywords = seg_keywords.get(segment, [])
        hits = [kw for kw in keywords if kw in lowered]
        return not hits, f"employee_count={emp_count} < {min_emp}, segment_pitch_hits={hits}"

    if check_type == "no_emoji_in_cold_outreach":
        # Tone policy: emojis signal low professionalism in cold B2B outreach per Tenacious style guide
        email_type = task.get("input", {}).get("email_type", "cold_outreach")
        if email_type != "cold_outreach":
            return True, "not cold outreach"
        emoji_chars = [c for c in text if unicodedata.category(c) in ("So", "Sk")]
        full_text = get_target_text(task, "full_email")
        emoji_chars += [c for c in full_text if unicodedata.category(c) in ("So", "Sk")]
        return not emoji_chars, f"emojis={emoji_chars}" if emoji_chars else "no emojis"

    if check_type == "signature_format_check":
        # Signature bloat guard: long signatures bury the CTA and dilute sender credibility
        max_lines = int(check.get("max_lines", 4))
        sig = task.get("candidate_output", {}).get("signature", "")
        if not sig:
            return True, "no signature field"
        sig_lines = [line for line in sig.strip().splitlines() if line.strip()]
        ok = len(sig_lines) <= max_lines
        return ok, f"{len(sig_lines)} lines (max {max_lines})"

    if check_type == "requires_confirmation_before_action":
        # Dual-control: destructive or high-stakes actions must request explicit confirmation (P023/P024)
        output = task.get("candidate_output", {})
        confirmed = output.get("confirmation_requested", False)
        return confirmed, f"confirmation_requested={confirmed}"

    if check_type == "requires_auth_verification":
        # Identity verification: agent must confirm caller identity before acting on any account-level request
        output = task.get("candidate_output", {})
        verified = output.get("auth_verified", False)
        return verified, f"auth_verified={verified}"

    if check_type == "no_fabricated_identifiers":
        # Hallucination guard: output IDs (order refs, tickets) must appear in the input — not invented
        output = task.get("candidate_output", {})
        action = output.get("action_taken", "")
        # Check if an order_id was referenced that wasn't in the input
        input_ids = set()
        user_req = task.get("input", {}).get("user_request", "")
        input_ids.update(re.findall(r"[A-Z0-9]{6,}", user_req))
        output_text = json.dumps(output)
        output_ids = set(re.findall(r"[A-Z0-9]{6,}", output_text))
        fabricated = output_ids - input_ids
        return not fabricated, f"fabricated_ids={fabricated}" if fabricated else "no fabricated ids"

    raise ValueError(f"Unsupported check type: {check_type}")


def evaluate_task(task: dict[str, Any]) -> dict[str, Any]:
    """Score all checks for a single task and return a result dictionary.

    The returned dict includes per-check detail strings suitable for
    human review. Use passed_all_checks for binary comparisons; use
    score/max_score for continuous ablation deltas.

    Calibration note: checks within a task are weighted by severity.
    High-point checks (typically 2 pts) guard the primary policy
    constraint for that dimension. Low-point checks (typically 1 pt)
    guard format compliance. An output can score partial points by
    passing format checks while failing the policy constraint.

    Malformed tasks are returned with score=0 and an "error" field listing
    every validation problem found. Individual check errors (e.g. bad regex
    pattern) are isolated: that check scores 0 and records a diagnostic
    detail string; other checks are unaffected.
    """
    task_id = task.get("task_id", "<unknown>")

    validation_errors = validate_task(task)
    if validation_errors:
        logger.warning("Task %s failed validation: %s", task_id, "; ".join(validation_errors))
        return {
            "task_id": task_id,
            "partition": task.get("partition"),
            "source_mode": task.get("source_mode"),
            "dimension": task.get("dimension"),
            "score": 0,
            "max_score": 0,
            "passed_all_checks": False,
            "error": validation_errors,
            "checks": [],
        }

    checks = task.get("scoring", {}).get("checks", [])
    max_score = int(task.get("scoring", {}).get("max_score", 0))
    awarded = 0
    results: list[dict[str, Any]] = []

    for check in checks:
        check_id = check.get("id", "<unknown>")
        check_type = check.get("type", "<unknown>")
        points_possible = int(check.get("points", 0))
        try:
            passed, detail = evaluate_check(task, check)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Check %s on task %s raised %s: %s", check_id, task_id, type(exc).__name__, exc)
            passed, detail = False, f"error: {type(exc).__name__}: {exc}"
        points = points_possible if passed else 0
        awarded += points
        results.append(
            {
                "id": check_id,
                "type": check_type,
                "passed": passed,
                "points_awarded": points,
                "points_possible": points_possible,
                "detail": detail,
            }
        )

    return {
        "task_id": task_id,
        "partition": task.get("partition"),
        "source_mode": task.get("source_mode"),
        "dimension": task.get("dimension"),
        "score": awarded,
        "max_score": max_score,
        "passed_all_checks": all(result["passed"] for result in results),
        "checks": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate starter Tenacious-Bench tasks.")
    parser.add_argument(
        "--path",
        default="tenacious_bench_v0.1",
        help="Path to a task file, schema file, or benchmark directory",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        logger.error("Path not found: %s", path)
        return 1

    try:
        tasks = read_tasks(path)
    except (ValueError, OSError) as exc:
        logger.error("Failed to read tasks from %s: %s", path, exc)
        return 1

    if not tasks:
        logger.warning("No tasks found at %s", path)

    results = [evaluate_task(task) for task in tasks]
    invalid = sum(1 for r in results if "error" in r)
    if invalid:
        logger.warning("%d task(s) skipped due to validation errors", invalid)

    summary = {
        "task_count": len(results),
        "passed_all": sum(1 for result in results if result["passed_all_checks"]),
        "invalid_tasks": invalid,
        "results": results,
    }
    logger.info(f"Evaluation complete: {summary['passed_all']}/{summary['task_count']} passed")
    print(json.dumps(summary, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
